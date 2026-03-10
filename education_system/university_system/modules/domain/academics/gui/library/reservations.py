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

def show_reservations(self):
    """Show reservations management"""
    # Check permission instead of user directly
    if not self.check_permission('manage_reservations'):
        return

    self.clear_content_area()

    reservations_frame = ttk.Frame(self.notebook)
    self.notebook.add(reservations_frame, text="Reservations")

    # Control frame
    control_frame = ttk.Frame(reservations_frame)
    control_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(control_frame, text="New Reservation", command=self.new_reservation_dialog).pack(side=tk.LEFT, padx=5)
    ttk.Button(control_frame, text="Cancel Reservation", command=self.cancel_reservation).pack(side=tk.LEFT, padx=5)
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
    """Create new reservation dialog"""
    dialog = tk.Toplevel(self.master)
    dialog.title(_("library.dialogs.new_reservation"))
    dialog.geometry("400x300")
    dialog.transient(self.master)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Book selection
    ttk.Label(main_frame, text="Book ID:").pack(anchor='w', pady=5)
    book_id_var = tk.StringVar()
    ttk.Entry(main_frame, textvariable=book_id_var, width=30).pack(anchor='w', pady=5)

    # User selection
    ttk.Label(main_frame, text="User ID:").pack(anchor='w', pady=5)
    user_id_var = tk.StringVar()
    ttk.Entry(main_frame, textvariable=user_id_var, width=30).pack(anchor='w', pady=5)

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=20)

    def create_reservation():
        book_id = book_id_var.get().strip()
        user_id = user_id_var.get().strip()

        if not book_id or not user_id:
            messagebox.showwarning(_("common.warning"), "Please enter both Book ID and User ID")
            return

        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                success = self.create_reservation_database(book_id, user_id)
                if success:
                    messagebox.showinfo(_("common.success"), "Reservation created successfully!")
                    dialog.destroy()
                    self.refresh_reservations()
                else:
                    messagebox.showerror(_("common.error"), "Failed to create reservation")
            else:
                messagebox.showinfo(_("common.demo"), f"Reservation created for book {book_id} by user {user_id}")
                dialog.destroy()
        except tk.TclError as e:
            messagebox.showerror(_("common.error"), f"Error creating reservation: {str(e)}")

    ttk.Button(button_frame, text="Create", command=create_reservation).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

def create_reservation_database(self, book_id, user_id):
    """Create reservation in database"""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Check if book exists
        cursor.execute('SELECT title, status FROM books WHERE book_id = ?', (book_id,))
        book = cursor.fetchone()

        if not book:
            messagebox.showerror(_("common.error"), "Book not found")
            return False

        title, status = book

        # Check if user already has reservation
        cursor.execute('''
        SELECT reservation_id FROM book_reservations 
        WHERE book_id = ? AND user_id = ? AND status = 'active'
        ''', (book_id, user_id))

        if cursor.fetchone():
            messagebox.showwarning(_("common.warning"), "User already has a reservation for this book")
            return False

        # Get next priority order
        cursor.execute('''
        SELECT COALESCE(MAX(priority_order), 0) + 1 
        FROM book_reservations 
        WHERE book_id = ? AND status = 'active'
        ''', (book_id,))

        priority_order = cursor.fetchone()[0]

        # Get reservation period
        reservation_days = 3  # Default
        try:
            cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "reservation_period_days"')
            setting = cursor.fetchone()
            if setting:
                reservation_days = int(setting[0])
        except (sqlite3.Error, DatabaseError, ValueError, TypeError):
            pass

        # Create reservation
        reservation_date = datetime.now()
        expiry_date = reservation_date + timedelta(days=reservation_days)

        cursor.execute('''
        INSERT INTO book_reservations 
        (book_id, user_id, reservation_date, expiry_date, status, priority_order)
        VALUES (?, ?, ?, ?, 'active', ?)
        ''', (
            book_id, user_id,
            reservation_date.strftime('%Y-%m-%d %H:%M:%S'),
            expiry_date.strftime('%Y-%m-%d %H:%M:%S'),
            priority_order
        ))

        conn.commit()
        conn.close()

        # Log the action
        if ORIGINAL_LIBRARY_AVAILABLE:
            log_audit_event(get_current_user_id(), 
                          f"GUI: Created reservation for book {book_id}", 
                          "book_reservations")

        return True

    except (sqlite3.Error, DatabaseError) as e:
        print(f"Error creating reservation: {e}")
        return False

