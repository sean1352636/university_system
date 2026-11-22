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

def show_reservations(self):
    """Show reservations management"""
    # Check permission instead of user directly
    if not self.check_permission('manage_reservations'):
        return

    self.clear_content_area()

    reservations_frame = ttk.Frame(self.notebook)
    self.notebook.add(reservations_frame, text=_t('gui.academics.library.reservations.tabs.reservations', default="Reservations"))

    # Control frame
    control_frame = ttk.Frame(reservations_frame)
    control_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(control_frame, text=_t('gui.academics.library.reservations.buttons.new_reservation', default="New Reservation"), command=self.new_reservation_dialog).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_frame, text=_t('gui.academics.library.reservations.buttons.cancel_reservation', default="Cancel Reservation"), command=self.cancel_reservation).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_frame, text=_("common.refresh"), command=self.refresh_reservations).pack(side=tk.LEFT, padx=5)

    # Reservations table
    table_frame = ttk.Frame(reservations_frame)
    table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    columns = ('ID', 'Book ID', 'Title', 'User', 'Date', 'Expires', 'Position', 'Status')
    self.reservations_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

    for col in columns:
        self.reservations_tree.heading(col, text=col)
        self.reservations_tree.column(col, width=100)

    # Add scrollbar
    scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.reservations_tree.yview)
    self.reservations_tree.configure(yscrollcommand=scrollbar.set)

    self.reservations_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Right-click: jump to student record / email / course.
    try:
        from education_system.systems.university.domains.library.interfaces.gui.library import _cross_links
        _cross_links.attach_cross_link_menu(
            self.reservations_tree,
            _cross_links.reservations_menu_items,
            parent=self.master,
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Could not attach cross-link menu to reservations_tree")
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Load reservations
    self.load_reservations()

def load_reservations(self):
    """Load reservations data"""
    # Clear existing data
    for item in self.reservations_tree.get_children():
        self.reservations_tree.delete(item)

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('''
            SELECT br.reservation_id, br.book_id, b.title, br.user_id,
                   br.reservation_date, br.expiry_date, br.priority_order, br.status
            FROM book_reservations br
            JOIN books b ON br.book_id = b.book_id
            WHERE br.status = 'active'
            ORDER BY br.book_id, br.priority_order
            ''')

            reservations = cursor.fetchall()
            conn.close()

            for reservation in reservations:
                # Format dates
                formatted_reservation = list(reservation)
                formatted_reservation[4] = reservation[4][:10]  # reservation_date
                formatted_reservation[5] = reservation[5][:10]  # expiry_date
                self.reservations_tree.insert('', 'end', values=formatted_reservation)

    except (sqlite3.Error, DatabaseError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), f"Error loading reservations: {str(e)}")

def refresh_reservations(self):
    """Refresh reservations table"""
    self.load_reservations()

