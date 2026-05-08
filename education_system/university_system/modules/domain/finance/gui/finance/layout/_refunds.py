"""Refunds management mixin for LayoutManager."""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
from datetime import datetime

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.i18n import get_text as _


class RefundsMixin:
    """Refund viewing, export, and financial summary."""

    def create_refunds_tab(self):
        """Top-level Refunds tab — aggregate view of all refunds across departments."""
        frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['refunds'] = frame

        # Table (built first so toolbar/search closures can reference it)
        table_frame = ttk.Frame(frame)
        columns = ('ID', 'Reference', 'Source', 'Department', 'Amount', 'Method', 'Date',
                   'Reference ID', 'Processed By', 'Notes')
        refunds_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=25)
        column_specs = [
            ('ID', 'ID', 50, 'center'),
            ('Reference', 'Refund Reference', 180, 'w'),
            ('Source', 'Source Type', 100, 'w'),
            ('Department', 'Department', 120, 'w'),
            ('Amount', 'Amount', 100, 'e'),
            ('Method', 'Method', 120, 'w'),
            ('Date', 'Date', 120, 'center'),
            ('Reference ID', 'Reference ID', 150, 'w'),
            ('Processed By', 'Processed By', 120, 'w'),
            ('Notes', 'Notes', 200, 'w'),
        ]
        for col, heading, width, anchor in column_specs:
            refunds_tree.heading(col, text=heading)
            refunds_tree.column(col, width=width, anchor=anchor)

        # Toolbar
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill='x', padx=10, pady=10)
        ttk.Label(
            toolbar,
            text=_("finance_gui.refunds.title", default="\U0001f501 Refunds"),
            font=('Arial', 14, 'bold'),
        ).pack(side='left')
        ttk.Button(
            toolbar,
            text=_("common.refresh", default="Refresh"),
            command=lambda: self._refresh_refunds_table(refunds_tree),
        ).pack(side='right', padx=5)
        ttk.Button(
            toolbar,
            text=_("finance_gui.refunds.export_csv", default="Export to CSV"),
            command=lambda: self._export_refunds_to_csv(refunds_tree),
        ).pack(side='right', padx=5)
        ttk.Button(
            toolbar,
            text=_("finance_gui.refunds.process", default="Process Refund"),
            command=self._manage_refunds,
        ).pack(side='right', padx=5)

        # Search
        search_frame = ttk.Frame(frame)
        search_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(search_frame, text=_("common.search", default="Search") + ":").pack(side='left', padx=5)
        search_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=search_var, width=40).pack(side='left', padx=5)
        search_var.trace(
            'w',
            lambda *_a: self._load_refunds_to_table(refunds_tree, search_var.get().lower() or None),
        )

        # Layout the table with scrollbars
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)
        vsb = ttk.Scrollbar(table_frame, orient='vertical', command=refunds_tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient='horizontal', command=refunds_tree.xview)
        refunds_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        refunds_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Summary
        summary_frame = ttk.Frame(frame)
        summary_frame.pack(fill='x', padx=10, pady=5)
        self.summary_label = ttk.Label(summary_frame, text="Loading...", font=('Arial', 10, 'bold'))
        self.summary_label.pack()

        self._load_refunds_to_table(refunds_tree)

    def _manage_refunds(self):
        """Manage refunds"""
        try:
            # Call transaction manager's refund function if available
            if hasattr(self.gui, 'transactions') and hasattr(self.gui.transactions, 'gui_process_refund'):
                self.gui.transactions.gui_process_refund()
            else:
                messagebox.showinfo(_("finance_gui.buttons.manage_refunds"), _("finance_gui.messages.transaction_manager_unavailable"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("finance_gui.messages.failed_open_refunds_dialog", error=str(e)))

    def _view_all_refunds(self):
        """View all refunds in a table"""
        try:
            # Create refunds window
            refunds_window = tk.Toplevel(self.root)
            refunds_window.title("All Refunds - Database Records")
            refunds_window.geometry("1200x700")
            refunds_window.transient(self.root)

            # Header
            header_frame = ttk.Frame(refunds_window)
            header_frame.pack(fill='x', padx=10, pady=10)

            ttk.Label(header_frame, text="All Refunds", font=('Arial', 16, 'bold')).pack(side='left')

            # Refresh button
            ttk.Button(header_frame, text="Refresh",
                      command=lambda: self._refresh_refunds_table(refunds_tree)).pack(side='right', padx=5)

            # Export button
            ttk.Button(header_frame, text="Export to CSV",
                      command=lambda: self._export_refunds_to_csv(refunds_tree)).pack(side='right', padx=5)

            # Search frame
            search_frame = ttk.Frame(refunds_window)
            search_frame.pack(fill='x', padx=10, pady=5)

            ttk.Label(search_frame, text="Search:").pack(side='left', padx=5)
            search_var = tk.StringVar()
            search_entry = ttk.Entry(search_frame, textvariable=search_var, width=40)
            search_entry.pack(side='left', padx=5)

            def search_refunds(*args):
                search_term = search_var.get().lower()
                self._load_refunds_to_table(refunds_tree, search_term)

            search_var.trace('w', search_refunds)
            ttk.Button(search_frame, text="Clear",
                      command=lambda: search_var.set("")).pack(side='left', padx=5)

            # Table frame with scrollbars
            table_frame = ttk.Frame(refunds_window)
            table_frame.pack(fill='both', expand=True, padx=10, pady=10)

            # Create Treeview
            columns = ('ID', 'Reference', 'Source', 'Department', 'Amount', 'Method', 'Date',
                      'Reference ID', 'Processed By', 'Notes')
            refunds_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=25)

            # Configure columns
            refunds_tree.heading('ID', text='ID')
            refunds_tree.heading('Reference', text='Refund Reference')
            refunds_tree.heading('Source', text='Source Type')
            refunds_tree.heading('Department', text='Department')
            refunds_tree.heading('Amount', text='Amount')
            refunds_tree.heading('Method', text='Method')
            refunds_tree.heading('Date', text='Date')
            refunds_tree.heading('Reference ID', text='Reference ID')
            refunds_tree.heading('Processed By', text='Processed By')
            refunds_tree.heading('Notes', text='Notes')

            # Set column widths
            refunds_tree.column('ID', width=50, anchor='center')
            refunds_tree.column('Reference', width=180, anchor='w')
            refunds_tree.column('Source', width=100, anchor='w')
            refunds_tree.column('Department', width=120, anchor='w')
            refunds_tree.column('Amount', width=100, anchor='e')
            refunds_tree.column('Method', width=120, anchor='w')
            refunds_tree.column('Date', width=120, anchor='center')
            refunds_tree.column('Reference ID', width=150, anchor='w')
            refunds_tree.column('Processed By', width=120, anchor='w')
            refunds_tree.column('Notes', width=200, anchor='w')

            # Add scrollbars
            vsb = ttk.Scrollbar(table_frame, orient="vertical", command=refunds_tree.yview)
            hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=refunds_tree.xview)
            refunds_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

            # Pack elements
            refunds_tree.grid(row=0, column=0, sticky='nsew')
            vsb.grid(row=0, column=1, sticky='ns')
            hsb.grid(row=1, column=0, sticky='ew')

            table_frame.grid_rowconfigure(0, weight=1)
            table_frame.grid_columnconfigure(0, weight=1)

            # Summary frame
            summary_frame = ttk.Frame(refunds_window)
            summary_frame.pack(fill='x', padx=10, pady=5)

            self.summary_label = ttk.Label(summary_frame, text="Loading...", font=('Arial', 10, 'bold'))
            self.summary_label.pack()

            # Load data
            self._load_refunds_to_table(refunds_tree)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open refunds view: {e}")
            import traceback
            traceback.print_exc()

    def _load_refunds_to_table(self, tree, search_term=None):
        """Load refunds data into the table"""
        try:
            # Clear existing items
            for item in tree.get_children():
                tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()

            # Check if unified_refunds table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='unified_refunds'")
            if not cursor.fetchone():
                tree.insert('', 'end', values=('No Data', 'unified_refunds table does not exist', '', '', '', '', '', '', '', ''))
                conn.close()
                return

            # Build query
            if search_term:
                cursor.execute('''
                    SELECT refund_id, refund_reference, source_type,
                           COALESCE(department, source_type) as department,
                           amount, refund_method, refund_date,
                           reference_id, processed_by, notes
                    FROM unified_refunds
                    WHERE LOWER(COALESCE(refund_reference, '')) LIKE ?
                       OR LOWER(COALESCE(department, '')) LIKE ?
                       OR LOWER(COALESCE(source_type, '')) LIKE ?
                       OR LOWER(COALESCE(reference_id, '')) LIKE ?
                       OR LOWER(COALESCE(processed_by, '')) LIKE ?
                       OR LOWER(COALESCE(notes, '')) LIKE ?
                    ORDER BY refund_id DESC
                ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%',
                      f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
            else:
                cursor.execute('''
                    SELECT refund_id, refund_reference, source_type,
                           COALESCE(department, source_type) as department,
                           amount, refund_method, refund_date,
                           reference_id, processed_by, notes
                    FROM unified_refunds
                    ORDER BY refund_id DESC
                ''')

            refunds = cursor.fetchall()

            # Calculate totals
            total_count = len(refunds)
            total_amount = 0.0

            # Insert data
            for refund in refunds:
                refund_id, ref, source_type, dept, amount, method, date, ref_id, processed_by, notes = refund

                # Format amount
                amount_val = float(amount) if amount else 0.0
                total_amount += amount_val
                amount_str = f"\u00a3{amount_val:.2f}"

                # Color code based on method
                tag = 'student_account' if method == 'Student Account' else 'normal'

                tree.insert('', 'end', values=(
                    refund_id or '',
                    ref or '',
                    source_type or '',
                    dept or '',
                    amount_str,
                    method or '',
                    date or '',
                    ref_id or '',
                    processed_by or '',
                    notes or ''
                ), tags=(tag,))

            # Configure tags
            tree.tag_configure('student_account', background='#e3f2fd')
            tree.tag_configure('normal', background='white')

            # Update summary
            if hasattr(self, 'summary_label'):
                summary_text = f"Total Refunds: {total_count} | Total Amount: \u00a3{total_amount:,.2f}"
                self.summary_label.config(text=summary_text)

            conn.close()

        except Exception as e:
            tree.insert('', 'end', values=('Error', str(e), '', '', '', '', '', '', '', ''))
            print(f"Error loading refunds: {e}")
            import traceback
            traceback.print_exc()

    def _refresh_refunds_table(self, tree):
        """Refresh the refunds table"""
        self._load_refunds_to_table(tree)
        messagebox.showinfo("Success", "Refunds list refreshed successfully")

    def _export_refunds_to_csv(self, tree):
        """Export refunds to CSV file"""
        try:
            import csv

            # Ask for save location
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile="refunds_export.csv"
            )

            if not filename:
                return

            # Write to CSV
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # Write headers
                writer.writerow(['ID', 'Reference', 'Source Type', 'Department', 'Amount', 'Method', 'Date',
                               'Reference ID', 'Processed By', 'Notes'])

                # Write data
                for item in tree.get_children():
                    values = tree.item(item)['values']
                    writer.writerow(values)

            messagebox.showinfo("Success", f"Refunds exported to:\n{filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {e}")

    def _show_financial_summary(self):
        """Show financial summary"""
        try:
            # Call dashboard or report manager if available
            if hasattr(self.gui, 'dashboard') and hasattr(self.gui.dashboard, 'gui_generate_financial_dashboard'):
                self.gui.dashboard.gui_generate_financial_dashboard()
            elif hasattr(self.gui, 'report_manager') and hasattr(self.gui.report_manager, 'gui_revenue_summary_report'):
                self.gui.report_manager.gui_revenue_summary_report()
            else:
                # Generate a simple financial summary
                self._generate_simple_financial_summary()
        except Exception as e:
            messagebox.showerror(_("common.error"), _("finance_gui.messages.failed_open_financial_summary", error=str(e)))

    def _generate_simple_financial_summary(self):
        """Generate a simple financial summary when dashboard not available"""
        try:
            # Create summary window
            summary_window = tk.Toplevel(self.root)
            summary_window.title(_("finance_gui.reports.financial_summary"))
            summary_window.geometry("800x600")
            summary_window.transient(self.root)
            summary_window.grab_set()

            # Title
            title_label = tk.Label(summary_window, text=_("finance_gui.reports.financial_summary_report"),
                                  font=('Arial', 16, 'bold'), bg=self.colors['primary'], fg='white', pady=10)
            title_label.pack(fill='x')

            # Summary text area
            summary_text = ScrolledText(summary_window, font=('Courier', 10), wrap='word')
            summary_text.pack(fill='both', expand=True, padx=10, pady=10)

            # Generate summary data
            conn = get_connection()
            cursor = conn.cursor()

            summary = "FINANCIAL SUMMARY REPORT\n"
            summary += "=" * 70 + "\n"
            summary += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

            # Total revenue
            try:
                cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'completed'")
                total_revenue = cursor.fetchone()[0] or 0

                # Add club payments to total revenue (from payments table with source_type='club')
                try:
                    cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE source_type = 'club' AND status = 'completed'")
                    club_revenue = cursor.fetchone()[0] or 0
                    total_revenue += club_revenue
                except Exception:
                    pass

                # Add housing payments to total revenue
                try:
                    cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE source_type = 'housing' AND status = 'completed'")
                    housing_revenue = cursor.fetchone()[0] or 0
                    total_revenue += housing_revenue
                except Exception:
                    pass

                summary += f"Total Revenue (All Sources): \u00a3{total_revenue:,.2f}\n"
            except Exception:
                summary += "Total Revenue: Data not available\n"

            # Outstanding fees
            try:
                cursor.execute('''
                    SELECT SUM(sf.amount - COALESCE(pa.total_paid, 0))
                    FROM student_fees sf
                    LEFT JOIN (
                        SELECT student_fee_id, SUM(amount) as total_paid
                        FROM payment_allocations
                        GROUP BY student_fee_id
                    ) pa ON sf.student_fee_id = pa.student_fee_id
                    WHERE sf.status != 'paid'
                ''')
                outstanding = cursor.fetchone()[0] or 0

                # Add library fines to outstanding amount
                try:
                    cursor.execute('''
                        SELECT COALESCE(SUM(fine_amount), 0)
                        FROM book_loans
                        WHERE fine_amount > 0 AND (status = 'active' OR status = 'overdue')
                    ''')
                    library_fines = cursor.fetchone()[0] or 0
                    outstanding += library_fines
                except Exception:
                    pass  # Table may not exist

                # Add late fees to outstanding amount
                try:
                    cursor.execute('''
                        SELECT COALESCE(SUM(late_fee_amount), 0)
                        FROM late_fees
                        WHERE waived = 0
                    ''')
                    late_fees = cursor.fetchone()[0] or 0
                    outstanding += late_fees
                except Exception:
                    pass  # Table may not exist

                summary += f"Total Outstanding Fees: \u00a3{outstanding:,.2f}\n"
            except Exception:
                summary += "Total Outstanding Fees: Data not available\n"

            # Student count
            try:
                cursor.execute("SELECT COUNT(*) FROM students WHERE status = 'Active'")
                active_students = cursor.fetchone()[0]
                summary += f"Active Students: {active_students}\n"
            except Exception:
                summary += "Active Students: Data not available\n"

            # Payment count
            try:
                cursor.execute("SELECT COUNT(*) FROM payments WHERE payment_date >= date('now', '-30 days')")
                recent_payments = cursor.fetchone()[0]
                summary += f"Payments (Last 30 Days): {recent_payments}\n"
            except Exception:
                summary += "Payments (Last 30 Days): Data not available\n"

            # Refund requests
            try:
                cursor.execute("SELECT COUNT(*) FROM unified_refunds WHERE source_type = 'general' AND status = 'pending'")
                pending_refunds = cursor.fetchone()[0]
                summary += f"Pending Refund Requests: {pending_refunds}\n"
            except Exception:
                summary += "Pending Refund Requests: Data not available\n"

            summary += "\n" + "=" * 70 + "\n"
            summary += "BUDGET SUMMARY\n"
            summary += "=" * 70 + "\n\n"

            # Budget information
            try:
                cursor.execute('''
                    SELECT COUNT(*) as plans,
                           SUM(total_revenue_budget) as revenue_budget,
                           SUM(total_expense_budget) as expense_budget
                    FROM budget_plans
                    WHERE status IN ('active', 'approved')
                ''')
                budget = cursor.fetchone()
                if budget and budget[0]:
                    revenue_budget = budget[1] or 0
                    expense_budget = budget[2] or 0
                    net_budget = revenue_budget - expense_budget
                    summary += f"Active Budget Plans: {budget[0]}\n"
                    summary += f"Total Revenue Budget: \u00a3{revenue_budget:,.2f}\n"
                    summary += f"Total Expense Budget: \u00a3{expense_budget:,.2f}\n"
                    summary += f"Net Budget: \u00a3{net_budget:,.2f}\n"
                else:
                    summary += "No active budget plans\n"
            except Exception:
                summary += "Budget data: Not available\n"

            summary += "\n" + "=" * 70 + "\n"
            summary += "FINANCIAL AID SUMMARY\n"
            summary += "=" * 70 + "\n\n"

            # Financial aid
            try:
                cursor.execute("SELECT COUNT(*) FROM financial_aid WHERE status = 'active'")
                active_aid = cursor.fetchone()[0]
                cursor.execute("SELECT SUM(amount) FROM financial_aid WHERE status = 'active'")
                total_aid = cursor.fetchone()[0] or 0
                summary += f"Active Financial Aid Awards: {active_aid}\n"
                summary += f"Total Financial Aid Amount: \u00a3{total_aid:,.2f}\n"
            except Exception:
                summary += "Financial aid data: Not available\n"

            summary += "\n" + "=" * 70 + "\n"
            summary += "COLLECTION SUMMARY\n"
            summary += "=" * 70 + "\n\n"

            # Collection cases
            try:
                cursor.execute("SELECT COUNT(*) FROM collection_cases WHERE status = 'active'")
                active_cases = cursor.fetchone()[0]
                cursor.execute("SELECT SUM(outstanding_amount) FROM collection_cases WHERE status = 'active'")
                outstanding_collection = cursor.fetchone()[0] or 0
                summary += f"Active Collection Cases: {active_cases}\n"
                summary += f"Total Outstanding in Collections: \u00a3{outstanding_collection:,.2f}\n"
            except Exception:
                summary += "Collection data: Not available\n"

            summary += "\n" + "=" * 70 + "\n\n"
            summary += "For detailed financial analysis, charts, and reports,\n"
            summary += "please use the Analytics tab or Advanced Reporting GUI.\n"

            conn.close()

            # Display summary
            summary_text.insert('1.0', summary)
            summary_text.config(state='disabled')

            # Close button
            close_btn = ttk.Button(summary_window, text="Close", command=summary_window.destroy)
            close_btn.pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate financial summary: {e}")
