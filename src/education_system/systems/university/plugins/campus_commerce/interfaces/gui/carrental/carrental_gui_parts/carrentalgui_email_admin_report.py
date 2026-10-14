"""Methods email_admin_report through show_carrental_refund_method_dialog."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import carrental_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class CarRentalGUI:
    def email_admin_report(self):
        """Email admin report"""
        try:
            from education_system.systems.university.infrastructure.email.email_service import send_email

            report = ReportManager.generate_admin_report()

            # Get admin email
            with get_db_connection() as conn:
                cursor = conn.execute(
                    "SELECT email FROM users WHERE role = 'admin' AND email IS NOT NULL LIMIT 1"
                )
                result = cursor.fetchone()

            if result and result[0]:
                send_email(
                    result[0],
                    _t("carrental.email.admin_report_subject"),
                    report
                )
                messagebox.showinfo(_t("common.success"), _t("carrental.messages.report_emailed"))
            else:
                messagebox.showwarning(_t("common.warning"), _t("carrental.errors.no_admin_email"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def create_refunds_tab(self):
        """Create the refunds management tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("carrental.tabs.refunds", default="Refunds"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(header_frame, text=_t("carrental.refunds.title", default="===== REFUNDS ====="),
                 font=('Arial', 14, 'bold')).pack(side=tk.LEFT)

        # Search frame
        search_frame = ttk.LabelFrame(tab, text=_t("common.search", default="Search"), padding="10")
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text=_t("common.search_label", default="Search:")).grid(row=0, column=0, sticky=tk.W, padx=5)
        self.refund_search_var = tk.StringVar()
        self.refund_search_var.trace('w', lambda *args: self.refresh_refunds_list())
        search_entry = ttk.Entry(search_frame, textvariable=self.refund_search_var, width=40)
        search_entry.grid(row=0, column=1, sticky=tk.W, padx=5)

        # Table frame
        table_frame = ttk.Frame(tab)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Create treeview with 7 columns
        columns = ('transaction_id', 'date', 'customer', 'amount', 'transaction_type', 'payment_method', 'status')
        self.refunds_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        # Configure columns
        self.refunds_tree.heading('transaction_id', text=_t('carrental.refunds.transaction_id', default='Transaction ID'))
        self.refunds_tree.heading('date', text=_t('common.date', default='Date'))
        self.refunds_tree.heading('customer', text=_t('carrental.common.customer', default='Customer'))
        self.refunds_tree.heading('amount', text=_t('common.amount', default='Amount'))
        self.refunds_tree.heading('transaction_type', text=_t('carrental.refunds.type', default='Type'))
        self.refunds_tree.heading('payment_method', text=_t('common.payment_method', default='Payment Method'))
        self.refunds_tree.heading('status', text=_t('common.status', default='Status'))

        self.refunds_tree.column('transaction_id', width=100)
        self.refunds_tree.column('date', width=150)
        self.refunds_tree.column('customer', width=150)
        self.refunds_tree.column('amount', width=100)
        self.refunds_tree.column('transaction_type', width=120)
        self.refunds_tree.column('payment_method', width=120)
        self.refunds_tree.column('status', width=100)

        # Scrollbars
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.refunds_tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.refunds_tree.xview)
        self.refunds_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.refunds_tree.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        vsb.grid(row=0, column=1, sticky=(tk.N, tk.S))
        hsb.grid(row=1, column=0, sticky=(tk.E, tk.W))

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Buttons frame - Make buttons more prominent and visible
        buttons_frame = tk.Frame(tab, bg='#f0f0f0', relief='raised', borderwidth=2)
        buttons_frame.pack(fill=tk.X, pady=15, padx=10)

        # Add instruction label
        tk.Label(buttons_frame, text=_t("carrental.labels.select_transaction_action"),
                font=('Arial', 10, 'italic'), bg='#f0f0f0', fg='#555').pack(pady=(10, 5))

        # Button container for centering
        btn_container = tk.Frame(buttons_frame, bg='#f0f0f0')
        btn_container.pack(pady=(0, 10))

        # Large, prominent refund button
        tk.Button(btn_container, text="💸 " + _t("carrental.refunds.process", default="Process Refund"),
                 command=self.process_carrental_refund,
                 font=('Arial', 12, 'bold'), bg='#e74c3c', fg='white',
                 activebackground='#c0392b', activeforeground='white',
                 relief='raised', padx=20, pady=12, cursor='hand2',
                 borderwidth=3).pack(side=tk.LEFT, padx=10)

        tk.Button(btn_container, text="📋 " + _t("common.view_details", default="View Details"),
                 command=self.view_carrental_transaction_details,
                 font=('Arial', 11, 'bold'), bg='#3498db', fg='white',
                 activebackground='#2980b9', activeforeground='white',
                 relief='raised', padx=15, pady=10, cursor='hand2',
                 borderwidth=2).pack(side=tk.LEFT, padx=10)

        tk.Button(btn_container, text="🔄 " + _t("common.refresh", default="Refresh"),
                 command=self.refresh_refunds_list,
                 font=('Arial', 11, 'bold'), bg='#95a5a6', fg='white',
                 activebackground='#7f8c8d', activeforeground='white',
                 relief='raised', padx=15, pady=10, cursor='hand2',
                 borderwidth=2).pack(side=tk.LEFT, padx=10)

        tk.Button(btn_container, text="📊 " + _t("common.export_csv", default="Export to CSV"),
                 command=self.export_refunds_to_csv,
                 font=('Arial', 11, 'bold'), bg='#27ae60', fg='white',
                 activebackground='#229954', activeforeground='white',
                 relief='raised', padx=15, pady=10, cursor='hand2',
                 borderwidth=2).pack(side=tk.LEFT, padx=10)

        # Load data
        self.refresh_refunds_list()

    def refresh_refunds_list(self):
        """Refresh the refunds list with search support"""
        # Clear existing items
        for item in self.refunds_tree.get_children():
            self.refunds_tree.delete(item)

        try:
            search_term = self.refund_search_var.get().lower()

            with get_db_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT
                        t.transaction_id,
                        t.created_at,
                        t.customer_id,
                        t.amount,
                        t.transaction_type,
                        t.payment_method,
                        t.status,
                        t.reference_number
                    FROM transactions t
                    WHERE t.source_type = 'car_rental'
                    ORDER BY t.created_at DESC
                """

                cursor.execute(query)
                transactions = cursor.fetchall()

                for trans in transactions:
                    transaction_id, date, customer_id, amount, transaction_type, payment_method, status, reference = trans

                    # Apply search filter
                    if search_term:
                        searchable = f"{transaction_id} {customer_id} {transaction_type} {status} {reference or ''}".lower()
                        if search_term not in searchable:
                            continue

                    # Format date
                    if date:
                        try:
                            date_obj = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
                            formatted_date = date_obj.strftime('%Y-%m-%d %H:%M')
                        except (ValueError, TypeError):
                            formatted_date = date
                    else:
                        formatted_date = ''

                    # Color code by status
                    tag = 'refunded' if status == 'refunded' else 'completed'

                    self.refunds_tree.insert('', tk.END, values=(
                        transaction_id,
                        formatted_date,
                        customer_id,
                        f"£{amount:.2f}",
                        transaction_type or 'N/A',
                        payment_method or 'N/A',
                        status or 'completed'
                    ), tags=(tag,))

                # Configure tags
                self.refunds_tree.tag_configure('refunded', background='#ffcccc')
                self.refunds_tree.tag_configure('completed', background='#ccffcc')

        except Exception as e:
            logger.error(f"Error refreshing refunds list: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to load refunds: {str(e)}")

    def refund_from_returns_tab(self):
        """Process a refund from the Returns tab by finding the transaction for the selected rental"""
        # Get selected rental
        selection = self.active_rentals_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning", default="Warning"),
                                  _t('gui.operations.commerce.carrental.carrental_gui_parts.carrentalgui_email_admin_report.dialogs.please_select_a_rental_to_refund', default="Please select a rental to refund."))
            return

        item = self.active_rentals_tree.item(selection[0])
        values = item['values']
        rental_id = values[0]
        rental_number = values[1]
        customer_name = values[2]
        amount_str = values[5]

        try:
            # Find the transaction for this rental
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT transaction_id, amount, customer_id, payment_method, status
                    FROM transactions
                    WHERE source_type = 'car_rental' AND reference_id = ? AND reference_type = 'rental'
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (rental_id,))
                result = cursor.fetchone()

                if not result:
                    messagebox.showerror(_t("common.error", default="Error"),
                                       f"No transaction found for rental {rental_number}.\n\n"
                                       "The rental may not have been paid yet.")
                    return

                transaction_id, amount, customer_id, payment_method, status = result

                # Check if already refunded
                if status == 'refunded':
                    messagebox.showwarning(_t("carrental.refunds.already_refunded", default="Already Refunded"),
                                          f"Rental {rental_number} has already been refunded.")
                    return

            # Confirm refund
            if not messagebox.askyesno(_t("carrental.refunds.confirm", default="Confirm Refund"),
                                       f"Process refund for Rental {rental_number}?\n\n"
                                       f"Customer: {customer_name}\n"
                                       f"Amount: £{amount:.2f}\n"
                                       f"Payment Method: {payment_method}"):
                return

            # Show refund method dialog
            self.show_carrental_refund_method_dialog(transaction_id, amount, customer_id)

        except Exception as e:
            logger.error(f"Error processing refund from returns tab: {e}")
            messagebox.showerror(_t("common.error", default="Error"),
                               f"Failed to process refund: {str(e)}")

    def process_carrental_refund(self):
        """Process a refund for a car rental transaction"""
        # Get selected transaction
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.no_selection", default="No Selection"),
                                  _t("carrental.refunds.select_transaction", default="Please select a transaction to refund."))
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']
        transaction_id = values[0]
        amount_str = values[3]
        status = values[6]

        # Check if already refunded
        if status == 'refunded':
            messagebox.showwarning(_t("carrental.refunds.already_refunded", default="Already Refunded"),
                                  _t("carrental.refunds.already_refunded_msg", default="This transaction has already been refunded."))
            return

        # Parse amount
        try:
            amount = float(amount_str.replace('£', '').replace(',', ''))
        except (ValueError, TypeError):
            messagebox.showerror(_t("common.error", default="Error"),
                               _t("common.invalid_amount", default="Invalid amount format."))
            return

        # Confirm refund
        if not messagebox.askyesno(_t("carrental.refunds.confirm", default="Confirm Refund"),
                                   f"Refund £{amount:.2f} for Transaction #{transaction_id}?"):
            return

        try:
            # Get customer ID
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT customer_id FROM transactions WHERE transaction_id = ? AND source_type = 'car_rental'",
                             (transaction_id,))
                result = cursor.fetchone()
                if not result:
                    messagebox.showerror(_t("common.error", default="Error"),
                                       _t("carrental.refunds.transaction_not_found", default="Transaction not found."))
                    return
                customer_id = result[0]

            # Show refund method dialog
            self.show_carrental_refund_method_dialog(transaction_id, amount, customer_id)

        except Exception as e:
            logger.error(f"Error processing car rental refund: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to process refund: {str(e)}")

    def show_carrental_refund_method_dialog(self, transaction_id, amount, customer_id):
        """Show dialog to select refund method"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("carrental.refunds.select_method", default="Select Refund Method"))
        dialog.geometry("500x350")
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        # Header
        ttk.Label(dialog, text=_t("carrental.refunds.select_method", default="Select Refund Method"),
                 font=('Arial', 12, 'bold')).pack(pady=10)

        ttk.Label(dialog, text=f"Refund Amount: £{amount:.2f}").pack(pady=5)

        # Get current balance if finance is available
        current_balance = None
        if customer_id:
            try:
                current_balance = get_student_finance_account_balance(customer_id)
                ttk.Label(dialog, text=f"Current Student Account Balance: £{current_balance:.2f}",
                         foreground='blue').pack(pady=5)
                new_balance = current_balance + amount
                ttk.Label(dialog, text=f"New Balance After Refund: £{new_balance:.2f}",
                         foreground='green').pack(pady=5)
            except Exception as e:
                logger.warning(f"Could not get student balance: {e}")

        # Buttons frame
        buttons_frame = ttk.Frame(dialog)
        buttons_frame.pack(pady=20, fill=tk.BOTH, expand=True)

        def refund_cash():
            dialog.destroy()
            self._complete_carrental_refund(transaction_id, amount, 'cash', customer_id)

        def refund_card():
            dialog.destroy()
            self._complete_carrental_refund(transaction_id, amount, 'card', customer_id)

        def refund_student_account():
            dialog.destroy()
            self.add_carrental_refund_to_student_account(transaction_id, amount, customer_id)

        # Create buttons
        cash_btn = ttk.Button(buttons_frame, text=_t("common.refund_cash", default="💵 Refund as Cash"),
                             command=refund_cash, width=30)
        cash_btn.pack(pady=10)

        card_btn = ttk.Button(buttons_frame, text=_t("common.refund_card", default="💳 Refund to Card"),
                             command=refund_card, width=30)
        card_btn.pack(pady=10)

        account_btn = ttk.Button(buttons_frame, text=_t("common.refund_account", default="🏦 Refund to Student Account"),
                                command=refund_student_account, width=30)
        account_btn.pack(pady=10)

        ttk.Button(buttons_frame, text=_t("common.cancel", default="Cancel"),
                  command=dialog.destroy, width=30).pack(pady=10)