def new_reservation_dialog(self):
    """Create new reservation dialog with book dropdown and auto-filled user"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_("library.dialogs.new_reservation"))
    dialog.geometry("500x300")
    dialog.transient(self.master)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Book selection dropdown
    ttk.Label(main_frame, text=_t('gui.academics.library.reservations.labels.select_book', default="Select Book:")).pack(anchor='w', pady=5)
    book_var = tk.StringVar()
    book_combo = ttk.Combobox(main_frame, textvariable=book_var, width=55, state='readonly')
    book_combo.pack(anchor='w', pady=5)

    # Load books
    book_map = {}
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT book_id, title, author, status FROM books ORDER BY title")
            books = cursor.fetchall()
            conn.close()
            book_list = []
            for bid, title, author, status in books:
                display = f"{bid} - {title[:35]} ({author[:20]}) [{status}]"
                book_list.append(display)
                book_map[display] = bid
            book_combo['values'] = book_list
    except Exception:
        logger.debug("Suppressed exception", exc_info=True)

    # User ID — auto-fill from current user
    ttk.Label(main_frame, text=_t('gui.academics.library.reservations.labels.user_id', default="User ID:")).pack(anchor='w', pady=5)
    user_id_var = tk.StringVar()
    if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
        user_id_var.set(self.auth.current_user.get('username', ''))
    ttk.Entry(main_frame, textvariable=user_id_var, width=30).pack(anchor='w', pady=5)

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=20)

    def create_reservation():
        selected = book_var.get()
        book_id = book_map.get(selected, selected.split(' - ')[0] if selected else '').strip()
        user_id = user_id_var.get().strip()

        if not book_id or not user_id:
            messagebox.showwarning(_("common.warning"), _t('gui.academics.library.reservations.dialogs.please_select_a_book_and_enter_a_user_id', default="Please select a book and enter a User ID"))
            return

        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                success = self.create_reservation_database(book_id, user_id)
                if success:
                    # Email user about reservation
                    self._send_reservation_email(user_id, book_id, 'created')
                    messagebox.showinfo(_("common.success"), _t('gui.academics.library.reservations.dialogs.reservation_created_successfully', default="Reservation created successfully!"))
                    dialog.destroy()
                    self.refresh_reservations()
                else:
                    messagebox.showerror(_("common.error"), _t('gui.academics.library.reservations.dialogs.failed_to_create_reservation', default="Failed to create reservation"))
            else:
                messagebox.showinfo(_("common.demo"), f"Reservation created for book {book_id} by user {user_id}")
                dialog.destroy()
        except tk.TclError as e:
            messagebox.showerror(_("common.error"), f"Error creating reservation: {str(e)}")

    ttk.Button(button_frame, text=_t('gui.academics.library.reservations.buttons.create_reservation', default="Create Reservation"), command=create_reservation).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

def _run_holds(fn, *args, **kwargs):
    """Run a ``library_circulation`` hold rule in its own transaction and send
    the notices it returns (recall to the current borrower, ready-to-collect)."""
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
    emails = result.get("emails") if isinstance(result, dict) else result
    if emails:
        timetable_occurrences.send_emails(emails)
    return result


def create_reservation_database(self, book_id, user_id):
    """Place a hold: queued, or straight onto the holds shelf when a copy is
    in; a hold with no copy in recalls the loan held longest."""
    from education_system.systems.university.application.library import circulation as circ
    try:
        result = _run_holds(circ.place_hold, book_id, user_id)
    except ValueError as exc:
        messagebox.showwarning(_("common.warning"), str(exc))
        return False
    if ORIGINAL_LIBRARY_AVAILABLE:
        log_audit_event(get_current_user_id(),
                        f"GUI: Created reservation {result['reservation_id']} for book {book_id}",
                        "book_reservations")
    return True

def cancel_reservation(self):
    """Cancel selected reservation"""
    selection = self.reservations_tree.selection()
    if not selection:
        messagebox.showwarning(_("common.warning"), _t('gui.academics.library.reservations.dialogs.please_select_a_reservation_to_cancel', default="Please select a reservation to cancel"))
        return

    item = self.reservations_tree.item(selection[0])
    reservation_id = item['values'][0]
    book_title = item['values'][2]
    user_id = item['values'][3]

    result = messagebox.askyesno(_t('gui.academics.library.reservations.dialogs.confirm', default="Confirm"), f"Cancel reservation for '{book_title}' by {user_id}?")

    if result:
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                from education_system.systems.university.application.library import (
                    circulation as circ,
                )
                try:
                    _run_holds(circ.cancel_hold, reservation_id)
                except ValueError as exc:
                    messagebox.showwarning(_("common.warning"), str(exc))
                    return

                # Log the action
                log_audit_event(get_current_user_id(),
                              f"GUI: Cancelled reservation {reservation_id}",
                              "book_reservations")

                # Email user about cancellation
                self._send_reservation_email(user_id, item['values'][1], 'cancelled')

                messagebox.showinfo(_("common.success"), _t('gui.academics.library.reservations.dialogs.reservation_cancelled_successfully', default="Reservation cancelled successfully!"))
                self.refresh_reservations()
            else:
                messagebox.showinfo(_("common.demo"), _t('gui.academics.library.reservations.dialogs.reservation_cancelled_variant_2', default="Reservation cancelled!"))
                self.refresh_reservations()

        except tk.TclError as e:
            messagebox.showerror(_("common.error"), f"Error cancelling reservation: {str(e)}")

def reserve_selected_book(self):
    """Quick reserve from context menu"""
    selection = self.books_tree.selection()
    if not selection:
        messagebox.showwarning(_("common.warning"), _("library.messages.please_select_book"))
        return

    item = self.books_tree.item(selection[0])
    book_id = item['values'][0]

    # Create quick reservation dialog
    dialog = tk.Toplevel(self.master)
    dialog.title(_("library.dialogs.quick_reservation"))
    dialog.geometry("400x200")
    dialog.transient(self.master)

    ttk.Label(dialog, text=f"Reserve Book: {book_id}", font=('Arial', 12, 'bold')).pack(pady=10)
    ttk.Label(dialog, text=f"Title: {item['values'][1]}").pack(pady=5)

    ttk.Label(dialog, text=_t('gui.academics.library.reservations.labels.user_id_or_email', default="User ID or Email:")).pack(pady=10)
    user_var = tk.StringVar()
    user_entry = ttk.Entry(dialog, textvariable=user_var, width=30)
    user_entry.pack(pady=5)
    user_entry.focus()

    def process_quick_reservation():
        try:
            user_id = user_var.get().strip()
            if not user_id:
                messagebox.showwarning(_("common.warning"), _t('gui.academics.library.reservations.dialogs.please_enter_a_user_id', default="Please enter a user ID"))
                return

            # A student by ID or email; anyone else by username.
            conn = get_db_connection()
            row = conn.execute(
                'SELECT student_id FROM students WHERE student_id = ? OR email_address = ?',
                (user_id, user_id)).fetchone()
            conn.close()
            if not self.create_reservation_database(book_id, row[0] if row else user_id):
                return
            messagebox.showinfo(_("common.success"), _t('gui.academics.library.reservations.dialogs.book_reserved_successfully', default="Book reserved successfully!"))
            dialog.destroy()

        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Reservation failed: {str(e)}")

    ttk.Button(dialog, text=_t('gui.academics.library.reservations.buttons.reserve', default="Reserve"), command=process_quick_reservation).pack(pady=10)
    ttk.Button(dialog, text=_("common.cancel"), command=dialog.destroy).pack(pady=5)

def reserve_book_gui(self, book_id=None):
    """Reserve a book that's currently unavailable"""
    reserve_window = tk.Toplevel(self.master)
    reserve_window.title(_t('gui.academics.library.reservations.windows.reserve_book', default="Reserve Book"))
    reserve_window.geometry("500x400")

    ttk.Label(reserve_window, text=_t('gui.academics.library.reservations.labels.reserve_book', default="Reserve Book"),
             font=('Arial', 16, 'bold')).pack(pady=10)

    # Book info frame
    book_frame = ttk.LabelFrame(reserve_window, text=_("library.frames.book_information"), padding=15)
    book_frame.pack(fill=tk.X, padx=10, pady=10)

    book_id_var = tk.StringVar(value=book_id or "")
    user_id_var = tk.StringVar()
    book_info_var = tk.StringVar(value=_t('gui.academics.library.reservations.values.no_book_selected', default="No book selected"))

    ttk.Label(book_frame, text=_t('gui.academics.library.reservations.labels.book_id', default="Book ID:")).grid(row=0, column=0, sticky=tk.W, pady=5)
    ttk.Entry(book_frame, textvariable=book_id_var, width=30).grid(row=0, column=1, padx=10, pady=5)

    def lookup_book():
        bid = book_id_var.get().strip()
        if not bid:
            messagebox.showwarning(_("common.warning"), _t('gui.academics.library.reservations.dialogs.please_enter_a_book_id', default="Please enter a Book ID"))
            return

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT title, author, status FROM books WHERE book_id = ?', (bid,))
            book = cursor.fetchone()

            if book:
                title, author, status = book
                book_info_var.set(f"{title} by {author}\nStatus: {status}")

                if status == 'available':
                    messagebox.showinfo(_t('gui.academics.library.reservations.dialogs.available', default="Available"),
                        _t('gui.academics.library.reservations.dialogs.this_book_is_currently_available_you_can_check_it_out_directly_i', default="This book is currently available. You can check it out directly instead of reserving it."))
            else:
                book_info_var.set("Book not found")
                messagebox.showerror(_("common.error"), _t('gui.academics.library.reservations.dialogs.book_not_found', default="Book not found"))

            conn.close()
        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Failed to lookup book: {str(e)}")

    ttk.Button(book_frame, text=_t('gui.academics.library.reservations.buttons.lookup', default="Lookup"), command=lookup_book).grid(row=0, column=2, padx=5)

    ttk.Label(book_frame, textvariable=book_info_var, foreground='blue').grid(
        row=1, column=0, columnspan=3, pady=10, sticky=tk.W)

    # User frame
    user_frame = ttk.LabelFrame(reserve_window, text=_("library.frames.user_information"), padding=15)
    user_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Label(user_frame, text=_t('gui.academics.library.reservations.labels.user_student_id', default="User/Student ID:")).grid(row=0, column=0, sticky=tk.W, pady=5)
    ttk.Entry(user_frame, textvariable=user_id_var, width=30).grid(row=0, column=1, padx=10, pady=5)

    def perform_reservation():
        bid = book_id_var.get().strip()
        uid = user_id_var.get().strip()

        if not bid or not uid:
            messagebox.showerror(_("common.error"), _t('gui.academics.library.reservations.dialogs.please_provide_both_book_id_and_user_id', default="Please provide both Book ID and User ID"))
            return

        from education_system.systems.university.application.library import circulation as circ
        try:
            result = _run_holds(circ.place_hold, bid, uid)
        except ValueError as exc:
            messagebox.showerror(_("common.error"), str(exc))
            return
        log_audit_event(get_current_user_id(), f"Reserved book {bid} for {uid}", "book_reservations")
        messagebox.showinfo(_("common.success"),
            ("A copy is in: it is on the holds shelf for them now." if result["ready"] else
             f"Request placed — #{result['position']} in the queue. The longest-held loan "
             "has been recalled if it could be."))
        reserve_window.destroy()

    # Button frame
    button_frame = ttk.Frame(reserve_window)
    button_frame.pack(fill=tk.X, padx=10, pady=20)

    ttk.Button(button_frame, text=_t('gui.academics.library.reservations.buttons.reserve', default="Reserve"), command=perform_reservation).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.cancel"), command=reserve_window.destroy).pack(side=tk.LEFT, padx=5)

