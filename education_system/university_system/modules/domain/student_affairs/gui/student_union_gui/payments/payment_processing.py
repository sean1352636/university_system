import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.university_system.infrastructure.email.template_utils import render_template
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

try:
    # Import CLI components to maintain backwards compatibility. If available,
    # include the full database initializer so the GUI can create the
    # comprehensive schema when running stand‑alone.
    from education_system.university_system.infrastructure.database.db import get_connection
    from education_system.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False
    

def show_club_payments_content(self):
    """Open Club Payment Management window directly in Student Union GUI"""
    # Check if GUI was properly initialized
    if not self.initialized or not self.current_user:
        messagebox.showerror("Error", "Authentication required. Please log in.")
        return
    try:
        # Create new window for Club Payments
        payments_window = tk.Toplevel(self.root)
        payments_window.title("Club Payment Management")
        payments_window.geometry("1200x800")
        payments_window.transient(self.root)
        # Main content frame
        main_frame = ttk.Frame(payments_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        # Title
        title_label = ttk.Label(main_frame, text="Club Payment Management",
                                font=('Arial', 18, 'bold'))
        title_label.pack(pady=10)
        # Info label
        info_label = ttk.Label(main_frame,
                               text="Manage payments for student clubs and organizations",
                               font=('Arial', 10))
        info_label.pack(pady=5)
        # Create notebook for different sections
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=10)
        # Payment Overview Tab
        overview_frame = ttk.Frame(notebook)
        notebook.add(overview_frame, text="Payment Overview")
        self._create_payment_overview_tab(overview_frame)
        # Record Payment Tab
        record_frame = ttk.Frame(notebook)
        notebook.add(record_frame, text="Record Payment")
        self._create_record_payment_tab(record_frame)
        # Payment History Tab
        history_frame = ttk.Frame(notebook)
        notebook.add(history_frame, text="Payment History")
        self._create_payment_history_tab(history_frame)
        # Reports Tab
        reports_frame = ttk.Frame(notebook)
        notebook.add(reports_frame, text="Reports")
        self._create_payment_reports_tab(reports_frame)
        # Refunds Tab
        refunds_frame = ttk.Frame(notebook)
        notebook.add(refunds_frame, text="Refunds")
        self._create_refunds_tab(refunds_frame, payments_window)
        # Close button
        close_frame = ttk.Frame(payments_window)
        close_frame.pack(fill=tk.X, pady=10)
        ttk.Button(close_frame, text="Close",
                   command=payments_window.destroy).pack()
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Could not open Club Payments: {e}")


