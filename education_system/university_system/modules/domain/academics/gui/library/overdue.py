"""
Enhanced Library Management System - GUI Version
Maintains all original CLI functions while adding a modern GUI interface
Backwards compatible with existing database and auth systems
"""


from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from education_system.university_system.core.i18n import get_text as _, init_i18n
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
from education_system.university_system.core.exceptions import (
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

from education_system.university_system.core.paths import DEFAULT_DB_PATH
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

def show_overdue_books(self):
    """Show overdue books interface"""
    if not self.check_permission('view_reports'):
        return

    self.clear_content_area()

    overdue_frame = ttk.Frame(self.notebook)
    self.notebook.add(overdue_frame, text="Overdue Books")

    title_label = ttk.Label(overdue_frame, text="Overdue Books Management", style='Title.TLabel')
    title_label.pack(pady=10)

    # Control frame
    control_frame = ttk.Frame(overdue_frame)
    control_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(control_frame, text="Send Reminders", command=self.send_overdue_reminders).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_frame, text="Process Fines", command=self.process_overdue_fines).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_frame, text="Export Report", command=self.export_overdue_report).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_frame, text=_("common.refresh"), command=self.refresh_overdue_books).pack(side=tk.LEFT, padx=5)

    # Summary frame
    summary_frame = ttk.LabelFrame(overdue_frame, text="Summary")
    summary_frame.pack(fill=tk.X, padx=10, pady=5)

    self.overdue_summary_label = ttk.Label(summary_frame, text="Loading summary...")
    self.overdue_summary_label.pack(pady=10)

    # Overdue books table
    table_frame = ttk.Frame(overdue_frame)
    table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    columns = ('User ID', 'Book ID', 'Title', 'Due Date', 'Days Overdue', 'Fine Amount', 'Contact')
    self.overdue_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

    for col in columns:
        self.overdue_tree.heading(col, text=col)
        self.overdue_tree.column(col, width=100)

    # Add scrollbar
    overdue_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.overdue_tree.yview)
    self.overdue_tree.configure(yscrollcommand=overdue_scrollbar.set)

    self.overdue_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    overdue_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Context menu
    self.create_overdue_context_menu()

    # Load data
    self.load_overdue_books()

def create_overdue_context_menu(self):
    """Create context menu for overdue books"""
    self.overdue_context_menu = tk.Menu(self.master, tearoff=0)
    self.overdue_context_menu.add_command(label="Contact User", command=self.contact_overdue_user)
    self.overdue_context_menu.add_command(label="Process Return", command=self.process_overdue_return)
    self.overdue_context_menu.add_command(label="Waive Fine", command=self.waive_fine)
    self.overdue_context_menu.add_separator()
    self.overdue_context_menu.add_command(label="View User History", command=self.view_user_history)

    self.overdue_tree.bind('<Button-3>', self.show_overdue_context_menu)

def show_overdue_context_menu(self, event):
    """Show context menu for overdue books"""
    item = self.overdue_tree.selection()[0] if self.overdue_tree.selection() else None
    if item:
        # Rebuild cross-link items each click so they match the currently
        # selected row's user_id / book_id.
        try:
            from education_system.university_system.modules.domain.academics.gui.library import _cross_links
            menu = self.overdue_context_menu
            # Drop any previously appended cross-link items so we don't
            # accumulate duplicates across right-clicks.
            try:
                # Original menu ends at index 4 (View User History);
                # delete anything beyond that — it must be ours from a
                # previous right-click.
                while (menu.index("end") is not None
                       and menu.index("end") > 4):
                    menu.delete("end")
            except Exception:
                pass
            values = self.overdue_tree.item(item).get("values") or []
            _cross_links.append_cross_links(
                menu,
                _cross_links.overdue_menu_items(values, parent=self.master),
            )
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Could not append cross-link items")
        self.overdue_context_menu.post(event.x_root, event.y_root)

