"""Methods create_refunds_tab through send_musicshop_refund_receipt."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import musicshop_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class MusicShopGUI:
    def create_refunds_tab(self):
        """Create the refunds management tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("musicshop.tabs.refunds"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(header_frame, text=_t("musicshop.labels.transaction_refunds"),
                 font=('Helvetica', 14, 'bold')).pack(side=tk.LEFT)

        # Search frame
        search_frame = ttk.LabelFrame(tab, text=_t("musicshop.labels.search_transactions"), padding="10")
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text=_t("musicshop.labels.search_by")).pack(side=tk.LEFT, padx=5)
        self.refunds_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.refunds_search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(search_frame, text=_t("musicshop.btn.search"), command=self.refresh_refunds_list).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_frame, text=_t("musicshop.btn.show_all"), command=lambda: [self.refunds_search_var.set(''), self.refresh_refunds_list()]).pack(side=tk.LEFT, padx=2)

        # Transactions table
        trans_frame = ttk.Frame(tab)
        trans_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ('transaction_id', 'order_id', 'date', 'customer', 'amount', 'payment_method', 'status')
        self.refunds_tree = ttk.Treeview(trans_frame, columns=columns, show='headings', height=15)

        self.refunds_tree.heading('transaction_id', text=_t('musicshop.columns.transaction_id'))
        self.refunds_tree.heading('order_id', text=_t('musicshop.columns.order_id'))
        self.refunds_tree.heading('date', text=_t('musicshop.columns.date'))
        self.refunds_tree.heading('customer', text=_t('musicshop.columns.customer'))
        self.refunds_tree.heading('amount', text=_t('musicshop.columns.amount'))
        self.refunds_tree.heading('payment_method', text=_t('musicshop.columns.payment_method'))
        self.refunds_tree.heading('status', text=_t('musicshop.columns.status'))

        self.refunds_tree.column('transaction_id', width=120)
        self.refunds_tree.column('order_id', width=100)
        self.refunds_tree.column('date', width=150)
        self.refunds_tree.column('customer', width=120)
        self.refunds_tree.column('amount', width=100)
        self.refunds_tree.column('payment_method', width=120)
        self.refunds_tree.column('status', width=100)

        scrollbar = ttk.Scrollbar(trans_frame, orient=tk.VERTICAL, command=self.refunds_tree.yview)
        self.refunds_tree.configure(yscrollcommand=scrollbar.set)

        self.refunds_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        button_frame = ttk.Frame(tab)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text=_t("musicshop.btn.process_refund"), command=self.process_musicshop_refund).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("musicshop.btn.view_details"), command=self.view_refund_transaction_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("musicshop.btn.export_csv"), command=self.export_refunds_to_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("musicshop.btn.refresh"), command=self.refresh_refunds_list).pack(side=tk.LEFT, padx=5)

        # Initial load
        self.refresh_refunds_list()

    def refresh_refunds_list(self):
        """Refresh the refunds list with all transactions"""
        # Clear existing items
        for item in self.refunds_tree.get_children():
            self.refunds_tree.delete(item)

        try:
            with get_db_connection() as conn:
                search_term = self.refunds_search_var.get().strip()

                if search_term:
                    query = '''
                        SELECT transaction_id, reference_id as order_id, created_at, customer_id,
                               amount, payment_method, status
                        FROM transactions
                        WHERE source_type = 'music_shop' AND (transaction_id LIKE ? OR reference_id LIKE ? OR customer_id LIKE ?)
                        ORDER BY created_at DESC
                        LIMIT 500
                    '''
                    search_pattern = f'%{search_term}%'
                    cursor = conn.execute(query, (search_pattern, search_pattern, search_pattern))
                else:
                    query = '''
                        SELECT transaction_id, reference_id as order_id, created_at, customer_id,
                               amount, payment_method, status
                        FROM transactions
                        WHERE source_type = 'music_shop'
                        ORDER BY created_at DESC
                        LIMIT 500
                    '''
                    cursor = conn.execute(query)

                transactions = cursor.fetchall()

                for trans in transactions:
                    trans_id, order_id, created_at, customer_id, amount, payment_method, status = trans

                    # Format payment method
                    payment_display = payment_method.replace('_', ' ').title() if payment_method else 'N/A'

                    # Format status
                    status_display = status.upper() if status else 'COMPLETED'

                    self.refunds_tree.insert('', tk.END, values=(
                        trans_id,
                        order_id,
                        created_at,
                        customer_id or 'N/A',
                        f"£{amount:.2f}",
                        payment_display,
                        status_display
                    ))

        except Exception as e:
            messagebox.showerror(_t("musicshop.msg_titles.database_error"), f"Error loading transactions: {e}")
            logger.error(f"Error loading transactions: {e}")

    def process_musicshop_refund(self):
        """Process a refund for selected music shop transaction"""
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("musicshop.msg_titles.no_selection"), _t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_create_refunds_tab.dialogs.please_select_a_transaction_to_refund', default="Please select a transaction to refund."))
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']

        if len(values) < 7:
            messagebox.showerror(_t("musicshop.msg_titles.error"), _t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_create_refunds_tab.dialogs.invalid_transaction_data', default="Invalid transaction data."))
            return

        transaction_id = values[0]
        order_id = values[1]
        amount_str = values[4].replace('£', '').strip()
        try:
            amount = float(amount_str)
        except ValueError:
            messagebox.showerror(_t("musicshop.msg_titles.error"), _t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_create_refunds_tab.dialogs.invalid_amount_format', default="Invalid amount format."))
            return

        status = values[6]

        # Check if already refunded
        if status == 'REFUNDED':
            messagebox.showinfo(_t("musicshop.msg_titles.already_refunded"), _t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_create_refunds_tab.dialogs.this_transaction_has_already_been_refunded', default="This transaction has already been refunded."))
            return

        # Confirm refund
        if not messagebox.askyesno(_t("musicshop.msg_titles.confirm_refund"), f"Process refund of £{amount:.2f} for transaction {transaction_id}?"):
            return

        # Get transaction details
        try:
            with get_db_connection() as conn:
                cursor = conn.execute('''
                    SELECT customer_id, payment_method
                    FROM transactions
                    WHERE transaction_id = ? AND source_type = 'music_shop'
                ''', (transaction_id,))

                trans_data = cursor.fetchone()

                if not trans_data:
                    messagebox.showerror(_t("musicshop.msg_titles.error"), _t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_create_refunds_tab.dialogs.transaction_not_found_in_database', default="Transaction not found in database."))
                    return

                customer_id = trans_data[0]
                payment_method = trans_data[1]

        except Exception as e:
            messagebox.showerror(_t("musicshop.msg_titles.database_error"), f"Error fetching transaction details: {e}")
            return

        # Show refund method dialog
        refund_method = self.show_musicshop_refund_method_dialog(amount, transaction_id, customer_id)

        if not refund_method:
            return

        # Process refund through the service (local write + Finance posting +
        # student-account credit all live in TransactionManager.refund_order)
        try:
            processed_by = self.current_user.get('username', 'System') if self.current_user else 'System'
            result = TransactionManager.refund_order(
                int(order_id), amount, refund_method,
                reason=f"Refund of transaction {transaction_id}",
                processed_by=processed_by,
                transaction_id=transaction_id,
            )
            if not result.get('success'):
                messagebox.showerror(_t("musicshop.msg_titles.error"), result.get('message', 'Failed to process refund'))
                return
            refund_ref = result.get('refund_ref') or f"MUSIC-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # If student account refund, warn when the credit failed
            if refund_method == 'Student Account' and not result.get('credited'):
                messagebox.showwarning(_t("musicshop.msg_titles.partial_success"),
                                     _t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_create_refunds_tab.dialogs.refund_recorded_but_failed_to_credit_student_account_please_cred', default="Refund recorded but failed to credit student account. Please credit manually."))

            # Send refund receipt email
            self.send_musicshop_refund_receipt(transaction_id, customer_id, amount, refund_method, refund_ref)

            # Notify finance GUI
            self.notify_musicshop_finance_gui(transaction_id, amount, refund_method, refund_ref, customer_id)

            messagebox.showinfo(_t("musicshop.msg_titles.refund_processed"),
                              f"Refund of £{amount:.2f} processed successfully.\nRefund Reference: {refund_ref}\nOrder status updated to Refunded.")

            # Refresh the list
            self.refresh_refunds_list()

        except Exception as e:
            messagebox.showerror(_t("musicshop.msg_titles.database_error"), f"Error processing refund: {e}")
            logger.error(f"Error processing refund: {e}")

    def show_musicshop_refund_method_dialog(self, amount, transaction_id, customer_id):
        """Show dialog to select refund method"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_create_refunds_tab.windows.select_refund_method', default="Select Refund Method"))
        dialog.geometry("400x350")
        dialog.transient(self.root)
        dialog.grab_set()

        result = {'method': None}

        ttk.Label(dialog, text=f"Refund Amount: £{amount:.2f}", font=('Arial', 12, 'bold')).pack(pady=10)
        ttk.Label(dialog, text=f"Transaction ID: {transaction_id}").pack(pady=5)

        # Show student account balance if customer_id available
        if customer_id:
            try:
                current_balance = get_student_finance_account_balance(customer_id)
                if current_balance is not None:
                    new_balance = current_balance + amount
                    balance_frame = ttk.LabelFrame(dialog, text=_t("musicshop.btn.student_finance"), padding=10)
                    balance_frame.pack(pady=10, padx=20, fill=tk.X)

                    ttk.Label(balance_frame, text=f"Current Balance: £{current_balance:.2f}").pack(anchor='w')
                    ttk.Label(balance_frame, text=f"After Refund: £{new_balance:.2f}",
                            font=('Arial', 10, 'bold')).pack(anchor='w')
            except Exception as e:
                logger.error(f"Error getting balance: {e}")

        ttk.Label(dialog, text=_t("musicshop.labels.select_refund_method"), font=('Arial', 10)).pack(pady=10)

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def select_cash():
            result['method'] = 'Cash'
            dialog.destroy()

        def select_card():
            result['method'] = 'Card'
            dialog.destroy()

        def select_student_account():
            if not customer_id:
                messagebox.showerror(_t("musicshop.msg_titles.error"), _t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_create_refunds_tab.dialogs.no_customer_id_associated_with_this_transaction', default="No customer ID associated with this transaction."))
                return
            result['method'] = 'Student Account'
            dialog.destroy()

        ttk.Button(button_frame, text=_t("musicshop.btn.cash_refund"), command=select_cash, width=20).pack(pady=5)
        ttk.Button(button_frame, text=_t("musicshop.btn.card_refund"), command=select_card, width=20).pack(pady=5)

        if customer_id:
            ttk.Button(button_frame, text=_t("musicshop.btn.student_finance"), command=select_student_account, width=20).pack(pady=5)

        ttk.Button(button_frame, text=_t("musicshop.btn.cancel"), command=dialog.destroy, width=20).pack(pady=10)

        dialog.wait_window()
        return result['method']

    def send_musicshop_refund_receipt(self, transaction_id, customer_id, amount, method, refund_ref):
        """Send refund receipt email to customer"""
        try:
            from education_system.systems.university.infrastructure.email.email_service import send_email
            from education_system.systems.university.domains.finance.infrastructure.finance_integration import get_student_info
            from education_system.systems.university.infrastructure.email.template_utils import render_template

            # Get customer email
            customer_info = get_student_info(customer_id)
            if not customer_info or not customer_info.get('email'):
                logger.warning(f"No email found for customer {customer_id}")
                return

            customer_email = customer_info['email']
            customer_name = customer_info.get('full_name', 'Valued Customer')

            # Get updated balance if student account refund
            balance_text = ""
            if method == 'Student Account':
                try:
                    new_balance = get_student_finance_account_balance(customer_id)
                    if new_balance is not None:
                        balance_text = f"Your updated account balance is: £{new_balance:.2f}"
                except Exception:
                    logger.debug("Could not retrieve updated student finance balance")

            # Use JSON template for email
            subject, body = render_template('finance_commerce/commerce/musicshop/refund_receipt', {
                'customer_name': customer_name,
                'refund_ref': refund_ref,
                'original_transaction': str(transaction_id),
                'refund_amount': f"£{amount:.2f}",
                'refund_method': method,
                'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'balance_text': balance_text
            })

            result = send_email(customer_email, subject, body)
            if result:
                logger.info(f"Refund receipt sent to {customer_email}")
            else:
                logger.warning(f"Failed to send refund receipt to {customer_email}")

        except Exception as e:
            logger.error(f"Error sending refund receipt: {e}")
