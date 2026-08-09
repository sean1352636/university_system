"""Payments tab UI: table, context menu, refresh, export"""

from unittest.mock import Mock

from education_system.systems.university.interfaces.gui.finance.finance.transaction_manager._imports import (
    tk, ttk, messagebox, filedialog, csv, _, get_connection,
)


class PaymentsTabMixin:
    """Mixin for payments tab UI and table management"""

    def create_payments_tab(self):
        """Create payments management tab"""
        payments_frame = tk.Frame(self.gui.layout.content_frame, bg='white')
        self.gui.layout.tab_frames['payments'] = payments_frame

        # Payments toolbar
        toolbar = tk.Frame(payments_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=5)

        tk.Button(toolbar, text=_("finance_gui.transaction_manager.btn_record_payment"), command=self.show_payment_dialog,
                 bg=self.gui.layout.colors['success'], fg='white', font=('Arial', 9, 'bold')).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.transaction_manager.btn_search_payments"), command=self.search_payments,
                 bg=self.gui.layout.colors['secondary'], fg='white', font=('Arial', 9, 'bold')).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.transaction_manager.btn_payment_analytics"), command=self.show_payment_analytics,
                 bg=self.gui.layout.colors['warning'], fg='white', font=('Arial', 9, 'bold')).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.transaction_manager.btn_email_reminders"), command=self.send_payment_email_reminders,
                 bg=self.gui.layout.colors['info'], fg='white', font=('Arial', 9, 'bold')).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.transaction_manager.btn_refresh"), command=self.refresh_payments,
                 bg=self.gui.layout.colors['dark'], fg='white', font=('Arial', 9, 'bold')).pack(side='right', padx=5)

        # Payments table
        self.create_payments_table(payments_frame)

        # Load payments data
        self.refresh_payments()


    def create_payments_table(self, parent):
        """Create payments table with treeview"""
        table_frame = tk.Frame(parent)
        table_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('payment_id', 'student_id', 'amount', 'method', 'date', 'status')
        self.payments_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        # Configure columns
        self.payments_tree.heading('payment_id', text=_("finance_gui.transaction_manager.column_payment_id"))
        self.payments_tree.heading('student_id', text=_("finance_gui.transaction_manager.column_student_id"))
        self.payments_tree.heading('amount', text=_("finance_gui.transaction_manager.column_amount"))
        self.payments_tree.heading('method', text=_("finance_gui.transaction_manager.column_method"))
        self.payments_tree.heading('date', text=_("finance_gui.transaction_manager.column_date"))
        self.payments_tree.heading('status', text=_("finance_gui.transaction_manager.column_status"))

        self.payments_tree.column('payment_id', width=100)
        self.payments_tree.column('student_id', width=100)
        self.payments_tree.column('amount', width=100)
        self.payments_tree.column('method', width=120)
        self.payments_tree.column('date', width=100)
        self.payments_tree.column('status', width=80)

        # Scrollbars
        v_scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.payments_tree.yview)
        h_scroll = ttk.Scrollbar(table_frame, orient='horizontal', command=self.payments_tree.xview)
        self.payments_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        # Pack table and scrollbars
        self.payments_tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Context menu
        self.create_payments_context_menu()


    def create_payments_context_menu(self):
        """Create context menu for payments table"""
        self.payments_menu = tk.Menu(self.root, tearoff=0)
        self.payments_menu.add_command(label=_("finance_gui.transaction_manager.context_view_details"), command=self.view_payment_details)
        self.payments_menu.add_command(label=_("finance_gui.transaction_manager.context_process_refund"), command=self.process_refund)
        self.payments_menu.add_separator()
        self.payments_menu.add_command(label=_("finance_gui.transaction_manager.context_export_csv"), command=self.export_payments)

        if hasattr(self, 'payments_tree'):
            self.payments_tree.bind("<Button-3>", self.show_payments_menu)


    def refresh_payments(self):
        """Refresh payments data"""
        def refresh_thread():
            try:
                conn = self._get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT payment_id, student_id, amount, payment_method, payment_date, status
                FROM payments
                ORDER BY payment_date DESC
                LIMIT 100
                ''')

                payments = cursor.fetchall()
                conn.close()

                # Update UI in main thread using after() method
                self.root.after(0, lambda: self.update_payments_table(payments))

            except Exception as e:
                error_msg = f"Error refreshing payments: {e}"
                print(error_msg)
                # Update status in main thread
                self.root.after(0, lambda msg=error_msg: self.update_status(msg))

        # Only start thread if we have a real Tk root running
        if hasattr(self.root, 'tk') and hasattr(self.root, '_w') and self.root.tk.call('winfo', 'exists', self.root._w):
            refresh_thread()
        else:
            # If no main loop, run directly
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                SELECT payment_id, student_id, amount, payment_method, payment_date, status
                FROM payments ORDER BY payment_date DESC LIMIT 100
                ''')
                payments = cursor.fetchall()
                conn.close()
                self.update_payments_table(payments)
            except Exception as e:
                print(f"Error refreshing payments: {e}")


    def update_payments_table(self, payments):
        """Update payments table"""
        # Clear existing data
        existing_items = self.payments_tree.get_children()
        self.payments_tree.delete(*existing_items)

        # Insert new data (convert sqlite3.Row to tuple)
        for payment in payments:
            self.payments_tree.insert('', 'end', values=tuple(payment))


    def show_payments_menu(self, event):
        """Show payments context menu"""
        item = self.payments_tree.selection()
        if item:
            self.payments_menu.post(event.x_root, event.y_root)


    def export_payments(self):
        """Export payments to CSV"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title=_("finance_gui.transaction_manager.export_title")
            )

            if filename:
                conn = self._get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT p.payment_id, p.student_id, s.first_name, s.last_name,
                       p.amount, p.payment_method, p.payment_date, p.status
                FROM payments p
                JOIN students s ON p.student_id = s.student_id
                ORDER BY p.payment_date DESC
                ''')

                payments = cursor.fetchall()
                conn.close()

                with open(filename, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Payment ID', 'Student ID', 'First Name', 'Last Name',
                                   'Amount', 'Method', 'Date', 'Status'])
                    writer.writerows(payments)

                self.update_status(_("finance_gui.transaction_manager.export_complete", filename=filename))
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.export_complete", filename=filename))

        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.export_error", error=str(e)))
