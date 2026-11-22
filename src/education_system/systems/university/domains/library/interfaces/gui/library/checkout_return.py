"""
Enhanced Library Management System - GUI Version
Maintains all original CLI functions while adding a modern GUI interface
Backwards compatible with existing database and auth systems
"""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t


from education_system.systems.university.infrastructure.sql_safety import escape_like
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
    from education_system.systems.university.domains.library.domain.library.settings import (
        auth, get_current_user_id, set_auth, get_library_settings, update_library_setting
    )
    from education_system.systems.university.domains.library.domain.library.menu import display_library_menu
    from education_system.systems.university.domains.library.domain.library.barcode import (
        generate_barcode, generate_qr_code, process_scanned_barcode
    )
    from education_system.systems.university.domains.library.domain.library.reports import (
        generate_circulation_report, generate_library_statistics_export, generate_user_activity_report
    )
    from education_system.systems.university.domains.library.domain.library.database import (
        get_db_connection, init_library_db, log_audit_event
    )
    from education_system.systems.university.domains.library.domain.library.backup import (
        quick_system_health_check, restore_from_backup
    )
    from education_system.systems.university.domains.library.domain.library.reading_lists import view_reading_list_details
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

from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH
DATABASE_FILE = str(UNIVERSITY_DEFAULT_DB_PATH)

# Import finance integration for student finance account payments
try:
    from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
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

# Matplotlib is imported lazily by finance_shared, the one module in this
# package whose names are actually read (by the two chart dialogs under
# finance_parts/). This module carried an identical eager copy of that import
# and never used any of it — importing matplotlib.pyplot costs ~1.3s and was
# paid by anything that touched the library package at all.

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

from education_system.systems.university.domains.library.interfaces.gui.library.base import LibraryGUI

from education_system.systems.university.domains.library.interfaces.gui.library._pickers import attach_picker


def _run_circulation(fn, *args, **kwargs):
    """Run a ``library_circulation`` rule in its own transaction, then send the
    emails it returns. Every desk action goes through these shared rules
    (copies, loan rules, holds, recalls, fines) — see
    ``university/application/library/circulation``."""
    from education_system.systems.university.application.teaching import (
        occurrences as timetable_occurrences,
    )
    from education_system.systems.university.infrastructure.database.db import get_connection
    conn = get_connection(row_factory=False)
    try:
        result = fn(conn, *args, **kwargs)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    if isinstance(result, dict) and result.get("emails"):
        timetable_occurrences.send_emails(result["emails"])
    return result


def _checkout_via_rules(self, item, borrower_ref, method="gui"):
    """Lend *item* (a copy barcode or a title) to *borrower_ref*. A blocked
    borrower can be lent to anyway by staff, after a warning. Returns the
    loan dict, or None when refused or cancelled."""
    from education_system.systems.university.application.library import circulation as circ
    staff = get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else None
    try:
        return _run_circulation(circ.checkout, item, borrower_ref, staff=staff, method=method)
    except ValueError as exc:
        can_override = "cannot borrow" in str(exc) and (self.is_admin() or self.is_staff())
        if can_override and messagebox.askyesno(
                _t('gui.academics.library.checkout_return.dialogs.override', default="Borrowing blocked"),
                f"{exc}\n\nLend anyway as a staff override?"):
            return _run_circulation(circ.checkout, item, borrower_ref, staff=staff,
                                    method=method, override=True)
        messagebox.showerror(_("common.error"), str(exc))
        return None


def show_checkout(self):
    """Show checkout interface"""
    if not self.check_permission('checkout_books'):
        return

    self.checkout_dialog()

