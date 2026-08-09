"""Methods view_order_details through email_admin_report."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import musicshop_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class MusicShopGUI:
    def view_order_details(self):
        """View order details"""
        selected = self.orders_tree.selection()
        if not selected:
            return

        order_id = self.orders_tree.item(selected[0])['values'][0]
        order = OrderManager.get_order(order_id)
        if not order:
            return

        details = f"Order: {order['order_number']}\nCustomer: {order['customer_name']}\n\nItems:\n"
        for item in order.get('items', []):
            details += f"  - {item['product_title']} x{item['quantity']} = £{item['subtotal']:.2f}\n"
        details += f"\nTotal: £{order['total_amount']:.2f}\nStatus: {order['status']}"
        messagebox.showinfo(_t("musicshop.labels.order_details"), details)

    def cancel_order(self):
        """Cancel an order"""
        selected = self.orders_tree.selection()
        if not selected:
            return

        order_id = self.orders_tree.item(selected[0])['values'][0]
        if messagebox.askyesno(_t("common.confirm"), _t("musicshop.confirm.cancel_order")):
            if OrderManager.cancel_order(order_id, "Cancelled"):
                self._load_orders()
                self._load_products()

    def process_refund(self):
        """Process a refund with method selection"""
        selected = self.orders_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_view_order_details.dialogs.please_select_an_order_to_refund', default="Please select an order to refund"))
            return

        values = self.orders_tree.item(selected[0])['values']
        order_id = values[0]
        amount = float(values[3].replace('£', ''))

        # Get order details
        order = OrderManager.get_order(order_id)
        if not order:
            messagebox.showerror(_t("common.error"), _t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_view_order_details.dialogs.order_not_found', default="Order not found"))
            return

        customer_id = order.get('customer_id', 'GUEST')

        # Confirm refund
        if not messagebox.askyesno(_t("common.confirm"), f"Process refund of £{amount:.2f} for order {order['order_number']}?"):
            return

        # Get transaction_id for this order
        try:
            with get_db_connection() as conn:
                cursor = conn.execute('''
                    SELECT transaction_id FROM transactions
                    WHERE source_type = 'music_shop' AND reference_id = ? AND reference_type = 'order' AND transaction_type = 'payment'
                    ORDER BY created_at DESC LIMIT 1
                ''', (order_id,))
                trans_result = cursor.fetchone()
                transaction_id = trans_result[0] if trans_result else None
        except Exception as e:
            logger.error(f"Error getting transaction: {e}")
            transaction_id = None

        # Show refund method dialog
        refund_method = self.show_refund_method_dialog(amount, order['order_number'], customer_id)
        if not refund_method:
            return

        # Process the refund
        try:
            if TransactionManager.process_refund(order_id, amount, processed_by=self.current_user.get('username')):
                # Generate refund reference
                refund_ref = f"MUSIC-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

                # Update transaction status if found
                if transaction_id:
                    with get_db_connection() as conn:
                        conn.execute('''
                            UPDATE transactions
                            SET status = 'refunded'
                            WHERE transaction_id = ? AND source_type = 'music_shop'
                        ''', (transaction_id,))
                        conn.commit()

                # Automatically mark order as refunded
                OrderManager.update_order_status(order_id, 'refunded')

                # If student account refund, add to their account
                if refund_method == 'Student Account':
                    success = self.add_musicshop_refund_to_student_account(customer_id, amount, refund_ref)
                    if not success:
                        messagebox.showwarning(_t("musicshop.msg_titles.partial_success"),
                                             _t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_view_order_details.dialogs.refund_recorded_but_failed_to_credit_student_account_please_cred', default="Refund recorded but failed to credit student account. Please credit manually."))

                # Send refund receipt email
                if transaction_id:
                    self.send_musicshop_refund_receipt(transaction_id, customer_id, amount, refund_method, refund_ref)

                # Notify finance GUI
                if transaction_id:
                    self.notify_musicshop_finance_gui(transaction_id, amount, refund_method, refund_ref, customer_id)

                messagebox.showinfo(_t("common.success"),
                    f"Refund of £{amount:.2f} processed successfully.\nRefund Method: {refund_method}\nRefund Reference: {refund_ref}\nOrder status updated to Refunded.")
                self._load_orders()
            else:
                messagebox.showerror(_t("common.error"), _t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_view_order_details.dialogs.failed_to_process_refund', default="Failed to process refund"))
        except Exception as e:
            logger.error(f"Error processing refund: {e}")
            messagebox.showerror(_t("common.error"), f"Error processing refund: {e}")

    def show_refund_method_dialog(self, amount, order_number, customer_id):
        """Show dialog to select refund method for order refunds"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_view_order_details.windows.select_refund_method', default="Select Refund Method"))
        dialog.geometry("450x400")
        dialog.transient(self.root)
        dialog.grab_set()

        result = {'method': None}

        ttk.Label(dialog, text=f"Refund Amount: £{amount:.2f}", font=('Arial', 12, 'bold')).pack(pady=10)
        ttk.Label(dialog, text=f"Order: {order_number}").pack(pady=5)

        # Show student account balance if customer_id available
        if customer_id and customer_id != 'GUEST':
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
            if not customer_id or customer_id == 'GUEST':
                messagebox.showerror(_t("musicshop.msg_titles.error"), _t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_view_order_details.dialogs.no_customer_id_associated_with_this_order', default="No customer ID associated with this order."))
                return
            result['method'] = 'Student Account'
            dialog.destroy()

        ttk.Button(button_frame, text=_t("musicshop.btn.cash_refund"), command=select_cash, width=20).pack(pady=5)
        ttk.Button(button_frame, text=_t("musicshop.btn.card_refund"), command=select_card, width=20).pack(pady=5)

        if customer_id and customer_id != 'GUEST':
            ttk.Button(button_frame, text=_t("musicshop.btn.student_finance"), command=select_student_account, width=20).pack(pady=5)

        ttk.Button(button_frame, text=_t("musicshop.btn.cancel"), command=dialog.destroy, width=20).pack(pady=10)

        dialog.wait_window()
        return result['method']

    def add_product(self):
        """Add a new product"""
        try:
            sku = self.product_entries['sku'].get().strip()
            title = self.product_entries['title'].get().strip()
            price = self.product_entries['price'].get().strip()
            category = self.new_product_category.get()

            if not all([sku, title, price, category]):
                messagebox.showerror(_t("common.error"), _t("musicshop.errors.fill_required"))
                return

            product_id = ProductManager.add_product(
                sku=sku, title=title, category=category, price=float(price),
                artist=self.product_entries['artist'].get().strip() or None,
                label=self.product_entries['label'].get().strip() or None,
                release_year=int(self.product_entries['release_year'].get() or 0) or None,
                cost_price=float(self.product_entries['cost_price'].get() or 0),
                stock_quantity=int(self.product_entries['stock_quantity'].get() or 0),
                genre=self.new_product_genre.get() or None,
                condition=self.new_product_condition.get(),
                is_rare=self.is_rare_var.get()
            )

            if product_id:
                messagebox.showinfo(_t("common.success"), _t("musicshop.messages.product_added"))
                self._clear_product_form()
                self._load_products()
        except ValueError:
            messagebox.showerror(_t("common.error"), _t("musicshop.errors.invalid_input"))

    def update_product(self):
        """Update selected product"""
        selected = self.products_tree.selection()
        if not selected:
            return

        product_id = self.products_tree.item(selected[0])['values'][0]
        updates = {}
        if self.product_entries['price'].get():
            updates['price'] = float(self.product_entries['price'].get())
        if self.product_entries['stock_quantity'].get():
            updates['stock_quantity'] = int(self.product_entries['stock_quantity'].get())

        if ProductManager.update_product(product_id, **updates):
            messagebox.showinfo(_t("common.success"), _t("musicshop.messages.product_updated"))
            self._load_products()

    def _clear_product_form(self):
        """Clear product form"""
        for entry in self.product_entries.values():
            entry.delete(0, tk.END)
        self.new_product_category.set('')
        self.new_product_genre.set('')
        self.new_product_condition.set('new')
        self.is_rare_var.set(False)

    def record_revenue_to_finance(self, order_id: int, amount: float, payment_method: str):
        """Record music shop revenue to the central finance system"""
        try:
            order = OrderManager.get_order(order_id)
            if not order:
                return

            payment_id = record_payment_to_finance(
                student_id=order.get('customer_id', 'EXTERNAL'),
                amount=amount,
                payment_method=payment_method,
                transaction_source='MusicShop',
                transaction_ref=order.get('order_number', str(order_id)),
                notes="Music shop purchase",
                created_by=self.current_user.get('username')
            )
            if payment_id:
                logger.info(f"Revenue recorded: £{amount:.2f} for order {order.get('order_number')}")
        except Exception as e:
            logger.error(f"Failed to record revenue: {e}")

    def send_receipt_email(self, order_id: int):
        """Send receipt email to customer"""
        try:
            from education_system.systems.university.infrastructure.email.email_service import send_email

            order = OrderManager.get_order(order_id)
            if not order:
                logger.info("Receipt email skipped - order not found")
                return

            customer_email = order.get('customer_email', '')
            if not customer_email or '@' not in customer_email:
                logger.info(f"Receipt email skipped - invalid email format: {customer_email}")
                return

            subject = _t("musicshop.email.receipt_subject").format(order_num=order['order_number'])
            body = _t("musicshop.email.receipt_body").format(
                customer=order['customer_name'],
                order_num=order['order_number'],
                total=order['total_amount']
            )
            send_email(customer_email, subject, body)
            logger.info(f"Receipt email sent to {customer_email}")
        except Exception as e:
            logger.error(f"Failed to send receipt: {e}")

    def show_sales_summary(self):
        """Show sales summary"""
        summary = ReportManager.get_sales_summary()
        report = f"""
SALES SUMMARY
=============
Total Orders: {summary['total_orders']}
Total Revenue: £{summary['total_revenue']:.2f}
Average Order Value: £{summary['avg_order_value']:.2f}
Pending Orders: {summary['pending_orders']}
Completed Orders: {summary['completed_orders']}
"""
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)

    def show_inventory_report(self):
        """Show inventory report"""
        summary = ReportManager.get_inventory_summary()
        report = f"""
INVENTORY REPORT
================
Total Products: {summary['total_products']}
Total Stock Units: {summary['total_stock']}
Total Inventory Value: £{summary['total_value']:.2f}
Low Stock Items: {summary['low_stock_count']}
Rare/Collectible Items: {summary['rare_items_count']}
"""
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)

    def show_top_products(self):
        """Show top selling products"""
        products = ReportManager.get_top_selling_products(10)
        report = "TOP SELLING PRODUCTS\n" + "=" * 30 + "\n\n"
        for i, p in enumerate(products, 1):
            report += f"{i}. {p['title']} by {p.get('artist', 'Unknown')}\n"
            report += f"   Sold: {p.get('total_sold', 0)} | Revenue: £{p.get('total_revenue', 0):.2f}\n\n"
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)

    def show_top_artists(self):
        """Show top selling artists"""
        artists = ReportManager.get_top_artists(10)
        report = "TOP SELLING ARTISTS\n" + "=" * 30 + "\n\n"
        for i, a in enumerate(artists, 1):
            report += f"{i}. {a['artist']}\n"
            report += f"   Items: {a.get('items_sold', 0)} | Revenue: £{a.get('revenue', 0):.2f}\n\n"
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)

    def show_genre_analysis(self):
        """Show sales by genre"""
        genres = ReportManager.get_sales_by_genre()
        report = "SALES BY GENRE\n" + "=" * 30 + "\n\n"
        for g in genres:
            report += f"{g['genre']}: £{g.get('revenue', 0):.2f} ({g.get('items_sold', 0)} items)\n"
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)

    def generate_admin_report(self):
        """Generate admin report"""
        report = ReportManager.generate_admin_report()
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)

    def email_admin_report(self):
        """Email admin report"""
        try:
            from education_system.systems.university.infrastructure.email.email_service import send_email

            report = ReportManager.generate_admin_report()

            with get_db_connection() as conn:
                cursor = conn.execute(
                    "SELECT email FROM users WHERE role = 'admin' AND email IS NOT NULL LIMIT 1"
                )
                result = cursor.fetchone()

            if result and result[0]:
                send_email(result[0], _t("musicshop.email.admin_report_subject"), report)
                messagebox.showinfo(_t("common.success"), _t("musicshop.messages.report_emailed"))
            else:
                messagebox.showwarning(_t("common.warning"), _t("musicshop.errors.no_admin_email"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))