def load_overdue_books(self):
    """Load overdue books data"""
    # Clear existing data
    for item in self.overdue_tree.get_children():
        self.overdue_tree.delete(item)

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('''
            SELECT bl.user_id, bl.book_id, b.title, bl.due_date,
                   julianday('now') - julianday(bl.due_date) as days_overdue,
                   bl.fine_amount, s.email
            FROM book_loans bl
            JOIN books b ON bl.book_id = b.book_id
            LEFT JOIN students s ON bl.user_id = s.student_id
            WHERE bl.status = 'overdue'
            ORDER BY days_overdue DESC
            ''')

            overdue_books = cursor.fetchall()
            conn.close()

            total_fines = 0
            for book in overdue_books:
                user_id, book_id, title, due_date, days_overdue, fine, email = book
                fine_amount = fine if fine else 0
                total_fines += fine_amount
                contact = email if email else "No email"

                self.overdue_tree.insert('', 'end', values=(
                    user_id, book_id, title[:30], due_date[:10],
                    int(days_overdue), f"£{fine_amount:.2f}", contact
                ))

            # Update summary
            summary_text = f"Total Overdue Items: {len(overdue_books)} | Total Fines: £{total_fines:.2f}"
            self.overdue_summary_label.config(text=summary_text)

        else:
            # Demo data
            demo_overdue = [
                ("USER001", "B10001", "Sample Book 1", "2024-01-10", 5, "£2.50", "user1@email.com"),
                ("USER002", "B10002", "Sample Book 2", "2024-01-08", 7, "£3.50", "user2@email.com"),
            ]

            for book in demo_overdue:
                self.overdue_tree.insert('', 'end', values=book)

            self.overdue_summary_label.config(text="Demo Mode: 2 overdue items | Total Fines: £6.00")

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Error loading overdue books: {str(e)}")

def refresh_overdue_books(self):
    """Refresh overdue books"""
    self.load_overdue_books()

def send_overdue_reminders(self):
    """Send reminder emails for overdue books"""
    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()

                # Get overdue books with user details
                cursor.execute('''
                    SELECT bl.book_id, bl.user_id, bl.due_date, bl.fine_amount,
                           b.title, b.author,
                           s.first_name, s.last_name, s.email,
                           julianday('now') - julianday(bl.due_date) as days_overdue
                    FROM book_loans bl
                    JOIN books b ON bl.book_id = b.book_id
                    JOIN students s ON bl.user_id = s.student_id
                    WHERE bl.status = 'active' AND bl.due_date < date('now')
                    AND s.email IS NOT NULL AND s.email != ''
                    ORDER BY days_overdue DESC
                ''')

                overdue_books = cursor.fetchall()
                conn.close()

                if not overdue_books:
                    messagebox.showinfo("No Overdue Books", "No overdue books found.")
                    return

                # Send reminder emails
                sent_count = 0
                for book in overdue_books:
                    book_id, user_id, due_date, fine_amount, title, author, first_name, last_name, email, days_overdue = book

                    fine_amount = fine_amount or 0.0

                    template_vars = {
                        'student_name': f"{first_name} {last_name}",
                        'student_id': user_id,
                        'book_id': book_id,
                        'book_title': title,
                        'author': author,
                        'due_date': due_date,
                        'days_overdue': int(days_overdue),
                        'fine_amount': f"{fine_amount:.2f}"
                    }

                    subject, message = render_template('overdue_book_reminder', template_vars)

                    if not subject or not message:
                        print("Failed to load email template.")
                        continue

                    # Send email
                    success = self._send_email_via_gui(email, subject, message)

                    if success:
                        sent_count += 1
                        print(f"Overdue reminder sent to {first_name} {last_name} ({email})")
                    else:
                        self._show_library_email_fallback(f"{first_name} {last_name}", email, subject, message, "Overdue Reminder")

                messagebox.showinfo("Reminders Sent",
                    f"Overdue reminder emails sent to {sent_count} students with overdue books.")

    except (tk.TclError, ValueError, TypeError) as e:
        messagebox.showerror(_("common.error"), f"Failed to send overdue reminders: {e}")

