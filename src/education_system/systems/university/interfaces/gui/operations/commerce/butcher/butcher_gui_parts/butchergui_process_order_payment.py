"""Methods process_order_payment through email_admin_report."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import butcher_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class ButcherGUI:
    def process_order_payment(self):
        """Process payment for selected order - Function 22"""
        selected = self.orders_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("butcher.errors.select_order"))
            return

        item = self.orders_tree.item(selected[0])
        order_number = item['values'][0]
        payment_status = item['values'][4]

        if payment_status == 'paid':
            messagebox.showinfo(_t("common.info"), _t("butcher.messages.already_paid"))
            return

        from education_system.systems.university.domain.operations.commerce.butcher.services.butcher_core import OrderManager, TransactionManager
        order = OrderManager.get_order_by_number(order_number)

        if not order:
            return

        amount = order['total_amount']

        # Show payment method selection dialog
        payment_method = self._show_payment_dialog(amount, f"Order {order_number}")
        if not payment_method:
            return  # User cancelled

        # Handle student account payment
        if payment_method == 'Student Account':
            if not self._deduct_from_student_account(amount):
                return  # Payment failed

        try:
            transaction_id = TransactionManager.process_payment(
                order_id=order['order_id'],
                amount=amount,
                payment_method=payment_method.lower().replace(' ', '_'),
                customer_id=order['customer_id'],
                processed_by=self.current_user.get('username')
            )

            # Add to finance revenue
            self._add_to_revenue(amount, f"Butcher Order {order_number}", order_number)

            # Send receipt email
            customer_email = order.get('customer_email') or self._get_user_email()
            if customer_email:
                self._send_payment_receipt(order, transaction_id, payment_method, customer_email)

            log_activity('payment', 'butcher_order',
                        details={'order_id': order['order_id'], 'amount': amount,
                                'payment_method': payment_method, 'user_id': self.current_user.get('user_id')})

            messagebox.showinfo(_t("common.success"), _t("butcher.messages.payment_processed"))
            self._load_orders()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("butcher.errors.payment_failed").format(error=str(e)))

    def _send_payment_receipt(self, order: dict, transaction_id: int, payment_method: str, email: str):
        """Send payment receipt email."""
        items_list = ""
        for item in order.get('items', []):
            items_list += f"  - {item['item_name']}: {item['quantity']} {item['unit_type']} = £{item['subtotal']:.2f}\n"

        subject = f"Butcher Shop Payment Receipt - Order {order['order_number']}"
        body = f"""Dear {order['customer_name']},

Thank you for your payment at the University Butcher Shop.

PAYMENT RECEIPT
===============
Order Number: {order['order_number']}
Transaction ID: {transaction_id}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}

Items:
{items_list}
Total: £{order['total_amount']:.2f}
Payment Method: {payment_method}
Status: Paid

Your order is being prepared. We will notify you when it's ready for collection.

