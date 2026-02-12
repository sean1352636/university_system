"""
Enhanced Library Management System - GUI Version
Maintains all original CLI functions while adding a modern GUI interface
Backwards compatible with existing database and auth systems
"""


from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()
from tkinter.scrolledtext import ScrolledText
import threading
import queue
import os
import sys
from datetime import datetime, timedelta
import json
from university_system.infrastructure.database.db import sqlite3
from typing import Dict, List, Optional, Any
import logging
import urllib.request
import urllib.parse
import urllib.error

# Import custom exceptions for better error handling
from university_system.infrastructure.exceptions import (
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
    from university_system.modules.domain.academics.services.library.settings import (
        auth, get_current_user_id, set_auth, get_library_settings, update_library_setting
    )
    from university_system.modules.domain.academics.services.library.menu import display_library_menu
    from university_system.modules.domain.academics.services.library.barcode import (
        generate_barcode, generate_qr_code, process_scanned_barcode
    )
    from university_system.modules.domain.academics.services.library.reports import (
        generate_circulation_report, generate_library_statistics_export, generate_user_activity_report
    )
    from university_system.modules.domain.academics.services.library.database import (
        get_db_connection, init_library_db, log_audit_event
    )
    from university_system.modules.domain.academics.services.library.backup import (
        quick_system_health_check, restore_from_backup
    )
    from university_system.modules.domain.academics.services.library.reading_lists import view_reading_list_details
    ORIGINAL_LIBRARY_AVAILABLE = True
except ImportError:
    print("Warning: Original library module not found. GUI will use standalone functions.")
    ORIGINAL_LIBRARY_AVAILABLE = False

# Import shared authentication system
try:
    from university_system.infrastructure.auth import UserAuth
    from university_system.infrastructure.shared_context import get_auth, get_current_user
    SHARED_AUTH_AVAILABLE = True
except ImportError:
    print("Warning: Shared authentication system not found.")
    SHARED_AUTH_AVAILABLE = False
    # Provide fallback functions
    def get_auth():
        return None
    def get_current_user():
        return None

from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import finance integration for student finance account payments
try:
    from university_system.modules.shared.utils.finance_integration import (
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
    from university_system.infrastructure.email.email_service import send_email_as_system
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    def send_email_as_system(*args, **kwargs):
        return False
    print("Warning: Email service not available for library finance")

_AUDIT_LOG_COLUMNS_CACHE: Optional[List[str]] = None
_STUDENT_COLUMNS_CACHE: Optional[List[str]] = None

from .base import LibraryGUI

def show_fine_management(self):
    """Show fine management interface (basic - kept for backward compatibility)"""
    if not self.check_permission('manage_loans'):
        return

    dialog = tk.Toplevel(self.master)
    dialog.title(_("library.dialogs.fine_management"))
    dialog.geometry("700x500")
    dialog.transient(self.master)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    title_label = ttk.Label(main_frame, text="Fine Management System", style='Title.TLabel')
    title_label.pack(pady=(0, 10))

    # Search frame
    search_frame = ttk.LabelFrame(main_frame, text="Find User")
    search_frame.pack(fill=tk.X, pady=(0, 10))

    search_inner = ttk.Frame(search_frame)
    search_inner.pack(fill=tk.X, padx=5, pady=5)

    ttk.Label(search_inner, text="User ID:").pack(side=tk.LEFT)
    self.fine_user_var = tk.StringVar()
    ttk.Entry(search_inner, textvariable=self.fine_user_var, width=20).pack(side=tk.LEFT, padx=5)
    ttk.Button(search_inner, text=_("common.search"), command=self.load_user_fines).pack(side=tk.LEFT, padx=5)

    # User info frame
    info_frame = ttk.LabelFrame(main_frame, text=_("library.frames.user_information"))
    info_frame.pack(fill=tk.X, pady=(0, 10))

    self.user_info_text = tk.Text(info_frame, height=3, state=tk.DISABLED)
    self.user_info_text.pack(fill=tk.X, padx=5, pady=5)

    # Fines table
    fines_frame = ttk.LabelFrame(main_frame, text="Outstanding Fines")
    fines_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    columns = ('Loan ID', 'Book ID', 'Title', 'Days Overdue', 'Fine Amount')
    self.fines_tree = ttk.Treeview(fines_frame, columns=columns, show='headings', height=8)

    for col in columns:
        self.fines_tree.heading(col, text=col)
        self.fines_tree.column(col, width=100)

    fines_scrollbar = ttk.Scrollbar(fines_frame, orient=tk.VERTICAL, command=self.fines_tree.yview)
    self.fines_tree.configure(yscrollcommand=fines_scrollbar.set)

    self.fines_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
    fines_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

    # Payment frame
    payment_frame = ttk.LabelFrame(main_frame, text="Process Payment")
    payment_frame.pack(fill=tk.X)

    payment_inner = ttk.Frame(payment_frame)
    payment_inner.pack(fill=tk.X, padx=5, pady=5)

    ttk.Label(payment_inner, text="Payment Amount: £").pack(side=tk.LEFT)
    self.payment_amount_var = tk.StringVar()
    ttk.Entry(payment_inner, textvariable=self.payment_amount_var, width=10).pack(side=tk.LEFT, padx=5)
    ttk.Button(payment_inner, text="Process Payment", command=self.process_fine_payment).pack(side=tk.LEFT, padx=5)
    if FINANCE_ACCOUNT_AVAILABLE:
        ttk.Button(payment_inner, text="💰 Pay from Finance Account", command=self.pay_fine_from_finance_account).pack(side=tk.LEFT, padx=5)
    ttk.Button(payment_inner, text="💳 Pay via Finance System", command=self.pay_fine_via_finance).pack(side=tk.LEFT, padx=5)
    ttk.Button(payment_inner, text="Waive All Fines", command=self.waive_all_fines).pack(side=tk.LEFT, padx=5)
    ttk.Button(payment_inner, text="🔄 Refund Fine", command=self.refund_fine_dialog).pack(side=tk.LEFT, padx=5)

    ttk.Button(main_frame, text=_("common.close"), command=dialog.destroy).pack(pady=10)

def load_user_fines(self):
    """Load outstanding fines for a user"""
    user_id = self.fine_user_var.get().strip()

    if not user_id:
        messagebox.showwarning(_("common.warning"), "Please enter a User ID")
        return

    # Clear existing data
    for item in self.fines_tree.get_children():
        self.fines_tree.delete(item)

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()

                # Get user info
                student_columns = self._get_student_columns()
                grade_sql = ', grade_level' if 'grade_level' in student_columns else ''
                cursor.execute('SELECT first_name, last_name' + grade_sql + ' FROM students WHERE student_id = ?', (user_id,))
                user_info = cursor.fetchone()

                if user_info:
                    first_name, last_name = user_info[:2]
                    grade = user_info[2] if len(user_info) > 2 else 'N/A'
                    info_text = f"Name: {first_name} {last_name}\nGrade: {grade}\nUser ID: {user_id}"
                else:
                    info_text = f"User ID: {user_id}\nName: Not found in student records"

                # Add finance account balance info
                if FINANCE_ACCOUNT_AVAILABLE:
                    balance = get_student_finance_account_balance(user_id)
                    if balance is not None:
                        info_text += f"\n\n💰 Finance Account: £{balance:.2f}"
                    else:
                        info_text += f"\n\n💰 Finance Account: Not created"

                self.user_info_text.config(state=tk.NORMAL)
                self.user_info_text.delete("1.0", tk.END)
                self.user_info_text.insert("1.0", info_text)
                self.user_info_text.config(state=tk.DISABLED)

                # Get outstanding fines
                cursor.execute('''
                SELECT bl.loan_id, bl.book_id, b.title, 
                       julianday('now') - julianday(bl.due_date) as days_overdue,
                       bl.fine_amount
                FROM book_loans bl
                JOIN books b ON bl.book_id = b.book_id
                WHERE bl.user_id = ? AND bl.fine_amount > 0 AND bl.status != 'returned'
                ORDER BY bl.due_date
                ''', (user_id,))

                fines = cursor.fetchall()

                total_fines = 0
                for fine in fines:
                    loan_id, book_id, title, days_overdue, fine_amount = fine
                    total_fines += fine_amount

                    self.fines_tree.insert('', 'end', values=(
                        loan_id, book_id, title[:20], int(days_overdue), f"${fine_amount:.2f}"
                    ))

                # Update user info with total
                updated_info = info_text + f"\nTotal Outstanding Fines: ${total_fines:.2f}"
                self.user_info_text.config(state=tk.NORMAL)
                self.user_info_text.delete("1.0", tk.END)
                self.user_info_text.insert("1.0", updated_info)
                self.user_info_text.config(state=tk.DISABLED)

                conn.close()
        else:
            # Demo mode
            info_text = f"User ID: {user_id}\nName: Demo User\nTotal Fines: $5.00"
            self.user_info_text.config(state=tk.NORMAL)
            self.user_info_text.delete("1.0", tk.END)
            self.user_info_text.insert("1.0", info_text)
            self.user_info_text.config(state=tk.DISABLED)

            # Demo fine data
            self.fines_tree.insert('', 'end', values=(1, "B10001", "Demo Book", 5, "$5.00"))

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Error loading fines: {str(e)}")

    def refund_fine_dialog(self):
        """Show dialog to process a fine refund - with user selection"""
        print("\n" + "="*60)
        print("REFUND FINE DIALOG - Starting...")
        print("="*60)

        # Create refund dialog with user search
        refund_main_dialog = tk.Toplevel()
        refund_main_dialog.title("Refund Library Fines")
        refund_main_dialog.geometry("1000x750")
        refund_main_dialog.transient(self.master)
        refund_main_dialog.grab_set()

        print("Dialog window created")

        # Header
        header_frame = ttk.Frame(refund_main_dialog)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Library Fine Refund System",
         font=('Arial', 16, 'bold')).pack()
        ttk.Label(header_frame, text="Search for users with paid fines and process refunds",
         font=('Arial', 10)).pack()

        # User search section
        search_frame = ttk.LabelFrame(refund_main_dialog, text="Search for User", padding=10)
        search_frame.pack(fill=tk.X, padx=10, pady=10)

        search_row = ttk.Frame(search_frame)
        search_row.pack(fill=tk.X)

        ttk.Label(search_row, text="Student ID or Name:", font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_row, textvariable=search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)

        # Users list with paid fines
        users_frame = ttk.LabelFrame(refund_main_dialog, text="Users with Paid Fines", padding=10)
        users_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('User ID', 'Name', 'Email', 'Total Paid', 'Total Refunded', 'Available', 'Payments')
        users_tree = ttk.Treeview(users_frame, columns=columns, show='headings', height=12)

        for col in columns:
            users_tree.heading(col, text=col)
        users_tree.column('User ID', width=100, anchor='center')
        users_tree.column('Name', width=180)
        users_tree.column('Email', width=200)
        users_tree.column('Total Paid', width=100, anchor='e')
        users_tree.column('Total Refunded', width=110, anchor='e')
        users_tree.column('Available', width=100, anchor='e')
        users_tree.column('Payments', width=80, anchor='center')

        users_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        def load_users_with_paid_fines(search_term=""):
            """Load all users who have paid fines"""
            for item in users_tree.get_children():
                users_tree.delete(item)

            if not ORIGINAL_LIBRARY_AVAILABLE:
                print("ERROR: Library module not available")
                messagebox.showerror(_("common.error"), "Library database module is not available.\nPlease ensure all dependencies are installed.", parent=refund_main_dialog)
                return

            try:
                conn = get_db_connection()
                if not conn:
                    print("ERROR: Could not get database connection")
                    messagebox.showerror(_("common.error"), "Database connection failed", parent=refund_main_dialog)
                    return

                cursor = conn.cursor()

                print(f"Loading users with paid fines (search: '{search_term}')...")

                # Build search query
                if search_term:
                    cursor.execute('''
                        SELECT lfp.user_id,
                               s.first_name, s.last_name, s.email_address,
                               SUM(lfp.payment_amount) as total_paid,
                               SUM(COALESCE(lfp.refund_amount, 0)) as total_refunded,
                               COUNT(DISTINCT lfp.payment_id) as payment_count
                        FROM library_fine_payments lfp
                        JOIN students s ON lfp.user_id = s.student_id
                        WHERE lfp.status = 'completed'
                        AND (lfp.user_id LIKE ? OR s.first_name LIKE ? OR s.last_name LIKE ? OR s.email_address LIKE ?)
                        GROUP BY lfp.user_id, s.first_name, s.last_name, s.email_address
                        HAVING (total_paid - total_refunded) > 0
                        ORDER BY s.last_name, s.first_name
                    ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
                else:
                    cursor.execute('''
                        SELECT lfp.user_id,
                               s.first_name, s.last_name, s.email_address,
                               SUM(lfp.payment_amount) as total_paid,
                               SUM(COALESCE(lfp.refund_amount, 0)) as total_refunded,
                               COUNT(DISTINCT lfp.payment_id) as payment_count
                        FROM library_fine_payments lfp
                        JOIN students s ON lfp.user_id = s.student_id
                        WHERE lfp.status = 'completed'
                        GROUP BY lfp.user_id, s.first_name, s.last_name, s.email_address
                        HAVING (total_paid - total_refunded) > 0
                        ORDER BY s.last_name, s.first_name
                    ''')

                users = cursor.fetchall()
                conn.close()

                print(f"Query returned {len(users)} users")

                if not users:
                    print("WARNING: No users with paid fines found!")
                    messagebox.showinfo("No Data", "No users with paid fines found in the database.", parent=refund_main_dialog)
                    return

                for user_id, first_name, last_name, email, total_paid, total_refunded, payment_count in users:
                    full_name = f"{first_name} {last_name}"
                    available = total_paid - total_refunded
                    print(f"  Adding user: {user_id} - {full_name} - {payment_count} payments, £{available:.2f} available")
                    users_tree.insert('', 'end', values=(
                        user_id, full_name, email or 'N/A',
                        f"£{total_paid:.2f}", f"£{total_refunded:.2f}", f"£{available:.2f}",
                        payment_count
                    ))

                print(f"Successfully loaded {len(users)} users into tree")

            except Exception as e:
                print(f"EXCEPTION in load_users_with_paid_fines: {e}")
                import traceback
                traceback.print_exc()
                messagebox.showerror(_("common.error"), f"Failed to load users: {str(e)}", parent=refund_main_dialog)

        def search_users():
            search_term = search_var.get().strip()
            load_users_with_paid_fines(search_term)

        def show_user_refund_details():
            selection = users_tree.selection()
            if not selection:
                messagebox.showwarning(_("common.warning"), "Please select a user first", parent=refund_main_dialog)
                return

            user_id = users_tree.item(selection[0])['values'][0]
            refund_main_dialog.destroy()
            self._show_user_refund_details(user_id)

        ttk.Button(search_row, text="Search", command=search_users).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_row, text="Show All", command=lambda: load_users_with_paid_fines("")).pack(side=tk.LEFT, padx=5)

        # Buttons
        btn_frame = ttk.Frame(refund_main_dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(btn_frame, text="View Refund Details", command=show_user_refund_details,
          style='Accent.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("common.close"), command=refund_main_dialog.destroy).pack(side=tk.RIGHT, padx=5)

        # Load users on start
        print("About to load users with paid fines...")
        load_users_with_paid_fines()
        print("Finished initial load")
        search_entry.focus()

    def _show_user_refund_details(self, user_id):
        """Show refund details dialog for a specific user"""
        print(f"\n_show_user_refund_details called for user_id: {user_id}")
        print(f"ORIGINAL_LIBRARY_AVAILABLE: {ORIGINAL_LIBRARY_AVAILABLE}")

        try:
            if ORIGINAL_LIBRARY_AVAILABLE:
                print("Attempting to connect to database...")
                conn = get_db_connection()
                if not conn:
                    print("ERROR: Database connection failed")
                    messagebox.showerror(_("common.error"), "Database connection unavailable")
                    return

                cursor = conn.cursor()
                print("Database connection successful")

                # Get user's paid fines that can be refunded from library_fine_payments table
                print(f"Querying payments for user {user_id}...")
                cursor.execute('''
                    SELECT lfp.payment_id, lfp.loan_id, lfp.book_id, lfp.book_title,
                           lfp.payment_amount, lfp.payment_method, lfp.payment_date,
                           lfp.refund_amount
                    FROM library_fine_payments lfp
                    WHERE lfp.user_id = ?
                    AND lfp.status = 'completed'
                    AND (lfp.payment_amount - COALESCE(lfp.refund_amount, 0)) > 0
                    ORDER BY lfp.payment_date DESC
                ''', (user_id,))

                paid_fines = cursor.fetchall()
                print(f"Query returned {len(paid_fines)} refundable payments")

                # Get user name
                cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?', (user_id,))
                user_info = cursor.fetchone()
                user_name = f"{user_info[0]} {user_info[1]}" if user_info else user_id
                print(f"User name: {user_name}")

                conn.close()

                if not paid_fines:
                    print("WARNING: No refundable payments found for this user")
                    messagebox.showinfo("No Paid Fines", "This user has no paid fines available to refund")
                    return

                # Create refund dialog
                refund_dialog = tk.Toplevel()
                refund_dialog.title("Refund Library Fine")
                refund_dialog.geometry("900x700")
                refund_dialog.transient(self.master)
                refund_dialog.grab_set()

                # Header
                header_frame = ttk.Frame(refund_dialog)
                header_frame.pack(fill=tk.X, padx=10, pady=10)
                ttk.Label(header_frame, text="Refund Library Fine",
                         font=('Arial', 14, 'bold')).pack()
                ttk.Label(header_frame, text=f"User: {user_name} (ID: {user_id})",
                         font=('Arial', 11)).pack()

                # Paid fines selection
                selection_frame = ttk.LabelFrame(refund_dialog, text="Select Paid Fine to Refund", padding=10)
                selection_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

                columns = ('Payment ID', 'Loan ID', 'Book Title', 'Paid Amount', 'Refunded', 'Available', 'Method', 'Date')
                fines_tree = ttk.Treeview(selection_frame, columns=columns, show='headings', height=8)

                for col in columns:
                    fines_tree.heading(col, text=col)
                fines_tree.column('Payment ID', width=80, anchor='center')
                fines_tree.column('Loan ID', width=80, anchor='center')
                fines_tree.column('Book Title', width=200)
                fines_tree.column('Paid Amount', width=90, anchor='e')
                fines_tree.column('Refunded', width=80, anchor='e')
                fines_tree.column('Available', width=80, anchor='e')
                fines_tree.column('Method', width=120)
                fines_tree.column('Date', width=150, anchor='center')

                print(f"Populating tree with {len(paid_fines)} payments...")
                for payment_id, loan_id, book_id, book_title, payment_amount, payment_method, payment_date, refund_amount in paid_fines:
                    refund_amount = refund_amount or 0.0
                    available = payment_amount - refund_amount
                    print(f"  - Payment {payment_id}: £{available:.2f} available")
                    fines_tree.insert('', 'end', values=(
                        payment_id, loan_id, book_title[:30] if book_title else 'N/A',
                        f"£{payment_amount:.2f}", f"£{refund_amount:.2f}", f"£{available:.2f}",
                        payment_method, payment_date
                    ))

                fines_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
                print("Tree populated and packed successfully")

                # Refund details frame
                details_frame = ttk.LabelFrame(refund_dialog, text="Refund Details", padding=10)
                details_frame.pack(fill=tk.X, padx=10, pady=10)

                ttk.Label(details_frame, text="Refund Amount (£):").grid(row=0, column=0, sticky='w', pady=5)
                refund_amount_var = tk.StringVar()
                ttk.Entry(details_frame, textvariable=refund_amount_var, width=15).grid(row=0, column=1, sticky='w', pady=5)

                ttk.Label(details_frame, text="Refund Method:").grid(row=1, column=0, sticky='w', pady=5)
                refund_method_var = tk.StringVar(value="Cash")
                method_options = ["Cash", "Card", "Student Finance Account"]
                method_combo = ttk.Combobox(details_frame, textvariable=refund_method_var,
                                           values=method_options, state='readonly', width=22)
                method_combo.grid(row=1, column=1, sticky='w', pady=5)

                ttk.Label(details_frame, text="Refund Reason:").grid(row=2, column=0, sticky='w', pady=5)
                reason_text = tk.Text(details_frame, height=3, width=35)
                reason_text.grid(row=2, column=1, pady=5)

                # Show finance account balance if available
                if FINANCE_ACCOUNT_AVAILABLE:
                    balance = get_student_finance_account_balance(user_id)
                    if balance is not None:
                        ttk.Label(details_frame, text=f"💰 Current Finance Account Balance: £{balance:.2f}",
                                 font=('Arial', 9), foreground='green').grid(row=3, column=0, columnspan=2, pady=5)

                def process_refund():
                    selected = fines_tree.selection()
                    if not selected:
                        messagebox.showwarning(_("common.warning"), "Please select a paid fine to refund", parent=refund_dialog)
                        return

                    refund_amount_str = refund_amount_var.get().strip()
                    refund_method = refund_method_var.get()
                    refund_reason = reason_text.get("1.0", tk.END).strip()

                    if not refund_amount_str or not refund_reason:
                        messagebox.showwarning(_("common.warning"), "Please fill in all fields", parent=refund_dialog)
                        return

                    try:
                        refund_amount = float(refund_amount_str)
                        if refund_amount <= 0:
                            messagebox.showwarning(_("common.warning"), "Refund amount must be greater than 0", parent=refund_dialog)
                            return
                    except ValueError:
                        messagebox.showwarning(_("common.warning"), "Please enter a valid amount", parent=refund_dialog)
                        return

                    # Process the refund
                    values = fines_tree.item(selected[0])['values']
                    payment_id = values[0]
                    loan_id = values[1]
                    book_title = values[2]
                    paid_amount = float(values[3].replace('£', ''))
                    already_refunded = float(values[4].replace('£', ''))
                    available = float(values[5].replace('£', ''))

                    # Validate refund amount doesn't exceed available amount
                    if refund_amount > available:
                        messagebox.showwarning(_("common.warning"),
                            f"Refund amount (£{refund_amount:.2f}) cannot exceed available amount (£{available:.2f})",
                            parent=refund_dialog)
                        return

                    success = self._process_library_fine_refund(
                        user_id=user_id,
                        payment_id=payment_id,
                        loan_id=loan_id,
                        book_title=book_title,
                        refund_amount=refund_amount,
                        refund_method=refund_method,
                        refund_reason=refund_reason
                    )

                    if success:
                        messagebox.showinfo(_("common.success"),
                            f"Refund of £{refund_amount:.2f} processed successfully!\n\n"
                            f"Method: {refund_method}\n"
                            f"User ID: {user_id}", parent=refund_dialog)
                        refund_dialog.destroy()
                        self.load_user_fines()
                    else:
                        messagebox.showerror(_("common.error"), "Failed to process refund", parent=refund_dialog)

                # Buttons
                btn_frame = ttk.Frame(refund_dialog)
                btn_frame.pack(fill=tk.X, padx=10, pady=10)

                ttk.Button(btn_frame, text="Process Refund", command=process_refund).pack(side=tk.LEFT, padx=5)
                ttk.Button(btn_frame, text=_("common.cancel"), command=refund_dialog.destroy).pack(side=tk.RIGHT, padx=5)

            else:
                print("WARNING: ORIGINAL_LIBRARY_AVAILABLE is False - showing demo message")
                messagebox.showinfo(_("common.demo"), f"Demo: Refund fine for {user_id}")

        except Exception as e:
            print(f"EXCEPTION in _show_user_refund_details: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror(_("common.error"), f"Failed to open refund dialog: {str(e)}")

def _process_library_fine_refund(self, user_id, payment_id, loan_id, book_title, refund_amount, refund_method, refund_reason):
    """Process a library fine refund with multiple payment methods"""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        current_date = datetime.now().strftime('%Y-%m-%d')

        # Handle refund based on method
        if refund_method == "Student Finance Account":
            # Credit the student's finance account
            if FINANCE_ACCOUNT_AVAILABLE:
                # Ensure account exists
                ensure_student_finance_account_exists(user_id)

                # Get current balance
                current_balance = get_student_finance_account_balance(user_id) or 0.0

                # Add refund to student finance account
                from university_system.modules.shared.utils.finance_integration import top_up_student_finance_account

                result = top_up_student_finance_account(
                    student_id=user_id,
                    amount=refund_amount,
                    description=f"Library fine refund (Loan {loan_id})",
                    payment_method="Refund Credit",
                    processed_by=get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else 'System'
                )

                if not result or not result.get('success'):
                    conn.close()
                    return False

                new_balance = result.get('new_balance', current_balance + refund_amount)
            else:
                conn.close()
                return False

        # Update library_fine_payments table with refund information
        cursor.execute('''
            UPDATE library_fine_payments
            SET refund_amount = COALESCE(refund_amount, 0) + ?,
                refunded_date = ?,
                refunded_by = ?,
                refund_reason = CASE
                    WHEN refund_reason IS NULL THEN ?
                    ELSE refund_reason || '; ' || ?
                END,
                notes = CASE
                    WHEN notes IS NULL THEN ?
                    ELSE notes || '; ' || ?
                END
            WHERE payment_id = ?
        ''', (
            refund_amount, current_datetime,
            get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else 'System',
            refund_reason, refund_reason,
            f"Refund £{refund_amount:.2f} via {refund_method}", f"Refund £{refund_amount:.2f} via {refund_method}",
            payment_id
        ))

        # Record refund in finance system
        try:
            from university_system.modules.shared.utils.finance_integration import record_refund_to_finance

            refund_id = record_refund_to_finance(
                student_id=user_id,
                refund_amount=refund_amount,
                original_payment_id=None,
                refund_reason=refund_reason,
                refund_type="library_fine",
                transaction_source="Library",
                transaction_ref=f"FINE_REFUND_{payment_id}",
                refund_method=refund_method.lower().replace(' ', '_'),
                currency="GBP",
                requested_by=get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else 'System',
                notes=f"Book: {book_title}"
            )
        except ImportError:
            refund_id = None
            print("Warning: Could not record refund in finance system")

        conn.commit()
        conn.close()

        # Send refund receipt email
        if EMAIL_SERVICE_AVAILABLE:
            self._send_refund_receipt_email(
                user_id=user_id,
                refund_amount=refund_amount,
                refund_method=refund_method,
                book_title=book_title,
                refund_reason=refund_reason,
                loan_id=loan_id
            )

        # Log the action
        if ORIGINAL_LIBRARY_AVAILABLE:
            log_audit_event(get_current_user_id(),
                          f"GUI: Processed library fine refund £{refund_amount:.2f} for user {user_id} (Loan {loan_id}) via {refund_method}",
                          "book_loans", user_id)

        return True

    except Exception as e:
        print(f"Error processing refund: {e}")
        import traceback
        traceback.print_exc()
        if 'conn' in locals():
            conn.close()
        return False

def _send_refund_receipt_email(self, user_id, refund_amount, refund_method, book_title, refund_reason, loan_id):
    """Send email receipt for library fine refund"""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        cursor.execute('SELECT first_name, last_name, email_address FROM students WHERE student_id = ?', (user_id,))
        user_info = cursor.fetchone()
        conn.close()

        if not user_info or not user_info[2]:
            return False

        first_name, last_name, email = user_info
        full_name = f"{first_name} {last_name}"

        # Render email from template
        from university_system.infrastructure.email.template_utils import render_template

        receipt_number = f"LIB-REFUND-{loan_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        refund_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        refund_message = f"Your student finance account has been credited with £{refund_amount:.2f}." if refund_method == "Student Finance Account" else f"Your refund has been processed using {refund_method}."

        subject, body = render_template('library/refund_receipt', {
            'student_name': full_name,
            'receipt_number': receipt_number,
            'refund_date': refund_date,
            'refund_amount': f'{refund_amount:.2f}',
            'refund_method': refund_method,
            'book_title': book_title,
            'refund_reason': refund_reason,
            'refund_message': refund_message
        })

        # Fallback if template not found
        if not subject or not body:
            subject = "Library Fine Refund Receipt"
            body = f"""Dear {full_name},

This email confirms your library fine refund has been processed.

REFUND DETAILS
Receipt Number:  {receipt_number}
Refund Date:     {refund_date}
Refund Amount:   £{refund_amount:.2f}
Refund Method:   {refund_method}

BOOK DETAILS:
Book Title:      {book_title}

REASON:
{refund_reason}

{refund_message}

If you have any questions about this refund, please contact the library.

Best regards,
University Library System
"""

        send_email_as_system(
            recipient_email=email,
            subject=subject,
            body=body,
            system_name="Library System"
        )
        return True

    except Exception as e:
        print(f"Error sending refund receipt email: {e}")
        return False

def process_fine_payment(self):
    """Process a manual fine payment (cash/card at library desk)"""
    user_id = self.fine_user_var.get().strip()
    payment_amount = self.payment_amount_var.get().strip()

    if not user_id:
        messagebox.showwarning(_("common.warning"), "Please search for a user first")
        return

    if not payment_amount:
        messagebox.showwarning(_("common.warning"), "Please enter a payment amount")
        return

    try:
        amount = float(payment_amount)
        if amount <= 0:
            messagebox.showwarning(_("common.warning"), "Payment amount must be greater than 0")
            return
    except ValueError:
        messagebox.showwarning(_("common.warning"), "Please enter a valid payment amount")
        return

    # Get user details
    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror(_("common.error"), "Database connection unavailable")
                return

            cursor = conn.cursor()

            # Get total outstanding fines
            cursor.execute('''
                SELECT SUM(fine_amount) FROM book_loans
                WHERE user_id = ? AND fine_amount > 0
            ''', (user_id,))
            total_fines = cursor.fetchone()[0] or 0.0

            if total_fines == 0:
                messagebox.showinfo("No Fines", "This user has no outstanding fines")
                conn.close()
                return

            if amount > total_fines:
                response = messagebox.askyesno(
                    "Payment Exceeds Fines",
                    f"Payment amount (${amount:.2f}) exceeds total fines (${total_fines:.2f}).\n\n"
                    f"Do you want to process payment of ${total_fines:.2f} (full balance) instead?"
                )
                if response:
                    amount = total_fines
                else:
                    conn.close()
                    return

            # Apply payment to fines (oldest first)
            cursor.execute('''
                SELECT loan_id, fine_amount FROM book_loans
                WHERE user_id = ? AND fine_amount > 0
                ORDER BY due_date ASC
            ''', (user_id,))

            loans_with_fines = cursor.fetchall()
            remaining_payment = amount
            current_date = datetime.now().strftime('%Y-%m-%d')

            for loan_id, fine_amount in loans_with_fines:
                if remaining_payment <= 0:
                    break

                if remaining_payment >= fine_amount:
                    # Pay full fine for this loan
                    cursor.execute('''
                        UPDATE book_loans
                        SET fine_amount = 0,
                            notes = COALESCE(notes || '; ', '') || 'Fine paid on ' || ?
                        WHERE loan_id = ?
                    ''', (current_date, loan_id))
                    remaining_payment -= fine_amount
                else:
                    # Partial payment
                    new_fine_amount = fine_amount - remaining_payment
                    cursor.execute('''
                        UPDATE book_loans
                        SET fine_amount = ?
                        WHERE loan_id = ?
                    ''', (new_fine_amount, loan_id))
                    remaining_payment = 0

            # Record payment in library_fine_payments table for refund tracking
            self._record_fine_payment(
                conn=conn,
                user_id=user_id,
                amount=amount,
                payment_method="Cash/Card at Library Desk"
            )

            # Record payment in finance system
            finance_success = self._record_library_payment_in_finance(
                user_id=user_id,
                amount=amount,
                payment_method="Cash/Card at Library Desk"
            )

            conn.commit()
            conn.close()

            # Log the action
            if ORIGINAL_LIBRARY_AVAILABLE:
                log_audit_event(get_current_user_id(),
                              f"GUI: Processed manual fine payment ${amount:.2f} for user {user_id}",
                              "book_loans", user_id)

            success_msg = (
                f"Payment of ${amount:.2f} processed successfully!\n\n"
                f"Payment Method: Manual (Cash/Card at Desk)\n"
                f"User ID: {user_id}\n"
                f"Remaining balance will be shown in the refreshed list."
            )

            if finance_success:
                success_msg += "\n\n✓ Payment recorded in Finance System"
            else:
                success_msg += "\n\n⚠ Payment processed but finance recording failed"

            messagebox.showinfo(_("common.success"), success_msg)

            # Clear payment amount field
            self.payment_amount_var.set("")

            # Refresh the fines display
            self.load_user_fines()

        else:
            # Demo mode
            messagebox.showinfo(_("common.demo"), f"Demo: Payment of ${amount:.2f} processed for {user_id}")

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Failed to process payment: {str(e)}")

def pay_fine_from_finance_account(self):
    """Process fine payment from student's finance account balance"""
    user_id = self.fine_user_var.get().strip()
    payment_amount = self.payment_amount_var.get().strip()

    if not user_id:
        messagebox.showwarning(_("common.warning"), "Please search for a user first")
        return

    if not payment_amount:
        messagebox.showwarning(_("common.warning"), "Please enter a payment amount")
        return

    try:
        amount = float(payment_amount)
        if amount <= 0:
            messagebox.showwarning(_("common.warning"), "Payment amount must be greater than 0")
            return
    except ValueError:
        messagebox.showwarning(_("common.warning"), "Please enter a valid payment amount")
        return

    if not FINANCE_ACCOUNT_AVAILABLE:
        messagebox.showerror(_("common.error"), "Finance account integration is not available")
        return

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror(_("common.error"), "Database connection unavailable")
                return

            cursor = conn.cursor()

            # Get total outstanding fines
            cursor.execute('''
                SELECT SUM(fine_amount) FROM book_loans
                WHERE user_id = ? AND fine_amount > 0
            ''', (user_id,))
            total_fines = cursor.fetchone()[0] or 0.0

            if total_fines == 0:
                messagebox.showinfo("No Fines", "This user has no outstanding fines")
                conn.close()
                return

            if amount > total_fines:
                response = messagebox.askyesno(
                    "Payment Exceeds Fines",
                    f"Payment amount (£{amount:.2f}) exceeds total fines (£{total_fines:.2f}).\n\n"
                    f"Do you want to process payment of £{total_fines:.2f} (full balance) instead?"
                )
                if response:
                    amount = total_fines
                else:
                    conn.close()
                    return

            # Check student finance account balance
            current_balance = get_student_finance_account_balance(user_id)
            if current_balance is None:
                # Offer to create a finance account
                create_account = messagebox.askyesno(
                    "No Finance Account",
                    f"No finance account found for user {user_id}.\n\n"
                    "Would you like to create a finance account now?"
                )
                if create_account:
                    if ensure_student_finance_account_exists(user_id):
                        current_balance = 0.0
                        messagebox.showinfo("Account Created",
                            f"Finance account created for user {user_id}.\n"
                            "The account has a £0.00 balance. You can top up now.")
                    else:
                        messagebox.showerror(_("common.error"), "Failed to create finance account")
                        conn.close()
                        return
                else:
                    conn.close()
                    return

            if current_balance < amount:
                # Offer to top up the account
                shortfall = amount - current_balance
                topup_response = messagebox.askyesno(
                    "Insufficient Balance",
                    f"Student finance account balance is insufficient.\n\n"
                    f"Current Balance: £{current_balance:.2f}\n"
                    f"Required Amount: £{amount:.2f}\n"
                    f"Shortfall: £{shortfall:.2f}\n\n"
                    f"Would you like to top up the account now?"
                )
                if topup_response:
                    self._show_topup_dialog(user_id, shortfall, amount, total_fines, conn)
                    return
                else:
                    conn.close()
                    return

            # Process the payment from finance account
            processed_by = get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else 'System'
            payment_result = process_student_finance_account_payment(
                student_id=user_id,
                amount=amount,
                description=f"Library fine payment",
                transaction_source="Library",
                transaction_ref=f"FINE_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                processed_by=processed_by,
                check_balance=True,
                send_low_balance_alert=True
            )

            if not payment_result['success']:
                messagebox.showerror("Payment Failed", payment_result['message'])
                conn.close()
                return

            # Apply payment to fines (oldest first)
            cursor.execute('''
                SELECT loan_id, fine_amount FROM book_loans
                WHERE user_id = ? AND fine_amount > 0
                ORDER BY due_date ASC
            ''', (user_id,))

            loans_with_fines = cursor.fetchall()
            remaining_payment = amount
            current_date = datetime.now().strftime('%Y-%m-%d')

            for loan_id, fine_amount in loans_with_fines:
                if remaining_payment <= 0:
                    break

                if remaining_payment >= fine_amount:
                    # Pay full fine for this loan
                    cursor.execute('''
                        UPDATE book_loans
                        SET fine_amount = 0,
                            notes = COALESCE(notes || '; ', '') || 'Fine paid via Finance Account on ' || ?
                        WHERE loan_id = ?
                    ''', (current_date, loan_id))
                    remaining_payment -= fine_amount
                else:
                    # Partial payment
                    new_fine_amount = fine_amount - remaining_payment
                    cursor.execute('''
                        UPDATE book_loans
                        SET fine_amount = ?
                        WHERE loan_id = ?
                    ''', (new_fine_amount, loan_id))
                    remaining_payment = 0

            # Record payment in library_fine_payments table for refund tracking
            self._record_fine_payment(
                conn=conn,
                user_id=user_id,
                amount=amount,
                payment_method="Student Finance Account"
            )

            # Record payment in library system
            self._record_library_payment_in_finance(
                user_id=user_id,
                amount=amount,
                payment_method="Student Finance Account"
            )

            conn.commit()
            conn.close()

            # Log the action
            if ORIGINAL_LIBRARY_AVAILABLE:
                log_audit_event(get_current_user_id(),
                              f"GUI: Processed finance account payment £{amount:.2f} for user {user_id}",
                              "book_loans", user_id)

            # Build success message
            new_balance = payment_result.get('new_balance', 0)
            low_balance_email_sent = payment_result.get('email_sent', False)

            success_msg = (
                f"Payment of £{amount:.2f} processed successfully!\n\n"
                f"Payment Method: Student Finance Account\n"
                f"New Account Balance: £{new_balance:.2f}\n"
                f"User ID: {user_id}\n"
                f"Remaining library balance will be shown in the refreshed list."
            )

            if low_balance_email_sent:
                success_msg += "\n\n⚠ Low balance alert email sent to student"

            messagebox.showinfo(_("common.success"), success_msg)

            # Clear payment amount field
            self.payment_amount_var.set("")

            # Refresh the fines display
            self.load_user_fines()

        else:
            # Demo mode
            messagebox.showinfo(_("common.demo"), f"Demo: Finance account payment of £{amount:.2f} processed for {user_id}")

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Failed to process payment: {str(e)}")
    except Exception as e:
        messagebox.showerror(_("common.error"), f"Failed to process payment: {str(e)}")

def _show_topup_dialog(self, user_id, shortfall, fine_amount, total_fines, conn):
    """Show dialog to top up finance account and pay fine"""
    dialog = tk.Toplevel(self.root)
    dialog.title(_("library.dialogs.top_up_finance_account"))
    dialog.geometry("400x300")
    dialog.transient(self.root)
    dialog.grab_set()

    # Get current balance
    current_balance = get_student_finance_account_balance(user_id) or 0.0

    ttk.Label(dialog, text=f"Top Up Account for User: {user_id}",
              font=('Segoe UI', 12, 'bold')).pack(pady=10)

    info_frame = ttk.Frame(dialog)
    info_frame.pack(fill=tk.X, padx=20, pady=5)

    ttk.Label(info_frame, text=f"Current Balance: £{current_balance:.2f}").pack(anchor=tk.W)
    ttk.Label(info_frame, text=f"Fine Amount: £{fine_amount:.2f}").pack(anchor=tk.W)
    ttk.Label(info_frame, text=f"Minimum Top-up Required: £{shortfall:.2f}").pack(anchor=tk.W)

    ttk.Separator(dialog, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=20, pady=10)

    # Top-up amount entry
    amount_frame = ttk.Frame(dialog)
    amount_frame.pack(fill=tk.X, padx=20, pady=5)

    ttk.Label(amount_frame, text="Top-up Amount: £").pack(side=tk.LEFT)
    topup_var = tk.StringVar(value=str(round(shortfall, 2)))
    topup_entry = ttk.Entry(amount_frame, textvariable=topup_var, width=15)
    topup_entry.pack(side=tk.LEFT, padx=5)

    # Quick amount buttons
    quick_frame = ttk.Frame(dialog)
    quick_frame.pack(fill=tk.X, padx=20, pady=5)
    ttk.Label(quick_frame, text="Quick amounts:").pack(side=tk.LEFT)
    for amt in [5, 10, 20, 50]:
        ttk.Button(quick_frame, text=f"£{amt}",
                   command=lambda a=amt: topup_var.set(str(a))).pack(side=tk.LEFT, padx=2)

    # Pay full fines button
    ttk.Button(quick_frame, text=f"£{shortfall:.2f} (exact)",
               command=lambda: topup_var.set(str(round(shortfall, 2)))).pack(side=tk.LEFT, padx=2)

    def process_topup_and_pay():
        try:
            topup_amount = float(topup_var.get())
            if topup_amount < shortfall:
                messagebox.showwarning(_("common.warning"),
                    f"Top-up amount (£{topup_amount:.2f}) is less than required (£{shortfall:.2f}).\n"
                    "Please enter at least the minimum amount.")
                return

            # Process top-up
            processed_by = get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else 'System'
            topup_result = top_up_student_finance_account(
                student_id=user_id,
                amount=topup_amount,
                description="Top-up for library fine payment",
                payment_method="Cash/Card at Library",
                processed_by=processed_by
            )

            if not topup_result['success']:
                messagebox.showerror("Top-up Failed", topup_result.get('message', 'Unknown error'))
                return

            # Now process the fine payment
            new_balance = topup_result.get('new_balance', current_balance + topup_amount)

            payment_result = process_student_finance_account_payment(
                student_id=user_id,
                amount=fine_amount,
                description="Library fine payment",
                transaction_source="Library",
                transaction_ref=f"FINE_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                processed_by=processed_by,
                check_balance=True,
                send_low_balance_alert=True
            )

            if not payment_result['success']:
                messagebox.showerror("Payment Failed",
                    f"Top-up succeeded but payment failed: {payment_result.get('message', 'Unknown error')}")
                return

            # Update fines in database
            cursor = conn.cursor()
            cursor.execute('''
                SELECT loan_id, fine_amount FROM book_loans
                WHERE user_id = ? AND fine_amount > 0
                ORDER BY due_date ASC
            ''', (user_id,))

            loans_with_fines = cursor.fetchall()
            remaining_payment = fine_amount
            current_date = datetime.now().strftime('%Y-%m-%d')

            for loan_id, loan_fine in loans_with_fines:
                if remaining_payment <= 0:
                    break
                if remaining_payment >= loan_fine:
                    cursor.execute('''
                        UPDATE book_loans
                        SET fine_amount = 0,
                            notes = COALESCE(notes || '; ', '') || 'Fine paid via Finance Account on ' || ?
                        WHERE loan_id = ?
                    ''', (current_date, loan_id))
                    remaining_payment -= loan_fine
                else:
                    new_fine = loan_fine - remaining_payment
                    cursor.execute('''
                        UPDATE book_loans SET fine_amount = ? WHERE loan_id = ?
                    ''', (new_fine, loan_id))
                    remaining_payment = 0

            conn.commit()
            conn.close()

            final_balance = payment_result.get('new_balance', new_balance - fine_amount)
            messagebox.showinfo(_("common.success"),
                f"Transaction completed successfully!\n\n"
                f"Top-up Amount: £{topup_amount:.2f}\n"
                f"Fine Paid: £{fine_amount:.2f}\n"
                f"New Account Balance: £{final_balance:.2f}")

            dialog.destroy()
            self.payment_amount_var.set("")
            self.load_user_fines()

        except ValueError:
            messagebox.showwarning(_("common.warning"), "Please enter a valid amount")
        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to process: {str(e)}")

    # Buttons
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill=tk.X, padx=20, pady=20)

    ttk.Button(btn_frame, text="Top Up & Pay Fine", command=process_topup_and_pay).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text=_("common.cancel"), command=lambda: [conn.close(), dialog.destroy()]).pack(side=tk.LEFT, padx=5)

def waive_all_fines(self):
    """Waive all outstanding fines for a user"""
    user_id = self.fine_user_var.get().strip()

    if not user_id:
        messagebox.showwarning(_("common.warning"), "Please search for a user first")
        return

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror(_("common.error"), "Database connection unavailable")
                return

            cursor = conn.cursor()

            # Get total outstanding fines
            cursor.execute('''
                SELECT SUM(fine_amount) FROM book_loans
                WHERE user_id = ? AND fine_amount > 0
            ''', (user_id,))
            total_fines = cursor.fetchone()[0] or 0.0

            if total_fines == 0:
                messagebox.showinfo("No Fines", "This user has no outstanding fines to waive")
                conn.close()
                return

            # Confirm waiver
            response = messagebox.askyesno(
                "Confirm Waive Fines",
                f"Are you sure you want to waive all fines for user {user_id}?\n\n"
                f"Total amount to be waived: ${total_fines:.2f}\n\n"
                f"This action cannot be undone."
            )

            if not response:
                conn.close()
                return

            # Waive all fines
            current_date = datetime.now().strftime('%Y-%m-%d')
            cursor.execute('''
                UPDATE book_loans
                SET fine_amount = 0,
                    notes = COALESCE(notes || '; ', '') || 'Fine waived on ' || ?
                WHERE user_id = ? AND fine_amount > 0
            ''', (current_date, user_id))

            rows_affected = cursor.rowcount
            conn.commit()
            conn.close()

            # Log the action
            if ORIGINAL_LIBRARY_AVAILABLE:
                log_audit_event(get_current_user_id(),
                              f"GUI: Waived all fines (${total_fines:.2f}) for user {user_id}",
                              "book_loans", user_id)

            messagebox.showinfo(_("common.success"),
                f"All fines waived successfully!\n\n"
                f"User ID: {user_id}\n"
                f"Amount waived: ${total_fines:.2f}\n"
                f"Loans affected: {rows_affected}")

            # Refresh the fines display
            self.load_user_fines()

        else:
            # Demo mode
            messagebox.showinfo(_("common.demo"), f"Demo: All fines waived for {user_id}")

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Failed to waive fines: {str(e)}")

def view_fine_history(self):
    """View complete fine payment and waiver history for a user"""
    user_id = self.fine_user_var.get().strip()

    if not user_id:
        messagebox.showwarning(_("common.warning"), "Please search for a user first")
        return

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror(_("common.error"), "Database connection unavailable")
                return

            cursor = conn.cursor()

            # Get all fine-related transactions
            cursor.execute('''
                SELECT loan_id, book_id, checkout_date, due_date, return_date,
                       fine_amount, status, notes
                FROM book_loans
                WHERE user_id = ?
                ORDER BY checkout_date DESC
            ''', (user_id,))

            transactions = cursor.fetchall()
            conn.close()

            if not transactions:
                messagebox.showinfo("No History", "No fine history found for this user")
                return

            # Create history window
            history_window = tk.Toplevel()
            history_window.title(f"Fine History - User {user_id}")
            history_window.geometry("900x500")

            # Header
            header_frame = ttk.Frame(history_window)
            header_frame.pack(fill='x', padx=10, pady=10)

            ttk.Label(header_frame, text=f"Complete Fine History for User: {user_id}",
                     font=('Arial', 12, 'bold')).pack()

            # Calculate statistics
            total_paid = sum(0 for _, _, _, _, _, fine, _, notes in transactions
                           if notes and 'Fine paid on' in notes)
            total_waived = sum(0 for _, _, _, _, _, fine, _, notes in transactions
                             if notes and 'Fine waived on' in notes)
            total_outstanding = sum(fine for _, _, _, _, _, fine, _, _ in transactions if fine > 0)

            stats_frame = ttk.Frame(history_window)
            stats_frame.pack(fill='x', padx=10, pady=5)

            ttk.Label(stats_frame, text=f"Payments: {total_paid} | Waivers: {total_waived} | Outstanding: ${total_outstanding:.2f}",
                     font=('Arial', 10)).pack()

            # Scrollable frame for transactions
            canvas = tk.Canvas(history_window)
            scrollbar = ttk.Scrollbar(history_window, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            # Display transactions
            for loan_id, book_id, checkout, due, returned, fine, status, notes in transactions:
                trans_frame = ttk.LabelFrame(scrollable_frame, text=f"Loan #{loan_id} - Book: {book_id}",
                                            relief='solid', borderwidth=1)
                trans_frame.pack(fill='x', padx=10, pady=5)

                info_text = f"Checkout: {checkout} | Due: {due} | Status: {status}\n"
                if returned:
                    info_text += f"Returned: {returned}\n"
                if fine > 0:
                    info_text += f"Current Fine: ${fine:.2f}\n"
                if notes:
                    info_text += f"Notes: {notes}\n"

                ttk.Label(trans_frame, text=info_text).pack(padx=10, pady=5)

            canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
            scrollbar.pack(side="right", fill="y")

            # Close button
            ttk.Button(history_window, text=_("common.close"), command=history_window.destroy).pack(pady=10)

        else:
            messagebox.showinfo(_("common.demo"), f"Demo: Fine history for {user_id}")

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Failed to load fine history: {str(e)}")

def generate_fine_statistics_report(self):
    """Generate comprehensive statistics report for all library fines"""
    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror(_("common.error"), "Database connection unavailable")
                return

            cursor = conn.cursor()

            # Get overall statistics
            cursor.execute('''
                SELECT
                    COUNT(*) as total_fines_issued,
                    COUNT(CASE WHEN fine_amount = 0 AND notes LIKE '%Fine paid on%' THEN 1 END) as total_paid,
                    COUNT(CASE WHEN fine_amount = 0 AND notes LIKE '%Fine waived on%' THEN 1 END) as total_waived,
                    COUNT(CASE WHEN fine_amount > 0 THEN 1 END) as total_outstanding,
                    SUM(CASE WHEN fine_amount > 0 THEN fine_amount ELSE 0 END) as outstanding_amount,
                    AVG(CASE WHEN fine_amount > 0 THEN fine_amount ELSE NULL END) as avg_outstanding_fine
                FROM book_loans
                WHERE fine_amount > 0 OR notes LIKE '%Fine%'
            ''')

            stats = cursor.fetchone()
            total_fines, total_paid, total_waived, total_outstanding, outstanding_amt, avg_fine = stats

            # Get top defaulters
            cursor.execute('''
                SELECT user_id, SUM(fine_amount) as total_owed, COUNT(*) as fine_count
                FROM book_loans
                WHERE fine_amount > 0
                GROUP BY user_id
                ORDER BY total_owed DESC
                LIMIT 10
            ''')

            top_defaulters = cursor.fetchall()

            # Get recent fine activity
            cursor.execute('''
                SELECT COUNT(*) as recent_fines
                FROM book_loans
                WHERE (notes LIKE '%Fine paid on%' OR notes LIKE '%Fine waived on%')
                AND (notes LIKE '%' || date('now', '-30 days') || '%')
            ''')

            recent_activity = cursor.fetchone()[0]

            conn.close()

            # Create report window
            report_window = tk.Toplevel()
            report_window.title("Library Fine Statistics Report")
            report_window.geometry("700x600")

            # Header
            header_frame = ttk.Frame(report_window, relief='raised', borderwidth=2)
            header_frame.pack(fill='x', padx=10, pady=10)

            ttk.Label(header_frame, text="Library Fine Statistics Report",
                     font=('Arial', 14, 'bold')).pack(pady=10)
            ttk.Label(header_frame, text=f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                     font=('Arial', 9)).pack(pady=5)

            # Create scrollable text widget
            text_frame = ttk.Frame(report_window)
            text_frame.pack(fill='both', expand=True, padx=10, pady=10)

            text_widget = tk.Text(text_frame, wrap='word', font=('Courier', 10))
            scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=text_widget.yview)
            text_widget.configure(yscrollcommand=scrollbar.set)

            scrollbar.pack(side='right', fill='y')
            text_widget.pack(side='left', fill='both', expand=True)

            # Build report content
            report_content = f"""
═══════════════════════════════════════════════════════
OVERALL FINE STATISTICS
═══════════════════════════════════════════════════════

Total Fines Issued:       {total_fines or 0}
Total Paid:               {total_paid or 0}
Total Waived:             {total_waived or 0}
Total Outstanding:        {total_outstanding or 0}
Outstanding Amount:       ${outstanding_amt or 0:.2f}
Average Outstanding Fine: ${avg_fine or 0:.2f}

Recent Activity (30 days): {recent_activity} fine transactions

═══════════════════════════════════════════════════════
TOP 10 USERS WITH OUTSTANDING FINES
═══════════════════════════════════════════════════════

"""
            if top_defaulters:
                report_content += f"{'User ID':<20} {'Total Owed':>12} {'Fine Count':>12}\n"
                report_content += "-" * 55 + "\n"
                for user_id, total_owed, fine_count in top_defaulters:
                    report_content += f"{user_id:<20} ${total_owed:>11.2f} {fine_count:>12}\n"
            else:
                report_content += "No outstanding fines found.\n"

            report_content += "\n═══════════════════════════════════════════════════════\n"
            report_content += "RECOMMENDATIONS\n"
            report_content += "═══════════════════════════════════════════════════════\n\n"

            if outstanding_amt and outstanding_amt > 1000:
                report_content += "⚠ High outstanding balance - consider reminder campaign\n"
            if total_outstanding and total_outstanding > 50:
                report_content += "⚠ Many outstanding fines - review fine policy\n"
            if avg_fine and avg_fine > 20:
                report_content += "⚠ High average fine - users may need overdue alerts\n"

            text_widget.insert('1.0', report_content)
            text_widget.configure(state='disabled')

            # Button frame
            button_frame = ttk.Frame(report_window)
            button_frame.pack(fill='x', padx=10, pady=10)

            ttk.Button(button_frame, text="Export to File",
                      command=lambda: self._save_text_report(report_content, "fine_statistics")).pack(side='left', padx=5)
            ttk.Button(button_frame, text=_("common.close"),
                      command=report_window.destroy).pack(side='right', padx=5)

        else:
            messagebox.showinfo(_("common.demo"), "Demo: Fine statistics report")

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Failed to generate statistics: {str(e)}")

def adjust_fine_amount(self):
    """Manually adjust a fine amount for a specific loan"""
    user_id = self.fine_user_var.get().strip()

    if not user_id:
        messagebox.showwarning(_("common.warning"), "Please search for a user first")
        return

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror(_("common.error"), "Database connection unavailable")
                return

            cursor = conn.cursor()

            # Get loans with fines
            cursor.execute('''
                SELECT loan_id, book_id, fine_amount FROM book_loans
                WHERE user_id = ? AND fine_amount > 0
                ORDER BY due_date ASC
            ''', (user_id,))

            loans = cursor.fetchall()

            if not loans:
                messagebox.showinfo("No Fines", "This user has no outstanding fines to adjust")
                conn.close()
                return

            # Create adjustment dialog
            adjust_dialog = tk.Toplevel()
            adjust_dialog.title("Adjust Fine Amount")
            adjust_dialog.geometry("500x400")

            ttk.Label(adjust_dialog, text="Select Loan and Adjust Fine",
                     font=('Arial', 12, 'bold')).pack(pady=10)

            # Loan selection
            loan_frame = ttk.LabelFrame(adjust_dialog, text="Select Loan", padding=10)
            loan_frame.pack(fill='x', padx=10, pady=5)

            loan_var = tk.StringVar()
            for loan_id, book_id, fine_amt in loans:
                ttk.Radiobutton(loan_frame,
                               text=f"Loan #{loan_id} - Book: {book_id} - Current Fine: ${fine_amt:.2f}",
                               variable=loan_var,
                               value=f"{loan_id}:{fine_amt}").pack(anchor='w', pady=2)

            # Adjustment options
            adjust_options_frame = ttk.LabelFrame(adjust_dialog, text="Adjustment", padding=10)
            adjust_options_frame.pack(fill='x', padx=10, pady=10)

            adjust_type_var = tk.StringVar(value="set")
            ttk.Radiobutton(adjust_options_frame, text="Set to specific amount",
                           variable=adjust_type_var, value="set").grid(row=0, column=0, sticky='w')
            ttk.Radiobutton(adjust_options_frame, text="Increase by",
                           variable=adjust_type_var, value="increase").grid(row=1, column=0, sticky='w')
            ttk.Radiobutton(adjust_options_frame, text="Decrease by",
                           variable=adjust_type_var, value="decrease").grid(row=2, column=0, sticky='w')

            amount_var = tk.StringVar()
            ttk.Entry(adjust_options_frame, textvariable=amount_var, width=15).grid(row=0, column=1, padx=5)
            ttk.Entry(adjust_options_frame, textvariable=amount_var, width=15).grid(row=1, column=1, padx=5)
            ttk.Entry(adjust_options_frame, textvariable=amount_var, width=15).grid(row=2, column=1, padx=5)

            # Reason
            reason_frame = ttk.LabelFrame(adjust_dialog, text="Reason for Adjustment", padding=10)
            reason_frame.pack(fill='both', expand=True, padx=10, pady=5)

            reason_text = tk.Text(reason_frame, height=4, width=50)
            reason_text.pack(fill='both', expand=True)

            def process_adjustment():
                if not loan_var.get():
                    messagebox.showwarning(_("common.warning"), "Please select a loan")
                    return

                try:
                    loan_id, current_fine = loan_var.get().split(':')
                    current_fine = float(current_fine)
                    adjustment = float(amount_var.get())
                    adjust_type = adjust_type_var.get()
                    reason = reason_text.get('1.0', 'end-1c').strip()

                    if not reason:
                        messagebox.showwarning(_("common.warning"), "Please provide a reason for adjustment")
                        return

                    # Calculate new fine amount
                    if adjust_type == "set":
                        new_fine = adjustment
                    elif adjust_type == "increase":
                        new_fine = current_fine + adjustment
                    else:  # decrease
                        new_fine = max(0, current_fine - adjustment)

                    # Update database
                    current_date = datetime.now().strftime('%Y-%m-%d')
                    cursor.execute('''
                        UPDATE book_loans
                        SET fine_amount = ?,
                            notes = COALESCE(notes || '; ', '') || 'Fine adjusted on ' || ? || ': ' || ?
                        WHERE loan_id = ?
                    ''', (new_fine, current_date, reason, loan_id))

                    conn.commit()
                    conn.close()

                    # Log the action
                    if ORIGINAL_LIBRARY_AVAILABLE:
                        log_audit_event(get_current_user_id(),
                                      f"GUI: Adjusted fine for loan {loan_id} from ${current_fine:.2f} to ${new_fine:.2f}. Reason: {reason}",
                                      "book_loans", loan_id)

                    messagebox.showinfo(_("common.success"),
                        f"Fine adjusted successfully!\n\n"
                        f"Loan ID: {loan_id}\n"
                        f"Previous amount: ${current_fine:.2f}\n"
                        f"New amount: ${new_fine:.2f}")

                    adjust_dialog.destroy()
                    self.load_user_fines()

                except ValueError:
                    messagebox.showerror(_("common.error"), "Please enter a valid amount")
                except tk.TclError as e:
                    messagebox.showerror(_("common.error"), f"Failed to adjust fine: {str(e)}")

            # Buttons
            button_frame = ttk.Frame(adjust_dialog)
            button_frame.pack(fill='x', padx=10, pady=10)

            ttk.Button(button_frame, text="Apply Adjustment",
                      command=process_adjustment).pack(side='left', padx=5)
            ttk.Button(button_frame, text=_("common.cancel"),
                      command=adjust_dialog.destroy).pack(side='right', padx=5)

        else:
            messagebox.showinfo(_("common.demo"), f"Demo: Adjust fine for {user_id}")

    except (tk.TclError, ValueError, TypeError) as e:
        messagebox.showerror(_("common.error"), f"Failed to open adjustment dialog: {str(e)}")

def export_fines_to_csv(self):
    """Export all outstanding fines to CSV file"""
    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror(_("common.error"), "Database connection unavailable")
                return

            cursor = conn.cursor()

            # Get all fines
            cursor.execute('''
                SELECT bl.user_id, bl.loan_id, bl.book_id, bl.checkout_date, bl.due_date,
                       bl.return_date, bl.fine_amount, bl.status, bl.notes,
                       b.title, b.author
                FROM book_loans bl
                LEFT JOIN books b ON bl.book_id = b.book_id
                WHERE bl.fine_amount > 0
                ORDER BY bl.due_date ASC
            ''')

            fines_data = cursor.fetchall()
            conn.close()

            if not fines_data:
                messagebox.showinfo("No Data", "No outstanding fines to export")
                return

            # Ask for save location
            from tkinter import filedialog
            default_filename = f"library_fines_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=default_filename
            )

            if not file_path:
                return

            # Write CSV
            import csv
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # Header
                writer.writerow(['User ID', 'Loan ID', 'Book ID', 'Book Title', 'Author',
                               'Checkout Date', 'Due Date', 'Return Date',
                               'Fine Amount', 'Status', 'Notes'])

                # Data rows
                for row in fines_data:
                    writer.writerow(row)

                # Summary row
                writer.writerow([])
                writer.writerow(['SUMMARY'])
                writer.writerow(['Total Outstanding Fines:', len(fines_data)])
                writer.writerow(['Total Amount:', f'${sum(row[6] for row in fines_data):.2f}'])

            messagebox.showinfo(_("common.success"),
                f"Fines exported successfully!\n\n"
                f"File: {file_path}\n"
                f"Records: {len(fines_data)}")

        else:
            messagebox.showinfo(_("common.demo"), "Demo: Export fines to CSV")

    except (OSError, IOError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), f"Failed to export fines: {str(e)}")

def _save_text_report(self, content, report_type):
    """Helper function to save text report to file"""
    try:
        from tkinter import filedialog
        default_filename = f"{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=default_filename
        )

        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            messagebox.showinfo(_("common.success"), f"Report saved to:\n{file_path}")

    except (OSError, IOError, tk.TclError) as e:
        messagebox.showerror(_("common.error"), f"Failed to save report: {str(e)}")

def _record_fine_payment(self, conn, user_id, amount, payment_method, loans_paid=None):
    """Record fine payment in library_fine_payments table for refund tracking.

    Args:
        conn: Database connection
        user_id: Student ID
        amount: Total payment amount
        payment_method: How the payment was made
        loans_paid: Optional list of (loan_id, book_id, amount_paid) tuples for the loans that were paid
    """
    try:
        cursor = conn.cursor()
        current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # If specific loans weren't provided, try to find recently paid loans
        if not loans_paid:
            cursor.execute('''
                SELECT loan_id, book_id, 0 as amount_paid FROM book_loans
                WHERE user_id = ?
                AND notes LIKE '%Fine paid on%'
                AND fine_amount = 0
                ORDER BY due_date DESC
                LIMIT 5
            ''', (user_id,))
            loans_paid = cursor.fetchall()

        # Record payment for each loan
        for loan_id, book_id, amount_paid in loans_paid:
            # Get book title
            cursor.execute('SELECT title FROM books WHERE book_id = ?', (book_id,))
            book_result = cursor.fetchone()
            book_title = book_result[0] if book_result else 'Unknown'

            # Use the total amount if individual amounts not specified
            payment_amt = amount_paid if amount_paid > 0 else amount

            # Insert into library_fine_payments
            cursor.execute('''
                INSERT INTO library_fine_payments
                (loan_id, user_id, book_id, book_title, fine_amount, payment_amount,
                 payment_method, payment_date, processed_by, transaction_ref, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                loan_id, user_id, book_id, book_title, payment_amt, payment_amt,
                payment_method, current_datetime,
                get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else 'System',
                f'PAY_{loan_id}_{datetime.now().strftime("%Y%m%d%H%M%S")}',
                'completed'
            ))

        return True

    except Exception as e:
        print(f"Error recording fine payment: {e}")
        import traceback
        traceback.print_exc()
        return False

def _record_library_payment_in_finance(self, user_id, amount, payment_method):
    """Record library fine payment in the finance system for tracking."""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        current_date = datetime.now().strftime('%Y-%m-%d')
        current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Get or create student_fees record for library fines
        # First, check if there's an existing unpaid library fee
        cursor.execute('''
            SELECT student_fee_id, amount FROM student_fees
            WHERE student_id = ? AND fee_type_id = 3 AND status = 'unpaid'
            ORDER BY created_at DESC LIMIT 1
        ''', (user_id,))

        existing_fee = cursor.fetchone()

        if existing_fee:
            # Update existing fee (reduce amount or mark as paid)
            student_fee_id, current_fee_amount = existing_fee
            new_fee_amount = max(0, current_fee_amount - amount)

            if new_fee_amount == 0:
                # Fully paid
                cursor.execute('''
                    UPDATE student_fees
                    SET status = 'paid', amount = 0, updated_at = ?
                    WHERE student_fee_id = ?
                ''', (current_datetime, student_fee_id))
            else:
                # Partial payment
                cursor.execute('''
                    UPDATE student_fees
                    SET amount = ?, updated_at = ?
                    WHERE student_fee_id = ?
                ''', (new_fee_amount, current_datetime, student_fee_id))
        else:
            # Create a new fee record marked as paid (for historical tracking)
            cursor.execute('''
                INSERT INTO student_fees
                (student_id, fee_type_id, amount, currency, status, due_date, created_at, updated_at)
                VALUES (?, 3, 0, 'GBP', 'paid', ?, ?, ?)
            ''', (user_id, current_date, current_datetime, current_datetime))
            student_fee_id = cursor.lastrowid

        # Create payment record
        cursor.execute('''
            INSERT INTO payments
            (student_id, amount, currency, payment_method, payment_date, status, notes, created_by, created_at)
            VALUES (?, ?, 'GBP', ?, ?, 'completed', 'Library fine payment', ?, ?)
        ''', (user_id, amount, payment_method, current_date,
              get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else 'system',
              current_datetime))

        payment_id = cursor.lastrowid

        # Link payment to fee via payment_allocations
        cursor.execute('''
            INSERT INTO payment_allocations
            (payment_id, student_fee_id, amount, created_at)
            VALUES (?, ?, ?, ?)
        ''', (payment_id, student_fee_id, amount, current_datetime))

        conn.commit()
        conn.close()

        return True

    except (sqlite3.Error, DatabaseError) as e:
        print(f"Error recording library payment in finance system: {e}")
        import traceback
        traceback.print_exc()
        return False

def pay_fine_via_finance(self):
    """Pay library fines through the finance system"""
    user_id = self.fine_user_var.get().strip()
    payment_amount = self.payment_amount_var.get().strip()

    if not user_id:
        messagebox.showwarning(_("common.warning"), "Please search for a user first")
        return

    if not payment_amount:
        messagebox.showwarning(_("common.warning"), "Please enter a payment amount")
        return

    try:
        amount = float(payment_amount)
        if amount <= 0:
            messagebox.showwarning(_("common.warning"), "Payment amount must be greater than 0")
            return
    except ValueError:
        messagebox.showwarning(_("common.warning"), "Please enter a valid payment amount")
        return

    # Get user details for the finance transaction
    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('SELECT first_name, last_name, email_address FROM students WHERE student_id = ?', (user_id,))
                user_info = cursor.fetchone()
                conn.close()

                if not user_info:
                    messagebox.showerror(_("common.error"), "Student not found in system")
                    return

                first_name, last_name, email = user_info
            else:
                first_name, last_name, email = "Demo", "User", "demo@university.edu"
        else:
            first_name, last_name, email = "Demo", "User", "demo@university.edu"

        # Create finance transaction via Finance GUI
        success = self._process_library_fine_payment(
            student_id=user_id,
            amount=amount,
            student_name=f"{first_name} {last_name}",
            email=email
        )

        if success:
            messagebox.showinfo(_("common.success"),
                f"Library fine payment of ${amount:.2f} processed successfully!\n"
                f"Payment has been charged to {first_name} {last_name}'s account.")

            # Send email confirmation
            self._send_library_payment_confirmation_email(
                student_id=user_id,
                student_name=f"{first_name} {last_name}",
                email=email,
                amount=amount
            )

            # Refresh the fines display
            self.load_user_fines()
        else:
            messagebox.showerror(_("common.error"),
                "Failed to process payment through finance system.\n"
                "Please try again or contact the finance office.")

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Failed to process finance payment: {e}")

def _process_library_fine_payment(self, student_id, amount, student_name, email):
    """Process library fine payment through finance system"""
    try:
        # Try to integrate with finance GUI
        from university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH

        with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
            cursor = conn.cursor()
            current_date = datetime.now().strftime('%Y-%m-%d')
            due_date = current_date  # Library fines are due immediately

            # Check for existing unpaid library fee, or create new one
            cursor.execute('''
                SELECT student_fee_id, amount FROM student_fees
                WHERE student_id = ? AND fee_type_id = 3 AND status = 'unpaid'
                ORDER BY created_at DESC LIMIT 1
            ''', (student_id,))

            existing_fee = cursor.fetchone()

            if existing_fee:
                # Update existing fee
                student_fee_id, current_fee_amount = existing_fee
                new_fee_amount = max(0, current_fee_amount - amount)

                if new_fee_amount == 0:
                    # Fully paid
                    cursor.execute('''
                        UPDATE student_fees
                        SET status = 'paid', updated_at = ?
                        WHERE student_fee_id = ?
                    ''', (current_date, student_fee_id))
                else:
                    # Partial payment
                    cursor.execute('''
                        UPDATE student_fees
                        SET amount = ?, updated_at = ?
                        WHERE student_fee_id = ?
                    ''', (new_fee_amount, current_date, student_fee_id))
            else:
                # Create new fee record (already paid)
                cursor.execute('''
                    INSERT INTO student_fees
                    (student_id, fee_type_id, amount, currency, status, due_date, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, 3, 0.00, 'GBP', 'paid', due_date, current_date, current_date))
                student_fee_id = cursor.lastrowid

            # Record payment in payments table
            cursor.execute('''
                INSERT INTO payments
                (student_id, amount, payment_method, payment_date, status, reference_number, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                student_id, amount, 'Student Account', current_date, 'completed',
                f'LIB-{student_id}-{datetime.now().strftime("%Y%m%d%H%M%S")}',
                f'Library fine payment for {student_name}', current_date
            ))
            payment_id = cursor.lastrowid

            # Link payment to fee via payment_allocations
            cursor.execute('''
                INSERT INTO payment_allocations
                (payment_id, student_fee_id, amount, created_at)
                VALUES (?, ?, ?, ?)
            ''', (payment_id, student_fee_id, amount, current_date))

            # Update library fine status to paid (set amount to 0, add note)
            cursor.execute('''
                UPDATE book_loans
                SET fine_amount = 0,
                    notes = COALESCE(notes || '; ', '') || 'Fine paid on ' || ?
                WHERE user_id = ? AND fine_amount > 0
            ''', (current_date, student_id))

            conn.commit()
            return True

    except (sqlite3.Error, DatabaseError) as e:
        print(f"Finance integration error: {e}")
        import traceback
        traceback.print_exc()
        return False

def open_finance_payment_for_user(self, user_id, amount):
    """Open finance system for user to pay late fees"""
    try:
        # Try to launch finance GUI for payment
        try:
            from university_system.modules.domain.finance.gui.finance import FinanceGUI
            finance_window = tk.Toplevel(self.master)
            finance_window.title(f"Pay Library Fees - ${amount:.2f}")
            finance_window.geometry("800x600")

            # Initialize finance GUI in payment mode
            finance_gui = FinanceGUI(finance_window, auth=self.auth)
            # Pre-populate with library fee information if method exists
            if hasattr(finance_gui, 'prepopulate_library_fee_payment'):
                finance_gui.prepopulate_library_fee_payment(user_id, amount)

        except ImportError:
            # Fallback to showing fine management dialog
            self.fine_user_var = tk.StringVar(value=user_id)
            self.payment_amount_var = tk.StringVar(value=str(amount))
            self.show_fine_management()

    except (tk.TclError, ValueError, TypeError) as e:
        messagebox.showerror(_("common.error"), f"Could not open payment system: {e}")

def process_fine_payment_gui(self):
    """Process fine payment interface"""
    payment_window = tk.Toplevel(self.master)
    payment_window.title("Process Fine Payment")
    payment_window.geometry("600x500")

    ttk.Label(payment_window, text="Process Fine Payment",
             font=('Arial', 16, 'bold')).pack(pady=10)

    # Search frame
    search_frame = ttk.LabelFrame(payment_window, text="Find Loan with Fine", padding=15)
    search_frame.pack(fill=tk.X, padx=10, pady=10)

    search_type = tk.StringVar(value="user_id")
    search_value = tk.StringVar()

    ttk.Radiobutton(search_frame, text="By User ID", variable=search_type, value="user_id").grid(row=0, column=0, sticky=tk.W, padx=5)
    ttk.Radiobutton(search_frame, text="By Loan ID", variable=search_type, value="loan_id").grid(row=0, column=1, sticky=tk.W, padx=5)

    ttk.Entry(search_frame, textvariable=search_value, width=30).grid(row=1, column=0, columnspan=2, padx=5, pady=10)

    # Results frame
    results_frame = ttk.LabelFrame(payment_window, text="Outstanding Fines", padding=10)
    results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    columns = ('Loan ID', 'Book Title', 'User', 'Fine Amount', 'Days Overdue')
    fines_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=8)

    for col in columns:
        fines_tree.heading(col, text=col)
        fines_tree.column(col, width=110)

    fines_tree.pack(fill=tk.BOTH, expand=True)

    def search_fines():
        for item in fines_tree.get_children():
            fines_tree.delete(item)

        stype = search_type.get()
        svalue = search_value.get().strip()

        if not svalue:
            messagebox.showwarning(_("common.warning"), "Please enter a search value")
            return

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            if stype == "user_id":
                query = '''
                SELECT l.loan_id, b.title, l.user_id, l.fine_amount,
                       CAST((julianday('now') - julianday(l.due_date)) AS INTEGER) as days_overdue
                FROM book_loans l
                JOIN books b ON l.book_id = b.book_id
                WHERE l.user_id = ? AND l.fine_amount > 0 AND l.status != 'returned'
                '''
            else:
                query = '''
                SELECT l.loan_id, b.title, l.user_id, l.fine_amount,
                       CAST((julianday('now') - julianday(l.due_date)) AS INTEGER) as days_overdue
                FROM book_loans l
                JOIN books b ON l.book_id = b.book_id
                WHERE l.loan_id = ? AND l.fine_amount > 0 AND l.status != 'returned'
                '''

            cursor.execute(query, (svalue,))
            fines = cursor.fetchall()
            conn.close()

            for fine in fines:
                fines_tree.insert('', 'end', values=(
                    fine[0], fine[1][:40], fine[2], f"${fine[3]:.2f}", fine[4]
                ))

            if not fines:
                messagebox.showinfo("No Fines", "No outstanding fines found")

        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Search failed: {str(e)}")

    ttk.Button(search_frame, text=_("common.search"), command=search_fines).grid(row=1, column=2, padx=5)

    def process_payment():
        selection = fines_tree.selection()
        if not selection:
            messagebox.showwarning(_("common.warning"), "Please select a fine to pay")
            return

        item = fines_tree.item(selection[0])
        loan_id = item['values'][0]
        fine_amount_str = item['values'][3]
        fine_amount = float(fine_amount_str.replace('$', ''))

        # Payment dialog
        pay_dialog = tk.Toplevel(payment_window)
        pay_dialog.title("Process Payment")
        pay_dialog.geometry("400x300")

        ttk.Label(pay_dialog, text="Process Fine Payment",
                 font=('Arial', 12, 'bold')).pack(pady=10)

        info_frame = ttk.Frame(pay_dialog, padding=15)
        info_frame.pack(fill=tk.X)

        ttk.Label(info_frame, text=f"Loan ID: {loan_id}").pack(anchor=tk.W, pady=2)
        ttk.Label(info_frame, text=f"Fine Amount: ${fine_amount:.2f}",
                 font=('Arial', 11, 'bold')).pack(anchor=tk.W, pady=2)

        payment_method_var = tk.StringVar(value="cash")
        ttk.Label(info_frame, text="Payment Method:").pack(anchor=tk.W, pady=(10, 2))
        ttk.Radiobutton(info_frame, text="Cash", variable=payment_method_var, value="cash").pack(anchor=tk.W, padx=20)
        ttk.Radiobutton(info_frame, text="Card", variable=payment_method_var, value="card").pack(anchor=tk.W, padx=20)
        ttk.Radiobutton(info_frame, text="Check", variable=payment_method_var, value="check").pack(anchor=tk.W, padx=20)
        if FINANCE_ACCOUNT_AVAILABLE:
            ttk.Radiobutton(info_frame, text="Finance Account", variable=payment_method_var, value="finance_account").pack(anchor=tk.W, padx=20)

        # Get user_id from the selected fine
        user_id_for_payment = item['values'][2]

        def confirm_payment():
            try:
                payment_method = payment_method_var.get()
                payment_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Handle finance account payment separately
                if payment_method == "finance_account":
                    if not FINANCE_ACCOUNT_AVAILABLE:
                        messagebox.showerror(_("common.error"), "Finance account integration not available")
                        return

                    # Check if account exists
                    current_balance = get_student_finance_account_balance(user_id_for_payment)
                    if current_balance is None:
                        # Offer to create account
                        create = messagebox.askyesno("No Account",
                            f"No finance account found for {user_id_for_payment}.\n\nCreate one now?")
                        if create:
                            if ensure_student_finance_account_exists(user_id_for_payment):
                                current_balance = 0.0
                                messagebox.showinfo("Created", "Account created with £0.00 balance.\nPlease top up first.")
                                return
                            else:
                                messagebox.showerror(_("common.error"), "Failed to create account")
                                return
                        else:
                            return

                    if current_balance < fine_amount:
                        shortfall = fine_amount - current_balance
                        topup = messagebox.askyesno("Insufficient Balance",
                            f"Balance: £{current_balance:.2f}\nRequired: £{fine_amount:.2f}\nShortfall: £{shortfall:.2f}\n\nTop up now?")
                        if topup:
                            # Show simple top-up dialog
                            topup_amt = simpledialog.askfloat("Top Up", f"Enter top-up amount (min £{shortfall:.2f}):",
                                minvalue=shortfall, initialvalue=shortfall)
                            if topup_amt:
                                result = top_up_student_finance_account(
                                    student_id=user_id_for_payment,
                                    amount=topup_amt,
                                    description="Top-up for library fine",
                                    payment_method="Cash/Card",
                                    processed_by=get_current_user_id()
                                )
                                if not result['success']:
                                    messagebox.showerror(_("common.error"), f"Top-up failed: {result.get('message')}")
                                    return
                                current_balance = result.get('new_balance', current_balance + topup_amt)
                            else:
                                return
                        else:
                            return

                    # Process payment from finance account
                    processed_by = get_current_user_id()
                    payment_result = process_student_finance_account_payment(
                        student_id=user_id_for_payment,
                        amount=fine_amount,
                        description=f"Library fine payment (Loan {loan_id})",
                        transaction_source="Library",
                        transaction_ref=f"FINE_{loan_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        processed_by=processed_by,
                        check_balance=True
                    )

                    if not payment_result['success']:
                        messagebox.showerror(_("common.error"), f"Payment failed: {payment_result.get('message')}")
                        return

                    new_balance = payment_result.get('new_balance', 0)

                # Update database
                conn = get_db_connection()
                cursor = conn.cursor()

                # Record payment in fine_payments table
                cursor.execute('''
                INSERT INTO fine_payments (
                    loan_id, amount, payment_method, payment_date, processed_by
                ) VALUES (?, ?, ?, ?, ?)
                ''', (loan_id, fine_amount, payment_method, payment_date, get_current_user_id()))

                # Update loan - mark fine as paid
                cursor.execute('''
                UPDATE book_loans
                SET fine_amount = 0
                WHERE loan_id = ?
                ''', (loan_id,))

                conn.commit()
                conn.close()

                log_audit_event(get_current_user_id(),
                              f"Processed fine payment: ${fine_amount:.2f} for loan {loan_id} via {payment_method}",
                              "fine_payments")

                # Generate receipt
                self.generate_fine_receipt_gui(loan_id, fine_amount, payment_method, payment_date)

                pay_dialog.destroy()

                if payment_method == "finance_account":
                    messagebox.showinfo(_("common.success"),
                        f"Payment processed successfully!\n\nAmount: £{fine_amount:.2f}\nNew Balance: £{new_balance:.2f}")
                else:
                    messagebox.showinfo(_("common.success"), f"Payment processed successfully!\n\nAmount: ${fine_amount:.2f}")

                search_fines()  # Refresh list

            except Exception as e:
                messagebox.showerror(_("common.error"), f"Payment failed: {str(e)}")

        ttk.Button(info_frame, text="Process Payment", command=confirm_payment).pack(pady=20)

    # Button frame
    button_frame = ttk.Frame(payment_window)
    button_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(button_frame, text="Process Payment", command=process_payment).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.close"), command=payment_window.destroy).pack(side=tk.RIGHT, padx=5)