def _create_payment_overview_tab(self, parent):
    """Create payment overview tab with summary statistics"""
    # Header
    header_frame = ttk.Frame(parent)
    header_frame.pack(fill=tk.X, padx=10, pady=10)
    ttk.Label(header_frame, text="Payment Summary", font=('Arial', 12, 'bold')).pack(anchor=tk.W)
    # Stats frame
    stats_frame = ttk.LabelFrame(parent, text="Payment Statistics (Last 30 Days)")
    stats_frame.pack(fill=tk.X, padx=10, pady=10)
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        # Get payment statistics from payments table (club source)
        cursor.execute('''
            SELECT COUNT(*), SUM(amount), AVG(amount), COUNT(DISTINCT reference_id)
            FROM payments
            WHERE source_type = 'club'
              AND payment_date >= date('now', '-30 days')
        ''')
        count, total, avg, clubs_count = cursor.fetchone()
        # Display stats in grid
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(stats_grid, text="Total Payments:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(stats_grid, text=str(count or 0)).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Label(stats_grid, text="Total Amount:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(stats_grid, text=f"£{total or 0:.2f}").grid(row=1, column=1, sticky=tk.W, padx=5)
        ttk.Label(stats_grid, text="Average Payment:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(stats_grid, text=f"£{avg or 0:.2f}").grid(row=2, column=1, sticky=tk.W, padx=5)
        ttk.Label(stats_grid, text="Clubs with Payments:", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(stats_grid, text=str(clubs_count or 0)).grid(row=3, column=1, sticky=tk.W, padx=5)
        conn.close()
    except (sqlite3.Error, tk.TclError) as e:
        ttk.Label(stats_frame, text=f"Error loading statistics: {e}").pack(padx=10, pady=10)
    # Recent payments frame
    recent_frame = ttk.LabelFrame(parent, text="Recent Payments")
    recent_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    # Create treeview for recent payments
    columns = ('Date', 'Club', 'Type', 'Amount', 'Status')
    tree = ttk.Treeview(recent_frame, columns=columns, show='headings', height=10)
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=120)
    tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    # Add scrollbar
    scrollbar = ttk.Scrollbar(recent_frame, orient=tk.VERTICAL, command=tree.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    tree.configure(yscrollcommand=scrollbar.set)
    # Load recent payments
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        # Get recent club payments from payments table
        cursor.execute('''
            SELECT
                cp.payment_date,
                sc.club_name,
                cp.payment_type,
                cp.amount,
                cp.status
            FROM payments cp
            LEFT JOIN student_clubs sc ON CAST(cp.reference_id AS INTEGER) = sc.club_id
            WHERE cp.source_type = 'club'
            ORDER BY cp.payment_date DESC
            LIMIT 20
        ''')
        for row in cursor.fetchall():
            tree.insert('', tk.END, values=row)
        conn.close()
    except sqlite3.Error as e:
        print(f"Error loading recent payments: {e}")


def _create_record_payment_tab(self, parent):
    """Create tab for recording new club payments"""
    # Header
    header_frame = ttk.Frame(parent)
    header_frame.pack(fill=tk.X, padx=10, pady=10)
    ttk.Label(header_frame, text="Record New Payment", font=('Arial', 12, 'bold')).pack(anchor=tk.W)
    # Form frame
    form_frame = ttk.LabelFrame(parent, text="Payment Details")
    form_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    # Club Selection
    ttk.Label(form_frame, text="Club:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
    club_var = tk.StringVar()
    club_combo = ttk.Combobox(form_frame, textvariable=club_var, width=28, state='readonly')
    # Load clubs with IDs
    club_data = []
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute('SELECT club_id, club_name FROM student_clubs WHERE status = "active" ORDER BY club_name')
        club_data = cursor.fetchall()
        club_combo['values'] = [f"{club[0]} - {club[1]}" for club in club_data]
        conn.close()
    except sqlite3.Error:
        pass
    club_combo.grid(row=0, column=1, padx=10, pady=5)
    # Amount
    ttk.Label(form_frame, text="Amount (£):").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
    amount_var = tk.StringVar()
    ttk.Entry(form_frame, textvariable=amount_var, width=30).grid(row=1, column=1, padx=10, pady=5)
    # Payment Type
    ttk.Label(form_frame, text="Payment Type:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
    payment_type_var = tk.StringVar()
    payment_type_combo = ttk.Combobox(form_frame, textvariable=payment_type_var, width=28, state='readonly')
    payment_type_combo['values'] = ('membership_fee', 'event_fee', 'donation', 'merchandise', 'other')
    payment_type_combo.current(0)
    payment_type_combo.grid(row=2, column=1, padx=10, pady=5)
    # Payment Method
    ttk.Label(form_frame, text="Payment Method:").grid(row=3, column=0, sticky=tk.W, padx=10, pady=5)
    payment_method_var = tk.StringVar()
    payment_method_combo = ttk.Combobox(form_frame, textvariable=payment_method_var, width=28, state='readonly')
    payment_method_combo['values'] = ('cash', 'card', 'bank_transfer', 'online')
    payment_method_combo.current(0)
    payment_method_combo.grid(row=3, column=1, padx=10, pady=5)
    # Student ID (optional)
    ttk.Label(form_frame, text="Student ID (optional):").grid(row=4, column=0, sticky=tk.W, padx=10, pady=5)
    student_id_var = tk.StringVar()
    ttk.Entry(form_frame, textvariable=student_id_var, width=30).grid(row=4, column=1, padx=10, pady=5)
    # Description
    ttk.Label(form_frame, text="Description:").grid(row=5, column=0, sticky=tk.W, padx=10, pady=5)
    description_var = tk.StringVar()
    ttk.Entry(form_frame, textvariable=description_var, width=30).grid(row=5, column=1, padx=10, pady=5)
    # Notes
    ttk.Label(form_frame, text="Notes:").grid(row=6, column=0, sticky=tk.W, padx=10, pady=5)
    notes_text = tk.Text(form_frame, width=30, height=3)
    notes_text.grid(row=6, column=1, padx=10, pady=5)
    # Button frame
    button_frame = ttk.Frame(parent)
    button_frame.pack(fill=tk.X, padx=10, pady=10)
    def record_payment():
        """Record the payment to payments table with source_type='club'"""
        try:
            if not club_var.get():
                messagebox.showerror("Error", "Please select a club")
                return
            if not amount_var.get():
                messagebox.showerror("Error", "Please enter an amount")
                return
            try:
                amount = float(amount_var.get().strip())
                if amount <= 0:
                    messagebox.showerror("Error", "Amount must be greater than 0")
                    return
            except ValueError:
                messagebox.showerror("Error", "Invalid amount")
                return
            # Extract club_id from combo selection
            club_id = int(club_var.get().split(' - ')[0])
            # Get current user
            processed_by = self.current_user.get('username', 'Unknown') if self.current_user else 'Unknown'
            # Insert into payments with source_type='club'
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO payments
                    (source_type, reference_id, reference_type, amount, payment_type,
                     payment_method, payment_date, student_id, description, notes,
                     processed_by, status)
                    VALUES ('club', ?, 'club', ?, ?, ?, datetime('now'), ?, ?, ?, ?, 'completed')
                ''', (
                    str(club_id),
                    amount,
                    payment_type_var.get(),
                    payment_method_var.get(),
                    student_id_var.get().strip() or None,
                    description_var.get().strip() or None,
                    notes_text.get('1.0', tk.END).strip() or None,
                    processed_by
                ))
                conn.commit()
            finally:
                conn.close()
            messagebox.showinfo("Success", f"Payment of £{amount:.2f} recorded successfully!")
            # Clear form
            club_combo.set('')
            amount_var.set('')
            payment_type_combo.current(0)
            payment_method_combo.current(0)
            student_id_var.set('')
            description_var.set('')
            notes_text.delete('1.0', tk.END)
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to record payment: {e}")
    ttk.Button(button_frame, text="Record Payment", command=record_payment).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Clear Form",
              command=lambda: [club_combo.set(''), amount_var.set(''),
                              payment_type_combo.current(0), payment_method_combo.current(0),
                              student_id_var.set(''), description_var.set(''),
                              notes_text.delete('1.0', tk.END)]).pack(side=tk.LEFT, padx=5)


def _create_payment_history_tab(self, parent):
    """Create tab for viewing payment history"""
    # Header
    header_frame = ttk.Frame(parent)
    header_frame.pack(fill=tk.X, padx=10, pady=10)
    ttk.Label(header_frame, text="Payment History", font=('Arial', 12, 'bold')).pack(anchor=tk.W)
    # Filter frame
    filter_frame = ttk.LabelFrame(parent, text="Filters")
    filter_frame.pack(fill=tk.X, padx=10, pady=10)
    filter_grid = ttk.Frame(filter_frame)
    filter_grid.pack(fill=tk.X, padx=10, pady=10)
    # Club filter
    ttk.Label(filter_grid, text="Club:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
    filter_club_var = tk.StringVar()
    filter_club_combo = ttk.Combobox(filter_grid, textvariable=filter_club_var, width=20, state='readonly')
    filter_club_combo['values'] = ['All']
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute('SELECT club_name FROM student_clubs ORDER BY club_name')
        clubs = ['All'] + [row[0] for row in cursor.fetchall()]
        filter_club_combo['values'] = clubs
        conn.close()
    except sqlite3.Error:
        pass
    filter_club_combo.set('All')
    filter_club_combo.grid(row=0, column=1, padx=5, pady=5)
    # Payment Type filter
    ttk.Label(filter_grid, text="Payment Type:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
    filter_type_var = tk.StringVar()
    filter_type_combo = ttk.Combobox(filter_grid, textvariable=filter_type_var, width=18, state='readonly')
    filter_type_combo['values'] = ('All', 'membership_fee', 'event_fee', 'donation', 'merchandise', 'other')
    filter_type_combo.set('All')
    filter_type_combo.grid(row=0, column=3, padx=5, pady=5)
    # Payment history treeview
    history_frame = ttk.LabelFrame(parent, text="Payment Records")
    history_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    columns = ('ID', 'Date', 'Club', 'Amount', 'Type', 'Method', 'Description', 'Status')
    tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=15)
    for col in columns:
        tree.heading(col, text=col)
        if col == 'Description':
            tree.column(col, width=200)
        elif col == 'Club':
            tree.column(col, width=150)
        else:
            tree.column(col, width=100)
    tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    # Add scrollbars
    v_scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=tree.yview)
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    h_scrollbar = ttk.Scrollbar(history_frame, orient=tk.HORIZONTAL, command=tree.xview)
    h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
    tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
    def load_payment_history():
        """Load payment history with filters"""
        # Clear existing items
        for item in tree.get_children():
            tree.delete(item)
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            query = '''
                SELECT cp.payment_id, cp.payment_date, sc.club_name,
                       cp.amount, cp.payment_type, cp.payment_method,
                       cp.description, cp.status
                FROM payments cp
                LEFT JOIN student_clubs sc ON CAST(cp.reference_id AS INTEGER) = sc.club_id
                WHERE cp.source_type = 'club'
            '''
            params = []
            # Apply filters
            club_filter = filter_club_var.get()
            if club_filter and club_filter != 'All':
                query += ' AND sc.club_name = ?'
                params.append(club_filter)
            type_filter = filter_type_var.get()
            if type_filter and type_filter != 'All':
                query += ' AND cp.payment_type = ?'
                params.append(type_filter)
            query += ' ORDER BY cp.payment_date DESC LIMIT 500'
            cursor.execute(query, params)
            for row in cursor.fetchall():
                tree.insert('', tk.END, values=row)
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Error loading payment history: {e}")
    # Load button
    button_frame = ttk.Frame(filter_frame)
    button_frame.pack(fill=tk.X, padx=10, pady=5)
    ttk.Button(button_frame, text="Apply Filters", command=load_payment_history).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Clear Filters",
              command=lambda: [filter_club_var.set('All'), filter_type_var.set('All'), load_payment_history()]).pack(side=tk.LEFT, padx=5)
    # Load initial data
    load_payment_history()


def _create_payment_reports_tab(self, parent):
    """Create tab for payment reports and analytics"""
    # Header
    header_frame = ttk.Frame(parent)
    header_frame.pack(fill=tk.X, padx=10, pady=10)
    ttk.Label(header_frame, text="Payment Reports & Analytics", font=('Arial', 12, 'bold')).pack(anchor=tk.W)
    # Report options frame
    options_frame = ttk.LabelFrame(parent, text="Report Options")
    options_frame.pack(fill=tk.X, padx=10, pady=10)
    options_grid = ttk.Frame(options_frame)
    options_grid.pack(fill=tk.X, padx=10, pady=10)
    # Report type
    ttk.Label(options_grid, text="Report Type:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
    report_type_var = tk.StringVar()
    report_type_combo = ttk.Combobox(options_grid, textvariable=report_type_var, width=25, state='readonly')
    report_type_combo['values'] = ('By Club', 'By Payment Type', 'By Payment Method', 'Monthly Summary')
    report_type_combo.set('By Club')
    report_type_combo.grid(row=0, column=1, padx=5, pady=5)
    # Results frame
    results_frame = ttk.LabelFrame(parent, text="Report Results")
    results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD, height=20)
    results_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    def generate_report():
        """Generate selected report"""
        results_text.delete('1.0', tk.END)
        report_type = report_type_var.get()
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            if report_type == 'By Club':
                cursor.execute('''
                    SELECT sc.club_name, COUNT(*) as count, SUM(cp.amount) as total
                    FROM payments cp
                    LEFT JOIN student_clubs sc ON CAST(cp.reference_id AS INTEGER) = sc.club_id
                    WHERE cp.source_type = 'club'
                    GROUP BY cp.reference_id
                    ORDER BY total DESC
                ''')
                results_text.insert('1.0', "PAYMENT REPORT BY CLUB\n")
                results_text.insert(tk.END, "=" * 60 + "\n\n")
                results_text.insert(tk.END, f"{'Club':<30} {'Count':<10} {'Total':<15}\n")
                results_text.insert(tk.END, "-" * 60 + "\n")
                for club, count, total in cursor.fetchall():
                    club_name = club or 'Unknown Club'
                    results_text.insert(tk.END, f"{club_name:<30} {count:<10} £{total or 0:>12.2f}\n")
            elif report_type == 'By Payment Type':
                cursor.execute('''
                    SELECT cp.payment_type, COUNT(*), SUM(cp.amount)
                    FROM payments cp
                    WHERE cp.source_type = 'club'
                    GROUP BY cp.payment_type
                    ORDER BY SUM(cp.amount) DESC
                ''')
                results_text.insert('1.0', "PAYMENT REPORT BY TYPE\n")
                results_text.insert(tk.END, "=" * 60 + "\n\n")
                results_text.insert(tk.END, f"{'Type':<30} {'Count':<10} {'Total':<15}\n")
                results_text.insert(tk.END, "-" * 60 + "\n")
                for payment_type, count, total in cursor.fetchall():
                    results_text.insert(tk.END, f"{payment_type:<30} {count:<10} £{total or 0:>12.2f}\n")
            elif report_type == 'By Payment Method':
                cursor.execute('''
                    SELECT cp.payment_method, COUNT(*), SUM(cp.amount)
                    FROM payments cp
                    WHERE cp.source_type = 'club'
                    GROUP BY cp.payment_method
                    ORDER BY SUM(cp.amount) DESC
                ''')
                results_text.insert('1.0', "PAYMENT REPORT BY METHOD\n")
                results_text.insert(tk.END, "=" * 60 + "\n\n")
                results_text.insert(tk.END, f"{'Method':<30} {'Count':<10} {'Total':<15}\n")
                results_text.insert(tk.END, "-" * 60 + "\n")
                for method, count, total in cursor.fetchall():
                    results_text.insert(tk.END, f"{method:<30} {count:<10} £{total or 0:>12.2f}\n")
            elif report_type == 'Monthly Summary':
                cursor.execute('''
                    SELECT strftime('%Y-%m', cp.payment_date) as month,
                           COUNT(*), SUM(cp.amount)
                    FROM payments cp
                    WHERE cp.source_type = 'club'
                    GROUP BY month
                    ORDER BY month DESC
                    LIMIT 12
                ''')
                results_text.insert('1.0', "MONTHLY PAYMENT SUMMARY\n")
                results_text.insert(tk.END, "=" * 60 + "\n\n")
                results_text.insert(tk.END, f"{'Month':<15} {'Count':<10} {'Total':<15}\n")
                results_text.insert(tk.END, "-" * 60 + "\n")
                for month, count, total in cursor.fetchall():
                    results_text.insert(tk.END, f"{month or 'N/A':<15} {count:<10} £{total or 0:>12.2f}\n")
            conn.close()
        except sqlite3.Error as e:
            results_text.insert('1.0', f"Error generating report: {e}")
    def export_to_csv():
        """Export report data to CSV"""
        from tkinter import filedialog
        import csv
        report_type = report_var.get()
        if not report_type:
            messagebox.showwarning("Warning", "Please select a report type first")
            return
        file_path = filedialog.asksaveasfilename(
            title="Export Report to CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"payment_report_{report_type.lower().replace(' ', '_')}"
        )
        if not file_path:
            return
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                if report_type == 'By Club':
                    cursor.execute('''
                        SELECT sc.club_name, COUNT(*), SUM(cp.amount)
                        FROM payments cp
                        LEFT JOIN student_clubs sc ON CAST(cp.reference_id AS INTEGER) = sc.club_id
                        WHERE cp.source_type = 'club'
                        GROUP BY sc.club_name
                        ORDER BY SUM(cp.amount) DESC
                    ''')
                    writer.writerow(['Club Name', 'Payment Count', 'Total Amount'])
                    for club, count, total in cursor.fetchall():
                        writer.writerow([club or 'Unknown Club', count, f"{total or 0:.2f}"])
                elif report_type == 'By Payment Type':
                    cursor.execute('''
                        SELECT cp.payment_type, COUNT(*), SUM(cp.amount)
                        FROM payments cp
                        WHERE cp.source_type = 'club'
                        GROUP BY cp.payment_type
                        ORDER BY SUM(cp.amount) DESC
                    ''')
                    writer.writerow(['Payment Type', 'Count', 'Total Amount'])
                    for payment_type, count, total in cursor.fetchall():
                        writer.writerow([payment_type, count, f"{total or 0:.2f}"])
                elif report_type == 'By Payment Method':
                    cursor.execute('''
                        SELECT cp.payment_method, COUNT(*), SUM(cp.amount)
                        FROM payments cp
                        WHERE cp.source_type = 'club'
                        GROUP BY cp.payment_method
                        ORDER BY SUM(cp.amount) DESC
                    ''')
                    writer.writerow(['Payment Method', 'Count', 'Total Amount'])
                    for method, count, total in cursor.fetchall():
                        writer.writerow([method, count, f"{total or 0:.2f}"])
                elif report_type == 'Monthly Summary':
                    cursor.execute('''
                        SELECT strftime('%Y-%m', cp.payment_date) as month,
                               COUNT(*), SUM(cp.amount)
                        FROM payments cp
                        WHERE cp.source_type = 'club'
                        GROUP BY month
                        ORDER BY month DESC
                        LIMIT 12
                    ''')
                    writer.writerow(['Month', 'Payment Count', 'Total Amount'])
                    for month, count, total in cursor.fetchall():
                        writer.writerow([month or 'N/A', count, f"{total or 0:.2f}"])
            conn.close()
            messagebox.showinfo("Success", f"Report exported successfully to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export CSV: {e}")
    # Button frame
    button_frame = ttk.Frame(options_frame)
    button_frame.pack(fill=tk.X, padx=10, pady=5)
    ttk.Button(button_frame, text="Generate Report", command=generate_report).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Export to CSV", command=export_to_csv).pack(side=tk.LEFT, padx=5)


def _create_refunds_tab(self, parent, payments_window):
    """Create refunds management tab with payment list and refund processing"""
    # Header
    header_frame = ttk.Frame(parent)
    header_frame.pack(fill=tk.X, padx=10, pady=10)
    ttk.Label(header_frame, text="Payment Refunds", font=('Arial', 12, 'bold')).pack(anchor=tk.W)

    # Search/Filter frame
    search_frame = ttk.LabelFrame(parent, text="Search Payments", padding="10")
    search_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

    ttk.Label(search_frame, text="Student ID or Club Name:").grid(row=0, column=0, sticky=tk.W, padx=5)
    search_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
    search_entry.grid(row=0, column=1, padx=5)

    # Payments list frame
    list_frame = ttk.LabelFrame(parent, text="All Student Union Payments", padding="5")
    list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    columns = ('payment_id', 'date', 'student_id', 'club', 'type', 'amount', 'method', 'status')
    payments_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

    payments_tree.heading('payment_id', text='ID')
    payments_tree.heading('date', text='Date')
    payments_tree.heading('student_id', text='Student ID')
    payments_tree.heading('club', text='Club')
    payments_tree.heading('type', text='Type')
    payments_tree.heading('amount', text='Amount (GBP)')
    payments_tree.heading('method', text='Payment Method')
    payments_tree.heading('status', text='Status')

    payments_tree.column('payment_id', width=50)
    payments_tree.column('date', width=100)
    payments_tree.column('student_id', width=100)
    payments_tree.column('club', width=150)
    payments_tree.column('type', width=120)
    payments_tree.column('amount', width=80)
    payments_tree.column('method', width=100)
    payments_tree.column('status', width=80)

    # Add scrollbar
    scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=payments_tree.yview)
    payments_tree.configure(yscrollcommand=scrollbar.set)

    payments_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def refresh_payments_list():
        """Refresh the payments list from database"""
        for item in payments_tree.get_children():
            payments_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            search_term = search_var.get().strip()
            if search_term:
                cursor.execute('''
                    SELECT
                        cp.payment_id,
                        cp.payment_date,
                        cp.student_id,
                        COALESCE(sc.club_name, 'N/A') as club_name,
                        cp.payment_type,
                        cp.amount,
                        cp.payment_method,
                        cp.status
                    FROM payments cp
                    LEFT JOIN student_clubs sc ON CAST(cp.reference_id AS INTEGER) = sc.club_id
                    WHERE cp.source_type = 'club'
                      AND (cp.student_id LIKE ? OR sc.club_name LIKE ?)
                    ORDER BY cp.payment_date DESC
                ''', (f'%{search_term}%', f'%{search_term}%'))
            else:
                cursor.execute('''
                    SELECT
                        cp.payment_id,
                        cp.payment_date,
                        cp.student_id,
                        COALESCE(sc.club_name, 'N/A') as club_name,
                        cp.payment_type,
                        cp.amount,
                        cp.payment_method,
                        cp.status
                    FROM payments cp
                    LEFT JOIN student_clubs sc ON CAST(cp.reference_id AS INTEGER) = sc.club_id
                    WHERE cp.source_type = 'club'
                    ORDER BY cp.payment_date DESC
                    LIMIT 100
                ''')

            for row in cursor.fetchall():
                # Ensure all values are present
                values = list(row)
                while len(values) < 8:
                    values.append('N/A')
                # Format amount
                if values[5] and values[5] != 'N/A':
                    try:
                        values[5] = f"{float(values[5]):.2f}"
                    except (ValueError, TypeError):
                        pass
                payments_tree.insert('', tk.END, values=values)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load payments: {e}")

    def view_payment_details():
        """View detailed payment information"""
        selection = payments_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a payment to view details")
            return

        try:
            values = payments_tree.item(selection[0])['values']
            if len(values) < 8:
                messagebox.showerror("Data Error", "Payment record is incomplete")
                return

            details = f"""PAYMENT DETAILS
==================
Payment ID: {values[0]}
Date: {values[1]}
Student ID: {values[2]}
Club: {values[3]}
Type: {values[4]}
Amount: GBP {values[5]}
Payment Method: {values[6]}
Status: {values[7]}
"""
            messagebox.showinfo("Payment Details", details)
        except Exception as e:
            messagebox.showerror("Error", f"Error viewing payment details: {e}")

    def export_payments_csv():
        """Export payments to CSV file"""
        try:
            from tkinter import filedialog
            import csv

            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"union_payments_{datetime.now().strftime('%Y%m%d')}.csv"
            )

            if filepath:
                with open(filepath, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Payment ID', 'Date', 'Student ID', 'Club',
                                   'Type', 'Amount', 'Method', 'Status'])

                    for item in payments_tree.get_children():
                        values = payments_tree.item(item)['values']
                        writer.writerow(values)

                messagebox.showinfo("Export Successful", f"Payments exported to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export payments: {e}")

    def process_refund():
        """Process a refund with cash/card/student account options"""
        selection = payments_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a payment to refund")
            return

        try:
            values = payments_tree.item(selection[0])['values']
            if len(values) < 8:
                messagebox.showerror("Data Error", "Payment record is incomplete")
                return

            payment_id = values[0]
            payment_date = values[1]
            student_id = values[2]
            club_name = values[3]
            payment_type = values[4]
            amount = float(values[5])
            payment_method = values[6]
            status = values[7]
        except (IndexError, ValueError) as e:
            messagebox.showerror("Error", f"Error reading payment data: {e}")
            return

        if status == 'refunded':
            messagebox.showinfo("Already Refunded", "This payment has already been refunded")
            return

        # Confirm refund
        if not messagebox.askyesno("Confirm Refund",
                                   f"Refund GBP {amount:.2f} to {student_id}?\n\n"
                                   f"Payment ID: {payment_id}\n"
                                   f"Club: {club_name}\n"
                                   f"Type: {payment_type}"):
            return

        # Show refund method selection dialog
        refund_method = show_refund_method_dialog(amount, student_id, payments_window)
        if not refund_method:
            return

        # Process based on method
        success = False
        if refund_method == 'Student Account':
            success = add_to_student_account(student_id, amount, payment_id)
        else:
            # For cash/card, just record the refund
            success = True

        if success:
            # Update payment status to refunded
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE payments
                    SET status = 'refunded'
                    WHERE payment_id = ? AND source_type = 'club'
                ''', (payment_id,))

                # Generate refund reference
                import uuid
                refund_ref = f"UNION-REFUND-{uuid.uuid4().hex[:12].upper()}"

                # Record refund transaction
                cursor.execute('''
                    INSERT INTO payments
                    (source_type, student_id, reference_id, reference_type,
                     payment_type, amount, payment_method,
                     payment_date, status, notes)
                    SELECT 'club', student_id, reference_id, 'club',
                           ?, ?, ?, date('now'), 'completed', ?
                    FROM payments WHERE payment_id = ? AND source_type = 'club'
                ''', (f'refund_{payment_type}', amount, refund_method.lower().replace(' ', '_'),
                      f'Refund for payment {payment_id}', payment_id))

                conn.commit()
                conn.close()

                # Send refund receipt email
                send_refund_receipt(student_id, amount, refund_method, payment_id, refund_ref, club_name)

                # Notify finance GUI
                notify_finance_gui(student_id, amount, refund_method, refund_ref)

                messagebox.showinfo("Refund Processed",
                                  f"Refund of GBP {amount:.2f} processed successfully\n\n"
                                  f"Method: {refund_method}\n"
                                  f"Refund Reference: {refund_ref}")

                refresh_payments_list()
            except Exception as e:
                messagebox.showerror("Refund Error", f"Failed to process refund: {e}")
        else:
            messagebox.showerror("Refund Failed", "Failed to process student account refund")

    # Button frame
    button_frame = ttk.Frame(parent)
    button_frame.pack(fill=tk.X, padx=10)

    ttk.Button(button_frame, text="Search", command=refresh_payments_list).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Show All",
              command=lambda: [search_var.set(''), refresh_payments_list()]).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Process Refund", command=process_refund).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="View Details", command=view_payment_details).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Export to CSV", command=export_payments_csv).pack(side=tk.LEFT, padx=5)

    # Initial load
    refresh_payments_list()


def show_refund_method_dialog(amount: float, student_id: str, parent_window) -> Optional[str]:
    """Show refund method selection dialog"""
    dialog = tk.Toplevel(parent_window)
    dialog.title("Select Refund Method")
    dialog.geometry("450x400")
    dialog.transient(parent_window)
    dialog.grab_set()

    result = {'method': None}

    # Refund info frame
    info_frame = ttk.LabelFrame(dialog, text="Refund Details", padding="10")
    info_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Label(info_frame, text=f"Student ID: {student_id}").pack(anchor=tk.W)
    ttk.Label(info_frame, text=f"Refund Amount: GBP {amount:.2f}",
             font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=(5, 0))

    # Student account balance
    balance = get_student_account_balance_for_user(student_id)
    if balance is not None:
        ttk.Label(info_frame, text=f"Current Account Balance: GBP {balance:.2f}").pack(
            anchor=tk.W, pady=(5, 0))
        ttk.Label(info_frame, text=f"Balance After Refund: GBP {balance + amount:.2f}",
                 foreground='green').pack(anchor=tk.W)

    # Refund method selection
    method_frame = ttk.LabelFrame(dialog, text="Select Refund Method", padding="10")
    method_frame.pack(fill=tk.X, padx=10, pady=10)

    def select_method(method):
        result['method'] = method
        dialog.destroy()

    # Cash button
    ttk.Button(method_frame, text="Cash", width=30,
              command=lambda: select_method('Cash')).pack(pady=5)

    # Card button
    ttk.Button(method_frame, text="Card (Original Payment Method)", width=30,
              command=lambda: select_method('Card')).pack(pady=5)

    # Student Account button
    ttk.Button(method_frame, text="Student Finance Account", width=30,
              command=lambda: select_method('Student Account')).pack(pady=5)

    # Cancel button
    ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack(pady=10)

    dialog.wait_window()
    return result['method']


def get_student_account_balance_for_user(student_id: str) -> Optional[float]:
    """Get student's finance account balance by student ID"""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute('''
            SELECT balance FROM student_finance_accounts
            WHERE student_id = ? AND account_status = 'active'
        ''', (student_id,))
        row = cursor.fetchone()
        conn.close()
        return float(row[0]) if row else None
    except Exception as e:
        print(f"Error getting student balance: {e}")
        return None


def add_to_student_account(student_id: str, amount: float, payment_ref: str) -> bool:
    """Add refund amount to student's finance account"""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        # Get account_id and balance
        cursor.execute('''
            SELECT account_id, balance FROM student_finance_accounts
            WHERE student_id = ? AND account_status = 'active'
        ''', (student_id,))
        row = cursor.fetchone()

        if not row:
            # Try to create account if it doesn't exist
            cursor.execute('''
                INSERT INTO student_finance_accounts
                (student_id, account_type, balance, account_status, created_at)
                VALUES (?, 'standard', ?, 'active', CURRENT_TIMESTAMP)
            ''', (student_id, amount))
            account_id = cursor.lastrowid
            balance_before = 0
            balance_after = amount
        else:
            account_id = row[0]
            balance_before = float(row[1])
            balance_after = balance_before + amount

            # Add to balance
            cursor.execute('''
                UPDATE student_finance_accounts
                SET balance = ?, updated_at = CURRENT_TIMESTAMP
                WHERE account_id = ?
            ''', (balance_after, account_id))

        # Record transaction
        cursor.execute('''
            INSERT INTO transactions
            (source_type, account_id, student_id, transaction_type, amount, balance_before,
             balance_after, description, created_at)
            VALUES ('student_finance', ?, ?, 'credit', ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (account_id, student_id, amount, balance_before, balance_after,
              f'Student Union Refund - Payment: {payment_ref}'))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding to student account: {e}")
        return False


def send_refund_receipt(student_id: str, amount: float, method: str,
                       payment_id: int, refund_ref: str, club_name: str):
    """Send refund receipt email to student"""
    try:
        # Get student email
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM users WHERE username = ?", (student_id,))
        row = cursor.fetchone()
        email = row[0] if row and row[0] else None
        conn.close()

        if email:
            try:
                from education_system.university_system.infrastructure.email.email_service import send_email

                # Build account balance info
                account_balance_info = ""
                if method == 'Student Account':
                    balance = get_student_account_balance_for_user(student_id)
                    if balance is not None:
                        account_balance_info = f"\nYour new Student Finance Account balance: GBP {balance:.2f}\n\n"

                subject, body = render_template('student_union/payment_refund_receipt', {
                    'student_id': student_id,
                    'refund_ref': refund_ref,
                    'payment_id': payment_id,
                    'club_name': club_name,
                    'amount': f'{amount:.2f}',
                    'method': method,
                    'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'account_balance_info': account_balance_info
                })

                send_email(email, subject, body)
                print(f"[Student Union] Refund receipt sent to {email}")
            except Exception as e:
                print(f"Error sending email: {e}")
        else:
            print(f"[Student Union] No email found for student {student_id}")
    except Exception as e:
        print(f"Error sending refund receipt: {e}")


def notify_finance_gui(student_id: str, amount: float, method: str, refund_ref: str):
    """Record refund in unified refunds table for finance integration"""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        # Insert into unified_refunds table
        try:
            cursor.execute('''
                INSERT INTO unified_refunds
                (refund_reference, source_type, reference_type, student_id,
                 amount, refund_method, refund_date, processed_by, notes, status)
                VALUES (?, 'student_union', 'payment', ?, ?, ?, date('now'),
                        'student_union', 'Student Union Payment Refund', 'completed')
            ''', (refund_ref, student_id, amount, method))
            conn.commit()
            print(f"[Student Union] Refund recorded in unified_refunds: {refund_ref}")
        except sqlite3.Error:
            # Table might not exist yet, that's okay
            pass

        conn.close()
    except Exception as e:
        print(f"Error notifying finance GUI: {e}")