def cancel_reservation(self):
    """Cancel selected reservation"""
    selection = self.reservations_tree.selection()
    if not selection:
        messagebox.showwarning(_("common.warning"), "Please select a reservation to cancel")
        return

    item = self.reservations_tree.item(selection[0])
    reservation_id = item['values'][0]
    book_title = item['values'][2]
    user_id = item['values'][3]

    result = messagebox.askyesno("Confirm", f"Cancel reservation for '{book_title}' by {user_id}?")

    if result:
        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('UPDATE book_reservations SET status = "cancelled" WHERE reservation_id = ?', 
                                 (reservation_id,))
                    conn.commit()
                    conn.close()

                    # Log the action
                    log_audit_event(get_current_user_id(), 
                                  f"GUI: Cancelled reservation {reservation_id}", 
                                  "book_reservations")

                    messagebox.showinfo(_("common.success"), "Reservation cancelled successfully!")
                    self.refresh_reservations()
            else:
                messagebox.showinfo(_("common.demo"), "Reservation cancelled!")
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

    ttk.Label(dialog, text="User ID or Email:").pack(pady=10)
    user_var = tk.StringVar()
    user_entry = ttk.Entry(dialog, textvariable=user_var, width=30)
    user_entry.pack(pady=5)
    user_entry.focus()

    def process_quick_reservation():
        try:
            user_id = user_var.get().strip()
            if not user_id:
                messagebox.showwarning(_("common.warning"), "Please enter a user ID")
                return

            # Verify user exists
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT student_id FROM students
                WHERE student_id = ? OR email_address LIKE ?
            ''', (user_id, f"%{user_id}%"))

            user = cursor.fetchone()
            if not user:
                messagebox.showerror(_("common.error"), "User not found")
                conn.close()
                return

            actual_user_id = user[0]

            # Check if already reserved
            cursor.execute('''
                SELECT COUNT(*) FROM reservations
                WHERE book_id = ? AND user_id = ? AND status = 'active'
            ''', (book_id, actual_user_id))

            if cursor.fetchone()[0] > 0:
                messagebox.showwarning(_("common.warning"), "This book is already reserved by this user")
                conn.close()
                return

            # Create reservation
            reservation_date = datetime.now().strftime('%Y-%m-%d')

            cursor.execute('''
                INSERT INTO reservations (book_id, user_id, reservation_date, status)
                VALUES (?, ?, ?, 'active')
            ''', (book_id, actual_user_id, reservation_date))

            conn.commit()
            conn.close()

            messagebox.showinfo(_("common.success"), "Book reserved successfully!")
            dialog.destroy()

        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Reservation failed: {str(e)}")

    ttk.Button(dialog, text="Reserve", command=process_quick_reservation).pack(pady=10)
    ttk.Button(dialog, text=_("common.cancel"), command=dialog.destroy).pack(pady=5)

def reserve_book_gui(self, book_id=None):
    """Reserve a book that's currently unavailable"""
    reserve_window = tk.Toplevel(self.master)
    reserve_window.title("Reserve Book")
    reserve_window.geometry("500x400")

    ttk.Label(reserve_window, text="Reserve Book",
             font=('Arial', 16, 'bold')).pack(pady=10)

    # Book info frame
    book_frame = ttk.LabelFrame(reserve_window, text=_("library.frames.book_information"), padding=15)
    book_frame.pack(fill=tk.X, padx=10, pady=10)

    book_id_var = tk.StringVar(value=book_id or "")
    user_id_var = tk.StringVar()
    book_info_var = tk.StringVar(value="No book selected")

    ttk.Label(book_frame, text="Book ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
    ttk.Entry(book_frame, textvariable=book_id_var, width=30).grid(row=0, column=1, padx=10, pady=5)

    def lookup_book():
        bid = book_id_var.get().strip()
        if not bid:
            messagebox.showwarning(_("common.warning"), "Please enter a Book ID")
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
                    messagebox.showinfo("Available",
                        "This book is currently available. You can check it out directly instead of reserving it.")
            else:
                book_info_var.set("Book not found")
                messagebox.showerror(_("common.error"), "Book not found")

            conn.close()
        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Failed to lookup book: {str(e)}")

    ttk.Button(book_frame, text="Lookup", command=lookup_book).grid(row=0, column=2, padx=5)

    ttk.Label(book_frame, textvariable=book_info_var, foreground='blue').grid(
        row=1, column=0, columnspan=3, pady=10, sticky=tk.W)

    # User frame
    user_frame = ttk.LabelFrame(reserve_window, text=_("library.frames.user_information"), padding=15)
    user_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Label(user_frame, text="User/Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
    ttk.Entry(user_frame, textvariable=user_id_var, width=30).grid(row=0, column=1, padx=10, pady=5)

    def perform_reservation():
        bid = book_id_var.get().strip()
        uid = user_id_var.get().strip()

        if not bid or not uid:
            messagebox.showerror(_("common.error"), "Please provide both Book ID and User ID")
            return

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if book exists
            cursor.execute('SELECT title, status FROM books WHERE book_id = ?', (bid,))
            book = cursor.fetchone()

            if not book:
                messagebox.showerror(_("common.error"), "Book not found")
                conn.close()
                return

            title, status = book

            # Check if user already has a reservation
            cursor.execute('''
            SELECT reservation_id FROM book_reservations
            WHERE book_id = ? AND user_id = ? AND status = 'active'
            ''', (bid, uid))

            if cursor.fetchone():
                messagebox.showerror(_("common.error"), "User already has an active reservation for this book")
                conn.close()
                return

            # Get next priority order
            cursor.execute('''
            SELECT COALESCE(MAX(priority_order), 0) + 1
            FROM book_reservations
            WHERE book_id = ? AND status = 'active'
            ''', (bid,))
            priority_order = cursor.fetchone()[0]

            # Get reservation period
            cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "reservation_period_days"')
            reservation_period_result = cursor.fetchone()
            reservation_period = int(reservation_period_result[0]) if reservation_period_result else 3

            # Create reservation
            reservation_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            expiry_date = (datetime.now() + timedelta(days=reservation_period)).strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            INSERT INTO book_reservations (
                book_id, user_id, reservation_date, expiry_date, status, priority_order
            ) VALUES (?, ?, ?, ?, 'active', ?)
            ''', (bid, uid, reservation_date, expiry_date, priority_order))

            conn.commit()
            conn.close()

            log_audit_event(get_current_user_id(), f"Reserved book {bid} for {uid}", "book_reservations")

            messagebox.showinfo(_("common.success"),
                f"Book reserved successfully!\n\n" +
                f"Title: {title}\n" +
                f"User: {uid}\n" +
                f"Priority: #{priority_order}\n" +
                f"Expires: {expiry_date[:10]}")

            reserve_window.destroy()

        except tk.TclError as e:
            messagebox.showerror(_("common.error"), f"Reservation failed: {str(e)}")

    # Button frame
    button_frame = ttk.Frame(reserve_window)
    button_frame.pack(fill=tk.X, padx=10, pady=20)

    ttk.Button(button_frame, text="Reserve", command=perform_reservation).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.cancel"), command=reserve_window.destroy).pack(side=tk.LEFT, padx=5)

