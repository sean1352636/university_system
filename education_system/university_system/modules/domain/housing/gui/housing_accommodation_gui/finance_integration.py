"""
Finance integration functions - integration with finance management system.
Handles financial transactions, account management, and reporting for housing.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.simple_activity_logger import log_activity
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

# Import housing services
from education_system.university_system.modules.domain.housing.services.housing_accommodation import (
    init_housing_db,
    generate_id,
    set_auth
)

# Import finance GUI if available
try:
    from education_system.university_system.modules.domain.finance.gui.finance.finance_gui import FinanceGUI
    FINANCE_GUI_AVAILABLE = True
except ImportError:
    FINANCE_GUI_AVAILABLE = False

    def open_finance_gui(self):
        """Open Housing Finance Management in a new window"""
        try:
            # Create new top-level window for housing finance
            finance_window = tk.Toplevel(self.root)
            finance_window.title("Housing Finance Management")
            finance_window.geometry("1400x900")
            finance_window.transient(self.root)

            # Create the housing finance manager
            housing_finance = HousingFinanceManager(finance_window, self.auth)

            # Log the action
            log_menu_navigation(description='Opened housing finance management')

            print("✓ Housing Finance Management opened successfully")

        except Exception as e:
            messagebox.showerror(
                "Error Opening Housing Finance",
                f"Failed to open Housing Finance system:\n\n{str(e)}"
            )
            print(f"✗ Failed to open Housing Finance: {e}")
            import traceback
            traceback.print_exc()

class HousingFinanceManager:
    """Manages all housing-related financial operations - integrated into Housing GUI"""

    def __init__(self, root, auth=None):
        """Initialize manager with root window and auth"""
        self.root = root
        self.auth = auth

        # Color scheme
        self.colors = {
            'primary': '#2c3e50',
            'secondary': '#3498db',
            'success': '#27ae60',
            'warning': '#f39c12',
            'danger': '#e74c3c',
            'light': '#ecf0f1',
            'dark': '#34495e',
            'info': '#17a2b8'
        }

        # Create the main content frame
        self.content_frame = tk.Frame(root, bg='white')
        self.content_frame.pack(fill='both', expand=True)

        # Create the housing finance interface
        self.create_housing_finance_interface()

    def create_housing_finance_interface(self):
        """Create the Housing Finance interface"""
        # Header
        header_frame = tk.Frame(self.content_frame, bg=self.colors['primary'], height=60)
        header_frame.pack(fill='x', side='top')
        header_frame.pack_propagate(False)

        title_label = tk.Label(header_frame, text="🏠 Housing Finance Management",
                              font=('Arial', 20, 'bold'),
                              bg=self.colors['primary'], fg='white')
        title_label.pack(side='left', padx=20, pady=15)

        # Refresh button
        refresh_btn = tk.Button(header_frame, text="🔄 Refresh",
                               command=self.refresh_data,
                               bg=self.colors['secondary'], fg='white',
                               font=('Arial', 10, 'bold'), relief='flat',
                               padx=15, pady=5)
        refresh_btn.pack(side='right', padx=10, pady=15)

        # Close button
        close_btn = tk.Button(header_frame, text="✕ Close",
                             command=self.root.destroy,
                             bg=self.colors['danger'], fg='white',
                             font=('Arial', 10, 'bold'), relief='flat',
                             padx=15, pady=5)
        close_btn.pack(side='right', padx=10, pady=15)

        # Main content area with scrolling
        main_canvas = tk.Canvas(self.content_frame, bg='white')
        scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=main_canvas.yview)
        self.scrollable_frame = tk.Frame(main_canvas, bg='white')

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )

        main_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)

        main_canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Load housing data
        self.load_housing_finance_data()

    def load_housing_finance_data(self):
        """Load and display housing finance data"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            parent = self.scrollable_frame

            # Summary statistics frame
            stats_frame = tk.Frame(parent, bg='white')
            stats_frame.pack(fill='x', padx=20, pady=10)

            # Calculate statistics
            cursor.execute('''
                SELECT
                    COUNT(DISTINCT payment_id) as total_payments,
                    SUM(amount) as total_revenue,
                    COUNT(DISTINCT student_id) as unique_students
                FROM payments
                WHERE source_type = 'housing' AND status = 'Completed'
            ''')
            total_payments, total_revenue, unique_students = cursor.fetchone()
            total_revenue = total_revenue or 0.0
            total_payments = total_payments or 0
            unique_students = unique_students or 0

            # Outstanding payments
            cursor.execute('''
                SELECT COUNT(*) as pending_count
                FROM payments
                WHERE source_type = 'housing' AND status != 'Completed'
            ''')
            pending_count = cursor.fetchone()[0] or 0

            # Display summary cards
            summary_cards = [
                ("Total Revenue", f"£{total_revenue:,.2f}", "#27ae60"),
                ("Total Payments", str(total_payments), "#3498db"),
                ("Students with Housing", str(unique_students), "#9b59b6"),
                ("Pending Payments", str(pending_count), "#e74c3c")
            ]

            for idx, (label, value, color) in enumerate(summary_cards):
                card = tk.Frame(stats_frame, bg=color, relief='raised', bd=2)
                card.grid(row=0, column=idx, padx=10, pady=10, sticky='nsew')
                stats_frame.grid_columnconfigure(idx, weight=1)

                tk.Label(card, text=label, font=('Arial', 11, 'bold'),
                        bg=color, fg='white').pack(pady=(10, 5))
                tk.Label(card, text=value, font=('Arial', 16, 'bold'),
                        bg=color, fg='white').pack(pady=(0, 10))

            # Action toolbar
            toolbar_frame = tk.Frame(parent, bg='white')
            toolbar_frame.pack(fill='x', padx=20, pady=10)

            tk.Button(toolbar_frame, text="➕ Record Payment",
                     command=self.record_housing_payment,
                     bg=self.colors['success'], fg='white',
                     font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)

            tk.Button(toolbar_frame, text="🔍 Filter Payments",
                     command=self.filter_housing_payments,
                     bg=self.colors['info'], fg='white',
                     font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)

            tk.Button(toolbar_frame, text="📊 Export Report",
                     command=self.export_housing_report,
                     bg=self.colors['warning'], fg='white',
                     font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)

            tk.Button(toolbar_frame, text="💰 Outstanding Balances",
                     command=self.show_outstanding_balances,
                     bg=self.colors['danger'], fg='white',
                     font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)

            # Outstanding balance summary section
            outstanding_frame = tk.LabelFrame(parent, text="Outstanding Balances Summary",
                                            font=('Arial', 12, 'bold'),
                                            bg='white', padx=10, pady=10)
            outstanding_frame.pack(fill='x', padx=20, pady=10)

            # Calculate outstanding balances
            cursor.execute('''
                SELECT
                    COUNT(DISTINCT student_id) as students_with_balance,
                    SUM(amount) as total_outstanding,
                    AVG(amount) as avg_balance,
                    MAX(amount) as max_balance
                FROM payments
                WHERE source_type = 'housing' AND status IN ('Pending', 'Overdue', 'Failed')
            ''')
            outstanding_data = cursor.fetchone()
            students_with_balance = outstanding_data[0] or 0
            total_outstanding = outstanding_data[1] or 0.0
            avg_balance = outstanding_data[2] or 0.0
            max_balance = outstanding_data[3] or 0.0

            # Display outstanding balance metrics
            balance_grid = tk.Frame(outstanding_frame, bg='white')
            balance_grid.pack(fill='x', pady=5)

            metrics = [
                ("Students with Outstanding Balance", str(students_with_balance)),
                ("Total Outstanding", f"£{total_outstanding:,.2f}"),
                ("Average Balance", f"£{avg_balance:,.2f}"),
                ("Highest Outstanding Balance", f"£{max_balance:,.2f}")
            ]

            for idx, (label, value) in enumerate(metrics):
                metric_frame = tk.Frame(balance_grid, bg='#ecf0f1', relief='ridge', bd=1)
                metric_frame.grid(row=0, column=idx, padx=5, pady=5, sticky='ew')
                balance_grid.grid_columnconfigure(idx, weight=1)

                tk.Label(metric_frame, text=label, font=('Arial', 9),
                        bg='#ecf0f1', fg='#34495e').pack(pady=(5, 2))
                tk.Label(metric_frame, text=value, font=('Arial', 12, 'bold'),
                        bg='#ecf0f1', fg='#e74c3c').pack(pady=(2, 5))

            # Monthly revenue trend section
            trend_frame = tk.LabelFrame(parent, text="Monthly Revenue Trend (Last 6 Months)",
                                       font=('Arial', 12, 'bold'),
                                       bg='white', padx=10, pady=10)
            trend_frame.pack(fill='x', padx=20, pady=10)

            # Get monthly revenue data
            cursor.execute('''
                SELECT
                    strftime('%Y-%m', payment_date) as month,
                    COUNT(*) as payment_count,
                    SUM(amount) as monthly_revenue
                FROM payments
                WHERE source_type = 'housing' AND status = 'Completed'
                    AND payment_date >= date('now', '-6 months')
                GROUP BY month
                ORDER BY month DESC
            ''')
            monthly_data = cursor.fetchall()

            if monthly_data:
                # Create trend table
                trend_columns = ('Month', 'Payments', 'Revenue', 'Avg Payment')
                trend_tree = ttk.Treeview(trend_frame, columns=trend_columns,
                                         show='headings', height=6)

                trend_tree.heading('Month', text='Month')
                trend_tree.heading('Payments', text='Number of Payments')
                trend_tree.heading('Revenue', text='Total Revenue')
                trend_tree.heading('Avg Payment', text='Average Payment')

                trend_tree.column('Month', width=120, anchor='center')
                trend_tree.column('Payments', width=150, anchor='center')
                trend_tree.column('Revenue', width=150, anchor='e')
                trend_tree.column('Avg Payment', width=150, anchor='e')

                for month, count, revenue in monthly_data:
                    avg_payment = revenue / count if count > 0 else 0
                    trend_tree.insert('', 'end', values=(
                        month,
                        count,
                        f"£{revenue:,.2f}",
                        f"£{avg_payment:,.2f}"
                    ))

                trend_tree.pack(fill='x', pady=5)
            else:
                tk.Label(trend_frame, text="No monthly trend data available",
                        font=('Arial', 10), bg='white').pack(pady=10)

            # Recent payments section
            payments_frame = tk.LabelFrame(parent, text="Recent Housing Payments",
                                          font=('Arial', 12, 'bold'),
                                          bg='white', padx=10, pady=10)
            payments_frame.pack(fill='both', expand=True, padx=20, pady=10)

            # Create treeview for payments
            columns = ('Payment ID', 'Student', 'Amount', 'Date', 'Method', 'Period', 'Status')
            tree = ttk.Treeview(payments_frame, columns=columns, show='headings', height=15)

            for col in columns:
                tree.heading(col, text=col)
                if col == 'Amount':
                    tree.column(col, width=100, anchor='e')
                elif col == 'Payment ID':
                    tree.column(col, width=120)
                elif col == 'Student':
                    tree.column(col, width=200)
                else:
                    tree.column(col, width=120)

            # Load payment data
            cursor.execute('''
                SELECT
                    hp.source_payment_id,
                    s.first_name || ' ' || s.last_name as student_name,
                    hp.amount,
                    hp.payment_date,
                    hp.payment_method,
                    hp.payment_period_start || ' to ' || hp.payment_period_end as period,
                    hp.status
                FROM payments hp
                JOIN students s ON hp.student_id = s.student_id
                WHERE hp.source_type = 'housing'
                ORDER BY hp.payment_date DESC
                LIMIT 100
            ''')

            for row in cursor.fetchall():
                # Convert sqlite3.Row to tuple for treeview display
                tree.insert('', 'end', values=tuple(row))

            tree.pack(fill='both', expand=True)

            # Add scrollbar to treeview
            tree_scroll = ttk.Scrollbar(payments_frame, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=tree_scroll.set)
            tree_scroll.pack(side='right', fill='y')

            # Payment by building section
            building_frame = tk.LabelFrame(parent, text="Revenue by Building",
                                          font=('Arial', 12, 'bold'),
                                          bg='white', padx=10, pady=10)
            building_frame.pack(fill='both', expand=True, padx=20, pady=10)

            cursor.execute('''
                SELECT
                    hb.building_name,
                    COUNT(DISTINCT hp.payment_id) as payment_count,
                    SUM(hp.amount) as total_revenue
                FROM payments hp
                JOIN housing_assignments ha ON hp.reference_id = ha.assignment_id
                JOIN housing_rooms hr ON ha.room_id = hr.room_id
                JOIN housing_buildings hb ON hr.building_id = hb.building_id
                WHERE hp.source_type = 'housing' AND hp.status = 'Completed'
                GROUP BY hb.building_name
                ORDER BY total_revenue DESC
            ''')

            building_data = cursor.fetchall()

            if building_data:
                building_tree = ttk.Treeview(building_frame,
                                            columns=('Building', 'Payments', 'Revenue'),
                                            show='headings', height=8)

                building_tree.heading('Building', text='Building Name')
                building_tree.heading('Payments', text='Number of Payments')
                building_tree.heading('Revenue', text='Total Revenue')

                building_tree.column('Building', width=200)
                building_tree.column('Payments', width=150, anchor='center')
                building_tree.column('Revenue', width=150, anchor='e')

                for building, count, revenue in building_data:
                    building_tree.insert('', 'end', values=(
                        building,
                        count,
                        f"£{revenue:,.2f}"
                    ))

                building_tree.pack(fill='both', expand=True)
            else:
                tk.Label(building_frame, text="No building revenue data available",
                        font=('Arial', 10), bg='white').pack(pady=20)

            conn.close()

        except Exception as e:
            tk.Label(self.scrollable_frame, text=f"Error loading housing finance data: {str(e)}",
                    font=('Arial', 12), bg='white', fg='red').pack(pady=20)
            print(f"Error in load_housing_finance_data: {e}")
            import traceback
            traceback.print_exc()

    def refresh_data(self):
        """Refresh housing finance data"""
        try:
            # Clear existing content
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()
            # Reload data
            self.load_housing_finance_data()
        except Exception as e:
            print(f"Error refreshing housing data: {e}")

    def record_housing_payment(self):
        """Open dialog to record a new housing payment"""
        try:
            # Create payment dialog window
            dialog = tk.Toplevel(self.root)
            dialog.title("Record Housing Payment")
            dialog.geometry("500x600")
            dialog.transient(self.root)
            dialog.grab_set()

            # Title
            tk.Label(dialog, text="Record New Housing Payment",
                    font=('Arial', 14, 'bold')).pack(pady=10)

            # Form frame
            form_frame = ttk.Frame(dialog, padding="20")
            form_frame.pack(fill='both', expand=True)

            # Student ID with lookup button
            ttk.Label(form_frame, text="Student ID:").grid(row=0, column=0, sticky='w', pady=5)

            student_id_frame = ttk.Frame(form_frame)
            student_id_frame.grid(row=0, column=1, pady=5, padx=10, sticky='w')

            student_id_entry = ttk.Entry(student_id_frame, width=22)
            student_id_entry.pack(side='left')

            # Student name display
            student_name_var = tk.StringVar(value="")
            student_name_label = ttk.Label(student_id_frame, textvariable=student_name_var,
                                          foreground='green', font=('Arial', 9))
            student_name_label.pack(side='left', padx=(5, 0))

            def lookup_student():
                student_id = student_id_entry.get().strip()
                if not student_id:
                    messagebox.showwarning("Lookup", "Please enter a Student ID")
                    return

                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT student_id, first_name, last_name, email_address
                        FROM students WHERE student_id = ?
                    ''', (student_id,))
                    result = cursor.fetchone()
                    conn.close()

                    if result:
                        _, first_name, last_name, email = result
                        full_name = f"{first_name} {last_name}"
                        student_name_var.set(f"✓ {full_name}")
                        student_name_label.config(foreground='green')
                    else:
                        student_name_var.set("✗ Not Found")
                        student_name_label.config(foreground='red')
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to lookup student: {str(e)}")

            ttk.Button(student_id_frame, text="🔍 Lookup", command=lookup_student,
                      width=8).pack(side='left', padx=(5, 0))

            # Amount
            ttk.Label(form_frame, text="Amount (£):").grid(row=1, column=0, sticky='w', pady=5)
            amount_entry = ttk.Entry(form_frame, width=30)
            amount_entry.grid(row=1, column=1, pady=5, padx=10)

            # Payment Method
            ttk.Label(form_frame, text="Payment Method:").grid(row=2, column=0, sticky='w', pady=5)
            method_var = tk.StringVar(value="Credit Card")
            method_combo = ttk.Combobox(form_frame, textvariable=method_var, width=28,
                                       values=["Credit Card", "Debit Card", "Cash", "Check", "Bank Transfer", "Financial Aid"])
            method_combo.grid(row=2, column=1, pady=5, padx=10)

            # Payment Date
            ttk.Label(form_frame, text="Payment Date:").grid(row=3, column=0, sticky='w', pady=5)
            date_entry = ttk.Entry(form_frame, width=30)
            date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
            date_entry.grid(row=3, column=1, pady=5, padx=10)

            # Period Start
            ttk.Label(form_frame, text="Period Start:").grid(row=4, column=0, sticky='w', pady=5)
            period_start_entry = ttk.Entry(form_frame, width=30)
            period_start_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
            period_start_entry.grid(row=4, column=1, pady=5, padx=10)

            # Period End
            ttk.Label(form_frame, text="Period End:").grid(row=5, column=0, sticky='w', pady=5)
            period_end_entry = ttk.Entry(form_frame, width=30)
            period_end_entry.grid(row=5, column=1, pady=5, padx=10)

            # Status
            ttk.Label(form_frame, text="Status:").grid(row=6, column=0, sticky='w', pady=5)
            status_var = tk.StringVar(value="Completed")
            status_combo = ttk.Combobox(form_frame, textvariable=status_var, width=28,
                                       values=["Completed", "Pending", "Failed", "Overdue"])
            status_combo.grid(row=6, column=1, pady=5, padx=10)

            # Notes
            ttk.Label(form_frame, text="Notes:").grid(row=7, column=0, sticky='w', pady=5)
            notes_text = tk.Text(form_frame, width=30, height=5)
            notes_text.grid(row=7, column=1, pady=5, padx=10)

            def save_payment():
                try:
                    student_id = student_id_entry.get().strip()
                    if not student_id:
                        messagebox.showerror("Error", "Student ID is required")
                        return

                    try:
                        amount = float(amount_entry.get().strip())
                        if amount <= 0:
                            messagebox.showerror("Error", "Amount must be greater than 0")
                            return
                    except ValueError:
                        messagebox.showerror("Error", "Please enter a valid amount")
                        return

                    import uuid
                    payment_id = f"HP{uuid.uuid4().hex[:8].upper()}"
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    received_by = self.auth.get_current_user().get('username', 'SYSTEM') if self.auth else 'SYSTEM'

                    conn = get_connection()
                    cursor = conn.cursor()

                    # Get assignment_id for the student
                    cursor.execute('''
                        SELECT assignment_id FROM housing_assignments
                        WHERE student_id = ? AND status = 'Active'
                        ORDER BY move_in_date DESC LIMIT 1
                    ''', (student_id,))
                    result = cursor.fetchone()

                    if not result:
                        cursor.execute('''
                            SELECT assignment_id FROM housing_assignments
                            WHERE student_id = ?
                            ORDER BY created_at DESC LIMIT 1
                        ''', (student_id,))
                        result = cursor.fetchone()

                    if not result:
                        conn.close()
                        messagebox.showerror("Error",
                            f"Student '{student_id}' does not have a housing assignment.")
                        return

                    assignment_id = result[0]

                    cursor.execute('''
                        INSERT INTO payments
                        (source_payment_id, source_type, reference_id, reference_type,
                         student_id, amount, payment_date,
                         payment_method, payment_reference, payment_period_start,
                         payment_period_end, status, processed_by, created_at, updated_at)
                        VALUES (?, 'housing', ?, 'assignment', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (payment_id, assignment_id, student_id, amount, date_entry.get(),
                         method_var.get(), notes_text.get('1.0', 'end').strip(),
                         period_start_entry.get(), period_end_entry.get(),
                         status_var.get(), received_by, current_time, current_time))
                    payment_row_id = cursor.lastrowid

                    conn.commit()
                    conn.close()

                    # Auto-post to GL only if cash has actually moved (never raises)
                    if (status_var.get() or '').strip().lower() in ('completed', 'paid', 'success'):
                        try:
                            from education_system.university_system.modules.domain.finance.ledger import notify_ledger
                            notify_ledger('payment', payment_row_id, posted_by=received_by or 'housing')
                        except Exception as _e:
                            import logging
                            logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

                    messagebox.showinfo("Success", f"Payment {payment_id} recorded successfully!")
                    dialog.destroy()
                    self.refresh_data()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to record payment: {str(e)}")

            # Buttons
            button_frame = ttk.Frame(dialog)
            button_frame.pack(pady=20)

            ttk.Button(button_frame, text="Save Payment", command=save_payment).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open payment dialog: {str(e)}")

    def filter_housing_payments(self):
        """Open dialog to filter housing payments"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Filter Housing Payments")
            dialog.geometry("450x400")
            dialog.transient(self.root)
            dialog.grab_set()

            tk.Label(dialog, text="Filter Housing Payments",
                    font=('Arial', 14, 'bold')).pack(pady=10)

            form_frame = ttk.Frame(dialog, padding="20")
            form_frame.pack(fill='both', expand=True)

            ttk.Label(form_frame, text="Student ID:").grid(row=0, column=0, sticky='w', pady=5)
            student_filter = ttk.Entry(form_frame, width=30)
            student_filter.grid(row=0, column=1, pady=5, padx=10)

            ttk.Label(form_frame, text="Status:").grid(row=1, column=0, sticky='w', pady=5)
            status_filter = ttk.Combobox(form_frame, width=28,
                                        values=["All", "Completed", "Pending", "Failed", "Overdue"])
            status_filter.set("All")
            status_filter.grid(row=1, column=1, pady=5, padx=10)

            ttk.Label(form_frame, text="From Date:").grid(row=2, column=0, sticky='w', pady=5)
            from_date = ttk.Entry(form_frame, width=30)
            from_date.grid(row=2, column=1, pady=5, padx=10)

            ttk.Label(form_frame, text="To Date:").grid(row=3, column=0, sticky='w', pady=5)
            to_date = ttk.Entry(form_frame, width=30)
            to_date.grid(row=3, column=1, pady=5, padx=10)

            def apply_filter():
                try:
                    query = '''
                        SELECT hp.source_payment_id, s.first_name || ' ' || s.last_name,
                               hp.amount, hp.payment_date, hp.payment_method,
                               hp.payment_period_start || ' to ' || hp.payment_period_end, hp.status
                        FROM payments hp
                        JOIN students s ON hp.student_id = s.student_id
                        WHERE hp.source_type = 'housing'
                    '''
                    params = []

                    if student_filter.get().strip():
                        query += " AND hp.student_id = ?"
                        params.append(student_filter.get().strip())

                    if status_filter.get() != "All":
                        query += " AND hp.status = ?"
                        params.append(status_filter.get())

                    if from_date.get().strip():
                        query += " AND hp.payment_date >= ?"
                        params.append(from_date.get().strip())

                    if to_date.get().strip():
                        query += " AND hp.payment_date <= ?"
                        params.append(to_date.get().strip())

                    query += " ORDER BY hp.payment_date DESC"

                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute(query, params)
                    results = cursor.fetchall()
                    conn.close()

                    results_window = tk.Toplevel(dialog)
                    results_window.title("Filter Results")
                    results_window.geometry("900x500")

                    tk.Label(results_window, text=f"Found {len(results)} payments",
                            font=('Arial', 12, 'bold')).pack(pady=10)

                    columns = ('Payment ID', 'Student', 'Amount', 'Date', 'Method', 'Period', 'Status')
                    tree = ttk.Treeview(results_window, columns=columns, show='headings')

                    for col in columns:
                        tree.heading(col, text=col)
                        tree.column(col, width=120)

                    for row in results:
                        tree.insert('', 'end', values=tuple(row))

                    tree.pack(fill='both', expand=True, padx=10, pady=10)

                except Exception as e:
                    messagebox.showerror("Error", f"Filter failed: {str(e)}")

            button_frame = ttk.Frame(dialog)
            button_frame.pack(pady=20)

            ttk.Button(button_frame, text="Apply Filter", command=apply_filter).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open filter dialog: {str(e)}")

    def export_housing_report(self):
        """Export housing finance report to CSV"""
        try:
            from tkinter import filedialog
            import csv

            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"housing_finance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )

            if not filename:
                return

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT hp.source_payment_id, hp.student_id,
                       s.first_name || ' ' || s.last_name,
                       hp.amount, hp.payment_date, hp.payment_method,
                       hp.payment_period_start, hp.payment_period_end, hp.status
                FROM payments hp
                JOIN students s ON hp.student_id = s.student_id
                WHERE hp.source_type = 'housing'
                ORDER BY hp.payment_date DESC
            ''')

            data = cursor.fetchall()
            conn.close()

            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Payment ID', 'Student ID', 'Student Name', 'Amount',
                               'Payment Date', 'Payment Method', 'Period Start', 'Period End', 'Status'])
                for row in data:
                    writer.writerow(row)

            messagebox.showinfo("Success", f"Report exported to:\n{filename}\n\nTotal records: {len(data)}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export report: {str(e)}")

    def show_outstanding_balances(self):
        """Show detailed outstanding balances window"""
        try:
            window = tk.Toplevel(self.root)
            window.title("Outstanding Housing Balances")
            window.geometry("900x600")
            window.transient(self.root)

            tk.Label(window, text="Outstanding Housing Balances",
                    font=('Arial', 16, 'bold')).pack(pady=10)

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT hp.student_id, s.first_name || ' ' || s.last_name,
                       s.email_address, COUNT(*), SUM(hp.amount),
                       MAX(hp.payment_date), hp.status
                FROM payments hp
                JOIN students s ON hp.student_id = s.student_id
                WHERE hp.source_type = 'housing' AND hp.status IN ('Pending', 'Overdue', 'Failed')
                GROUP BY hp.student_id, s.first_name, s.last_name, s.email_address, hp.status
                ORDER BY SUM(hp.amount) DESC
            ''')

            data = cursor.fetchall()
            conn.close()

            tk.Label(window, text=f"Total students with outstanding balances: {len(data)}",
                    font=('Arial', 11)).pack(pady=5)

            columns = ('Student ID', 'Name', 'Email', 'Payments', 'Total Outstanding', 'Last Payment', 'Status')
            tree = ttk.Treeview(window, columns=columns, show='headings')

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=120)

            for row in data:
                student_id, name, email, count, total, last_date, status = row
                tree.insert('', 'end', values=(
                    student_id, name, email, count,
                    f"£{total:,.2f}", last_date, status
                ))

            tree.pack(fill='both', expand=True, padx=10, pady=10)

            ttk.Button(window, text="Close", command=window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load outstanding balances: {str(e)}")


# Export functions for backward compatibility
__all__ = [
    'HousingFinanceManager',
    'orig_init_housing_db',
    'orig_generate_id',
    'orig_set_auth',
]

# Create aliases for backward compatibility
orig_init_housing_db = init_housing_db
orig_generate_id = generate_id
orig_set_auth = set_auth
