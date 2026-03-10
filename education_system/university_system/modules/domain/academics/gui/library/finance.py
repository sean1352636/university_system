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

def open_library_finance(self):
    """Open the Library Finance management window directly in Library GUI"""
    if not self.check_permission('manage_loans'):
        return

    try:
        # Create new window for Library Finance
        finance_window = tk.Toplevel(self.master)
        finance_window.title("Library Finance Management")
        finance_window.geometry("1400x900")
        finance_window.transient(self.master)

        # Create and initialize the LibraryFinanceManager
        library_finance_manager = LibraryFinanceManager(finance_window, self.auth)

        # Add close button at the bottom
        close_frame = tk.Frame(finance_window, bg='white')
        close_frame.pack(fill='x', side='bottom', pady=10)
        tk.Button(
            close_frame,
            text=_("common.close"),
            command=finance_window.destroy,
            bg='#3498db',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=30,
            pady=8
        ).pack()

    except Exception as e:
        messagebox.showerror(
            "Error",
            f"Failed to open Library Finance:\n{str(e)}\n\nFalling back to basic fine management."
        )
        import traceback
        traceback.print_exc()
        # Fall back to basic fine management
        self.show_fine_management()

class LibraryFinanceManager:
    """Manages all library-related financial operations - integrated into Library GUI"""

    def __init__(self, root, auth=None):
        """Initialize manager with root window and auth"""
        self.root = root
        self.auth = auth
        self.conn = None

        # Color scheme
        self.colors = {
            'primary': '#2c3e50',
            'secondary': '#3498db',
            'success': '#27ae60',
            'warning': '#f39c12',
            'danger': '#e74c3c',
            'light': '#ecf0f1',
            'dark': '#34495e',
            'info': '#17a2b8',
            'library': '#9b59b6'  # Purple for library-specific items
        }

        # Current filter state
        self.start_date_var = tk.StringVar()
        self.end_date_var = tk.StringVar()
        self.search_var = tk.StringVar()

        # Create the main content frame
        self.content_frame = tk.Frame(root, bg='white')
        self.content_frame.pack(fill='both', expand=True)

        # Create the library finance interface
        self.create_library_finance_interface()

    # ==================== EMAIL NOTIFICATION HELPERS ====================

    def get_user_email(self, user_id):
        """Get user email address from database"""
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT email, first_name, last_name FROM users WHERE id = ?', (user_id,))
            result = cursor.fetchone()
            conn.close()

            if result:
                return {
                    'email': result[0],
                    'first_name': result[1],
                    'last_name': result[2],
                    'full_name': f"{result[1]} {result[2]}"
                }
            return None
        except Exception as e:
            print(f"Error getting user email: {e}")
            return None

    def send_fine_notification_email(self, user_info, fine_amount, book_title, due_date, days_overdue):
        """Send email notification when a fine is created"""
        try:
            if not user_info or not user_info.get('email'):
                return False

            # Render email from template
            from education_system.university_system.infrastructure.email.template_utils import render_template

            subject, body = render_template('library/fine_notice', {
                'student_name': user_info['full_name'],
                'book_title': book_title,
                'due_date': due_date,
                'days_overdue': str(days_overdue),
                'fine_amount': f'{fine_amount:.2f}'
            })

            # Fallback if template not found
            if not subject or not body:
                subject = "Library Fine Notice - Overdue Book"
                body = f"""Dear {user_info['full_name']},

This is to notify you that a library fine has been assessed on your account.

FINE DETAILS:
Book Title:      {book_title}
Due Date:        {due_date}
Days Overdue:    {days_overdue}
Fine Amount:     £{fine_amount:.2f}

Please return the book and pay the fine at your earliest convenience.

Thank you,
University Library System
"""
            send_email_as_system(
                recipient_email=user_info['email'],
                subject=subject,
                body=body,
                system_name="Library System"
            )
            return True
        except Exception as e:
            print(f"Error sending fine notification email: {e}")
            return False

    def send_payment_receipt_email(self, user_info, fine_amount, payment_amount, payment_method,
                                   book_title, transaction_id, payment_date):
        """Send email receipt when a fine is paid"""
        try:
            if not user_info or not user_info.get('email'):
                return False

            # Render email from template
            from education_system.university_system.infrastructure.email.template_utils import render_template

            subject, body = render_template('library/payment_receipt', {
                'student_name': user_info['full_name'],
                'transaction_id': transaction_id,
                'payment_date': payment_date,
                'payment_method': payment_method,
                'book_title': book_title,
                'fine_amount': f'{fine_amount:.2f}',
                'payment_amount': f'{payment_amount:.2f}'
            })

            # Fallback if template not found
            if not subject or not body:
                subject = "Library Fine Payment Receipt"
                body = f"""Dear {user_info['full_name']},

Thank you for your payment. This email confirms your library fine payment.

PAYMENT RECEIPT
Receipt Number:  {transaction_id}
Payment Date:    {payment_date}
Payment Method:  {payment_method}

FINE DETAILS:
Book Title:      {book_title}
Original Fine:   £{fine_amount:.2f}
Amount Paid:     £{payment_amount:.2f}

Your payment has been processed successfully.

Best regards,
University Library System
"""
            send_email_as_system(
                recipient_email=user_info['email'],
                subject=subject,
                body=body,
                system_name="Library System"
            )
            return True
        except Exception as e:
            print(f"Error sending payment receipt email: {e}")
            return False

    def send_fine_waived_email(self, user_info, fine_amount, book_title, waiver_reason="Administrative action"):
        """Send email notification when a fine is deleted/waived"""
        try:
            if not user_info or not user_info.get('email'):
                return False

            # Render email from template
            from education_system.university_system.infrastructure.email.template_utils import render_template

            subject, body = render_template('library/fine_waived', {
                'student_name': user_info['full_name'],
                'book_title': book_title,
                'fine_amount': f'{fine_amount:.2f}',
                'waiver_reason': waiver_reason
            })

            # Fallback if template not found
            if not subject or not body:
                subject = "Library Fine Waived - Good News!"
                body = f"""Dear {user_info['full_name']},

Good news! A library fine on your account has been waived.

WAIVED FINE DETAILS:
Book Title:      {book_title}
Fine Amount:     £{fine_amount:.2f}
Reason:          {waiver_reason}
Status:          WAIVED - No payment required

Your library account is now in good standing.

Best regards,
University Library System
"""
            send_email_as_system(
                recipient_email=user_info['email'],
                subject=subject,
                body=body,
                system_name="Library System"
            )
            return True
        except Exception as e:
            print(f"Error sending fine waived email: {e}")
            return False

    # ==================== INTERFACE CREATION ====================

    def create_library_finance_interface(self):
        """Create the Library Finance interface with all sections"""
        # Title
        title_label = tk.Label(
            self.content_frame,
            text="Library Finance Management",
            font=('Arial', 18, 'bold'),
            bg='white'
        )
        title_label.pack(pady=10)

        # Create notebook for different sections
        notebook = ttk.Notebook(self.content_frame)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Tab 1: Fine Management
        fines_tab = tk.Frame(notebook, bg='white')
        notebook.add(fines_tab, text="Fine Management")
        self.create_fines_section(fines_tab)

        # Tab 2: Revenue Analytics
        revenue_tab = tk.Frame(notebook, bg='white')
        notebook.add(revenue_tab, text="Revenue Analytics")
        self.create_revenue_section(revenue_tab)

        # Tab 3: Book Costs
        costs_tab = tk.Frame(notebook, bg='white')
        notebook.add(costs_tab, text="Book Costs")
        self.create_costs_section(costs_tab)

        # Tab 4: Financial Overview
        overview_tab = tk.Frame(notebook, bg='white')
        notebook.add(overview_tab, text="Overview")
        self.create_overview_section(overview_tab)

    def create_fines_section(self, parent):
        """Create fine management section with CRUD operations"""
        # Toolbar
        toolbar = tk.Frame(parent, bg='white')
        toolbar.pack(fill='x', padx=10, pady=10)

        tk.Label(toolbar, text="Search User:", bg='white', font=('Arial', 10)).pack(side='left', padx=5)
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=20)
        search_entry.pack(side='left', padx=5)

        tk.Button(toolbar, text=_("common.search"), command=self.search_fines,
                  bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        tk.Button(toolbar, text="Create Fine", command=self.create_fine_dialog,
                  bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        tk.Button(toolbar, text="Edit Fine", command=self.edit_fine_dialog,
                  bg=self.colors['warning'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        tk.Button(toolbar, text="Delete Fine", command=self.delete_fine,
                  bg=self.colors['danger'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        tk.Button(toolbar, text="Process Payment", command=self.process_payment_dialog,
                  bg=self.colors['library'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        tk.Button(toolbar, text="🔄 Process Refund", command=self.process_refund_dialog,
                  bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        tk.Button(toolbar, text=_("common.refresh"), command=self.load_all_fines,
                  bg=self.colors['info'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        # Fines table
        table_frame = tk.Frame(parent, bg='white')
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(table_frame)
        y_scroll.pack(side='right', fill='y')
        x_scroll = ttk.Scrollbar(table_frame, orient='horizontal')
        x_scroll.pack(side='bottom', fill='x')

        columns = ('Loan ID', 'User ID', 'Name', 'Book ID', 'Title', 'Days Overdue', 'Fine Amount', 'Status')
        self.fines_tree = ttk.Treeview(table_frame, columns=columns, show='headings',
                                        yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        y_scroll.config(command=self.fines_tree.yview)
        x_scroll.config(command=self.fines_tree.xview)

        for col in columns:
            self.fines_tree.heading(col, text=col)
        self.fines_tree.column('Loan ID', width=80, anchor='center')
        self.fines_tree.column('User ID', width=100)
        self.fines_tree.column('Name', width=150)
        self.fines_tree.column('Book ID', width=100)
        self.fines_tree.column('Title', width=200)
        self.fines_tree.column('Days Overdue', width=100, anchor='center')
        self.fines_tree.column('Fine Amount', width=100, anchor='e')
        self.fines_tree.column('Status', width=100, anchor='center')
        self.fines_tree.pack(fill='both', expand=True)

        self.fines_summary_label = tk.Label(parent, text="Total Outstanding Fines: £0.00 | Total Items: 0",
                                             font=('Arial', 11, 'bold'), bg='white', fg=self.colors['primary'])
        self.fines_summary_label.pack(pady=10)

        self.root.after(100, self.load_all_fines)

    def create_revenue_section(self, parent):
        """Create revenue analytics section"""
        toolbar = tk.Frame(parent, bg='white')
        toolbar.pack(fill='x', padx=10, pady=10)

        tk.Label(toolbar, text="Start Date:", bg='white', font=('Arial', 10)).pack(side='left', padx=5)
        start_entry = ttk.Entry(toolbar, textvariable=self.start_date_var, width=12)
        start_entry.pack(side='left', padx=5)
        start_entry.insert(0, (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'))

        tk.Label(toolbar, text="End Date:", bg='white', font=('Arial', 10)).pack(side='left', padx=5)
        end_entry = ttk.Entry(toolbar, textvariable=self.end_date_var, width=12)
        end_entry.pack(side='left', padx=5)
        end_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))

        tk.Button(toolbar, text="Generate Report", command=self.generate_revenue_report,
                  bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        tk.Button(toolbar, text="Show Charts", command=self.show_revenue_charts,
                  bg=self.colors['info'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        tk.Button(toolbar, text="Export CSV", command=self.export_revenue_csv,
                  bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        stats_frame = tk.LabelFrame(parent, text="Revenue Statistics", bg='white', font=('Arial', 12, 'bold'))
        stats_frame.pack(fill='x', padx=10, pady=10)
        self.revenue_stats_text = tk.Text(stats_frame, height=12, bg='#f8f9fa', font=('Courier', 10))
        self.revenue_stats_text.pack(fill='x', padx=10, pady=10)

        self.revenue_chart_frame = tk.Frame(parent, bg='white')
        self.revenue_chart_frame.pack(fill='both', expand=True, padx=10, pady=10)

    def create_costs_section(self, parent):
        """Create book costs section"""
        toolbar = tk.Frame(parent, bg='white')
        toolbar.pack(fill='x', padx=10, pady=10)

        tk.Button(toolbar, text="Add Book Cost", command=self.add_book_cost_dialog,
                  bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        tk.Button(toolbar, text="Edit Cost", command=self.edit_book_cost_dialog,
                  bg=self.colors['warning'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        tk.Button(toolbar, text="Cost Analysis", command=self.show_cost_analysis,
                  bg=self.colors['info'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        tk.Button(toolbar, text=_("common.refresh"), command=self.load_book_costs,
                  bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'),
                  padx=15, pady=5).pack(side='left', padx=5)

        table_frame = tk.Frame(parent, bg='white')
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        y_scroll = ttk.Scrollbar(table_frame)
        y_scroll.pack(side='right', fill='y')
        x_scroll = ttk.Scrollbar(table_frame, orient='horizontal')
        x_scroll.pack(side='bottom', fill='x')

        columns = ('Book ID', 'Title', 'Author', 'ISBN', 'Purchase Price', 'Purchase Date', 'Supplier', 'Quantity')
        self.costs_tree = ttk.Treeview(table_frame, columns=columns, show='headings',
                                        yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        y_scroll.config(command=self.costs_tree.yview)
        x_scroll.config(command=self.costs_tree.xview)

        for col in columns:
            self.costs_tree.heading(col, text=col)
        self.costs_tree.column('Book ID', width=80, anchor='center')
        self.costs_tree.column('Title', width=200)
        self.costs_tree.column('Author', width=150)
        self.costs_tree.column('ISBN', width=120)
        self.costs_tree.column('Purchase Price', width=100, anchor='e')
        self.costs_tree.column('Purchase Date', width=100, anchor='center')
        self.costs_tree.column('Supplier', width=150)
        self.costs_tree.column('Quantity', width=80, anchor='center')
        self.costs_tree.pack(fill='both', expand=True)

        self.costs_summary_label = tk.Label(parent, text="Total Book Investment: £0.00 | Total Books: 0",
                                             font=('Arial', 11, 'bold'), bg='white', fg=self.colors['primary'])
        self.costs_summary_label.pack(pady=10)

        self.root.after(100, self.load_book_costs)

    def create_overview_section(self, parent):
        """Create financial overview section"""
        metrics_frame = tk.Frame(parent, bg='white')
        metrics_frame.pack(fill='x', padx=10, pady=10)

        self.create_metric_card(metrics_frame, "Outstanding Fines", "£0.00", self.colors['danger'])
        self.create_metric_card(metrics_frame, "Collected This Month", "£0.00", self.colors['success'])
        self.create_metric_card(metrics_frame, "Total Revenue (YTD)", "£0.00", self.colors['info'])
        self.create_metric_card(metrics_frame, "Total Refunds", "£0.00", self.colors['warning'])
        self.create_metric_card(metrics_frame, "Book Investment", "£0.00", self.colors['library'])

        self.overview_chart_frame = tk.Frame(parent, bg='white')
        self.overview_chart_frame.pack(fill='both', expand=True, padx=10, pady=10)

        tk.Button(parent, text="Refresh Overview", command=self.refresh_overview,
                  bg=self.colors['secondary'], fg='white', font=('Arial', 11, 'bold'),
                  padx=20, pady=8).pack(pady=10)

        self.root.after(100, self.refresh_overview)

    def create_metric_card(self, parent, title, value, color):
        """Create a metric display card"""
        card = tk.Frame(parent, bg=color, relief='raised', bd=2)
        card.pack(side='left', fill='both', expand=True, padx=5, pady=5)

        tk.Label(card, text=title, bg=color, fg='white', font=('Arial', 11, 'bold')).pack(pady=5)
        label = tk.Label(card, text=value, bg=color, fg='white', font=('Arial', 20, 'bold'))
        label.pack(pady=10)

        attr_name = title.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('-', '_')
        setattr(self, f"{attr_name}_label", label)

    # ==================== FINE MANAGEMENT METHODS ====================

    def load_all_fines(self):
        """Load all outstanding fines"""
        try:
            for item in self.fines_tree.get_children():
                self.fines_tree.delete(item)

            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT bl.loan_id, bl.user_id, s.first_name || ' ' || s.last_name as name,
                       bl.book_id, b.title,
                       CAST(julianday('now') - julianday(bl.due_date) as INTEGER) as days_overdue,
                       bl.fine_amount, bl.status
                FROM book_loans bl
                JOIN books b ON bl.book_id = b.book_id
                LEFT JOIN students s ON bl.user_id = s.student_id
                WHERE bl.fine_amount >= 0.01
                ORDER BY bl.fine_amount DESC
            ''')

            fines = cursor.fetchall()
            total_fines = 0
            count = 0

            for fine in fines:
                loan_id, user_id, name, book_id, title, days_overdue, fine_amount, status = fine
                total_fines += fine_amount
                count += 1
                self.fines_tree.insert('', 'end', values=(
                    loan_id, user_id, name or 'N/A', book_id, title[:40] if title else 'N/A',
                    days_overdue, f"£{fine_amount:.2f}", status
                ))

            conn.close()
            self.fines_summary_label.config(text=f"Total Outstanding Fines: £{total_fines:,.2f} | Total Items: {count}")

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to load fines:\n{str(e)}")

    def search_fines(self):
        """Search fines by user ID or name"""
        search_term = self.search_var.get().strip()
        if not search_term:
            self.load_all_fines()
            return

        try:
            for item in self.fines_tree.get_children():
                self.fines_tree.delete(item)

            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT bl.loan_id, bl.user_id, s.first_name || ' ' || s.last_name as name,
                       bl.book_id, b.title,
                       CAST(julianday('now') - julianday(bl.due_date) as INTEGER) as days_overdue,
                       bl.fine_amount, bl.status
                FROM book_loans bl
                JOIN books b ON bl.book_id = b.book_id
                LEFT JOIN students s ON bl.user_id = s.student_id
                WHERE bl.fine_amount >= 0.01
                  AND (bl.user_id LIKE ? OR s.first_name || ' ' || s.last_name LIKE ?)
                ORDER BY bl.fine_amount DESC
            ''', (f'%{search_term}%', f'%{search_term}%'))

            fines = cursor.fetchall()
            total_fines = 0
            count = 0

            for fine in fines:
                loan_id, user_id, name, book_id, title, days_overdue, fine_amount, status = fine
                total_fines += fine_amount
                count += 1
                self.fines_tree.insert('', 'end', values=(
                    loan_id, user_id, name or 'N/A', book_id, title[:40] if title else 'N/A',
                    days_overdue, f"£{fine_amount:.2f}", status
                ))

            conn.close()
            self.fines_summary_label.config(text=f"Search Results - Total Fines: £{total_fines:,.2f} | Items: {count}")

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to search fines:\n{str(e)}")

    def create_fine_dialog(self):
        """Dialog to create a new fine"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create New Fine")
        dialog.geometry("400x300")
        dialog.transient(self.root)

        tk.Label(dialog, text="Loan ID:", font=('Arial', 10)).grid(row=0, column=0, padx=10, pady=10, sticky='e')
        loan_id_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=loan_id_var, width=30).grid(row=0, column=1, padx=10, pady=10)

        tk.Label(dialog, text="Fine Amount (£):", font=('Arial', 10)).grid(row=1, column=0, padx=10, pady=10, sticky='e')
        amount_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=amount_var, width=30).grid(row=1, column=1, padx=10, pady=10)

        def create():
            loan_id = loan_id_var.get().strip()
            amount_str = amount_var.get().strip()

            if not loan_id or not amount_str:
                messagebox.showwarning("Input Required", "Please fill all fields.", parent=dialog)
                return

            try:
                amount = float(amount_str)
                if amount <= 0:
                    messagebox.showwarning("Invalid Amount", "Fine amount must be greater than 0.", parent=dialog)
                    return

                from education_system.university_system.infrastructure.database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('UPDATE book_loans SET fine_amount = ? WHERE loan_id = ?', (amount, loan_id))
                if cursor.rowcount == 0:
                    messagebox.showerror(_("common.error"), f"Loan ID {loan_id} not found.", parent=dialog)
                    conn.close()
                    return

                cursor.execute('''
                    SELECT bl.user_id, b.title, bl.due_date,
                           CAST((julianday('now') - julianday(bl.due_date)) AS INTEGER) as days_overdue
                    FROM book_loans bl JOIN books b ON bl.book_id = b.book_id WHERE bl.loan_id = ?
                ''', (loan_id,))
                loan_details = cursor.fetchone()
                conn.commit()
                conn.close()

                if loan_details:
                    user_id, book_title, due_date, days_overdue = loan_details
                    user_info = self.get_user_email(user_id)
                    if user_info:
                        self.send_fine_notification_email(user_info, amount, book_title, due_date, max(days_overdue, 0))

                messagebox.showinfo(_("common.success"), f"Fine of £{amount:.2f} created for Loan ID {loan_id}.", parent=dialog)
                dialog.destroy()
                self.load_all_fines()

            except ValueError:
                messagebox.showwarning("Invalid Input", "Please enter a valid amount.", parent=dialog)
            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to create fine:\n{str(e)}", parent=dialog)

        tk.Button(dialog, text="Create Fine", command=create, bg=self.colors['success'], fg='white',
                  font=('Arial', 10, 'bold'), padx=20, pady=8).grid(row=2, column=0, columnspan=2, pady=20)

    def edit_fine_dialog(self):
        """Dialog to edit an existing fine"""
        selection = self.fines_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a fine to edit.")
            return

        values = self.fines_tree.item(selection[0])['values']
        loan_id = values[0]
        current_amount = float(str(values[6]).replace('£', ''))

        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Fine")
        dialog.geometry("400x250")
        dialog.transient(self.root)

        tk.Label(dialog, text=f"Loan ID: {loan_id}", font=('Arial', 11, 'bold')).pack(pady=10)
        tk.Label(dialog, text=f"Current Fine: £{current_amount:.2f}", font=('Arial', 10)).pack(pady=5)
        tk.Label(dialog, text="New Fine Amount (£):", font=('Arial', 10)).pack(pady=5)
        amount_var = tk.StringVar(value=str(current_amount))
        ttk.Entry(dialog, textvariable=amount_var, width=30).pack(pady=5)

        def update():
            amount_str = amount_var.get().strip()
            if not amount_str:
                messagebox.showwarning("Input Required", "Please enter an amount.", parent=dialog)
                return
            try:
                amount = float(amount_str)
                if amount < 0:
                    messagebox.showwarning("Invalid Amount", "Fine amount cannot be negative.", parent=dialog)
                    return

                from education_system.university_system.infrastructure.database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('UPDATE book_loans SET fine_amount = ? WHERE loan_id = ?', (amount, loan_id))
                conn.commit()
                conn.close()

                messagebox.showinfo(_("common.success"), f"Fine updated to £{amount:.2f}.", parent=dialog)
                dialog.destroy()
                self.load_all_fines()
            except ValueError:
                messagebox.showwarning("Invalid Input", "Please enter a valid amount.", parent=dialog)
            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to update fine:\n{str(e)}", parent=dialog)

        tk.Button(dialog, text="Update Fine", command=update, bg=self.colors['warning'], fg='white',
                  font=('Arial', 10, 'bold'), padx=20, pady=8).pack(pady=20)

    def delete_fine(self):
        """Delete (waive) a fine"""
        selection = self.fines_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a fine to delete.")
            return

        values = self.fines_tree.item(selection[0])['values']
        loan_id = values[0]
        fine_amount = values[6]

        if not messagebox.askyesno("Confirm Deletion",
            f"Are you sure you want to waive this fine?\n\nLoan ID: {loan_id}\nAmount: {fine_amount}"):
            return

        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT bl.user_id, b.title FROM book_loans bl
                JOIN books b ON bl.book_id = b.book_id WHERE bl.loan_id = ?
            ''', (loan_id,))
            loan_details = cursor.fetchone()

            cursor.execute('UPDATE book_loans SET fine_amount = 0 WHERE loan_id = ?', (loan_id,))
            conn.commit()
            conn.close()

            if loan_details:
                user_id, book_title = loan_details
                user_info = self.get_user_email(user_id)
                fine_amount_value = float(str(fine_amount).replace('£', ''))
                if user_info:
                    self.send_fine_waived_email(user_info, fine_amount_value, book_title)

            messagebox.showinfo(_("common.success"), "Fine waived successfully.")
            self.load_all_fines()

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to delete fine:\n{str(e)}")

    def process_payment_dialog(self):
        """Dialog to process a fine payment"""
        selection = self.fines_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a fine to process payment.")
            return

        values = self.fines_tree.item(selection[0])['values']
        loan_id = values[0]
        user_id = values[1]
        fine_amount = float(str(values[6]).replace('£', ''))

        dialog = tk.Toplevel(self.root)
        dialog.title("Process Fine Payment")
        dialog.geometry("400x300")
        dialog.transient(self.root)

        tk.Label(dialog, text=f"Loan ID: {loan_id}", font=('Arial', 10, 'bold')).pack(pady=5)
        tk.Label(dialog, text=f"User ID: {user_id}", font=('Arial', 10)).pack(pady=5)
        tk.Label(dialog, text=f"Fine Amount: £{fine_amount:.2f}", font=('Arial', 10, 'bold')).pack(pady=5)

        tk.Label(dialog, text="Payment Amount (£):", font=('Arial', 10)).pack(pady=5)
        payment_var = tk.StringVar(value=str(fine_amount))
        ttk.Entry(dialog, textvariable=payment_var, width=30).pack(pady=5)

        tk.Label(dialog, text="Payment Method:", font=('Arial', 10)).pack(pady=5)
        method_var = tk.StringVar(value="Cash")
        payment_methods = ["Cash", "Card", "Bank Transfer", "Online"]
        if FINANCE_ACCOUNT_AVAILABLE:
            payment_methods.append("Finance Account")
        ttk.Combobox(dialog, textvariable=method_var, values=payment_methods,
                     state='readonly', width=28).pack(pady=5)

        # Show finance account balance if available
        if FINANCE_ACCOUNT_AVAILABLE:
            balance = get_student_finance_account_balance(user_id)
            if balance is not None:
                tk.Label(dialog, text=f"💰 Finance Account Balance: £{balance:.2f}",
                        font=('Arial', 9), fg='green').pack(pady=2)
            else:
                tk.Label(dialog, text="💰 Finance Account: Not created",
                        font=('Arial', 9), fg='gray').pack(pady=2)

        def process():
            payment_str = payment_var.get().strip()
            if not payment_str:
                messagebox.showwarning("Input Required", "Please enter payment amount.", parent=dialog)
                return
            try:
                payment_amount = float(payment_str)
                if payment_amount <= 0:
                    messagebox.showwarning("Invalid Amount", "Payment must be greater than 0.", parent=dialog)
                    return
                if payment_amount > fine_amount:
                    messagebox.showwarning("Overpayment", "Payment exceeds fine amount.", parent=dialog)
                    return

                payment_method = method_var.get()

                # Handle Finance Account payment
                if payment_method == "Finance Account":
                    if not FINANCE_ACCOUNT_AVAILABLE:
                        messagebox.showerror(_("common.error"), "Finance account not available", parent=dialog)
                        return

                    current_balance = get_student_finance_account_balance(user_id)
                    if current_balance is None:
                        create = messagebox.askyesno("No Account",
                            f"No finance account for {user_id}.\nCreate one now?", parent=dialog)
                        if create:
                            if ensure_student_finance_account_exists(user_id):
                                messagebox.showinfo("Created",
                                    "Account created with £0.00 balance.\nPlease top up first.", parent=dialog)
                            else:
                                messagebox.showerror(_("common.error"), "Failed to create account", parent=dialog)
                        return

                    if current_balance < payment_amount:
                        shortfall = payment_amount - current_balance
                        topup = messagebox.askyesno("Insufficient Balance",
                            f"Balance: £{current_balance:.2f}\nRequired: £{payment_amount:.2f}\n"
                            f"Shortfall: £{shortfall:.2f}\n\nTop up now?", parent=dialog)
                        if topup:
                            topup_amt = simpledialog.askfloat("Top Up",
                                f"Enter top-up amount (min £{shortfall:.2f}):",
                                minvalue=shortfall, initialvalue=shortfall, parent=dialog)
                            if topup_amt:
                                result = top_up_student_finance_account(
                                    student_id=user_id,
                                    amount=topup_amt,
                                    description="Top-up for library fine",
                                    payment_method="Cash/Card",
                                    processed_by=get_current_user_id()
                                )
                                if not result['success']:
                                    messagebox.showerror(_("common.error"), f"Top-up failed: {result.get('message')}", parent=dialog)
                                    return
                                current_balance = result.get('new_balance', current_balance + topup_amt)
                            else:
                                return
                        else:
                            return

                    # Process finance account payment
                    payment_result = process_student_finance_account_payment(
                        student_id=user_id,
                        amount=payment_amount,
                        description=f"Library fine payment (Loan {loan_id})",
                        transaction_source="Library",
                        transaction_ref=f"FINE_{loan_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        processed_by=get_current_user_id(),
                        check_balance=True
                    )

                    if not payment_result['success']:
                        messagebox.showerror(_("common.error"), f"Payment failed: {payment_result.get('message')}", parent=dialog)
                        return

                    new_balance = payment_result.get('new_balance', 0)

                from education_system.university_system.infrastructure.database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()
                current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                new_fine = round(fine_amount - payment_amount, 2)
                if new_fine < 0.01:
                    new_fine = 0.0

                cursor.execute('UPDATE book_loans SET fine_amount = ? WHERE loan_id = ?', (new_fine, loan_id))
                cursor.execute('''
                    INSERT INTO payments (student_id, amount, currency, payment_method, payment_date, status, notes, created_at)
                    VALUES (?, ?, 'GBP', ?, DATE('now'), 'completed', 'Library fine payment - Loan ID: ' || ?, ?)
                ''', (user_id, payment_amount, payment_method, loan_id, current_datetime))

                payment_id = cursor.lastrowid

                cursor.execute('''
                    SELECT b.title FROM book_loans bl JOIN books b ON bl.book_id = b.book_id WHERE bl.loan_id = ?
                ''', (loan_id,))
                book_result = cursor.fetchone()
                book_title = book_result[0] if book_result else "Unknown Book"

                conn.commit()
                conn.close()

                user_info = self.get_user_email(user_id)
                if user_info:
                    self.send_payment_receipt_email(user_info, fine_amount, payment_amount, payment_method,
                                                     book_title, f"LIB-{payment_id}", current_datetime)

                if payment_method == "Finance Account":
                    messagebox.showinfo(_("common.success"),
                        f"Payment of £{payment_amount:.2f} processed from Finance Account.\n"
                        f"Remaining fine: £{new_fine:.2f}\nNew balance: £{new_balance:.2f}",
                        parent=dialog)
                else:
                    messagebox.showinfo(_("common.success"),
                        f"Payment of £{payment_amount:.2f} processed successfully.\nRemaining fine: £{new_fine:.2f}",
                        parent=dialog)
                dialog.destroy()
                self.load_all_fines()

            except ValueError:
                messagebox.showwarning("Invalid Input", "Please enter a valid amount.", parent=dialog)
            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to process payment:\n{str(e)}", parent=dialog)

        tk.Button(dialog, text="Process Payment", command=process, bg=self.colors['success'], fg='white',
                  font=('Arial', 10, 'bold'), padx=20, pady=8).pack(pady=20)

    def process_refund_dialog(self):
        """Dialog to process a library fine refund"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Process Library Fine Refund")
        dialog.geometry("700x750")
        dialog.transient(self.root)

        tk.Label(dialog, text="Process Library Fine Refund", font=('Arial', 14, 'bold')).pack(pady=10)

        # Student search
        search_frame = ttk.LabelFrame(dialog, text="Find Student", padding=10)
        search_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(search_frame, text="Student ID:", font=('Arial', 10)).grid(row=0, column=0, padx=5, pady=5, sticky='w')
        student_id_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=student_id_var, width=20).grid(row=0, column=1, padx=5, pady=5)

        # Paid fines list
        fines_frame = ttk.LabelFrame(dialog, text="Paid Fines (Select to Refund)", padding=10)
        fines_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('Loan ID', 'Book ID', 'Book Title', 'Payment Date', 'Amount')
        fines_tree = ttk.Treeview(fines_frame, columns=columns, show='headings', height=6)

        for col in columns:
            fines_tree.heading(col, text=col)
        fines_tree.column('Loan ID', width=80, anchor='center')
        fines_tree.column('Book ID', width=100)
        fines_tree.column('Book Title', width=200)
        fines_tree.column('Payment Date', width=120, anchor='center')
        fines_tree.column('Amount', width=100, anchor='e')

        fines_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        def load_paid_fines():
            student_id = student_id_var.get().strip()
            if not student_id:
                messagebox.showwarning("Input Required", "Please enter a student ID", parent=dialog)
                return

            for item in fines_tree.get_children():
                fines_tree.delete(item)

            try:
                from education_system.university_system.infrastructure.database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()

                # Query the library_fine_payments table for actual paid fines
                cursor.execute('''
                    SELECT lfp.loan_id, lfp.book_id, lfp.book_title,
                           lfp.payment_date,
                           (lfp.payment_amount - COALESCE(lfp.refund_amount, 0)) as available_amount
                    FROM library_fine_payments lfp
                    WHERE lfp.user_id = ?
                    AND lfp.status = 'completed'
                    AND (lfp.payment_amount - COALESCE(lfp.refund_amount, 0)) > 0
                    ORDER BY lfp.payment_date DESC
                ''', (student_id,))

                paid_fines = cursor.fetchall()
                conn.close()

                for fine in paid_fines:
                    loan_id, book_id, title, payment_date, amount = fine
                    fines_tree.insert('', 'end', values=(
                        loan_id, book_id, title[:40] if title else 'N/A',
                        payment_date if payment_date else 'N/A', f"£{amount:.2f}"
                    ))

                if not paid_fines:
                    messagebox.showinfo("No Paid Fines", f"No paid fines found for student {student_id}", parent=dialog)
                else:
                    print(f"Loaded {len(paid_fines)} refundable payments for {student_id}")

            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to load paid fines:\n{str(e)}", parent=dialog)

        tk.Button(search_frame, text="Load Paid Fines", command=load_paid_fines,
                  bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold')).grid(row=0, column=2, padx=5, pady=5)

        # Refund details
        refund_frame = ttk.LabelFrame(dialog, text="Refund Details", padding=10)
        refund_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(refund_frame, text="Refund Amount (£):", font=('Arial', 10)).grid(row=0, column=0, padx=5, pady=5, sticky='w')
        refund_amount_var = tk.StringVar()
        ttk.Entry(refund_frame, textvariable=refund_amount_var, width=15).grid(row=0, column=1, padx=5, pady=5, sticky='w')

        tk.Label(refund_frame, text="Refund Method:", font=('Arial', 10)).grid(row=1, column=0, padx=5, pady=5, sticky='w')
        refund_method_var = tk.StringVar(value="Cash")
        ttk.Combobox(refund_frame, textvariable=refund_method_var,
                     values=["Cash", "Card", "Student Finance Account"],
                     state='readonly', width=22).grid(row=1, column=1, padx=5, pady=5, sticky='w')

        tk.Label(refund_frame, text="Refund Reason:", font=('Arial', 10)).grid(row=2, column=0, padx=5, pady=5, sticky='nw')
        reason_text = tk.Text(refund_frame, height=3, width=35)
        reason_text.grid(row=2, column=1, padx=5, pady=5)

        def process_refund():
            selection = fines_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a paid fine to refund", parent=dialog)
                return

            student_id = student_id_var.get().strip()
            refund_amount_str = refund_amount_var.get().strip()
            refund_method = refund_method_var.get()
            refund_reason = reason_text.get("1.0", tk.END).strip()

            if not all([student_id, refund_amount_str, refund_method, refund_reason]):
                messagebox.showwarning("Input Required", "Please fill all fields", parent=dialog)
                return

            try:
                refund_amount = float(refund_amount_str)
                if refund_amount <= 0:
                    messagebox.showwarning("Invalid Amount", "Refund amount must be greater than 0", parent=dialog)
                    return

                values = fines_tree.item(selection[0])['values']
                loan_id = values[0]
                book_title = values[2]

                # Process the refund
                success = self._process_library_refund(
                    student_id=student_id,
                    loan_id=loan_id,
                    refund_amount=refund_amount,
                    refund_method=refund_method,
                    refund_reason=refund_reason,
                    book_title=book_title
                )

                if success:
                    messagebox.showinfo(_("common.success"),
                        f"Refund of £{refund_amount:.2f} processed successfully!\n\n"
                        f"Method: {refund_method}\n"
                        f"Student: {student_id}", parent=dialog)
                    dialog.destroy()
                    self.load_all_fines()
                    self.refresh_overview()
                else:
                    messagebox.showerror(_("common.error"), "Failed to process refund", parent=dialog)

            except ValueError:
                messagebox.showwarning("Invalid Input", "Please enter a valid amount", parent=dialog)
            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to process refund:\n{str(e)}", parent=dialog)

        tk.Button(refund_frame, text="Process Refund", command=process_refund,
                  bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'),
                  padx=20, pady=8).grid(row=3, column=0, columnspan=2, pady=15)

    def _process_library_refund(self, student_id, loan_id, refund_amount, refund_method, refund_reason, book_title):
        """Process a library fine refund with finance integration"""
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            current_date = datetime.now().strftime('%Y-%m-%d')

            # Handle finance account refund
            if refund_method == "Student Finance Account":
                try:
                    from education_system.university_system.modules.shared.utils.finance_integration import (
                        ensure_student_finance_account_exists,
                        top_up_student_finance_account,
                        get_student_finance_account_balance
                    )

                    ensure_student_finance_account_exists(student_id)

                    result = top_up_student_finance_account(
                        student_id=student_id,
                        amount=refund_amount,
                        description=f"Library fine refund (Loan {loan_id})",
                        payment_method="Refund Credit",
                        processed_by=get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else 'System'
                    )

                    if not result or not result.get('success'):
                        conn.close()
                        return False

                except ImportError:
                    messagebox.showwarning("Not Available", "Finance account integration not available")
                    conn.close()
                    return False

            # Record refund in finance system
            try:
                from education_system.university_system.modules.shared.utils.finance_integration import record_refund_to_finance

                refund_id = record_refund_to_finance(
                    student_id=student_id,
                    refund_amount=refund_amount,
                    original_payment_id=None,
                    refund_reason=refund_reason,
                    refund_type="library_fine",
                    transaction_source="Library",
                    transaction_ref=f"FINE_REFUND_{loan_id}",
                    refund_method=refund_method.lower().replace(' ', '_'),
                    currency="GBP",
                    requested_by="Library Manager",
                    notes=f"Book: {book_title}"
                )
            except ImportError:
                refund_id = None

            # Update loan notes
            cursor.execute('SELECT notes FROM book_loans WHERE loan_id = ?', (loan_id,))
            result = cursor.fetchone()
            current_notes = result[0] if result else ""

            refund_note = f"Refund of £{refund_amount:.2f} processed on {current_date} via {refund_method}. Reason: {refund_reason}"
            updated_notes = f"{current_notes}; {refund_note}" if current_notes else refund_note

            cursor.execute('UPDATE book_loans SET notes = ? WHERE loan_id = ?', (updated_notes, loan_id))

            conn.commit()
            conn.close()

            # Send refund receipt email
            user_info = self.get_user_email(student_id)
            if user_info:
                self._send_library_refund_email(user_info, refund_amount, refund_method, book_title, refund_reason, loan_id)

            return True

        except Exception as e:
            print(f"Error processing library refund: {e}")
            import traceback
            traceback.print_exc()
            if 'conn' in locals():
                conn.close()
            return False

    def _send_library_refund_email(self, user_info, refund_amount, refund_method, book_title, refund_reason, loan_id):
        """Send refund receipt email"""
        try:
            if not user_info or not user_info.get('email'):
                return False

            # Render email from template
            from education_system.university_system.infrastructure.email.template_utils import render_template

            receipt_number = f"LIB-REFUND-{loan_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            refund_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            refund_message = f"Your student finance account has been credited with £{refund_amount:.2f}." if refund_method == "Student Finance Account" else f"Your refund has been processed using {refund_method}."

            subject, body = render_template('library/refund_receipt', {
                'student_name': user_info['full_name'],
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
                body = f"""Dear {user_info['full_name']},

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
                recipient_email=user_info['email'],
                subject=subject,
                body=body,
                system_name="Library System"
            )
            return True

        except Exception as e:
            print(f"Error sending refund email: {e}")
            return False

    # ==================== REVENUE ANALYTICS METHODS ====================

    def generate_revenue_report(self):
        """Generate revenue report for specified date range"""
        start_date = self.start_date_var.get().strip()
        end_date = self.end_date_var.get().strip()

        if not start_date or not end_date:
            messagebox.showwarning("Input Required", "Please enter both start and end dates.")
            return

        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            # Query from payments table (library fine payments) and fine_payments table
            cursor.execute('''
                SELECT COUNT(*) as payment_count,
                       SUM(amount) as total_revenue, AVG(amount) as avg_payment
                FROM (
                    SELECT payment_id, amount, payment_date FROM payments
                    WHERE (notes LIKE '%Library fine%' OR notes LIKE '%[Library]%')
                    AND DATE(payment_date) BETWEEN DATE(?) AND DATE(?)
                    UNION ALL
                    SELECT payment_id, amount, payment_date FROM fine_payments
                    WHERE DATE(payment_date) BETWEEN DATE(?) AND DATE(?)
                )
            ''', (start_date, end_date, start_date, end_date))

            stats = cursor.fetchone()
            payment_count = stats[0] or 0
            total_revenue = stats[1] or 0.0
            avg_payment = stats[2] or 0.0

            cursor.execute('''
                SELECT strftime('%Y-%m', payment_date) as month, COUNT(*) as payments, SUM(amount) as revenue
                FROM (
                    SELECT payment_id, amount, payment_date FROM payments
                    WHERE (notes LIKE '%Library fine%' OR notes LIKE '%[Library]%')
                    AND DATE(payment_date) BETWEEN DATE(?) AND DATE(?)
                    UNION ALL
                    SELECT payment_id, amount, payment_date FROM fine_payments
                    WHERE DATE(payment_date) BETWEEN DATE(?) AND DATE(?)
                )
                GROUP BY month ORDER BY month DESC
            ''', (start_date, end_date, start_date, end_date))

            monthly_data = cursor.fetchall()
            conn.close()

            self.revenue_stats_text.delete('1.0', tk.END)
            report = f"""
LIBRARY FINE REVENUE REPORT
Period: {start_date} to {end_date}
{'='*60}

SUMMARY STATISTICS:
  Total Payments Received:    {payment_count:,}
  Total Revenue:              £{total_revenue:,.2f}
  Average Payment:            £{avg_payment:,.2f}

MONTHLY BREAKDOWN:
{'='*60}
Month          Payments      Revenue
{'-'*60}
"""
            for month, payments, revenue in monthly_data:
                report += f"{month}         {payments:>8}      £{revenue:>10,.2f}\n"
            report += f"{'='*60}\n"
            self.revenue_stats_text.insert('1.0', report)

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to generate revenue report:\n{str(e)}")

    def show_revenue_charts(self):
        """Display revenue charts"""
        if not MATPLOTLIB_AVAILABLE:
            messagebox.showwarning("Not Available", "Matplotlib is not available for charts.")
            return

        start_date = self.start_date_var.get().strip()
        end_date = self.end_date_var.get().strip()

        if not start_date or not end_date:
            messagebox.showwarning("Input Required", "Please enter date range first.")
            return

        try:
            for widget in self.revenue_chart_frame.winfo_children():
                widget.destroy()

            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT strftime('%Y-%m', p.payment_date) as month, SUM(pa.amount) as revenue
                FROM payment_allocations pa
                JOIN payments p ON pa.payment_id = p.payment_id
                JOIN student_fees sf ON pa.student_fee_id = sf.student_fee_id
                WHERE sf.fee_type_id = 3 AND p.payment_date BETWEEN ? AND ?
                GROUP BY month ORDER BY month ASC
            ''', (start_date, end_date))

            monthly_data = cursor.fetchall()
            conn.close()

            if not monthly_data:
                messagebox.showinfo("No Data", "No revenue data found for the specified period.")
                return

            fig = Figure(figsize=(10, 6), dpi=100)
            ax1 = fig.add_subplot(1, 2, 1)
            months = [item[0] for item in monthly_data]
            revenues = [item[1] for item in monthly_data]

            ax1.bar(range(len(months)), revenues, color=self.colors['library'])
            ax1.set_xticks(range(len(months)))
            ax1.set_xticklabels(months, rotation=45, ha='right')
            ax1.set_ylabel('Revenue (£)', fontweight='bold')
            ax1.set_title('Monthly Library Fine Revenue', fontsize=12, fontweight='bold')

            ax2 = fig.add_subplot(1, 2, 2)
            ax2.plot(range(len(months)), revenues, marker='o', linewidth=2, color=self.colors['library'])
            ax2.set_xticks(range(len(months)))
            ax2.set_xticklabels(months, rotation=45, ha='right')
            ax2.set_ylabel('Revenue (£)', fontweight='bold')
            ax2.set_title('Revenue Trend', fontsize=12, fontweight='bold')

            fig.tight_layout()
            canvas = FigureCanvasTkAgg(fig, master=self.revenue_chart_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to create charts:\n{str(e)}")

    def export_revenue_csv(self):
        """Export revenue data to CSV"""
        start_date = self.start_date_var.get().strip()
        end_date = self.end_date_var.get().strip()

        if not start_date or not end_date:
            messagebox.showwarning("Input Required", "Please enter date range first.")
            return

        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"library_revenue_{datetime.now().strftime('%Y%m%d')}.csv"
            )
            if not filename:
                return

            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT p.payment_date, p.student_id, pa.amount, p.payment_method, p.notes
                FROM payment_allocations pa
                JOIN payments p ON pa.payment_id = p.payment_id
                JOIN student_fees sf ON pa.student_fee_id = sf.student_fee_id
                WHERE sf.fee_type_id = 3 AND p.payment_date BETWEEN ? AND ?
                ORDER BY p.payment_date DESC
            ''', (start_date, end_date))

            data = cursor.fetchall()
            conn.close()

            import csv
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Date', 'Student ID', 'Amount', 'Payment Method', 'Notes'])
                for row in data:
                    writer.writerow(row)

            messagebox.showinfo(_("common.success"), f"Revenue data exported to:\n{filename}")

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to export data:\n{str(e)}")

    # ==================== BOOK COSTS METHODS ====================

    def load_book_costs(self):
        """Load book costs from database"""
        try:
            for item in self.costs_tree.get_children():
                self.costs_tree.delete(item)

            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("PRAGMA table_info(books)")
            columns = [col[1] for col in cursor.fetchall()]

            if 'purchase_price' not in columns:
                cursor.execute('ALTER TABLE books ADD COLUMN purchase_price REAL DEFAULT 0.0')
                cursor.execute('ALTER TABLE books ADD COLUMN purchase_date TEXT')
                cursor.execute('ALTER TABLE books ADD COLUMN supplier TEXT')
                cursor.execute('ALTER TABLE books ADD COLUMN quantity INTEGER DEFAULT 1')
                conn.commit()

            cursor.execute('''
                SELECT book_id, title, author, isbn, COALESCE(purchase_price, 0.0),
                       purchase_date, supplier, COALESCE(quantity, 1)
                FROM books ORDER BY title
            ''')

            books = cursor.fetchall()
            total_cost = 0
            total_books = 0

            for book in books:
                book_id, title, author, isbn, price, date, supplier, qty = book
                total_cost += price * qty
                total_books += qty
                self.costs_tree.insert('', 'end', values=(
                    book_id, (title[:40] if title else 'N/A'), (author[:30] if author else 'N/A'),
                    isbn or 'N/A', f"£{price:.2f}", date or 'N/A', supplier or 'N/A', qty
                ))

            conn.close()
            self.costs_summary_label.config(text=f"Total Book Investment: £{total_cost:,.2f} | Total Books: {total_books}")

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to load book costs:\n{str(e)}")

    def add_book_cost_dialog(self):
        """Dialog to add book cost information"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Book Cost")
        dialog.geometry("450x400")
        dialog.transient(self.root)

        fields = [
            ("Book ID:", tk.StringVar()),
            ("Purchase Price (£):", tk.StringVar()),
            ("Purchase Date (YYYY-MM-DD):", tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))),
            ("Supplier:", tk.StringVar()),
            ("Quantity:", tk.StringVar(value="1"))
        ]

        entries = {}
        for i, (label, var) in enumerate(fields):
            tk.Label(dialog, text=label, font=('Arial', 10)).grid(row=i, column=0, padx=10, pady=10, sticky='e')
            ttk.Entry(dialog, textvariable=var, width=30).grid(row=i, column=1, padx=10, pady=10)
            entries[label] = var

        def add():
            book_id = entries["Book ID:"].get().strip()
            price_str = entries["Purchase Price (£):"].get().strip()
            date = entries["Purchase Date (YYYY-MM-DD):"].get().strip()
            supplier = entries["Supplier:"].get().strip()
            qty_str = entries["Quantity:"].get().strip()

            if not book_id or not price_str:
                messagebox.showwarning("Input Required", "Please fill required fields.", parent=dialog)
                return

            try:
                price = float(price_str)
                qty = int(qty_str) if qty_str else 1

                if price < 0 or qty < 1:
                    messagebox.showwarning("Invalid Input", "Price and quantity must be positive.", parent=dialog)
                    return

                from education_system.university_system.infrastructure.database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE books SET purchase_price = ?, purchase_date = ?, supplier = ?, quantity = ?
                    WHERE book_id = ?
                ''', (price, date, supplier, qty, book_id))

                if cursor.rowcount == 0:
                    messagebox.showerror(_("common.error"), f"Book ID {book_id} not found.", parent=dialog)
                    conn.close()
                    return

                conn.commit()
                conn.close()

                messagebox.showinfo(_("common.success"), "Book cost information added.", parent=dialog)
                dialog.destroy()
                self.load_book_costs()

            except ValueError:
                messagebox.showwarning("Invalid Input", "Please enter valid numbers.", parent=dialog)
            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to add book cost:\n{str(e)}", parent=dialog)

        tk.Button(dialog, text="Add Cost Info", command=add, bg=self.colors['success'], fg='white',
                  font=('Arial', 10, 'bold'), padx=20, pady=8).grid(row=len(fields), column=0, columnspan=2, pady=20)

    def edit_book_cost_dialog(self):
        """Dialog to edit book cost information"""
        selection = self.costs_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a book to edit.")
            return

        values = self.costs_tree.item(selection[0])['values']
        book_id = values[0]
        current_price = float(str(values[4]).replace('£', ''))

        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Book Cost")
        dialog.geometry("450x300")
        dialog.transient(self.root)

        tk.Label(dialog, text=f"Book ID: {book_id}", font=('Arial', 11, 'bold')).pack(pady=10)

        fields = [
            ("Purchase Price (£):", tk.StringVar(value=str(current_price))),
            ("Purchase Date (YYYY-MM-DD):", tk.StringVar(value=str(values[5]) if values[5] != 'N/A' else '')),
            ("Supplier:", tk.StringVar(value=str(values[6]) if values[6] != 'N/A' else '')),
            ("Quantity:", tk.StringVar(value=str(values[7])))
        ]

        entries = {}
        for label, var in fields:
            frame = tk.Frame(dialog)
            frame.pack(fill='x', padx=10, pady=5)
            tk.Label(frame, text=label, font=('Arial', 10), width=25, anchor='w').pack(side='left')
            ttk.Entry(frame, textvariable=var, width=25).pack(side='left', padx=5)
            entries[label] = var

        def update():
            price_str = entries["Purchase Price (£):"].get().strip()
            date = entries["Purchase Date (YYYY-MM-DD):"].get().strip()
            supplier = entries["Supplier:"].get().strip()
            qty_str = entries["Quantity:"].get().strip()

            try:
                price = float(price_str)
                qty = int(qty_str)

                if price < 0 or qty < 1:
                    messagebox.showwarning("Invalid Input", "Price and quantity must be positive.", parent=dialog)
                    return

                from education_system.university_system.infrastructure.database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE books SET purchase_price = ?, purchase_date = ?, supplier = ?, quantity = ?
                    WHERE book_id = ?
                ''', (price, date, supplier, qty, book_id))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("common.success"), "Book cost updated.", parent=dialog)
                dialog.destroy()
                self.load_book_costs()

            except ValueError:
                messagebox.showwarning("Invalid Input", "Please enter valid numbers.", parent=dialog)
            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to update:\n{str(e)}", parent=dialog)

        tk.Button(dialog, text="Update Cost", command=update, bg=self.colors['warning'], fg='white',
                  font=('Arial', 10, 'bold'), padx=20, pady=8).pack(pady=20)

    def show_cost_analysis(self):
        """Show book cost analysis"""
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT COUNT(*) as total_books,
                       SUM(COALESCE(purchase_price, 0) * COALESCE(quantity, 1)) as total_cost,
                       AVG(COALESCE(purchase_price, 0)) as avg_price,
                       MAX(COALESCE(purchase_price, 0)) as max_price,
                       MIN(COALESCE(purchase_price, 0)) as min_price
                FROM books
            ''')

            stats = cursor.fetchone()
            conn.close()

            total_books, total_cost, avg_price, max_price, min_price = stats

            report = f"""
BOOK COST ANALYSIS
{'='*60}

SUMMARY:
  Total Books in Collection:  {total_books:,}
  Total Investment:           £{total_cost or 0:,.2f}
  Average Book Price:         £{avg_price or 0:,.2f}
  Most Expensive Book:        £{max_price or 0:,.2f}
  Least Expensive Book:       £{min_price or 0:,.2f}

{'='*60}
"""
            messagebox.showinfo("Cost Analysis", report)

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to generate analysis:\n{str(e)}")

    # ==================== OVERVIEW METHODS ====================

    def refresh_overview(self):
        """Refresh the overview dashboard"""
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT SUM(fine_amount) FROM book_loans WHERE fine_amount >= 0.01')
            outstanding = cursor.fetchone()[0] or 0.0

            cursor.execute('''
                SELECT SUM(pa.amount)
                FROM payment_allocations pa
                JOIN payments p ON pa.payment_id = p.payment_id
                JOIN student_fees sf ON pa.student_fee_id = sf.student_fee_id
                WHERE sf.fee_type_id = 3 AND strftime('%Y-%m', p.payment_date) = strftime('%Y-%m', 'now')
            ''')
            this_month = cursor.fetchone()[0] or 0.0

            cursor.execute('''
                SELECT SUM(pa.amount)
                FROM payment_allocations pa
                JOIN payments p ON pa.payment_id = p.payment_id
                JOIN student_fees sf ON pa.student_fee_id = sf.student_fee_id
                WHERE sf.fee_type_id = 3 AND strftime('%Y', p.payment_date) = strftime('%Y', 'now')
            ''')
            ytd_revenue = cursor.fetchone()[0] or 0.0

            cursor.execute('SELECT SUM(COALESCE(purchase_price, 0) * COALESCE(quantity, 1)) FROM books')
            book_investment = cursor.fetchone()[0] or 0.0

            # Calculate total refunds from library_fine_payments table
            try:
                cursor.execute('SELECT COALESCE(SUM(refund_amount), 0) FROM library_fine_payments WHERE refund_amount > 0')
                total_refunds = cursor.fetchone()[0] or 0.0
            except Exception:
                total_refunds = 0.0  # Table might not exist yet

            conn.close()

            if hasattr(self, 'outstanding_fines_label'):
                self.outstanding_fines_label.config(text=f"£{outstanding:,.2f}")
            if hasattr(self, 'collected_this_month_label'):
                self.collected_this_month_label.config(text=f"£{this_month:,.2f}")
            if hasattr(self, 'total_revenue_ytd_label'):
                self.total_revenue_ytd_label.config(text=f"£{ytd_revenue:,.2f}")
            if hasattr(self, 'total_refunds_label'):
                self.total_refunds_label.config(text=f"£{total_refunds:,.2f}")
            if hasattr(self, 'book_investment_label'):
                self.book_investment_label.config(text=f"£{book_investment:,.2f}")

            self.create_overview_chart(outstanding, this_month, ytd_revenue, book_investment)

        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to refresh overview:\n{str(e)}")

    def create_overview_chart(self, outstanding, this_month, ytd, investment):
        """Create overview visualization"""
        if not MATPLOTLIB_AVAILABLE:
            return

        try:
            for widget in self.overview_chart_frame.winfo_children():
                widget.destroy()

            fig = Figure(figsize=(10, 6), dpi=100)

            ax1 = fig.add_subplot(1, 2, 1)
            categories = ['Outstanding Fines', 'Collected (Month)', 'YTD Revenue', 'Book Investment']
            values = [outstanding, this_month, ytd, investment]
            colors = [self.colors['danger'], self.colors['success'], self.colors['info'], self.colors['library']]

            filtered_data = [(cat, val, col) for cat, val, col in zip(categories, values, colors) if val > 0]

            if filtered_data:
                cats, vals, cols = zip(*filtered_data)
                ax1.pie(vals, labels=cats, autopct='%1.1f%%', colors=cols, startangle=90)
                ax1.set_title('Library Financial Overview', fontsize=12, fontweight='bold')
            else:
                ax1.text(0.5, 0.5, 'No Data Available', ha='center', va='center', fontsize=14)

            ax2 = fig.add_subplot(1, 2, 2)
            x_pos = range(len(categories))
            ax2.bar(x_pos, values, color=colors)
            ax2.set_xticks(x_pos)
            ax2.set_xticklabels(categories, rotation=45, ha='right', fontsize=9)
            ax2.set_ylabel('Amount (£)', fontweight='bold')
            ax2.set_title('Financial Metrics Comparison', fontsize=12, fontweight='bold')

            fig.tight_layout()
            canvas = FigureCanvasTkAgg(fig, master=self.overview_chart_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)

        except Exception as e:
            print(f"Error creating overview chart: {e}")

def get_library_settings(setting_name):
    """Get library setting value"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        cursor = conn.cursor()
        cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = ?', (setting_name,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    except (sqlite3.Error, DatabaseError) as e:
        print(f"Error getting setting {setting_name}: {e}")
        return None

def update_library_setting(setting_name, setting_value):
    """Update library setting"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        cursor.execute('''
        INSERT OR REPLACE INTO library_settings (setting_name, setting_value)
        VALUES (?, ?)
        ''', (setting_name, setting_value))
        
        conn.commit()
        conn.close()
        return True
    except (sqlite3.Error, DatabaseError) as e:
        print(f"Error updating setting {setting_name}: {e}")
        return False

def set_auth(auth_object):
    """Set global auth object for backwards compatibility"""
    global auth
    auth = auth_object
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_object)

def get_current_user_id():
    """Get current user ID"""
    if ORIGINAL_LIBRARY_AVAILABLE and 'auth' in globals() and auth and auth.current_user:
        return auth.current_user.get('user_id', 'unknown')
    return 'gui_user'

def log_audit_event(user_id, action, table_name=None, record_id=None, success=True):
    """Log audit event"""
    try:
        if not ORIGINAL_LIBRARY_AVAILABLE:
            return
            
        conn = get_db_connection()
        if not conn:
            return
            
        cursor = conn.cursor()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        user_value = user_id if user_id not in (None, "") else 'system'

        insert_attempts = [
            (
                "user_id, action, table_affected, record_id, timestamp, success",
                (user_value, action, table_name, record_id, timestamp, int(bool(success)))
            ),
            (
                "user_id, action, record_id, timestamp",
                (user_value, action, record_id, timestamp)
            ),
            (
                "action, user_id, timestamp",
                (action, user_value, timestamp)
            ),
            (
                "action, timestamp",
                (action, timestamp)
            ),
        ]

        logged = False
        for column_list, values in insert_attempts:
            placeholders = ', '.join('?' for _ in values)
            try:
                cursor.execute(
                    f"INSERT INTO audit_log ({column_list}) VALUES ({placeholders})",
                    values
                )
                logged = True
                break
            except sqlite3.OperationalError:
                continue

        if not logged:
            print("Warning: Unable to record audit event; audit_log schema not compatible.")

        conn.commit()
        conn.close()
    except (sqlite3.Error, DatabaseError, ValueError, TypeError) as e:
        print(f"Error logging audit event: {e}")

def process_scanned_barcode(barcode):
    """Process scanned barcode and return item info"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        cursor = conn.cursor()
        
        # Try to find book by barcode
        cursor.execute('''
        SELECT book_id, title, author, status, barcode
        FROM books 
        WHERE barcode = ?
        ''', (barcode,))
        
        result = cursor.fetchone()
        if result:
            book_id, title, author, status, barcode_val = result
            conn.close()
            return {
                'type': 'book',
                'id': book_id,
                'title': title,
                'author': author,
                'status': status,
                'barcode': barcode_val
            }
        
        # Try to find user by barcode (if user barcode system exists)
        cursor.execute('''
        SELECT student_id, first_name, last_name
        FROM students 
        WHERE student_id = ?
        ''', (barcode,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            student_id, first_name, last_name = result
            return {
                'type': 'user',
                'id': student_id,
                'name': f"{first_name} {last_name}",
                'barcode': barcode
            }
        
        return None
        
    except (sqlite3.Error, DatabaseError) as e:
        print(f"Error processing barcode: {e}")
        return None

def get_db_connection():
    """Get database connection - wrapper for backwards compatibility"""
    if ORIGINAL_LIBRARY_AVAILABLE:
        # This should call the original library's get_db_connection
        try:
            from library import get_db_connection as original_get_db_connection
            return original_get_db_connection()
        except ImportError:
            pass
    
    # Fallback implementation
    try:
        from education_system.university_system.infrastructure.database.db import sqlite3
        return sqlite3.connect(str(DEFAULT_DB_PATH))
    except (sqlite3.Error, DatabaseError, ValueError, TypeError) as e:
        print(f"Database connection error: {e}")
        return None

def start_gui_library_system():
    """Start the GUI library system"""
    root = tk.Tk()
    app = LibraryGUI(root)
    
    # Setup keyboard shortcuts
    setup_keyboard_shortcuts(root, app)
    
    root.mainloop()

def setup_keyboard_shortcuts(root, app):
    """Setup keyboard shortcuts"""
    # General shortcuts
    root.bind('<Control-n>', lambda e: app.show_add_book())
    root.bind('<Control-f>', lambda e: app.show_search_books())
    root.bind('<F5>', lambda e: app.refresh_books_table() if hasattr(app, 'books_tree') else None)
    root.bind('<Control-s>', lambda e: None)  # Save shortcut (context dependent)
    root.bind('<Escape>', lambda e: None)  # Cancel shortcut (context dependent)
    
    # Navigation shortcuts
    root.bind('<Control-Key-1>', lambda e: app.show_dashboard())
    root.bind('<Control-Key-2>', lambda e: app.show_all_books())
    root.bind('<Control-Key-3>', lambda e: app.show_search_books())
    root.bind('<Control-Key-4>', lambda e: app.show_reports())
    root.bind('<Control-Key-5>', lambda e: app.show_settings())

    # System shortcuts
    root.bind('<Control-b>', lambda e: app.backup_system_gui())
    root.bind('<Control-r>', lambda e: app.show_reports())

def display_library_menu_gui():
    """Display library menu in GUI mode (backwards compatible)"""
    start_gui_library_system()

def run_library_gui():
    """Run the library GUI"""
    start_gui_library_system()

def run_library_system_with_gui_option():
    """Run library system with option to choose CLI or GUI"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] in ['--gui', '-g']:
        # GUI mode
        print("Starting Library Management System - GUI Mode")
        start_gui_library_system()
    elif len(sys.argv) > 1 and sys.argv[1] in ['--cli', '-c']:
        # CLI mode
        print("Starting Library Management System - CLI Mode")
        if ORIGINAL_LIBRARY_AVAILABLE:
            display_library_menu()
        else:
            print("CLI mode requires original library module")
    else:
        # Ask user preference
        print("Enhanced Library Management System")
        print("=================================")
        print("1. GUI Mode (Recommended)")
        print("2. CLI Mode (Traditional)")
        print("3. Exit")
        
        choice = input("Choose interface (1-3): ").strip()
        
        if choice == '1':
            start_gui_library_system()
        elif choice == '2':
            if ORIGINAL_LIBRARY_AVAILABLE:
                display_library_menu()
            else:
                print("CLI mode requires original library module")
                start_gui_library_system()
        else:
            print("Goodbye!")

