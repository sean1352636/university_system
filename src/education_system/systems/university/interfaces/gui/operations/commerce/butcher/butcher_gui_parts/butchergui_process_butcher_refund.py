"""Methods process_butcher_refund through _load_orders."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import butcher_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class ButcherGUI:
    def process_butcher_refund(self):
        """Process a refund with cash/card/student account options.

        Available to: Butcher staff and Admin users
        """
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("butcher.msg_titles.no_selection"), _t('gui.operations.commerce.butcher.butcher_gui_parts.butchergui_process_butcher_refund.dialogs.please_select_an_order_to_refund', default="Please select an order to refund"))
            return

        try:
            values = self.refunds_tree.item(selection[0])['values']
            if len(values) < 8:
                messagebox.showerror(_t("butcher.msg_titles.data_error"), _t('gui.operations.commerce.butcher.butcher_gui_parts.butchergui_process_butcher_refund.dialogs.order_record_is_incomplete', default="Order record is incomplete"))
                return

            order_id = values[0]
            order_date = values[1]
            customer_name = values[2]
            customer_id = values[3]
            order_number = values[4]
            amount = float(values[5])
            payment_method = values[6]
            payment_status = values[7]
        except (IndexError, ValueError) as e:
            messagebox.showerror(_t("butcher.msg_titles.error"), f"Error reading order data: {e}")
            return

        if payment_status == 'refunded':
            messagebox.showinfo(_t("butcher.msg_titles.already_refunded"), _t('gui.operations.commerce.butcher.butcher_gui_parts.butchergui_process_butcher_refund.dialogs.this_order_has_already_been_refunded', default="This order has already been refunded"))
            return

        if payment_status == 'pending':
            messagebox.showinfo(_t("butcher.msg_titles.cannot_refund"), _t('gui.operations.commerce.butcher.butcher_gui_parts.butchergui_process_butcher_refund.dialogs.cannot_refund_unpaid_orders', default="Cannot refund unpaid orders"))
            return

        # Confirm refund
        if not messagebox.askyesno(_t("butcher.msg_titles.confirm_refund"),
                                   f"Refund GBP {amount:.2f} for Order {order_number}?\n\n"
                                   f"Customer: {customer_name}\n"
                                   f"Customer ID: {customer_id}\n"
                                   f"Order ID: {order_id}\n"
                                   f"Date: {order_date}"):
            return

        # Show refund method selection dialog
        refund_method = self.show_butcher_refund_method_dialog(amount, order_id, customer_id)
        if not refund_method:
            return

        # Process based on method
        success = False

        if refund_method == 'Student Account':
            success = self.add_butcher_refund_to_student_account(customer_id, amount, order_number)
        else:
            # For cash/card, just record the refund
            success = True

        if success:
            # Update order payment status to refunded
            try:
                with transaction() as conn:
                    conn.execute('''
                        UPDATE orders
                        SET payment_status = 'refunded'
                        WHERE order_id = ? AND source_type = 'butcher'
                    ''', (order_id,))

                    # Generate refund reference
                    import uuid
                    refund_ref = f"BUTCH-REFUND-{uuid.uuid4().hex[:12].upper()}"

                    # Record refund in unified_refunds table
                    cur = conn.execute('''
                        INSERT INTO unified_refunds
                        (source_type, reference_id, reference_type, amount, refund_method,
                         refund_reference, student_id, customer_name, refund_date, processed_by, status)
                        VALUES ('butcher', ?, 'order', ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, 'processed')
                    ''', (str(order_id), amount, refund_method, refund_ref, customer_id, customer_name,
                          self.current_user.get('username', 'system')))
                    refund_row_id = cur.lastrowid

                # Auto-post to GL (cash has moved). Never raises.
                try:
                    from education_system.systems.university.domains.finance.domain.ledger import notify_ledger
                    notify_ledger('refund', refund_row_id,
                                  posted_by=self.current_user.get('username', 'butcher'))
                except Exception as _e:
                    import logging
                    logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

                # Send refund receipt email
                self.send_butcher_refund_receipt(order_id, customer_id, amount, refund_method, refund_ref, customer_name, order_number)

                # Notify finance GUI
                self.notify_butcher_finance_gui(order_id, amount, refund_method, refund_ref, customer_id)

                messagebox.showinfo(_t("butcher.msg_titles.refund_processed"),
                                  f"Refund of GBP {amount:.2f} processed successfully\n\n"
                                  f"Order: {order_number}\n"
                                  f"Method: {refund_method}\n"
                                  f"Refund Reference: {refund_ref}")

                self.refresh_refunds_list()
                log_activity('refund_processed', 'butcher',
                           details={'ref': refund_ref, 'order': order_number, 'amount': amount, 'method': refund_method})
            except Exception as e:
                messagebox.showerror(_t("butcher.msg_titles.refund_error"), f"Failed to process refund: {e}")
        else:
            messagebox.showerror(_t("butcher.msg_titles.refund_failed"), _t('gui.operations.commerce.butcher.butcher_gui_parts.butchergui_process_butcher_refund.dialogs.failed_to_process_student_account_refund', default="Failed to process student account refund"))

    def show_butcher_refund_method_dialog(self, amount: float, order_id: int, customer_id: str):
        """Show refund method selection dialog."""
        dialog = tk.Toplevel(self.parent)
        dialog.title(_t("butcher.labels.select_refund_method"))
        dialog.geometry("450x400")
        dialog.transient(self.parent)
        dialog.grab_set()

        result = {'method': None}

        # Refund info frame
        info_frame = ttk.LabelFrame(dialog, text=_t("butcher.labels.refund_details"), padding="10")
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(info_frame, text=f"Order ID: {order_id}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Refund Amount: GBP {amount:.2f}",
                 font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=(5, 0))

        # Student account balance if available
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT balance FROM student_finance_accounts
                    WHERE student_id = ? AND account_status = 'active'
                ''', (customer_id,))
                row = cursor.fetchone()
                if row:
                    balance = float(row[0])
                    ttk.Label(info_frame, text=f"Customer ID: {customer_id}").pack(anchor=tk.W, pady=(5, 0))
                    ttk.Label(info_frame, text=f"Current Account Balance: GBP {balance:.2f}").pack(
                        anchor=tk.W, pady=(5, 0))
                    ttk.Label(info_frame, text=f"Balance After Refund: GBP {balance + amount:.2f}",
                             foreground='green').pack(anchor=tk.W)
        except Exception:
            pass

        # Refund method selection
        method_frame = ttk.LabelFrame(dialog, text=_t("butcher.labels.select_refund_method"), padding="10")
        method_frame.pack(fill=tk.X, padx=10, pady=10)

        def select_method(method):
            result['method'] = method
            dialog.destroy()

        # Cash button
        ttk.Button(method_frame, text=_t("butcher.btn.cash"), width=30,
                  command=lambda: select_method('Cash')).pack(pady=5)

        # Card button
        ttk.Button(method_frame, text=_t("butcher.labels.card_original"), width=30,
                  command=lambda: select_method('Card')).pack(pady=5)

        # Student Account button
        ttk.Button(method_frame, text=_t("butcher.btn.student_finance"), width=30,
                  command=lambda: select_method('Student Account')).pack(pady=5)

        # Cancel button
        ttk.Button(dialog, text=_t("butcher.btn.cancel"), command=dialog.destroy).pack(pady=10)

        dialog.wait_window()
        return result['method']

    def add_butcher_refund_to_student_account(self, customer_id: str, amount: float, order_number: str):
        """Add refund amount to student's finance account."""
        try:
            with transaction() as conn:
                # Get account_id and balance
                cursor = conn.execute('''
                    SELECT account_id, balance FROM student_finance_accounts
                    WHERE student_id = ? AND account_status = 'active'
                ''', (customer_id,))
                row = cursor.fetchone()

                if not row:
                    # Try to create account if it doesn't exist
                    conn.execute('''
                        INSERT INTO student_finance_accounts
                        (student_id, balance, account_status)
                        VALUES (?, ?, 'active')
                    ''', (customer_id, amount))

                    # Get the newly created account_id
                    cursor = conn.execute('''
                        SELECT account_id FROM student_finance_accounts
                        WHERE student_id = ?
                    ''', (customer_id,))
                    account_id = cursor.fetchone()[0]
                    balance_before = 0.00
                    balance_after = amount
                else:
                    account_id = row[0]
                    balance_before = float(row[1])
                    balance_after = balance_before + amount

                    # Add to balance
                    conn.execute('''
                        UPDATE student_finance_accounts
                        SET balance = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE account_id = ?
                    ''', (balance_after, account_id))

                # Record transaction
                conn.execute('''
                    INSERT INTO transactions
                    (source_type, account_id, student_id, transaction_type, amount, balance_before,
                     balance_after, description, reference_id, processed_by)
                    VALUES ('student_finance', ?, ?, 'credit', ?, ?, ?, ?, ?, ?)
                ''', (account_id, customer_id, amount, balance_before, balance_after,
                      f'Butcher Shop Refund - Order: {order_number}',
                      f'BUTCHER-REFUND-{order_number}',
                      self.current_user.get('username', 'system')))

            return True
        except Exception as e:
            print(f"Error adding to student account: {e}")
            return False

    def send_butcher_refund_receipt(self, order_id: int, customer_id: str, amount: float,
                                    method: str, refund_ref: str, customer_name: str, order_number: str):
        """Send refund receipt email."""
        try:
            # Get customer email
            with get_connection() as conn:
                # Try to get from orders first
                cursor = conn.execute("SELECT customer_email FROM orders WHERE order_id = ? AND source_type = 'butcher'", (order_id,))
                row = cursor.fetchone()
                if row and row[0]:
                    email = row[0]
                else:
                    # Fallback to students table
                    cursor = conn.execute("SELECT email FROM students WHERE student_id = ?", (customer_id,))
                    row = cursor.fetchone()
                    if row and row[0]:
                        email = row[0]
                    else:
                        # Fallback to users table
                        cursor = conn.execute("SELECT email FROM users WHERE username = ? OR id = ?", (customer_id, customer_id))
                        row = cursor.fetchone()
                        email = row[0] if row and row[0] else None

            if email:
                # Get balance for student accounts
                balance_text = ""
                if method == 'Student Account':
                    with get_connection() as conn:
                        cursor = conn.execute('''
                            SELECT balance FROM student_finance_accounts
                            WHERE student_id = ? AND account_status = 'active'
                        ''', (customer_id,))
                        row = cursor.fetchone()
                        if row:
                            balance = float(row[0])
                            balance_text = f"Your new Student Finance Account balance: GBP {balance:.2f}"

                # Render email from template
                subject, body = render_template('commerce/butcher/refund_receipt', {
                    'customer_name': customer_name,
                    'refund_ref': refund_ref,
                    'original_order': order_number,
                    'refund_amount': f"GBP {amount:.2f}",
                    'refund_method': method,
                    'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'balance_text': balance_text
                })

                # Fallback if template not found
                if not subject or not body:
                    subject = "Butcher Shop Payment Refund Receipt"
                    body = f"Dear {customer_name},\n\nYour refund of GBP {amount:.2f} has been processed.\nReference: {refund_ref}"

                _send_butcher_email(email, subject, body)
                print(f"[Butcher] Refund receipt sent to {email}")
            else:
                print(f"[Butcher] No email found for customer {customer_id}")
        except Exception as e:
            print(f"Error sending refund receipt: {e}")

    def notify_butcher_finance_gui(self, order_id: int, amount: float, method: str,
                                   refund_ref: str, customer_id: str):
        """Notify finance GUI about the refund - already recorded in unified_refunds."""
        try:
            print(f"[Butcher] Refund recorded in finance system: {refund_ref}")
        except Exception as e:
            print(f"Error notifying finance system: {e}")

    def create_reports_tab(self):
        """Create the reports and analytics tab - Function 9"""
        reports_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(reports_frame, text=_t("butcher.tabs.reports"))

        # Report options
        options_frame = ttk.LabelFrame(reports_frame, text=_t("butcher.labels.report_options"), padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(options_frame, text=_t("butcher.labels.date_from") + ":").pack(side=tk.LEFT)
        self.report_from_var = tk.StringVar(value=(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
        ttk.Entry(options_frame, textvariable=self.report_from_var, width=12).pack(side=tk.LEFT, padx=5)

        ttk.Label(options_frame, text=_t("butcher.labels.date_to") + ":").pack(side=tk.LEFT)
        self.report_to_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(options_frame, textvariable=self.report_to_var, width=12).pack(side=tk.LEFT, padx=5)

        ttk.Button(options_frame, text=_t("butcher.btn.generate_report"),
                  command=self.generate_admin_report).pack(side=tk.LEFT, padx=20)
        ttk.Button(options_frame, text=_t("butcher.btn.email_report"),
                  command=self.email_admin_report).pack(side=tk.LEFT, padx=5)

        # Report display
        report_display = ttk.LabelFrame(reports_frame, text=_t("butcher.labels.report_output"), padding="5")
        report_display.pack(fill=tk.BOTH, expand=True)

        self.report_text = tk.Text(report_display, wrap=tk.WORD, height=25)
        scrollbar = ttk.Scrollbar(report_display, orient=tk.VERTICAL, command=self.report_text.yview)
        self.report_text.configure(yscrollcommand=scrollbar.set)

        self.report_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _get_categories(self) -> dict:
        """Get meat categories - Function 10"""
        from education_system.systems.university.domain.operations.commerce.butcher.services.butcher_core import MEAT_CATEGORIES
        return MEAT_CATEGORIES

    def _load_products(self):
        """Load products into the treeview - Function 11"""
        for item in self.products_tree.get_children():
            self.products_tree.delete(item)

        try:
            with get_db_connection() as conn:
                category_filter = self.category_filter.get()
                query = "SELECT * FROM products WHERE source_type = 'butcher' AND is_available = 1"
                params = []

                if category_filter != 'All':
                    # Find category key from value
                    categories = self._get_categories()
                    cat_key = next((k for k, v in categories.items() if v == category_filter), None)
                    if cat_key:
                        query += ' AND category = ?'
                        params.append(cat_key)

                query += ' ORDER BY category, name'
                rows = conn.execute(query, params).fetchall()

                # Also populate order product combo
                product_list = []
                for row in rows:
                    categories = self._get_categories()
                    cat_name = categories.get(row['category'], row['category'])
                    self.products_tree.insert('', tk.END, values=(
                        row['product_id'],
                        row['name'],
                        cat_name,
                        f"£{row['price_per_unit']:.2f}",
                        f"{row['stock_quantity']:.1f}",
                        row['unit_type']
                    ))
                    product_list.append(f"{row['product_id']}: {row['name']} (£{row['price_per_unit']:.2f}/{row['unit_type']})")

                self.order_product_combo['values'] = product_list
                self.inv_product_combo['values'] = product_list

        except Exception as e:
            logger.error(f"Error loading products: {e}")

    def _load_orders(self):
        """Load orders into the treeview - Function 12"""
        for item in self.orders_tree.get_children():
            self.orders_tree.delete(item)

        try:
            with get_db_connection() as conn:
                rows = conn.execute('''
                    SELECT * FROM orders
                    WHERE source_type = 'butcher'
                    ORDER BY created_at DESC LIMIT 100
                ''').fetchall()

                for row in rows:
                    self.orders_tree.insert('', tk.END, values=(
                        row['order_number'],
                        row['customer_name'],
                        f"£{row['total_amount']:.2f}",
                        row['order_status'],
                        row['payment_status'],
                        row['created_at'][:10] if row['created_at'] else ''
                    ))
        except Exception as e:
            logger.error(f"Error loading orders: {e}")