def manage_reservations_gui(self):
    """Manage all book reservations"""
    manage_window = tk.Toplevel(self.master)
    manage_window.title("Manage Reservations")
    manage_window.geometry("900x600")

    ttk.Label(manage_window, text="Manage Book Reservations",
             font=('Arial', 16, 'bold')).pack(pady=10)

    # Filter frame
    filter_frame = ttk.LabelFrame(manage_window, text="Filter", padding=10)
    filter_frame.pack(fill=tk.X, padx=10, pady=10)

    status_filter = tk.StringVar(value="active")
    ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT, padx=5)
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
            messagebox.showwarning(_("common.warning"), "Please select a reservation to cancel")
            return

        item = res_tree.item(selection[0])
        res_id = item['values'][0]

        if messagebox.askyesno("Confirm", "Cancel this reservation?"):
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('UPDATE book_reservations SET status = "cancelled" WHERE reservation_id = ?', (res_id,))
                conn.commit()
                conn.close()

                log_audit_event(get_current_user_id(), f"Cancelled reservation {res_id}", "book_reservations")
                messagebox.showinfo(_("common.success"), "Reservation cancelled")
                load_reservations()

            except (sqlite3.Error, DatabaseError, tk.TclError) as e:
                messagebox.showerror(_("common.error"), f"Failed to cancel: {str(e)}")

    # Button frame
    button_frame = ttk.Frame(manage_window)
    button_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(button_frame, text="Cancel Selected", command=cancel_reservation).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.close"), command=manage_window.destroy).pack(side=tk.RIGHT, padx=5)

    # Load initial data
    load_reservations()