def generate_fine_receipt_gui(self, loan_id, amount, payment_method, payment_date):
    """Generate and display fine receipt"""
    receipt_window = tk.Toplevel(self.master)
    receipt_window.title("Fine Payment Receipt")
    receipt_window.geometry("500x600")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get loan details
        cursor.execute('''
        SELECT b.title, b.author, l.user_id, l.checkout_date, l.due_date
        FROM book_loans l
        JOIN books b ON l.book_id = b.book_id
        WHERE l.loan_id = ?
        ''', (loan_id,))

        loan_details = cursor.fetchone()
        conn.close()

        if loan_details:
            title, author, user_id, checkout, due = loan_details

            receipt_text = f"""
╔══════════════════════════════════════════════════════════════╗
║                  FINE PAYMENT RECEIPT                        ║
╚══════════════════════════════════════════════════════════════╝

Receipt Date: {payment_date}
Receipt ID: FP-{loan_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}

PAYMENT DETAILS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Loan ID:         {loan_id}
User ID:         {user_id}

Book:            {title}
Author:          {author}

Checkout Date:   {checkout[:10]}
Due Date:        {due[:10]}

PAYMENT INFORMATION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fine Amount:     ${amount:.2f}
Payment Method:  {payment_method.upper()}
Status:          PAID IN FULL

Thank you for your payment!

For questions, please contact the library front desk.
"""

            text_widget = ScrolledText(receipt_window, height=30, width=70, font=('Courier', 9))
            text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            text_widget.insert('1.0', receipt_text)
            text_widget.config(state=tk.DISABLED)

            def print_receipt():
                try:
                    file_path = filedialog.asksaveasfilename(
                        defaultextension=".txt",
                        filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                        initialfile=f"receipt_{loan_id}.txt"
                    )

                    if file_path:
                        with open(file_path, 'w') as f:
                            f.write(receipt_text)
                        messagebox.showinfo(_("common.success"), f"Receipt saved to:\n{file_path}")

                except (OSError, IOError, tk.TclError) as e:
                    messagebox.showerror(_("common.error"), f"Failed to save receipt: {str(e)}")

            button_frame = ttk.Frame(receipt_window)
            button_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Button(button_frame, text="Save Receipt", command=print_receipt).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text=_("common.close"), command=receipt_window.destroy).pack(side=tk.RIGHT, padx=5)

    except (OSError, IOError, tk.TclError, ValueError, TypeError) as e:
        messagebox.showerror(_("common.error"), f"Failed to generate receipt: {str(e)}")
        receipt_window.destroy()