def manage_reservations_gui(self):
    """Manage all book reservations"""
    manage_window = tk.Toplevel(self.master)
    manage_window.title(_t('gui.academics.library.reservations.windows.manage_reservations', default="Manage Reservations"))
    manage_window.geometry("900x600")

    ttk.Label(manage_window, text=_t('gui.academics.library.reservations.labels.manage_book_reservations', default="Manage Book Reservations"),
             font=('Arial', 16, 'bold')).pack(pady=10)

    # Filter frame
    filter_frame = ttk.LabelFrame(manage_window, text=_t('gui.academics.library.reservations.labels.filter', default="Filter"), padding=10)
    filter_frame.pack(fill=tk.X, padx=10, pady=10)

    status_filter = tk.StringVar(value=_t('gui.academics.library.reservations.values.active', default="active"))
    ttk.Label(filter_frame, text=_t('gui.academics.library.reservations.labels.status', default="Status:")).pack(side=tk.LEFT, padx=5)
    ttk.Combobox(filter_frame, textvariable=status_filter,
                values=["all", "active", "fulfilled", "expired", "cancelled"],
                width=15).pack(side=tk.LEFT, padx=5)

    # Reservations table
    table_frame = ttk.Frame(manage_window)
    table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    columns = ('ID', 'Book ID', 'Title', 'User', 'Reserved', 'Expires', 'Priority', 'Status')
    res_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

    for col in columns:
        res_tree.heading(col, text=col)
        res_tree.column(col, width=100)

    scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=res_tree.yview)
    res_tree.configure(yscrollcommand=scrollbar.set)

    res_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def load_reservations():
        for item in res_tree.get_children():
            res_tree.delete(item)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            status = status_filter.get()
            if status == "all":
                query = '''
                SELECT r.reservation_id, r.book_id, b.title, r.user_id,
                       r.reservation_date, r.expiry_date, r.priority_order, r.status
                FROM book_reservations r
                JOIN books b ON r.book_id = b.book_id
                ORDER BY r.priority_order
                '''
                cursor.execute(query)
            else:
                query = '''
                SELECT r.reservation_id, r.book_id, b.title, r.user_id,
                       r.reservation_date, r.expiry_date, r.priority_order, r.status
                FROM book_reservations r
                JOIN books b ON r.book_id = b.book_id
                WHERE r.status = ?
                ORDER BY r.priority_order
                '''
                cursor.execute(query, (status,))

            for row in cursor.fetchall():
                res_tree.insert('', 'end', values=(
                    row[0], row[1], row[2][:30], row[3], row[4][:10], row[5][:10], row[6], row[7]
                ))

            conn.close()

        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Failed to load reservations: {str(e)}")

    ttk.Button(filter_frame, text=_("common.refresh"), command=load_reservations).pack(side=tk.LEFT, padx=5)

    def cancel_reservation():
        selection = res_tree.selection()
        if not selection:
            messagebox.showwarning(_("common.warning"), _t('gui.academics.library.reservations.dialogs.please_select_a_reservation_to_cancel', default="Please select a reservation to cancel"))
            return

        item = res_tree.item(selection[0])
        res_id = item['values'][0]

        if messagebox.askyesno(_t('gui.academics.library.reservations.dialogs.confirm', default="Confirm"), _t('gui.academics.library.reservations.dialogs.cancel_this_reservation', default="Cancel this reservation?")):
            try:
                from education_system.systems.university.application.library import (
                    circulation as circ,
                )
                _run_holds(circ.cancel_hold, res_id)

                log_audit_event(get_current_user_id(), f"Cancelled reservation {res_id}", "book_reservations")
                messagebox.showinfo(_("common.success"), _t('gui.academics.library.reservations.dialogs.reservation_cancelled', default="Reservation cancelled"))
                load_reservations()

            except (sqlite3.Error, DatabaseError, tk.TclError, ValueError) as e:
                messagebox.showerror(_("common.error"), f"Failed to cancel: {str(e)}")

    # Button frame
    button_frame = ttk.Frame(manage_window)
    button_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(button_frame, text=_t('gui.academics.library.reservations.buttons.cancel_selected', default="Cancel Selected"), command=cancel_reservation).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.close"), command=manage_window.destroy).pack(side=tk.RIGHT, padx=5)

    # Load initial data
    load_reservations()