University Butcher Shop"""

        if _send_butcher_email(email, subject, body):
            messagebox.showinfo(_t("butcher.window_title"), f"Receipt sent to {email}")

    def send_receipt_email(self, order: dict, transaction_id: int):
        """Send receipt email to customer - Function 23"""
        try:
            from education_system.systems.university.infrastructure.email.email_service import send_email

            subject = _t("butcher.email.receipt_subject").format(order_number=order['order_number'])

            items_list = ""
            for item in order.get('items', []):
                items_list += f"  - {item['item_name']}: {item['quantity']} {item['unit_type']} = £{item['subtotal']:.2f}\n"

            body = _t("butcher.email.receipt_body").format(
                customer_name=order['customer_name'],
                order_number=order['order_number'],
                items=items_list,
                total=f"£{order['total_amount']:.2f}",
                date=datetime.now().strftime('%Y-%m-%d %H:%M')
            )

            send_email(
                recipient_email=order['customer_email'],
                subject=subject,
                body=body
            )

            from education_system.systems.university.domain.operations.commerce.butcher.services.butcher_core import TransactionManager
            TransactionManager.mark_receipt_sent(transaction_id)

            logger.info(f"Receipt sent to {order['customer_email']}")

        except Exception as e:
            logger.error(f"Failed to send receipt: {e}")

    def mark_order_ready(self):
        """Mark order as ready for collection - Function 24"""
        selected = self.orders_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("butcher.errors.select_order"))
            return

        item = self.orders_tree.item(selected[0])
        order_number = item['values'][0]

        try:
            from education_system.systems.university.domain.operations.commerce.butcher.services.butcher_core import OrderManager
            order = OrderManager.get_order_by_number(order_number)

            if order:
                OrderManager.update_order_status(order['order_id'], 'ready',
                                                self.current_user.get('user_id'))
                messagebox.showinfo(_t("common.success"), _t("butcher.messages.order_ready"))
                self._load_orders()

        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def mark_order_collected(self):
        """Mark order as collected - Function 25"""
        selected = self.orders_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("butcher.errors.select_order"))
            return

        item = self.orders_tree.item(selected[0])
        order_number = item['values'][0]

        try:
            from education_system.systems.university.domain.operations.commerce.butcher.services.butcher_core import OrderManager
            order = OrderManager.get_order_by_number(order_number)

            if order:
                OrderManager.update_order_status(order['order_id'], 'collected',
                                                self.current_user.get('user_id'))
                messagebox.showinfo(_t("common.success"), _t("butcher.messages.order_collected"))
                self._load_orders()

        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def show_change_status_dialog(self):
        """Show dialog for admin to change order status."""
        selected = self.orders_tree.selection()
        if not selected:
            messagebox.showwarning(_t("butcher.msg_titles.warning"), _t('gui.operations.commerce.butcher.butcher_gui_parts.butchergui_process_order_payment.dialogs.please_select_an_order_first', default="Please select an order first"))
            return

        try:
            item = self.orders_tree.item(selected[0])
            order_number = item['values'][0]
            current_status = item['values'][3]
            current_payment = item['values'][4]
        except (IndexError, KeyError) as e:
            messagebox.showerror(_t("butcher.msg_titles.error"), f"Failed to get order details: {e}")
            return

        # Create dialog
        dialog = tk.Toplevel(self.parent)
        dialog.title(_t("butcher.btn.change_order_status"))
        dialog.geometry("400x350")
        dialog.transient(self.parent)
        dialog.grab_set()

        # Center dialog
        dialog.update_idletasks()
        x = self.parent.winfo_x() + (self.parent.winfo_width() - 400) // 2
        y = self.parent.winfo_y() + (self.parent.winfo_height() - 350) // 2
        dialog.geometry(f"+{x}+{y}")

        # Header
        ttk.Label(dialog, text=f"Order: {order_number}",
                 font=('Helvetica', 14, 'bold')).pack(pady=15)

        # Current status display
        info_frame = ttk.LabelFrame(dialog, text=_t("butcher.labels.current_status"), padding="10")
        info_frame.pack(fill=tk.X, padx=20, pady=5)

        ttk.Label(info_frame, text=f"Order Status: {current_status}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Payment Status: {current_payment}").pack(anchor=tk.W)

        # New status selection
        status_frame = ttk.LabelFrame(dialog, text=_t("butcher.btn.change_order_status"), padding="10")
        status_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(status_frame, text=_t("butcher.labels.new_status")).pack(anchor=tk.W)
        status_var = tk.StringVar(value=current_status)
        status_options = ['pending', 'processing', 'ready', 'collected', 'cancelled']
        for status in status_options:
            ttk.Radiobutton(status_frame, text=status.capitalize(),
                           variable=status_var, value=status).pack(anchor=tk.W, pady=2)

        # Payment status selection
        payment_frame = ttk.LabelFrame(dialog, text=_t("butcher.btn.change_payment_status"), padding="10")
        payment_frame.pack(fill=tk.X, padx=20, pady=5)

        ttk.Label(payment_frame, text=_t("butcher.labels.payment_status")).pack(anchor=tk.W)
        payment_var = tk.StringVar(value=current_payment)
        payment_options = ['pending', 'paid', 'refunded']
        for payment in payment_options:
            ttk.Radiobutton(payment_frame, text=payment.capitalize(),
                           variable=payment_var, value=payment).pack(anchor=tk.W, pady=2)

        def apply_changes():
            new_status = status_var.get()
            new_payment = payment_var.get()

            try:
                from education_system.systems.university.domain.operations.commerce.butcher.services.butcher_core import OrderManager
                order = OrderManager.get_order_by_number(order_number)

                if order:
                    # Update order status
                    if new_status != current_status:
                        OrderManager.update_order_status(order['order_id'], new_status,
                                                        self.current_user.get('user_id'))

                    # Update payment status
                    if new_payment != current_payment:
                        OrderManager.update_payment_status(order['order_id'], new_payment)

                    log_activity('update', 'butcher_order_status',
                                details={'order_number': order_number, 'old_status': current_status,
                                        'new_status': new_status, 'old_payment': current_payment,
                                        'new_payment': new_payment, 'admin': self.current_user.get('username')})

                    messagebox.showinfo(_t("common.success"), f"Order {order_number} updated successfully")
                    dialog.destroy()
                    self._load_orders()

            except Exception as e:
                messagebox.showerror(_t("common.error"), str(e))

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=15)

        ttk.Button(btn_frame, text=_t("butcher.btn.apply_changes"), command=apply_changes).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t("butcher.btn.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def adjust_stock(self):
        """Adjust stock levels - Additional Function"""
        product_str = self.inv_product_combo.get()
        adjustment_str = self.inv_adjustment_var.get().strip()
        reason = self.inv_reason_var.get().strip()

        if not product_str or not adjustment_str:
            messagebox.showwarning(_t("common.warning"), _t("butcher.errors.fill_required"))
            return

        try:
            product_id = int(product_str.split(':')[0])
            adjustment = float(adjustment_str)

            from education_system.systems.university.domain.operations.commerce.butcher.services.butcher_core import ProductManager
            ProductManager.update_stock(product_id, adjustment, reason or 'Manual adjustment',
                                       self.current_user.get('user_id'))

            log_activity('update', 'butcher_inventory',
                        details={'product_id': product_id, 'adjustment': adjustment,
                                'user_id': self.current_user.get('user_id')})

            messagebox.showinfo(_t("common.success"), _t("butcher.messages.stock_adjusted"))
            self.inv_adjustment_var.set("")
            self.inv_reason_var.set("")
            self._load_inventory()
            self._load_products()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("butcher.errors.invalid_number"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def generate_admin_report(self):
        """Generate admin report - Additional Function"""
        try:
            from education_system.systems.university.domain.operations.commerce.butcher.services.butcher_core import ReportManager
            report = ReportManager.generate_admin_report()

            self.report_text.delete("1.0", tk.END)
            self.report_text.insert("1.0", report)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("butcher.errors.report_failed").format(error=str(e)))

    def email_admin_report(self):
        """Email admin report - Additional Function"""
        report_content = self.report_text.get("1.0", tk.END).strip()

        if not report_content:
            self.generate_admin_report()
            report_content = self.report_text.get("1.0", tk.END).strip()

        if not EMAIL_AVAILABLE:
            messagebox.showwarning(_t("common.warning"), _t('gui.operations.commerce.butcher.butcher_gui_parts.butchergui_process_order_payment.dialogs.email_service_not_available', default="Email service not available"))
            return

        # Auto-detect admin emails
        admin_emails = self._get_admin_emails()

        if not admin_emails:
            messagebox.showwarning(_t("common.warning"), _t("butcher.errors.no_admin_email"))
            return

        # Send report to all admins
        subject = f"Butcher Shop Admin Report - {datetime.now().strftime('%Y-%m-%d')}"
        success_count = 0
        for email in admin_emails:
            if _send_butcher_email(email, subject, report_content):
                success_count += 1

        if success_count > 0:
            log_activity('email', 'butcher_report',
                        details={'user_id': self.current_user.get('user_id'), 'recipients': admin_emails})
            messagebox.showinfo(_t("common.success"),
                              f"Report sent to {success_count} admin(s): {', '.join(admin_emails)}")
        else:
            messagebox.showerror(_t("common.error"), _t("butcher.errors.email_failed").format(error="All sends failed"))
