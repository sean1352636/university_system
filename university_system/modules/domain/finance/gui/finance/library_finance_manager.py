"""Library Finance Manager - Comprehensive library financial operations"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import pandas as pd
import csv
from typing import Optional

from university_system.infrastructure.database.db import get_connection
from university_system.infrastructure.email.email_service import send_email_as_system


class LibraryFinanceManager:
    """Manages all library-related financial operations"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.conn = gui.conn

        # Color scheme matching Finance GUI
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

    # ==================== EMAIL NOTIFICATION HELPERS ====================

    def get_user_email(self, user_id):
        """Get user email address from database"""
        try:
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

            subject = "Library Fine Notice - Overdue Book"

            body = f"""Dear {user_info['full_name']},

This is to notify you that a library fine has been assessed on your account.

FINE DETAILS:
═══════════════════════════════════════════════
Book Title:      {book_title}
Due Date:        {due_date}
Days Overdue:    {days_overdue}
Fine Amount:     £{fine_amount:.2f}
═══════════════════════════════════════════════

Please return the book and pay the fine at your earliest convenience. You can:
• Visit the library circulation desk
• Pay online through your student portal
• Contact the library for payment arrangements

If you have already returned this book, please contact the library immediately.

For questions or assistance, please contact:
University Library - Circulation Desk
Email: library@university.edu
Phone: (555) 123-4567

Thank you,
University Library System
"""

            # Send email as "Library System"
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

            subject = "Library Fine Payment Receipt"

            body = f"""Dear {user_info['full_name']},

Thank you for your payment. This email confirms your library fine payment.

PAYMENT RECEIPT
═══════════════════════════════════════════════
Receipt Number:  {transaction_id}
Payment Date:    {payment_date}
Payment Method:  {payment_method}
═══════════════════════════════════════════════

FINE DETAILS:
Book Title:      {book_title}
Original Fine:   £{fine_amount:.2f}
Amount Paid:     £{payment_amount:.2f}
═══════════════════════════════════════════════

Your payment has been processed successfully. Your library account is now in good standing.

Please keep this receipt for your records. If you have any questions about this payment,
please contact us with your receipt number.

For questions or assistance, please contact:
University Library - Circulation Desk
Email: library@university.edu
Phone: (555) 123-4567

Thank you for using our library services.

Best regards,
University Library System
"""

            # Send email as "Library System"
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

            subject = "Library Fine Waived - Good News!"

            body = f"""Dear {user_info['full_name']},

Good news! A library fine on your account has been waived.

WAIVED FINE DETAILS:
═══════════════════════════════════════════════
Book Title:      {book_title}
Fine Amount:     £{fine_amount:.2f}
Reason:          {waiver_reason}
Status:          WAIVED - No payment required
═══════════════════════════════════════════════

This fine has been removed from your account and no payment is required.
Your library account is now in good standing.

If you have any questions about this waiver, please feel free to contact us.

For questions or assistance, please contact:
University Library - Circulation Desk
Email: library@university.edu
Phone: (555) 123-4567

Thank you for using our library services.

Best regards,
University Library System
"""

            # Send email as "Library System"
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

    # ==================== TAB CREATION ====================

    def create_library_finance_tab(self):
        """Create the Library Finance tab with all library financial operations"""
        # Create main frame for this tab
        library_frame = tk.Frame(self.gui.layout.content_frame, bg='white')
        self.gui.layout.tab_frames['library_finance'] = library_frame

        # Title
        title_label = tk.Label(
            library_frame,
            text="📚 Library Finance Management",
            font=('Arial', 18, 'bold'),
            bg='white'
        )
        title_label.pack(pady=10)

        # Create notebook for different sections
        notebook = ttk.Notebook(library_frame)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Tab 1: Fine Management
        fines_tab = tk.Frame(notebook, bg='white')
        notebook.add(fines_tab, text="📋 Fine Management")
        self.create_fines_section(fines_tab)

        # Tab 2: Revenue Analytics
        revenue_tab = tk.Frame(notebook, bg='white')
        notebook.add(revenue_tab, text="💰 Revenue Analytics")
        self.create_revenue_section(revenue_tab)

        # Tab 3: Book Costs
        costs_tab = tk.Frame(notebook, bg='white')
        notebook.add(costs_tab, text="📖 Book Costs")
        self.create_costs_section(costs_tab)

        # Tab 4: Financial Overview
        overview_tab = tk.Frame(notebook, bg='white')
        notebook.add(overview_tab, text="📊 Overview")
        self.create_overview_section(overview_tab)

    def create_fines_section(self, parent):
        """Create fine management section with CRUD operations"""
        # Toolbar
        toolbar = tk.Frame(parent, bg='white')
        toolbar.pack(fill='x', padx=10, pady=10)

        tk.Label(toolbar, text="Search User:", bg='white', font=('Arial', 10)).pack(side='left', padx=5)
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=20)
        search_entry.pack(side='left', padx=5)

        tk.Button(
            toolbar,
            text="🔍 Search",
            command=self.search_fines,
            bg=self.colors['secondary'],
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5
        ).pack(side='left', padx=5)

        tk.Button(
            toolbar,
            text="➕ Create Fine",
            command=self.create_fine_dialog,
            bg=self.colors['success'],
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5
        ).pack(side='left', padx=5)

        tk.Button(
            toolbar,
            text="✏️ Edit Fine",
            command=self.edit_fine_dialog,
            bg=self.colors['warning'],
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5
        ).pack(side='left', padx=5)

        tk.Button(
            toolbar,
            text="🗑️ Delete Fine",
            command=self.delete_fine,
            bg=self.colors['danger'],
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5
        ).pack(side='left', padx=5)

        tk.Button(
            toolbar,
            text="💳 Process Payment",
            command=self.process_payment_dialog,
            bg=self.colors['library'],
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5
        ).pack(side='left', padx=5)

        tk.Button(
            toolbar,
            text="🔄 Refresh",
            command=self.load_all_fines,
            bg=self.colors['info'],
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5
        ).pack(side='left', padx=5)

        # Fines table
        table_frame = tk.Frame(parent, bg='white')
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Scrollbars
        y_scroll = ttk.Scrollbar(table_frame)
        y_scroll.pack(side='right', fill='y')

        x_scroll = ttk.Scrollbar(table_frame, orient='horizontal')
        x_scroll.pack(side='bottom', fill='x')

        # Treeview
        columns = ('Loan ID', 'User ID', 'Name', 'Book ID', 'Title', 'Days Overdue', 'Fine Amount', 'Status')
        self.fines_tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show='headings',
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set
        )

        y_scroll.config(command=self.fines_tree.yview)
        x_scroll.config(command=self.fines_tree.xview)

        # Configure columns
        self.fines_tree.heading('Loan ID', text='Loan ID')
        self.fines_tree.heading('User ID', text='User ID')
        self.fines_tree.heading('Name', text='Name')
        self.fines_tree.heading('Book ID', text='Book ID')
        self.fines_tree.heading('Title', text='Book Title')
        self.fines_tree.heading('Days Overdue', text='Days Overdue')
        self.fines_tree.heading('Fine Amount', text='Fine Amount')
        self.fines_tree.heading('Status', text='Status')

        self.fines_tree.column('Loan ID', width=80, anchor='center')
        self.fines_tree.column('User ID', width=100)
        self.fines_tree.column('Name', width=150)
        self.fines_tree.column('Book ID', width=100)
        self.fines_tree.column('Title', width=200)
        self.fines_tree.column('Days Overdue', width=100, anchor='center')
        self.fines_tree.column('Fine Amount', width=100, anchor='e')
        self.fines_tree.column('Status', width=100, anchor='center')

        self.fines_tree.pack(fill='both', expand=True)

        # Summary
        self.fines_summary_label = tk.Label(
            parent,
            text="Total Outstanding Fines: £0.00 | Total Items: 0",
            font=('Arial', 11, 'bold'),
            bg='white',
            fg=self.colors['primary']
        )
        self.fines_summary_label.pack(pady=10)

        # Load initial data
        self.root.after(100, self.load_all_fines)

    def create_revenue_section(self, parent):
        """Create revenue analytics section"""
        # Toolbar with date filters
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

        tk.Button(
            toolbar,
            text="📊 Generate Report",
            command=self.generate_revenue_report,
            bg=self.colors['secondary'],
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5
        ).pack(side='left', padx=5)

        tk.Button(
            toolbar,
            text="📈 Show Charts",
            command=self.show_revenue_charts,
            bg=self.colors['info'],
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5
        ).pack(side='left', padx=5)

        tk.Button(
            toolbar,
            text="💾 Export CSV",
            command=self.export_revenue_csv,
            bg=self.colors['success'],
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5
        ).pack(side='left', padx=5)

        # Revenue statistics panel
        stats_frame = tk.LabelFrame(parent, text="Revenue Statistics", bg='white', font=('Arial', 12, 'bold'))
        stats_frame.pack(fill='x', padx=10, pady=10)

        self.revenue_stats_text = tk.Text(stats_frame, height=12, bg='#f8f9fa', font=('Courier', 10))
        self.revenue_stats_text.pack(fill='x', padx=10, pady=10)

        # Chart area
        chart_label = tk.Label(parent, text="Revenue Visualizations", bg='white', font=('Arial', 12, 'bold'))
        chart_label.pack(pady=5)

        self.revenue_chart_frame = tk.Frame(parent, bg='white')
        self.revenue_chart_frame.pack(fill='both', expand=True, padx=10, pady=10)

    def create_costs_section(self, parent):
        """Create book costs section"""
        # Toolbar
        toolbar = tk.Frame(parent, bg='white')
        toolbar.pack(fill='x', padx=10, pady=10)

        tk.Button(
            toolbar,
            text="➕ Add Book Cost",
            command=self.add_book_cost_dialog,
            bg=self.colors['success'],
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5
        ).pack(side='left', padx=5)

        tk.Button(
            toolbar,
            text="✏️ Edit Cost",
            command=self.edit_book_cost_dialog,
            bg=self.colors['warning'],
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5
        ).pack(side='left', padx=5)

        tk.Button(
            toolbar,
            text="📊 Cost Analysis",
            command=self.show_cost_analysis,
            bg=self.colors['info'],
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5
        ).pack(side='left', padx=5)

        tk.Button(
            toolbar,
            text="🔄 Refresh",
            command=self.load_book_costs,
            bg=self.colors['secondary'],
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5
        ).pack(side='left', padx=5)

        # Book costs table
        table_frame = tk.Frame(parent, bg='white')
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Scrollbars
        y_scroll = ttk.Scrollbar(table_frame)
        y_scroll.pack(side='right', fill='y')

        x_scroll = ttk.Scrollbar(table_frame, orient='horizontal')
        x_scroll.pack(side='bottom', fill='x')

        # Treeview
        columns = ('Book ID', 'Title', 'Author', 'ISBN', 'Purchase Price', 'Purchase Date', 'Supplier', 'Quantity')
        self.costs_tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show='headings',
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set
        )

        y_scroll.config(command=self.costs_tree.yview)
        x_scroll.config(command=self.costs_tree.xview)

        # Configure columns
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

        # Summary
        self.costs_summary_label = tk.Label(
            parent,
            text="Total Book Investment: £0.00 | Total Books: 0",
            font=('Arial', 11, 'bold'),
            bg='white',
            fg=self.colors['primary']
        )
        self.costs_summary_label.pack(pady=10)

        # Load initial data
        self.root.after(100, self.load_book_costs)

    def create_overview_section(self, parent):
        """Create financial overview section"""
        # Key metrics
        metrics_frame = tk.Frame(parent, bg='white')
        metrics_frame.pack(fill='x', padx=10, pady=10)

        # Create metric cards
        self.create_metric_card(metrics_frame, "Outstanding Fines", "£0.00", self.colors['danger'])
        self.create_metric_card(metrics_frame, "Collected This Month", "£0.00", self.colors['success'])
        self.create_metric_card(metrics_frame, "Total Revenue (YTD)", "£0.00", self.colors['info'])
        self.create_metric_card(metrics_frame, "Book Investment", "£0.00", self.colors['library'])

        # Charts
        charts_frame = tk.Frame(parent, bg='white')
        charts_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.overview_chart_frame = tk.Frame(charts_frame, bg='white')
        self.overview_chart_frame.pack(fill='both', expand=True)

        # Refresh button
        tk.Button(
            parent,
            text="🔄 Refresh Overview",
            command=self.refresh_overview,
            bg=self.colors['secondary'],
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=20,
            pady=8
        ).pack(pady=10)

        # Load initial data
        self.root.after(100, self.refresh_overview)

    def create_metric_card(self, parent, title, value, color):
        """Create a metric display card"""
        card = tk.Frame(parent, bg=color, relief='raised', bd=2)
        card.pack(side='left', fill='both', expand=True, padx=5, pady=5)

        tk.Label(
            card,
            text=title,
            bg=color,
            fg='white',
            font=('Arial', 11, 'bold')
        ).pack(pady=5)

        label = tk.Label(
            card,
            text=value,
            bg=color,
            fg='white',
            font=('Arial', 20, 'bold')
        )
        label.pack(pady=10)

        # Store label for updating (remove parentheses and special chars)
        attr_name = title.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('-', '_')
        setattr(self, f"{attr_name}_label", label)

    # ==================== FINE MANAGEMENT METHODS ====================

    def load_all_fines(self):
        """Load all outstanding fines"""
        try:
            # Clear existing data
            for item in self.fines_tree.get_children():
                self.fines_tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()

            # Get all fines with student information
            cursor.execute('''
                SELECT
                    bl.loan_id,
                    bl.user_id,
                    s.first_name || ' ' || s.last_name as name,
                    bl.book_id,
                    b.title,
                    CAST(julianday('now') - julianday(bl.due_date) as INTEGER) as days_overdue,
                    bl.fine_amount,
                    bl.status
                FROM book_loans bl
                JOIN books b ON bl.book_id = b.book_id
                LEFT JOIN students s ON bl.user_id = s.student_id
                WHERE bl.fine_amount > 0
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
                    loan_id,
                    user_id,
                    name or 'N/A',
                    book_id,
                    title[:40],
                    days_overdue,
                    f"£{fine_amount:.2f}",
                    status
                ))

            conn.close()

            # Update summary
            self.fines_summary_label.config(
                text=f"Total Outstanding Fines: £{total_fines:,.2f} | Total Items: {count}"
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load fines:\n{str(e)}")

    def search_fines(self):
        """Search fines by user ID or name"""
        search_term = self.search_var.get().strip()

        if not search_term:
            self.load_all_fines()
            return

        try:
            # Clear existing data
            for item in self.fines_tree.get_children():
                self.fines_tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()

            # Search by user ID or name
            cursor.execute('''
                SELECT
                    bl.loan_id,
                    bl.user_id,
                    s.first_name || ' ' || s.last_name as name,
                    bl.book_id,
                    b.title,
                    CAST(julianday('now') - julianday(bl.due_date) as INTEGER) as days_overdue,
                    bl.fine_amount,
                    bl.status
                FROM book_loans bl
                JOIN books b ON bl.book_id = b.book_id
                LEFT JOIN students s ON bl.user_id = s.student_id
                WHERE bl.fine_amount > 0
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
                    loan_id,
                    user_id,
                    name or 'N/A',
                    book_id,
                    title[:40],
                    days_overdue,
                    f"£{fine_amount:.2f}",
                    status
                ))

            conn.close()

            # Update summary
            self.fines_summary_label.config(
                text=f"Search Results - Total Fines: £{total_fines:,.2f} | Items: {count}"
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to search fines:\n{str(e)}")

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

                conn = get_connection()
                cursor = conn.cursor()

                # Update the loan with the fine
                cursor.execute('''
                    UPDATE book_loans
                    SET fine_amount = ?
                    WHERE loan_id = ?
                ''', (amount, loan_id))

                if cursor.rowcount == 0:
                    messagebox.showerror("Error", f"Loan ID {loan_id} not found.", parent=dialog)
                    conn.close()
                    return

                # Get loan details for email notification
                cursor.execute('''
                    SELECT bl.user_id, b.title, bl.due_date,
                           CAST((julianday('now') - julianday(bl.due_date)) AS INTEGER) as days_overdue
                    FROM book_loans bl
                    JOIN books b ON bl.book_id = b.book_id
                    WHERE bl.loan_id = ?
                ''', (loan_id,))
                loan_details = cursor.fetchone()

                conn.commit()
                conn.close()

                # Send email notification to user
                if loan_details:
                    user_id, book_title, due_date, days_overdue = loan_details
                    user_info = self.get_user_email(user_id)

                    if user_info:
                        email_sent = self.send_fine_notification_email(
                            user_info=user_info,
                            fine_amount=amount,
                            book_title=book_title,
                            due_date=due_date,
                            days_overdue=days_overdue if days_overdue > 0 else 0
                        )

                        if email_sent:
                            messagebox.showinfo("Success",
                                f"Fine of £{amount:.2f} created for Loan ID {loan_id}.\n\n"
                                f"Email notification sent to {user_info['email']}",
                                parent=dialog)
                        else:
                            messagebox.showinfo("Success",
                                f"Fine of £{amount:.2f} created for Loan ID {loan_id}.\n\n"
                                f"Note: Email notification could not be sent.",
                                parent=dialog)
                    else:
                        messagebox.showinfo("Success",
                            f"Fine of £{amount:.2f} created for Loan ID {loan_id}.\n\n"
                            f"Note: User email not found.",
                            parent=dialog)
                else:
                    messagebox.showinfo("Success", f"Fine of £{amount:.2f} created for Loan ID {loan_id}.", parent=dialog)

                dialog.destroy()
                self.load_all_fines()

            except ValueError:
                messagebox.showwarning("Invalid Input", "Please enter a valid amount.", parent=dialog)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create fine:\n{str(e)}", parent=dialog)

        tk.Button(
            dialog,
            text="Create Fine",
            command=create,
            bg=self.colors['success'],
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=20,
            pady=8
        ).grid(row=2, column=0, columnspan=2, pady=20)

    def edit_fine_dialog(self):
        """Dialog to edit an existing fine"""
        selection = self.fines_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a fine to edit.")
            return

        # Get selected fine
        values = self.fines_tree.item(selection[0])['values']
        loan_id = values[0]
        current_amount = float(values[6].replace('£', ''))

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

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE book_loans
                    SET fine_amount = ?
                    WHERE loan_id = ?
                ''', (amount, loan_id))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Fine updated to £{amount:.2f}.", parent=dialog)
                dialog.destroy()
                self.load_all_fines()

            except ValueError:
                messagebox.showwarning("Invalid Input", "Please enter a valid amount.", parent=dialog)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update fine:\n{str(e)}", parent=dialog)

        tk.Button(
            dialog,
            text="Update Fine",
            command=update,
            bg=self.colors['warning'],
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=20,
            pady=8
        ).pack(pady=20)

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
            conn = get_connection()
            cursor = conn.cursor()

            # Get loan details for email notification
            cursor.execute('''
                SELECT bl.user_id, b.title
                FROM book_loans bl
                JOIN books b ON bl.book_id = b.book_id
                WHERE bl.loan_id = ?
            ''', (loan_id,))
            loan_details = cursor.fetchone()

            cursor.execute('''
                UPDATE book_loans
                SET fine_amount = 0
                WHERE loan_id = ?
            ''', (loan_id,))

            conn.commit()
            conn.close()

            # Send waived fine notification email
            if loan_details:
                user_id, book_title = loan_details
                user_info = self.get_user_email(user_id)

                # Extract fine amount (remove £ symbol)
                fine_amount_value = float(fine_amount.replace('£', ''))

                if user_info:
                    email_sent = self.send_fine_waived_email(
                        user_info=user_info,
                        fine_amount=fine_amount_value,
                        book_title=book_title,
                        waiver_reason="Fine waived by library administration"
                    )

                    if email_sent:
                        messagebox.showinfo("Success",
                            f"Fine waived successfully.\n\n"
                            f"Email notification sent to {user_info['email']}")
                    else:
                        messagebox.showinfo("Success",
                            "Fine waived successfully.\n\n"
                            "Note: Email notification could not be sent.")
                else:
                    messagebox.showinfo("Success", "Fine waived successfully.")
            else:
                messagebox.showinfo("Success", "Fine waived successfully.")

            self.load_all_fines()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete fine:\n{str(e)}")

    def process_payment_dialog(self):
        """Dialog to process a fine payment"""
        selection = self.fines_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a fine to process payment.")
            return

        values = self.fines_tree.item(selection[0])['values']
        loan_id = values[0]
        user_id = values[1]
        fine_amount = float(values[6].replace('£', ''))

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
        methods = ["Cash", "Card", "Bank Transfer", "Online"]
        ttk.Combobox(dialog, textvariable=method_var, values=methods, state='readonly', width=28).pack(pady=5)

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

                conn = get_connection()
                cursor = conn.cursor()
                current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Reduce fine amount
                new_fine = fine_amount - payment_amount

                cursor.execute('''
                    UPDATE book_loans
                    SET fine_amount = ?
                    WHERE loan_id = ?
                ''', (new_fine, loan_id))

                # Record payment in finance system
                cursor.execute('''
                    INSERT INTO payments
                    (student_id, amount, currency, payment_method, payment_date, status, notes, created_at)
                    VALUES (?, ?, 'GBP', ?, DATE('now'), 'completed', 'Library fine payment - Loan ID: ' || ?, ?)
                ''', (user_id, payment_amount, method_var.get(), loan_id, current_datetime))

                payment_id = cursor.lastrowid

                # Link to student fee if exists
                cursor.execute('''
                    SELECT student_fee_id FROM student_fees
                    WHERE student_id = ? AND fee_type_id = 3 AND status = 'unpaid'
                    ORDER BY created_at DESC LIMIT 1
                ''', (user_id,))

                fee_record = cursor.fetchone()
                if fee_record:
                    cursor.execute('''
                        INSERT INTO payment_allocations
                        (payment_id, student_fee_id, amount, created_at)
                        VALUES (?, ?, ?, ?)
                    ''', (payment_id, fee_record[0], payment_amount, current_datetime))

                # Get book details for email receipt
                cursor.execute('''
                    SELECT b.title
                    FROM book_loans bl
                    JOIN books b ON bl.book_id = b.book_id
                    WHERE bl.loan_id = ?
                ''', (loan_id,))
                book_result = cursor.fetchone()
                book_title = book_result[0] if book_result else "Unknown Book"

                conn.commit()
                conn.close()

                # Send payment receipt email
                user_info = self.get_user_email(user_id)
                if user_info:
                    email_sent = self.send_payment_receipt_email(
                        user_info=user_info,
                        fine_amount=fine_amount,
                        payment_amount=payment_amount,
                        payment_method=method_var.get(),
                        book_title=book_title,
                        transaction_id=f"LIB-{payment_id}",
                        payment_date=current_datetime
                    )

                    if email_sent:
                        messagebox.showinfo("Success",
                            f"Payment of £{payment_amount:.2f} processed successfully.\n"
                            f"Remaining fine: £{new_fine:.2f}\n\n"
                            f"Receipt sent to {user_info['email']}", parent=dialog)
                    else:
                        messagebox.showinfo("Success",
                            f"Payment of £{payment_amount:.2f} processed successfully.\n"
                            f"Remaining fine: £{new_fine:.2f}\n\n"
                            f"Note: Receipt email could not be sent.", parent=dialog)
                else:
                    messagebox.showinfo("Success",
                        f"Payment of £{payment_amount:.2f} processed successfully.\n"
                        f"Remaining fine: £{new_fine:.2f}", parent=dialog)

                dialog.destroy()
                self.load_all_fines()

            except ValueError:
                messagebox.showwarning("Invalid Input", "Please enter a valid amount.", parent=dialog)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to process payment:\n{str(e)}", parent=dialog)

        tk.Button(
            dialog,
            text="Process Payment",
            command=process,
            bg=self.colors['success'],
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=20,
            pady=8
        ).pack(pady=20)

    # ==================== REVENUE ANALYTICS METHODS ====================

    def generate_revenue_report(self):
        """Generate revenue report for specified date range"""
        start_date = self.start_date_var.get().strip()
        end_date = self.end_date_var.get().strip()

        if not start_date or not end_date:
            messagebox.showwarning("Input Required", "Please enter both start and end dates.")
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get fine payments from payment_allocations linked to library fees
            cursor.execute('''
                SELECT
                    COUNT(DISTINCT p.payment_id) as payment_count,
                    SUM(pa.amount) as total_revenue,
                    AVG(pa.amount) as avg_payment
                FROM payment_allocations pa
                JOIN payments p ON pa.payment_id = p.payment_id
                JOIN student_fees sf ON pa.student_fee_id = sf.student_fee_id
                WHERE sf.fee_type_id = 3
                  AND p.payment_date BETWEEN ? AND ?
            ''', (start_date, end_date))

            stats = cursor.fetchone()
            payment_count = stats[0] or 0
            total_revenue = stats[1] or 0.0
            avg_payment = stats[2] or 0.0

            # Get monthly breakdown
            cursor.execute('''
                SELECT
                    strftime('%Y-%m', p.payment_date) as month,
                    COUNT(p.payment_id) as payments,
                    SUM(pa.amount) as revenue
                FROM payment_allocations pa
                JOIN payments p ON pa.payment_id = p.payment_id
                JOIN student_fees sf ON pa.student_fee_id = sf.student_fee_id
                WHERE sf.fee_type_id = 3
                  AND p.payment_date BETWEEN ? AND ?
                GROUP BY month
                ORDER BY month DESC
            ''', (start_date, end_date))

            monthly_data = cursor.fetchall()
            conn.close()

            # Display report
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
            messagebox.showerror("Error", f"Failed to generate revenue report:\n{str(e)}")

    def show_revenue_charts(self):
        """Display revenue charts"""
        start_date = self.start_date_var.get().strip()
        end_date = self.end_date_var.get().strip()

        if not start_date or not end_date:
            messagebox.showwarning("Input Required", "Please enter date range first.")
            return

        try:
            # Clear existing charts
            for widget in self.revenue_chart_frame.winfo_children():
                widget.destroy()

            conn = get_connection()
            cursor = conn.cursor()

            # Get monthly data
            cursor.execute('''
                SELECT
                    strftime('%Y-%m', p.payment_date) as month,
                    SUM(pa.amount) as revenue
                FROM payment_allocations pa
                JOIN payments p ON pa.payment_id = p.payment_id
                JOIN student_fees sf ON pa.student_fee_id = sf.student_fee_id
                WHERE sf.fee_type_id = 3
                  AND p.payment_date BETWEEN ? AND ?
                GROUP BY month
                ORDER BY month ASC
            ''', (start_date, end_date))

            monthly_data = cursor.fetchall()
            conn.close()

            if not monthly_data:
                messagebox.showinfo("No Data", "No revenue data found for the specified period.")
                return

            # Create charts
            fig = Figure(figsize=(10, 6), dpi=100)

            # Bar chart
            ax1 = fig.add_subplot(1, 2, 1)
            months = [item[0] for item in monthly_data]
            revenues = [item[1] for item in monthly_data]

            bars = ax1.bar(range(len(months)), revenues, color=self.colors['library'])
            ax1.set_xticks(range(len(months)))
            ax1.set_xticklabels(months, rotation=45, ha='right')
            ax1.set_ylabel('Revenue (£)', fontweight='bold')
            ax1.set_title('Monthly Library Fine Revenue', fontsize=12, fontweight='bold')
            ax1.grid(axis='y', alpha=0.3)

            # Add value labels
            for bar in bars:
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width() / 2., height,
                        f'£{height:.0f}', ha='center', va='bottom', fontsize=8)

            # Line chart (trend)
            ax2 = fig.add_subplot(1, 2, 2)
            ax2.plot(range(len(months)), revenues, marker='o', linewidth=2,
                    color=self.colors['library'], markersize=8)
            ax2.set_xticks(range(len(months)))
            ax2.set_xticklabels(months, rotation=45, ha='right')
            ax2.set_ylabel('Revenue (£)', fontweight='bold')
            ax2.set_title('Revenue Trend', fontsize=12, fontweight='bold')
            ax2.grid(True, alpha=0.3)

            fig.tight_layout()

            # Embed in tkinter
            canvas = FigureCanvasTkAgg(fig, master=self.revenue_chart_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create charts:\n{str(e)}")

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

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT
                    p.payment_date,
                    p.student_id,
                    pa.amount,
                    p.payment_method,
                    p.notes
                FROM payment_allocations pa
                JOIN payments p ON pa.payment_id = p.payment_id
                JOIN student_fees sf ON pa.student_fee_id = sf.student_fee_id
                WHERE sf.fee_type_id = 3
                  AND p.payment_date BETWEEN ? AND ?
                ORDER BY p.payment_date DESC
            ''', (start_date, end_date))

            data = cursor.fetchall()
            conn.close()

            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Date', 'Student ID', 'Amount', 'Payment Method', 'Notes'])
                for row in data:
                    writer.writerow(row)

            messagebox.showinfo("Success", f"Revenue data exported to:\n{filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export data:\n{str(e)}")

    # ==================== BOOK COSTS METHODS ====================

    def load_book_costs(self):
        """Load book costs from database"""
        try:
            # Clear existing data
            for item in self.costs_tree.get_children():
                self.costs_tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()

            # Check if purchase_price column exists in books table
            cursor.execute("PRAGMA table_info(books)")
            columns = [col[1] for col in cursor.fetchall()]

            if 'purchase_price' not in columns:
                # Need to add column
                cursor.execute('ALTER TABLE books ADD COLUMN purchase_price REAL DEFAULT 0.0')
                cursor.execute('ALTER TABLE books ADD COLUMN purchase_date TEXT')
                cursor.execute('ALTER TABLE books ADD COLUMN supplier TEXT')
                cursor.execute('ALTER TABLE books ADD COLUMN quantity INTEGER DEFAULT 1')
                conn.commit()

            # Get book costs
            cursor.execute('''
                SELECT
                    book_id,
                    title,
                    author,
                    isbn,
                    COALESCE(purchase_price, 0.0),
                    purchase_date,
                    supplier,
                    COALESCE(quantity, 1)
                FROM books
                ORDER BY title
            ''')

            books = cursor.fetchall()
            total_cost = 0
            total_books = 0

            for book in books:
                book_id, title, author, isbn, price, date, supplier, qty = book
                total_cost += price * qty
                total_books += qty

                self.costs_tree.insert('', 'end', values=(
                    book_id,
                    title[:40],
                    author[:30] if author else 'N/A',
                    isbn or 'N/A',
                    f"£{price:.2f}",
                    date or 'N/A',
                    supplier or 'N/A',
                    qty
                ))

            conn.close()

            # Update summary
            self.costs_summary_label.config(
                text=f"Total Book Investment: £{total_cost:,.2f} | Total Books: {total_books}"
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load book costs:\n{str(e)}")

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
            entry = ttk.Entry(dialog, textvariable=var, width=30)
            entry.grid(row=i, column=1, padx=10, pady=10)
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

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE books
                    SET purchase_price = ?, purchase_date = ?, supplier = ?, quantity = ?
                    WHERE book_id = ?
                ''', (price, date, supplier, qty, book_id))

                if cursor.rowcount == 0:
                    messagebox.showerror("Error", f"Book ID {book_id} not found.", parent=dialog)
                    conn.close()
                    return

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Book cost information added.", parent=dialog)
                dialog.destroy()
                self.load_book_costs()

            except ValueError:
                messagebox.showwarning("Invalid Input", "Please enter valid numbers.", parent=dialog)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add book cost:\n{str(e)}", parent=dialog)

        tk.Button(
            dialog,
            text="Add Cost Info",
            command=add,
            bg=self.colors['success'],
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=20,
            pady=8
        ).grid(row=len(fields), column=0, columnspan=2, pady=20)

    def edit_book_cost_dialog(self):
        """Dialog to edit book cost information"""
        selection = self.costs_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a book to edit.")
            return

        values = self.costs_tree.item(selection[0])['values']
        book_id = values[0]
        current_price = float(values[4].replace('£', ''))

        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Book Cost")
        dialog.geometry("450x300")
        dialog.transient(self.root)

        tk.Label(dialog, text=f"Book ID: {book_id}", font=('Arial', 11, 'bold')).pack(pady=10)

        fields = [
            ("Purchase Price (£):", tk.StringVar(value=str(current_price))),
            ("Purchase Date (YYYY-MM-DD):", tk.StringVar(value=values[5])),
            ("Supplier:", tk.StringVar(value=values[6])),
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

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE books
                    SET purchase_price = ?, purchase_date = ?, supplier = ?, quantity = ?
                    WHERE book_id = ?
                ''', (price, date, supplier, qty, book_id))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Book cost updated.", parent=dialog)
                dialog.destroy()
                self.load_book_costs()

            except ValueError:
                messagebox.showwarning("Invalid Input", "Please enter valid numbers.", parent=dialog)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update:\n{str(e)}", parent=dialog)

        tk.Button(
            dialog,
            text="Update Cost",
            command=update,
            bg=self.colors['warning'],
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=20,
            pady=8
        ).pack(pady=20)

    def show_cost_analysis(self):
        """Show book cost analysis"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT
                    COUNT(*) as total_books,
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
            messagebox.showerror("Error", f"Failed to generate analysis:\n{str(e)}")

    # ==================== OVERVIEW METHODS ====================

    def refresh_overview(self):
        """Refresh the overview dashboard"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Outstanding fines
            cursor.execute('SELECT SUM(fine_amount) FROM book_loans WHERE fine_amount > 0')
            outstanding = cursor.fetchone()[0] or 0.0

            # Collected this month
            cursor.execute('''
                SELECT SUM(pa.amount)
                FROM payment_allocations pa
                JOIN payments p ON pa.payment_id = p.payment_id
                JOIN student_fees sf ON pa.student_fee_id = sf.student_fee_id
                WHERE sf.fee_type_id = 3
                  AND strftime('%Y-%m', p.payment_date) = strftime('%Y-%m', 'now')
            ''')
            this_month = cursor.fetchone()[0] or 0.0

            # YTD revenue
            cursor.execute('''
                SELECT SUM(pa.amount)
                FROM payment_allocations pa
                JOIN payments p ON pa.payment_id = p.payment_id
                JOIN student_fees sf ON pa.student_fee_id = sf.student_fee_id
                WHERE sf.fee_type_id = 3
                  AND strftime('%Y', p.payment_date) = strftime('%Y', 'now')
            ''')
            ytd_revenue = cursor.fetchone()[0] or 0.0

            # Book investment
            cursor.execute('SELECT SUM(COALESCE(purchase_price, 0) * COALESCE(quantity, 1)) FROM books')
            book_investment = cursor.fetchone()[0] or 0.0

            conn.close()

            # Update metric cards
            if hasattr(self, 'outstanding_fines_label'):
                self.outstanding_fines_label.config(text=f"£{outstanding:,.2f}")
            if hasattr(self, 'collected_this_month_label'):
                self.collected_this_month_label.config(text=f"£{this_month:,.2f}")
            if hasattr(self, 'total_revenue_ytd_label'):
                self.total_revenue_ytd_label.config(text=f"£{ytd_revenue:,.2f}")
            if hasattr(self, 'book_investment_label'):
                self.book_investment_label.config(text=f"£{book_investment:,.2f}")

            # Create overview chart
            self.create_overview_chart(outstanding, this_month, ytd_revenue, book_investment)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh overview:\n{str(e)}")

    def create_overview_chart(self, outstanding, this_month, ytd, investment):
        """Create overview visualization"""
        try:
            # Clear existing charts
            for widget in self.overview_chart_frame.winfo_children():
                widget.destroy()

            fig = Figure(figsize=(10, 6), dpi=100)

            # Pie chart for financial breakdown
            ax1 = fig.add_subplot(1, 2, 1)
            categories = ['Outstanding Fines', 'Collected (Month)', 'YTD Revenue', 'Book Investment']
            values = [outstanding, this_month, ytd, investment]
            colors = [self.colors['danger'], self.colors['success'], self.colors['info'], self.colors['library']]

            # Filter out zero values
            filtered_data = [(cat, val, col) for cat, val, col in zip(categories, values, colors) if val > 0]

            if filtered_data:
                cats, vals, cols = zip(*filtered_data)
                wedges, texts, autotexts = ax1.pie(vals, labels=cats, autopct='%1.1f%%', colors=cols, startangle=90)
                ax1.set_title('Library Financial Overview', fontsize=12, fontweight='bold')

                for autotext in autotexts:
                    autotext.set_color('white')
                    autotext.set_fontweight('bold')
            else:
                ax1.text(0.5, 0.5, 'No Data Available', ha='center', va='center', fontsize=14)
                ax1.set_title('Library Financial Overview', fontsize=12, fontweight='bold')

            # Bar chart comparison
            ax2 = fig.add_subplot(1, 2, 2)
            x_pos = range(len(categories))
            bars = ax2.bar(x_pos, values, color=colors)
            ax2.set_xticks(x_pos)
            ax2.set_xticklabels(categories, rotation=45, ha='right', fontsize=9)
            ax2.set_ylabel('Amount (£)', fontweight='bold')
            ax2.set_title('Financial Metrics Comparison', fontsize=12, fontweight='bold')
            ax2.grid(axis='y', alpha=0.3)

            # Add value labels
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax2.text(bar.get_x() + bar.get_width() / 2., height,
                            f'£{height:,.0f}', ha='center', va='bottom', fontsize=8)

            fig.tight_layout()

            # Embed in tkinter
            canvas = FigureCanvasTkAgg(fig, master=self.overview_chart_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)

        except Exception as e:
            print(f"Error creating overview chart: {e}")