def send_overdue_notifications(self):
    """Send overdue notifications"""
    try:
        conn = get_db_connection()
        if not conn:
            return 0

        cursor = conn.cursor()
        cursor.execute('''
        SELECT DISTINCT bl.user_id, s.email, s.first_name, s.last_name
        FROM book_loans bl
        LEFT JOIN students s ON bl.user_id = s.student_id
        WHERE bl.status = 'overdue' AND s.email IS NOT NULL
        ''')

        users = cursor.fetchall()
        conn.close()

        sent_count = 0
        for user_id, email, first_name, last_name in users:
            try:
                # In a real implementation, you would send actual emails
                print(f"Sending overdue reminder to {email} for user {user_id}")
                sent_count += 1
            except (sqlite3.Error, DatabaseError, ValueError, TypeError) as e:
                print(f"Failed to send reminder to {user_id}: {e}")

        return sent_count

    except (sqlite3.Error, DatabaseError, ValueError, TypeError) as e:
        print(f"Error sending overdue notifications: {e}")
        return 0

def process_overdue_fines(self):
    """Process overdue fines"""
    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            count = self.calculate_overdue_fines()
            messagebox.showinfo(_("common.success"), f"Processed fines for {count} overdue items")
            self.refresh_overdue_books()
        else:
            messagebox.showinfo(_("common.demo"), "Overdue fines would be calculated and updated")
    except (tk.TclError, ValueError, TypeError) as e:
        messagebox.showerror(_("common.error"), f"Error processing fines: {str(e)}")

def calculate_overdue_fines(self):
    """Calculate and update overdue fines"""
    try:
        conn = get_db_connection()
        if not conn:
            return 0

        cursor = conn.cursor()

        # Get fine per day setting
        fine_per_day = 0.50  # Default
        try:
            cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "fine_per_day"')
            setting = cursor.fetchone()
            if setting:
                fine_per_day = float(setting[0])
        except (sqlite3.Error, DatabaseError, ValueError, TypeError):
            pass

        # Snapshot the rows we're about to fine so we can post each one
        # to the finance bus *after* the local UPDATE commits. Without the
        # snapshot we'd have no way to know which loans we just changed.
        cursor.execute('''
            SELECT loan_id, user_id, book_id,
                   (julianday('now') - julianday(due_date)) * ? AS new_fine
            FROM book_loans
            WHERE status = 'overdue' AND due_date < datetime('now')
        ''', (fine_per_day,))
        about_to_fine = cursor.fetchall()

        # Update fines for overdue books
        cursor.execute('''
        UPDATE book_loans
        SET fine_amount = (julianday('now') - julianday(due_date)) * ?
        WHERE status = 'overdue' AND due_date < datetime('now')
        ''', (fine_per_day,))

        count = cursor.rowcount
        conn.commit()
        conn.close()

        # Closed-loop: each overdue loan posts a charge to Finance and
        # broadcasts a loan-changed event so any open Library, Finance,
        # or enrolment GUI auto-refreshes. Best-effort.
        try:
            from education_system.university_system.modules.services.finance_bus import (
                raise_charge,
            )
            from education_system.university_system.modules.domain.academics.gui._event_bus import (
                publish, EVENT_LOAN_CHANGED,
            )
            for row in about_to_fine:
                loan_id, user_id, book_id, new_fine = row
                if not user_id or not new_fine:
                    continue
                amount = round(float(new_fine), 2)
                if amount <= 0:
                    continue
                raise_charge(
                    user_id, amount,
                    source="library_overdue",
                    description=f"Library overdue fine — loan #{loan_id}",
                    reference_id=f"loan:{loan_id}",
                    processed_by="library_overdue_processor",
                )
                publish(
                    EVENT_LOAN_CHANGED,
                    loan_id=loan_id, user_id=user_id, book_id=book_id,
                    action="overdue_fined", fine_amount=amount,
                )
        except Exception as bus_err:
            print(f"Warning: overdue fine bus publish failed: {bus_err}")

        return count

    except (sqlite3.Error, DatabaseError) as e:
        print(f"Error calculating fines: {e}")
        return 0