def _send_reservation_email(self, user_id, book_id_or_title, action):
    """Email user about reservation status (created/cancelled/available)."""
    try:
        from education_system.systems.university.infrastructure.email.email_service import send_email

        conn = get_db_connection()
        if not conn:
            return
        cursor = conn.cursor()

        # Get user email
        email = None
        name = user_id
        cursor.execute("SELECT first_name, email_address FROM students WHERE student_id = ?", (user_id,))
        row = cursor.fetchone()
        if row and row[1]:
            name, email = row[0], row[1]
        else:
            cursor.execute("SELECT first_name, email FROM users WHERE username = ? OR id = ?", (user_id, user_id))
            row = cursor.fetchone()
            if row and row[1]:
                name, email = row[0], row[1]

        # Get book title if we have a book_id
        book_title = book_id_or_title
        cursor.execute("SELECT title FROM books WHERE book_id = ?", (book_id_or_title,))
        title_row = cursor.fetchone()
        if title_row:
            book_title = title_row[0]

        conn.close()

        if not email:
            return

        if action == 'created':
            subject = f"Book Reserved: {book_title}"
            body = (
                f"Dear {name},\n\n"
                f"Your reservation has been created:\n\n"
                f"Book: {book_title}\n\n"
                f"You will be notified when the book becomes available.\n\n"
                f"Best regards,\nLibrary Services"
            )
        elif action == 'cancelled':
            subject = f"Reservation Cancelled: {book_title}"
            body = (
                f"Dear {name},\n\n"
                f"Your reservation for the following book has been cancelled:\n\n"
                f"Book: {book_title}\n\n"
                f"If this was done in error, please contact the library.\n\n"
                f"Best regards,\nLibrary Services"
            )
        elif action == 'available':
            subject = f"Book Now Available: {book_title}"
            body = (
                f"Dear {name},\n\n"
                f"The book you reserved is now available for checkout:\n\n"
                f"Book: {book_title}\n\n"
                f"Please visit the library to check out the book before your reservation expires.\n\n"
                f"Best regards,\nLibrary Services"
            )
        else:
            return

        send_email(recipient_email=email, subject=subject, body=body)

    except Exception as e:
        import logging
        logging.warning(f"Reservation email failed: {e}")


def notify_reserved_users_on_return(self, book_id):
    """When a book is returned, email users who have active reservations for it."""
    try:
        conn = get_db_connection()
        if not conn:
            return
        cursor = conn.cursor()

        cursor.execute('''
            SELECT user_id FROM book_reservations
            WHERE book_id = ? AND status = 'active'
            ORDER BY priority_order ASC
        ''', (book_id,))
        reserved_users = cursor.fetchall()
        conn.close()

        for (uid,) in reserved_users:
            self._send_reservation_email(uid, book_id, 'available')

    except Exception as e:
        import logging
        logging.warning(f"Failed to notify reserved users: {e}")