def checkout_dialog(self):
    """Create checkout dialog"""
    # Get current logged-in user
    try:
        current_user = get_current_user()
        if not current_user:
            messagebox.showerror(_("common.error"), _t('gui.academics.library.checkout_return.dialogs.no_user_logged_in_please_log_in_to_checkout_books', default="No user logged in. Please log in to checkout books."))
            return

        current_user_id = current_user.get('username') or current_user.get('user_id') or current_user.get('id')
        if not current_user_id:
            messagebox.showerror(_("common.error"), _t('gui.academics.library.checkout_return.dialogs.could_not_determine_current_user_id', default="Could not determine current user ID."))
            return

        # Store current user ID for checkout
        self.selected_user_id = current_user_id

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Failed to get current user: {str(e)}")
        return

    dialog = tk.Toplevel(self.master)
    dialog.title(_("library.dialogs.checkout_book"))
    dialog.geometry("500x350")
    dialog.transient(self.master)
    dialog.grab_set()

    # Center dialog
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
    y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
    dialog.geometry(f"+{x}+{y}")

    main_frame = ttk.Frame(dialog)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Current user display
    user_frame = ttk.LabelFrame(main_frame, text=_t('gui.academics.library.checkout_return.labels.borrowing_as', default="Borrowing As"))
    user_frame.pack(fill=tk.X, pady=(0, 10))

    user_info = f"User ID: {current_user_id}\nRole: {current_user.get('role', 'N/A')}"
    if current_user.get('first_name'):
        user_info = f"Name: {current_user.get('first_name', '')} {current_user.get('last_name', '')}\n" + user_info

    ttk.Label(user_frame, text=user_info, justify=tk.LEFT).pack(anchor='w', padx=10, pady=10)

    # Book selection
    book_frame = ttk.LabelFrame(main_frame, text=_("library.frames.book_information"))
    book_frame.pack(fill=tk.X, pady=(0, 10))

    ttk.Label(book_frame, text=_t('gui.academics.library.checkout_return.labels.book_id_or_barcode', default="Book ID or Barcode:")).pack(anchor='w', padx=5, pady=5)
    self.checkout_book_var = tk.StringVar()
    book_entry = ttk.Entry(book_frame, textvariable=self.checkout_book_var, width=30)
    book_entry.pack(anchor='w', padx=5, pady=5)

    ttk.Button(book_frame, text=_t('gui.academics.library.checkout_return.buttons.lookup_book', default="Lookup Book"), command=self.lookup_checkout_book).pack(anchor='w', padx=5, pady=5)

    # Book details display
    self.checkout_book_info = tk.Text(book_frame, height=4, wrap=tk.WORD, state=tk.DISABLED)
    self.checkout_book_info.pack(fill=tk.X, padx=5, pady=5)

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, pady=10)

    self.checkout_button = ttk.Button(button_frame, text=_t('gui.academics.library.checkout_return.buttons.checkout', default="Checkout"), command=lambda: self.process_checkout(dialog), state=tk.DISABLED)
    self.checkout_button.pack(side=tk.LEFT, padx=5)

    ttk.Button(button_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    # Focus on book entry
    book_entry.focus()

def lookup_checkout_book(self):
    """Lookup book for checkout"""
    book_identifier = self.checkout_book_var.get().strip()
    if not book_identifier:
        messagebox.showwarning(_("common.warning"), _t('gui.academics.library.checkout_return.dialogs.please_enter_a_book_id_or_barcode', default="Please enter a book ID or barcode"))
        return

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            # Try to find book by ID or barcode
            cursor.execute('''
            SELECT book_id, title, author, status, location
            FROM books
            WHERE book_id = ? OR barcode = ?
            ''', (book_identifier, book_identifier))

            result = cursor.fetchone()
            conn.close()

            if result:
                book_id, title, author, status, location = result

                self.checkout_book_info.config(state=tk.NORMAL)
                self.checkout_book_info.delete("1.0", tk.END)
                self.checkout_book_info.insert(tk.END, f"ID: {book_id}\nTitle: {title}\nAuthor: {author}\nStatus: {status}\nLocation: {location}")
                self.checkout_book_info.config(state=tk.DISABLED)

                if status != 'available':
                    messagebox.showwarning(_("common.warning"), f"Book is currently {status} and cannot be checked out")
                else:
                    self.selected_book_id = book_id
                    self.check_checkout_ready()
            else:
                messagebox.showerror(_("common.error"), _t('gui.academics.library.checkout_return.dialogs.book_not_found', default="Book not found"))
                self.checkout_book_info.config(state=tk.NORMAL)
                self.checkout_book_info.delete("1.0", tk.END)
                self.checkout_book_info.config(state=tk.DISABLED)
        else:
            # Demo mode
            self.checkout_book_info.config(state=tk.NORMAL)
            self.checkout_book_info.delete("1.0", tk.END)
            self.checkout_book_info.insert(tk.END, "Demo Book\nTitle: Sample Book\nAuthor: Sample Author\nStatus: Available")
            self.checkout_book_info.config(state=tk.DISABLED)
            self.selected_book_id = book_identifier
            self.check_checkout_ready()

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Error looking up book: {str(e)}")

def verify_checkout_user(self):
    """Verify user for checkout"""
    user_id = self.checkout_user_var.get().strip()
    user_type = self.user_type_var.get()

    if not user_id:
        messagebox.showwarning(_("common.warning"), _t('gui.academics.library.checkout_return.dialogs.please_enter_a_user_id', default="Please enter a user ID"))
        return

    try:
        if ORIGINAL_LIBRARY_AVAILABLE and user_type == "Student":
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            student_columns = self._get_student_columns()
            grade_sql = ', grade_level' if 'grade_level' in student_columns else ''
            cursor.execute('SELECT first_name, last_name' + grade_sql + ' FROM students WHERE student_id = ?', (user_id,))
            result = cursor.fetchone()
            conn.close()

            if result:
                first_name, last_name = result[:2]
                grade_level = result[2] if len(result) > 2 else 'N/A'

                self.checkout_user_info.config(state=tk.NORMAL)
                self.checkout_user_info.delete("1.0", tk.END)
                self.checkout_user_info.insert(tk.END, f"Name: {first_name} {last_name}\nGrade: {grade_level}")
                self.checkout_user_info.config(state=tk.DISABLED)

                self.selected_user_id = user_id
                self.check_checkout_ready()
            else:
                messagebox.showwarning(_("common.warning"), f"Student with ID {user_id} not found")
                self.checkout_user_info.config(state=tk.NORMAL)
                self.checkout_user_info.delete("1.0", tk.END)
                self.checkout_user_info.config(state=tk.DISABLED)
        else:
            # For staff or demo mode
            self.checkout_user_info.config(state=tk.NORMAL)
            self.checkout_user_info.delete("1.0", tk.END)
            self.checkout_user_info.insert(tk.END, f"User ID: {user_id}\nType: {user_type}")
            self.checkout_user_info.config(state=tk.DISABLED)

            self.selected_user_id = user_id
            self.check_checkout_ready()

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Error verifying user: {str(e)}")

def check_checkout_ready(self):
    """Check if checkout is ready to proceed"""
    if hasattr(self, 'selected_book_id') and hasattr(self, 'selected_user_id'):
        self.checkout_button.config(state=tk.NORMAL)
    else:
        self.checkout_button.config(state=tk.DISABLED)

def process_checkout(self, dialog):
    """Process the book checkout"""
    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            # Use original checkout function
            success = self.checkout_book_database(self.selected_book_id, self.selected_user_id)

            if success:
                messagebox.showinfo(_("common.success"), _t('gui.academics.library.checkout_return.dialogs.book_checked_out_successfully', default="Book checked out successfully!"))

                # Send checkout confirmation email
                self._send_checkout_confirmation_email(self.selected_book_id, self.selected_user_id)

                dialog.destroy()
                self.refresh_books_table() if hasattr(self, 'books_tree') else None
            else:
                messagebox.showerror(_("common.error"), _t('gui.academics.library.checkout_return.dialogs.checkout_failed', default="Checkout failed"))
        else:
            # Demo mode
            messagebox.showinfo(_("common.demo"), f"Book {self.selected_book_id} checked out to {self.selected_user_id}")
            dialog.destroy()

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Checkout error: {str(e)}")

def checkout_book_database(self, book_id, user_id):
    """Checkout book in database (a copy of the title, under the loan rules)."""
    loan = _checkout_via_rules(self, book_id, user_id)
    if not loan:
        return False
    try:
        conn = get_db_connection()
        row = conn.execute('SELECT title FROM books WHERE book_id = ?', (book_id,)).fetchone()
        conn.close()
        self._send_checkout_emails(loan["borrower"]["ref"], book_id,
                                   row[0] if row else "Unknown Book", loan["due_date"][:10])
    except (sqlite3.Error, DatabaseError) as e:
        logger.warning("checkout email lookup failed: %s", e)
    if ORIGINAL_LIBRARY_AVAILABLE:
        log_audit_event(get_current_user_id(),
                        f"GUI: Checked out {loan['barcode']} to {loan['borrower']['ref']}",
                        "book_loans", str(loan["loan_id"]))
    return True

def checkout_selected_book(self):
    """Quick checkout from context menu"""
    selection = self.books_tree.selection()
    if not selection:
        messagebox.showwarning(_("common.warning"), _("library.messages.please_select_book"))
        return

    item = self.books_tree.item(selection[0])
    book_id = item['values'][0]

    # Create quick checkout dialog
    dialog = tk.Toplevel(self.master)
    dialog.title(_("library.dialogs.quick_checkout"))
    dialog.geometry("400x200")
    dialog.transient(self.master)

    ttk.Label(dialog, text=f"Checkout Book: {book_id}", font=('Arial', 12, 'bold')).pack(pady=10)
    ttk.Label(dialog, text=f"Title: {item['values'][1]}").pack(pady=5)

    ttk.Label(dialog, text=_t('gui.academics.library.checkout_return.labels.user_id_or_email', default="User ID or Email:")).pack(pady=10)
    user_var = tk.StringVar()
    user_entry = ttk.Entry(dialog, textvariable=user_var, width=30)
    user_entry.pack(pady=5)
    user_entry.focus()

    def process_quick_checkout():
        try:
            user_id = user_var.get().strip()
            if not user_id:
                messagebox.showwarning(_("common.warning"), _t('gui.academics.library.checkout_return.dialogs.please_enter_a_user_id', default="Please enter a user ID"))
                return

            # A student may be given by ID or email; anyone else by username.
            conn = get_db_connection()
            row = conn.execute(
                'SELECT student_id FROM students WHERE student_id = ? OR email_address = ?',
                (user_id, user_id)).fetchone()
            conn.close()
            loan = _checkout_via_rules(self, book_id, row[0] if row else user_id, method="quick")
            if not loan:
                return
            messagebox.showinfo(_("common.success"),
                                f"Copy {loan['barcode']} checked out.\nDue: {loan['due_date'][:16]}")
            dialog.destroy()
            self.load_books_data()

        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Checkout failed: {str(e)}")

    ttk.Button(dialog, text=_t('gui.academics.library.checkout_return.buttons.checkout', default="Checkout"), command=process_quick_checkout).pack(pady=10)
    ttk.Button(dialog, text=_("common.cancel"), command=dialog.destroy).pack(pady=5)

def show_return(self):
    """Show return book interface"""
    if not self.check_permission('checkout_books'):
        return

    self.return_dialog()

def return_dialog(self):
    """Create return book dialog"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_("library.dialogs.return_book"))
    dialog.geometry("500x350")
    dialog.transient(self.master)
    dialog.grab_set()

    # Center dialog
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
    y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
    dialog.geometry(f"+{x}+{y}")

    main_frame = ttk.Frame(dialog)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Book identification
    book_frame = ttk.LabelFrame(main_frame, text=_t('gui.academics.library.checkout_return.labels.book_identification', default="Book Identification"))
    book_frame.pack(fill=tk.X, pady=(0, 10))

    ttk.Label(book_frame, text=_t('gui.academics.library.checkout_return.labels.book_id_or_barcode', default="Book ID or Barcode:")).pack(anchor='w', padx=5, pady=5)
    self.return_book_var = tk.StringVar()
    book_entry = ttk.Entry(book_frame, textvariable=self.return_book_var, width=30)
    book_entry.pack(anchor='w', padx=5, pady=5)

    ttk.Button(book_frame, text=_t('gui.academics.library.checkout_return.buttons.lookup_book', default="Lookup Book"), command=self.lookup_return_book).pack(anchor='w', padx=5, pady=5)

    # Loan details
    loan_frame = ttk.LabelFrame(main_frame, text=_("library.frames.loan_details"))
    loan_frame.pack(fill=tk.X, pady=(0, 10))

    self.return_loan_info = tk.Text(loan_frame, height=6, wrap=tk.WORD, state=tk.DISABLED)
    self.return_loan_info.pack(fill=tk.X, padx=5, pady=5)

    # Return conditions
    condition_frame = ttk.LabelFrame(main_frame, text=_("library.frames.book_condition"))
    condition_frame.pack(fill=tk.X, pady=(0, 10))

    self.book_condition_var = tk.StringVar(value=_t('gui.academics.library.checkout_return.values.good', default="Good"))
    ttk.Radiobutton(condition_frame, text=_t('gui.academics.library.checkout_return.buttons.good_condition', default="Good Condition"), variable=self.book_condition_var, value="Good").pack(anchor='w', padx=5, pady=2)
    ttk.Radiobutton(condition_frame, text=_t('gui.academics.library.checkout_return.buttons.damaged', default="Damaged"), variable=self.book_condition_var, value="Damaged").pack(anchor='w', padx=5, pady=2)

    ttk.Label(condition_frame, text=_t('gui.academics.library.checkout_return.labels.notes_if_damaged', default="Notes (if damaged):")).pack(anchor='w', padx=5, pady=(5, 0))
    self.condition_notes = tk.Text(condition_frame, height=2, width=50)
    self.condition_notes.pack(anchor='w', padx=5, pady=5)

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, pady=10)

    self.return_button = ttk.Button(button_frame, text=_t('gui.academics.library.checkout_return.buttons.return_book', default="Return Book"), command=lambda: self.process_return(dialog), state=tk.DISABLED)
    self.return_button.pack(side=tk.LEFT, padx=5)

    ttk.Button(button_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    # Focus on book entry
    book_entry.focus()

def lookup_return_book(self):
    """Lookup book for return"""
    book_identifier = self.return_book_var.get().strip()
    if not book_identifier:
        messagebox.showwarning(_("common.warning"), _t('gui.academics.library.checkout_return.dialogs.please_enter_a_book_id_or_barcode', default="Please enter a book ID or barcode"))
        return

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            # Find active loan
            cursor.execute('''
            SELECT bl.loan_id, bl.user_id, bl.checkout_date, bl.due_date,
                   b.title, b.author, bl.status
            FROM book_loans bl
            JOIN books b ON bl.book_id = b.book_id
            WHERE (b.book_id = ? OR b.barcode = ?)
            AND bl.status IN ('active', 'overdue')
            ''', (book_identifier, book_identifier))

            result = cursor.fetchone()
            conn.close()

            if result:
                loan_id, user_id, checkout_date, due_date, title, author, status = result

                # Calculate if overdue
                due_date_obj = datetime.strptime(due_date, '%Y-%m-%d %H:%M:%S')
                now = datetime.now()
                is_overdue = now > due_date_obj
                days_overdue = (now - due_date_obj).days if is_overdue else 0

                # Calculate fine
                fine_amount = 0.0
                if is_overdue:
                    fine_per_day = 0.50  # Default fine
                    try:
                        cursor = get_db_connection().cursor()
                        cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "fine_per_day"')
                        fine_setting = cursor.fetchone()
                        if fine_setting:
                            fine_per_day = float(fine_setting[0])
                    except (sqlite3.Error, DatabaseError, ValueError, TypeError):
                        pass
                    fine_amount = days_overdue * fine_per_day

                # Display loan info
                loan_info = f"""Title: {title}
Author: {author}
Borrower: {user_id}
Checkout Date: {checkout_date[:10]}
Due Date: {due_date[:10]}
Status: {status.upper()}"""

                if is_overdue:
                    loan_info += f"\n⚠️ OVERDUE by {days_overdue} days"
                    loan_info += f"\nFine Amount: £{fine_amount:.2f}"

                self.return_loan_info.config(state=tk.NORMAL)
                self.return_loan_info.delete("1.0", tk.END)
                self.return_loan_info.insert(tk.END, loan_info)
                self.return_loan_info.config(state=tk.DISABLED)

                self.selected_loan_id = loan_id
                self.selected_return_book_id = book_identifier
                self.return_fine_amount = fine_amount
                self.return_borrower_id = user_id  # Store borrower ID for verification
                self.return_button.config(state=tk.NORMAL)

            else:
                messagebox.showerror(_("common.error"), _t('gui.academics.library.checkout_return.dialogs.no_active_loan_found_for_this_book', default="No active loan found for this book"))
                self.return_loan_info.config(state=tk.NORMAL)
                self.return_loan_info.delete("1.0", tk.END)
                self.return_loan_info.config(state=tk.DISABLED)
                self.return_button.config(state=tk.DISABLED)
        else:
            # Demo mode
            self.return_loan_info.config(state=tk.NORMAL)
            self.return_loan_info.delete("1.0", tk.END)
            self.return_loan_info.insert(tk.END, f"Demo loan for book {book_identifier}\nBorrower: DEMO_USER\nDue: Today")
            self.return_loan_info.config(state=tk.DISABLED)
            self.return_button.config(state=tk.NORMAL)

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Error looking up book: {str(e)}")

def process_return(self, dialog):
    """Process book return"""
    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            # Verify current user can return this book
            current_user = get_current_user()
            current_user_id = current_user.get('username') or current_user.get('user_id') or current_user.get('id')
            current_user_role = current_user.get('role', '').lower()

            # Only allow the borrower or staff/admin to return
            if hasattr(self, 'return_borrower_id'):
                if current_user_id != self.return_borrower_id and current_user_role not in ['admin', 'staff', 'librarian']:
                    messagebox.showerror(_t('gui.academics.library.checkout_return.dialogs.access_denied', default="Access Denied"),
                                       f"Only the borrower ({self.return_borrower_id}) or library staff can return this book.")
                    return

            success = self.return_book_database()

            if success:
                messagebox.showinfo(_("common.success"), _t('gui.academics.library.checkout_return.dialogs.book_returned_successfully', default="Book returned successfully!"))

                # Send return confirmation email
                if hasattr(self, 'return_borrower_id'):
                    self._send_return_confirmation_email(self.selected_return_book_id, self.return_borrower_id)

                dialog.destroy()
                self.refresh_books_table() if hasattr(self, 'books_tree') else None
            else:
                messagebox.showerror(_("common.error"), _t('gui.academics.library.checkout_return.dialogs.return_failed', default="Return failed"))
        else:
            # Demo mode
            messagebox.showinfo(_("common.demo"), _t('gui.academics.library.checkout_return.dialogs.book_returned_successfully', default="Book returned successfully!"))
            dialog.destroy()

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Return error: {str(e)}")

def return_book_database(self):
    """Return a copy: overdue fine, next hold, or damaged — shared rules."""
    from education_system.systems.university.application.library import circulation as circ
    condition = self.book_condition_var.get()
    notes = self.condition_notes.get("1.0", tk.END).strip()
    try:
        result = _run_circulation(
            circ.return_item, self.selected_loan_id,
            condition="damaged" if condition == "Damaged" else "good", notes=notes or None,
            staff=get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else None)
    except ValueError as exc:
        messagebox.showerror(_("common.error"), str(exc))
        return False
    self.return_fine_amount = result["fine"]
    if ORIGINAL_LIBRARY_AVAILABLE:
        log_audit_event(get_current_user_id(), f"GUI: Returned loan {result['loan_id']}",
                        "book_loans", str(result["loan_id"]))
    try:
        conn = get_db_connection()
        row = conn.execute('SELECT title FROM books WHERE book_id = ?',
                           (self.selected_return_book_id,)).fetchone()
        conn.close()
        self._send_return_emails(result["borrower"], self.selected_return_book_id,
                                 row[0] if row else "Unknown Book")
    except (sqlite3.Error, DatabaseError) as e:
        logger.warning("return email lookup failed: %s", e)
    if result["held"]:
        messagebox.showinfo(_("common.info"), "Someone has requested this title: put the copy "
                            "on the holds shelf. They have been told it is ready.")
    return True

def enhanced_checkout_book_gui(self, book_id=None):
    """Enhanced checkout with reading level check and notifications"""
    checkout_window = tk.Toplevel(self.master)
    checkout_window.title(_t('gui.academics.library.checkout_return.windows.enhanced_book_checkout', default="Enhanced Book Checkout"))
    checkout_window.geometry("600x500")

    ttk.Label(checkout_window, text=_t('gui.academics.library.checkout_return.labels.enhanced_book_checkout', default="Enhanced Book Checkout"),
             font=('Arial', 16, 'bold')).pack(pady=10)

    # Book selection frame
    book_frame = ttk.LabelFrame(checkout_window, text=_t('gui.academics.library.checkout_return.labels.book_selection', default="Book Selection"), padding=15)
    book_frame.pack(fill=tk.X, padx=10, pady=10)

    book_id_var = tk.StringVar(value=book_id or "")
    user_id_var = tk.StringVar()
    book_info_var = tk.StringVar(value=_t('gui.academics.library.checkout_return.values.no_book_selected', default="No book selected"))

    ttk.Label(book_frame, text=_t('gui.academics.library.checkout_return.labels.book_id', default="Book ID:")).grid(row=0, column=0, sticky=tk.W, pady=5)
    book_id_entry = ttk.Entry(book_frame, textvariable=book_id_var, width=30)
    book_id_entry.grid(row=0, column=1, padx=10, pady=5)

    def lookup_book():
        bid = book_id_var.get().strip()
        if not bid:
            messagebox.showwarning(_("common.warning"), _t('gui.academics.library.checkout_return.dialogs.please_enter_a_book_id', default="Please enter a Book ID"))
            return

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
            SELECT title, author, status, reading_level
            FROM books WHERE book_id = ?
            ''', (bid,))
            book = cursor.fetchone()
            conn.close()

            if book:
                title, author, status, reading_level = book
                book_info_var.set(f"{title} by {author}\nStatus: {status}\nReading Level: {reading_level or 'Unknown'}")
                if status != 'available':
                    messagebox.showwarning(_("common.warning"), f"This book is currently {status}")
            else:
                book_info_var.set("Book not found")
                messagebox.showerror(_("common.error"), _t('gui.academics.library.checkout_return.dialogs.book_not_found', default="Book not found"))
        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Failed to lookup book: {str(e)}")

    ttk.Button(book_frame, text=_t('gui.academics.library.checkout_return.buttons.lookup', default="Lookup"), command=lookup_book).grid(row=0, column=2, padx=5)

    # Book info display
    ttk.Label(book_frame, textvariable=book_info_var, foreground='blue').grid(
        row=1, column=0, columnspan=3, pady=10, sticky=tk.W)

    # User selection frame
    user_frame = ttk.LabelFrame(checkout_window, text=_("library.frames.user_information"), padding=15)
    user_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Label(user_frame, text=_t('gui.academics.library.checkout_return.labels.user_student_id', default="User/Student ID:")).grid(row=0, column=0, sticky=tk.W, pady=5)
    ttk.Entry(user_frame, textvariable=user_id_var, width=30).grid(row=0, column=1, padx=10, pady=5)

    # Checkout options
    options_frame = ttk.LabelFrame(checkout_window, text=_t('gui.academics.library.checkout_return.labels.checkout_options', default="Checkout Options"), padding=15)
    options_frame.pack(fill=tk.X, padx=10, pady=10)

    check_reading_level_var = tk.BooleanVar(value=True)
    send_notification_var = tk.BooleanVar(value=True)

    ttk.Checkbutton(options_frame, text=_t('gui.academics.library.checkout_return.buttons.check_reading_level_compatibility', default="Check Reading Level Compatibility"),
                   variable=check_reading_level_var).pack(anchor=tk.W, pady=2)
    ttk.Checkbutton(options_frame, text=_t('gui.academics.library.checkout_return.buttons.send_email_notification', default="Send Email Notification"),
                   variable=send_notification_var).pack(anchor=tk.W, pady=2)

    def perform_checkout():
        bid = book_id_var.get().strip()
        uid = user_id_var.get().strip()

        if not bid or not uid:
            messagebox.showerror(_("common.error"), _t('gui.academics.library.checkout_return.dialogs.please_provide_both_book_id_and_user_id', default="Please provide both Book ID and User ID"))
            return

        loan = _checkout_via_rules(self, bid, uid)
        if not loan:
            return
        messagebox.showinfo(_("common.success"),
            "Book checked out successfully!\n\n" +
            f"Copy: {loan['barcode']}\n" +
            f"User: {loan['borrower']['ref']} ({loan['borrower']['category']})\n" +
            f"Due: {loan['due_date'][:16]}")
        checkout_window.destroy()
        if hasattr(self, 'show_all_books'):
            self.show_all_books()

    # Button frame
    button_frame = ttk.Frame(checkout_window)
    button_frame.pack(fill=tk.X, padx=10, pady=20)

    ttk.Button(button_frame, text=_t('gui.academics.library.checkout_return.buttons.checkout', default="Checkout"), command=perform_checkout).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.cancel"), command=checkout_window.destroy).pack(side=tk.LEFT, padx=5)

def enhanced_return_book_gui(self):
    """Enhanced book return with fine calculation"""
    return_window = tk.Toplevel(self.master)
    return_window.title(_t('gui.academics.library.checkout_return.windows.enhanced_book_return', default="Enhanced Book Return"))
    return_window.geometry("600x500")

    ttk.Label(return_window, text=_t('gui.academics.library.checkout_return.labels.enhanced_book_return', default="Enhanced Book Return"),
             font=('Arial', 16, 'bold')).pack(pady=10)

    # Search frame
    search_frame = ttk.LabelFrame(return_window, text=_t('gui.academics.library.checkout_return.labels.find_loan', default="Find Loan"), padding=15)
    search_frame.pack(fill=tk.X, padx=10, pady=10)

    search_type = tk.StringVar(value=_t('gui.academics.library.checkout_return.values.book_id', default="book_id"))
    search_value = tk.StringVar()

    ttk.Radiobutton(search_frame, text=_t('gui.academics.library.checkout_return.buttons.by_book_id', default="By Book ID"), variable=search_type,
                   value="book_id").grid(row=0, column=0, sticky=tk.W, padx=5)
    ttk.Radiobutton(search_frame, text=_t('gui.academics.library.checkout_return.buttons.by_user_id', default="By User ID"), variable=search_type,
                   value="user_id").grid(row=0, column=1, sticky=tk.W, padx=5)
    ttk.Radiobutton(search_frame, text=_t('gui.academics.library.checkout_return.buttons.by_loan_id', default="By Loan ID"), variable=search_type,
                   value="loan_id").grid(row=0, column=2, sticky=tk.W, padx=5)

    # The three search modes want three different inputs. Book and
    # borrower are chosen from real rows — only a loan ID is genuinely
    # free text, since it is printed on the receipt the reader brings in.
    # Only books that are actually on loan are offered: searching for a
    # book nobody has out can only ever return nothing.
    book_picker = attach_picker(search_frame, "loaned_book", width=40)
    borrower_picker = attach_picker(search_frame, "borrower", width=40)
    loan_entry = ttk.Entry(search_frame, textvariable=search_value, width=30)
    for widget in (book_picker.combo, borrower_picker.combo, loan_entry):
        widget.grid(row=1, column=0, columnspan=2, padx=5, pady=10, sticky=tk.W)
        widget.grid_remove()

    def _show_input(*_args):
        mode = search_type.get()
        book_picker.combo.grid_remove()
        borrower_picker.combo.grid_remove()
        loan_entry.grid_remove()
        {"book_id": book_picker.combo,
         "user_id": borrower_picker.combo}.get(mode, loan_entry).grid()

    search_type.trace_add("write", _show_input)
    _show_input()

    # Results frame
    results_frame = ttk.LabelFrame(return_window, text=_t('gui.academics.library.checkout_return.labels.active_loans', default="Active Loans"), padding=10)
    results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    columns = ('Loan ID', 'Book ID', 'Title', 'User ID', 'Due Date', 'Fine')
    results_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=8)

    for col in columns:
        results_tree.heading(col, text=col)
        results_tree.column(col, width=100)

    results_tree.pack(fill=tk.BOTH, expand=True)

    def search_loans():
        # Clear previous results
        for item in results_tree.get_children():
            results_tree.delete(item)

        stype = search_type.get()
        svalue = {"book_id": book_picker.get,
                  "user_id": borrower_picker.get}.get(
                      stype, lambda: search_value.get().strip())()

        if not svalue:
            messagebox.showwarning(_("common.warning"), _t('gui.academics.library.checkout_return.dialogs.please_enter_a_search_value', default="Please enter a search value"))
            return

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Get fine per day
            cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "fine_per_day"')
            fine_per_day_result = cursor.fetchone()
            fine_per_day = float(fine_per_day_result[0]) if fine_per_day_result else 0.50

            # Build query based on search type
            if stype == "book_id":
                query = '''
                SELECT l.loan_id, l.book_id, b.title, l.user_id, l.due_date, l.fine_amount
                FROM book_loans l
                JOIN books b ON l.book_id = b.book_id
                WHERE l.book_id = ? AND l.status = 'active'
                '''
            elif stype == "user_id":
                query = '''
                SELECT l.loan_id, l.book_id, b.title, l.user_id, l.due_date, l.fine_amount
                FROM book_loans l
                JOIN books b ON l.book_id = b.book_id
                WHERE l.user_id = ? AND l.status = 'active'
                '''
            else:  # loan_id
                query = '''
                SELECT l.loan_id, l.book_id, b.title, l.user_id, l.due_date, l.fine_amount
                FROM book_loans l
                JOIN books b ON l.book_id = b.book_id
                WHERE l.loan_id = ? AND l.status = 'active'
                '''

            cursor.execute(query, (svalue,))
            loans = cursor.fetchall()

            # Calculate fines
            now = datetime.now()
            for loan in loans:
                loan_id, book_id, title, user_id, due_date, current_fine = loan

                # Calculate fine if overdue
                due_datetime = datetime.strptime(due_date, '%Y-%m-%d %H:%M:%S')
                if now > due_datetime:
                    days_overdue = (now - due_datetime).days
                    calculated_fine = days_overdue * fine_per_day
                else:
                    calculated_fine = 0.0

                results_tree.insert('', 'end', values=(
                    loan_id, book_id, title, user_id, due_date[:10], f"£{calculated_fine:.2f}"
                ))

            conn.close()

            if not loans:
                messagebox.showinfo(_t('gui.academics.library.checkout_return.dialogs.no_results', default="No Results"), _t('gui.academics.library.checkout_return.dialogs.no_active_loans_found', default="No active loans found"))

        except tk.TclError as e:
            messagebox.showerror(_("common.error"), f"Search failed: {str(e)}")

    ttk.Button(search_frame, text=_("common.search"), command=search_loans).grid(row=1, column=2, padx=5)

    def return_selected():
        selection = results_tree.selection()
        if not selection:
            messagebox.showwarning(_("common.warning"), _t('gui.academics.library.checkout_return.dialogs.please_select_a_loan_to_return', default="Please select a loan to return"))
            return

        item = results_tree.item(selection[0])
        loan_id = item['values'][0]
        book_id = item['values'][1]
        fine_str = item['values'][5]
        fine_amount = float(fine_str.replace('$', ''))

        # Confirm return
        if fine_amount > 0:
            confirm = messagebox.askyesno(_t('gui.academics.library.checkout_return.dialogs.confirm_return', default="Confirm Return"),
                f"Return this book?\n\nLoan ID: {loan_id}\n" +
                f"Book ID: {book_id}\n" +
                f"Fine: £{fine_amount:.2f}\n\n" +
                "Fine must be paid before return is complete.")
            if not confirm:
                return
        else:
            confirm = messagebox.askyesno(_t('gui.academics.library.checkout_return.dialogs.confirm_return', default="Confirm Return"),
                f"Return this book?\n\nLoan ID: {loan_id}\nBook ID: {book_id}")
            if not confirm:
                return

        from education_system.systems.university.application.library import circulation as circ
        try:
            result = _run_circulation(circ.return_item, loan_id,
                                      staff=get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else None)
        except ValueError as exc:
            messagebox.showerror(_("common.error"), f"Return failed: {exc}")
            return
        log_audit_event(get_current_user_id(), f"Returned loan {loan_id}", "book_loans")
        messagebox.showinfo(_("common.success"),
            "Book returned successfully!\n\n" +
            f"Loan ID: {loan_id}\n" +
            (f"Fine: £{result['fine']:.2f}" if result["fine"] else "No fine") +
            ("\n\nRequested by another reader — put it on the holds shelf." if result["held"]
             else ""))
        search_loans()

    # Button frame
    button_frame = ttk.Frame(return_window)
    button_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(button_frame, text=_t('gui.academics.library.checkout_return.buttons.return_selected', default="Return Selected"), command=return_selected).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.close"), command=return_window.destroy).pack(side=tk.RIGHT, padx=5)

def renew_book_gui(self):
    """Renew book loan"""
    renew_window = tk.Toplevel(self.master)
    renew_window.title(_t('gui.academics.library.checkout_return.windows.renew_book_loan', default="Renew Book Loan"))
    renew_window.geometry("700x500")

    ttk.Label(renew_window, text=_t('gui.academics.library.checkout_return.labels.renew_book_loan', default="Renew Book Loan"),
             font=('Arial', 16, 'bold')).pack(pady=10)

    # Search frame
    search_frame = ttk.LabelFrame(renew_window, text=_t('gui.academics.library.checkout_return.labels.find_loan', default="Find Loan"), padding=15)
    search_frame.pack(fill=tk.X, padx=10, pady=10)

    search_value = tk.StringVar()
    ttk.Label(search_frame, text=_t('gui.academics.library.checkout_return.labels.book_id_or_user_id', default="Book ID or User ID:")).pack(side=tk.LEFT, padx=5)
    ttk.Entry(search_frame, textvariable=search_value, width=30).pack(side=tk.LEFT, padx=5)

    # Results frame
    results_frame = ttk.LabelFrame(renew_window, text=_t('gui.academics.library.checkout_return.labels.renewable_loans', default="Renewable Loans"), padding=10)
    results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    columns = ('Loan ID', 'Book', 'User', 'Checkout', 'Due Date', 'Renewals', 'Status')
    results_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=10)

    for col in columns:
        results_tree.heading(col, text=col)
        results_tree.column(col, width=100)

    results_tree.pack(fill=tk.BOTH, expand=True)

    def search_loans():
        for item in results_tree.get_children():
            results_tree.delete(item)

        svalue = search_value.get().strip()
        if not svalue:
            messagebox.showwarning(_("common.warning"), _t('gui.academics.library.checkout_return.dialogs.please_enter_a_search_value', default="Please enter a search value"))
            return

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT l.loan_id, b.title, l.user_id, l.checkout_date, l.due_date,
                   l.renewal_count, l.status
            FROM book_loans l
            JOIN books b ON l.book_id = b.book_id
            WHERE (l.book_id = ? OR l.user_id = ?) AND l.status = 'active'
            ''', (svalue, svalue))

            loans = cursor.fetchall()
            conn.close()

            for loan in loans:
                results_tree.insert('', 'end', values=(
                    loan[0], loan[1][:30], loan[2], loan[3][:10], loan[4][:10], loan[5], loan[6]
                ))

            if not loans:
                messagebox.showinfo(_t('gui.academics.library.checkout_return.dialogs.no_results', default="No Results"), _t('gui.academics.library.checkout_return.dialogs.no_renewable_loans_found', default="No renewable loans found"))

        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Search failed: {str(e)}")

    ttk.Button(search_frame, text=_("common.search"), command=search_loans).pack(side=tk.LEFT, padx=5)

    def renew_selected():
        selection = results_tree.selection()
        if not selection:
            messagebox.showwarning(_("common.warning"), _t('gui.academics.library.checkout_return.dialogs.please_select_a_loan_to_renew', default="Please select a loan to renew"))
            return

        item = results_tree.item(selection[0])
        loan_id = item['values'][0]
        renewal_count = item['values'][5]

        from education_system.systems.university.application.library import circulation as circ
        try:
            result = _run_circulation(circ.renew, loan_id)
        except ValueError as exc:
            messagebox.showerror(_("common.error"), str(exc))
            return
        log_audit_event(get_current_user_id(), f"Renewed loan {loan_id}", "book_loans")
        messagebox.showinfo(_("common.success"),
            "Loan renewed successfully!\n\n" +
            f"New due date: {result['due_date'][:16]}\n" +
            f"Renewals left: {result['renewals_left']}")
        search_loans()

    # Button frame
    button_frame = ttk.Frame(renew_window)
    button_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(button_frame, text=_t('gui.academics.library.checkout_return.buttons.renew_selected', default="Renew Selected"), command=renew_selected).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.close"), command=renew_window.destroy).pack(side=tk.RIGHT, padx=5)

def view_loan_history_gui(self):
    """GUI for viewing loan history"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_("library.dialogs.loan_history_viewer"))
    dialog.geometry("800x600")
    dialog.transient(self.master)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Options frame
    options_frame = ttk.LabelFrame(main_frame, text=_t('gui.academics.library.checkout_return.labels.view_options', default="View Options"))
    options_frame.pack(fill=tk.X, pady=(0, 10))

    self.loan_history_type = tk.StringVar(value=_t('gui.academics.library.checkout_return.values.all', default="all"))
    ttk.Radiobutton(options_frame, text=_t('gui.academics.library.checkout_return.buttons.all_recent_loans', default="All Recent Loans"), variable=self.loan_history_type, value="all").pack(anchor='w', padx=5, pady=2)
    ttk.Radiobutton(options_frame, text=_t('gui.academics.library.checkout_return.buttons.by_user', default="By User"), variable=self.loan_history_type, value="user").pack(anchor='w', padx=5, pady=2)
    ttk.Radiobutton(options_frame, text=_t('gui.academics.library.checkout_return.buttons.by_book', default="By Book"), variable=self.loan_history_type, value="book").pack(anchor='w', padx=5, pady=2)

    # Search frame
    search_frame = ttk.Frame(options_frame)
    search_frame.pack(fill=tk.X, padx=5, pady=5)

    self.loan_history_label = ttk.Label(search_frame, text=_t('gui.academics.library.checkout_return.labels.user_book', default="User/Book:"))
    self.loan_history_label.pack(side=tk.LEFT)
    self.loan_search_var = tk.StringVar()

    # One picker per mode, swapped with the radio buttons above. History
    # covers returned loans too, so every book is offered here, not just
    # the ones currently out.
    self._loan_user_picker = attach_picker(search_frame, "borrower", width=36)
    self._loan_book_picker = attach_picker(search_frame, "book", width=36)
    for widget in (self._loan_user_picker.combo, self._loan_book_picker.combo):
        widget.pack(side=tk.LEFT, padx=5)
        widget.pack_forget()

    search_btn = ttk.Button(search_frame, text=_("common.search"),
                            command=self.load_loan_history)
    search_btn.pack(side=tk.LEFT, padx=5)

    def _show_loan_input(*_args):
        mode = self.loan_history_type.get()
        self._loan_user_picker.combo.pack_forget()
        self._loan_book_picker.combo.pack_forget()
        search_btn.pack_forget()
        if mode == "user":
            self.loan_history_label.config(text=_t('gui.academics.library.checkout_return.labels.user', default="User:"))
            self._loan_user_picker.combo.pack(side=tk.LEFT, padx=5)
        elif mode == "book":
            self.loan_history_label.config(text=_t('gui.academics.library.checkout_return.labels.book', default="Book:"))
            self._loan_book_picker.combo.pack(side=tk.LEFT, padx=5)
        else:
            self.loan_history_label.config(text=_t('gui.academics.library.checkout_return.labels.all_recent_loans', default="All recent loans"))
        search_btn.pack(side=tk.LEFT, padx=5)

    self.loan_history_type.trace_add("write", _show_loan_input)
    _show_loan_input()

    # Results table
    table_frame = ttk.Frame(main_frame)
    table_frame.pack(fill=tk.BOTH, expand=True)

    columns = ('Loan ID', 'User ID', 'Book ID', 'Title', 'Checkout Date', 'Due Date', 'Return Date', 'Status')
    self.loan_history_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=20)

    for col in columns:
        self.loan_history_tree.heading(col, text=col)
        self.loan_history_tree.column(col, width=100)

    scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.loan_history_tree.yview)
    self.loan_history_tree.configure(yscrollcommand=scrollbar.set)

    self.loan_history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Right-click: jump to student record / email / finance / course.
    try:
        from education_system.systems.university.domains.library.interfaces.gui.library import _cross_links
        _cross_links.attach_cross_link_menu(
            self.loan_history_tree,
            _cross_links.loan_history_menu_items,
            parent=self.master,
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Could not attach cross-link menu to loan_history_tree")

    # Load initial data
    self.load_loan_history()

    ttk.Button(main_frame, text=_("common.close"), command=dialog.destroy).pack(pady=10)


def _get_user_email(user_id):
    """Look up email for a user_id (checks students then users tables)."""
    try:
        conn = get_db_connection()
        if not conn:
            return None, None
        cursor = conn.cursor()

        # Try students table
        cursor.execute(
            "SELECT first_name, email_address FROM students WHERE student_id = ?",
            (user_id,))
        row = cursor.fetchone()
        if row and row[1]:
            conn.close()
            return row[0], row[1]

        # Try users table
        cursor.execute(
            "SELECT first_name, email FROM users WHERE username = ? OR id = ?",
            (user_id, user_id))
        row = cursor.fetchone()
        conn.close()
        if row and row[1]:
            return row[0], row[1]

        return None, None
    except Exception:
        return None, None


def _get_admin_emails():
    """Get all admin email addresses."""
    try:
        conn = get_db_connection()
        if not conn:
            return []
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM users WHERE LOWER(role) = 'admin' AND email IS NOT NULL AND email != ''")
        emails = [r[0] for r in cursor.fetchall()]
        conn.close()
        return emails
    except Exception:
        return []


def _send_checkout_emails(self, user_id, book_id, book_title, due_date):
    """Email user and admin about a book checkout."""
    try:
        from education_system.systems.university.infrastructure.email.email_service import send_email

        # Email the user
        name, email = _get_user_email(user_id)
        if email:
            send_email(
                recipient_email=email,
                subject=f"Book Checked Out: {book_title}",
                body=(
                    f"Dear {name or user_id},\n\n"
                    f"You have checked out the following book:\n\n"
                    f"Title: {book_title}\n"
                    f"Book ID: {book_id}\n"
                    f"Due Date: {due_date}\n\n"
                    f"Please return the book by the due date to avoid any late fees.\n\n"
                    f"Best regards,\nLibrary Services"
                )
            )

        # Email admin(s)
        for admin_email in _get_admin_emails():
            try:
                send_email(
                    recipient_email=admin_email,
                    subject=f"Library Checkout: {book_title}",
                    body=(
                        f"Book checkout notification:\n\n"
                        f"User: {user_id}\n"
                        f"Book: {book_title} ({book_id})\n"
                        f"Due Date: {due_date}\n"
                        f"Checked out via GUI"
                    )
                )
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

    except Exception as e:
        import logging
        logging.warning(f"Failed to send checkout emails: {e}")


def _send_return_emails(self, user_id, book_id, book_title):
    """Email user and admin about a book return."""
    try:
        from education_system.systems.university.infrastructure.email.email_service import send_email

        return_date = datetime.now().strftime('%Y-%m-%d %H:%M')

        # Email the user
        name, email = _get_user_email(user_id)
        if email:
            send_email(
                recipient_email=email,
                subject=f"Book Returned: {book_title}",
                body=(
                    f"Dear {name or user_id},\n\n"
                    f"You have successfully returned the following book:\n\n"
                    f"Title: {book_title}\n"
                    f"Book ID: {book_id}\n"
                    f"Returned: {return_date}\n\n"
                    f"Thank you for using our library services.\n\n"
                    f"Best regards,\nLibrary Services"
                )
            )

        # Email admin(s)
        for admin_email in _get_admin_emails():
            try:
                send_email(
                    recipient_email=admin_email,
                    subject=f"Library Return: {book_title}",
                    body=(
                        f"Book return notification:\n\n"
                        f"User: {user_id}\n"
                        f"Book: {book_title} ({book_id})\n"
                        f"Returned: {return_date}\n"
                        f"Returned via GUI"
                    )
                )
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

    except Exception as e:
        import logging
        logging.warning(f"Failed to send return emails: {e}")