def export_overdue_report(self):
    """Export overdue report"""
    file_path = filedialog.asksaveasfilename(
        title="Export Overdue Report",
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv"), ("PDF files", "*.pdf"), ("All files", "*.*")]
    )

    if file_path:
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                success = self.create_overdue_export(file_path)
                if success:
                    messagebox.showinfo(_("common.success"), f"Overdue report exported to {file_path}")
                else:
                    messagebox.showerror(_("common.error"), "Export failed")
            else:
                messagebox.showinfo(_("common.demo"), f"Would export overdue report to {file_path}")
        except (OSError, IOError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Export error: {str(e)}")

def create_overdue_export(self, file_path):
    """Create overdue export file"""
    try:
        import pandas as pd

        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        student_columns = self._get_student_columns()
        grade_sql = ', s.grade_level' if 'grade_level' in student_columns else ''
        cursor.execute('''
        SELECT bl.user_id, bl.book_id, b.title, b.author, bl.checkout_date,
               bl.due_date, julianday('now') - julianday(bl.due_date) as days_overdue,
               bl.fine_amount, s.first_name, s.last_name, s.email''' + grade_sql + '''
        FROM book_loans bl
        JOIN books b ON bl.book_id = b.book_id
        LEFT JOIN students s ON bl.user_id = s.student_id
        WHERE bl.status = 'overdue'
        ORDER BY days_overdue DESC
        ''')

        data = cursor.fetchall()
        conn.close()

        if not data:
            return False

        columns = ['User ID', 'Book ID', 'Title', 'Author', 'Checkout Date', 'Due Date',
                  'Days Overdue', 'Fine Amount', 'First Name', 'Last Name', 'Email']
        if 'grade_level' in student_columns:
            columns.append('Grade')

        df = pd.DataFrame(data, columns=columns)

        # Format dates and numbers
        df['Checkout Date'] = pd.to_datetime(df['Checkout Date']).dt.strftime('%Y-%m-%d')
        df['Due Date'] = pd.to_datetime(df['Due Date']).dt.strftime('%Y-%m-%d')
        df['Days Overdue'] = df['Days Overdue'].astype(int)
        df['Fine Amount'] = df['Fine Amount'].apply(lambda x: f"£{x:.2f}" if x else "£0.00")

        # Export based on file type
        if file_path.lower().endswith('.csv'):
            df.to_csv(file_path, index=False)
        elif file_path.lower().endswith('.pdf'):
            # For PDF export, you'd need reportlab or similar
            # For now, convert to CSV
            csv_path = file_path.replace('.pdf', '.csv')
            df.to_csv(csv_path, index=False)
            messagebox.showinfo("Note", f"Exported as CSV: {csv_path}")
        else:
            df.to_excel(file_path, index=False)

        return True

    except (OSError, IOError, tk.TclError) as e:
        print(f"Export error: {e}")
        return False

def check_and_display_late_fees(self):
    """Check if current user has any late fees and display notification"""
    if not self.auth or not hasattr(self.auth, 'current_user') or not self.auth.current_user:
        return

    current_user_id = self.auth.current_user.get('username', None)
    if not current_user_id:
        return

    try:
        conn = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor()

        # Check for overdue books with fines
        cursor.execute('''
            SELECT COUNT(*), SUM(COALESCE(fine_amount, 0))
            FROM book_loans
            WHERE user_id = ? AND status = 'overdue' AND fine_amount > 0
        ''', (current_user_id,))

        result = cursor.fetchone()
        conn.close()

        if result and result[0] > 0:
            overdue_count = result[0]
            total_fines = result[1] or 0

            # Create notification frame at the top
            notification_frame = ttk.Frame(self.master, style='Warning.TFrame')
            notification_frame.pack(fill=tk.X, padx=5, pady=(5,0))

            message = f"⚠️ You have {overdue_count} overdue book(s) with £{total_fines:.2f} in late fees"
            notification_label = ttk.Label(notification_frame, text=message,
                                         style='Warning.TLabel', font=('Arial', 10, 'bold'))
            notification_label.pack(side=tk.LEFT, padx=10, pady=5)

            # Add "Pay Now" button
            pay_button = ttk.Button(notification_frame, text="Pay via Finance System",
                                  command=lambda: self.open_finance_payment_for_user(current_user_id, total_fines))
            pay_button.pack(side=tk.RIGHT, padx=10, pady=5)

            # Configure warning style
            self.style.configure('Warning.TFrame', background='#fff3cd')
            self.style.configure('Warning.TLabel', background='#fff3cd', foreground='#856404')

    except tk.TclError as e:
        print(f"Error checking late fees: {e}")

