"""Methods _populate_orders_tree through view_order_details."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import butcher_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class ButcherGUI:
    def _populate_orders_tree(self, orders):
        """Render a list of order dicts into the orders treeview."""
        for item in self.orders_tree.get_children():
            self.orders_tree.delete(item)
        for row in orders:
            created = row.get('created_at') or ''
            self.orders_tree.insert('', tk.END, values=(
                row.get('order_number', ''),
                row.get('customer_name', ''),
                f"£{(row.get('total_amount') or 0):.2f}",
                row.get('order_status', ''),
                row.get('payment_status', ''),
                created[:10] if created else ''
            ))

    def filter_orders_by_status(self):
        """Filter the order history by the selected status."""
        status = self.orders_status_filter.get().strip()
        if not status:
            messagebox.showwarning(_t("common.warning"), _t('gui.operations.commerce.butcher.butcher_gui_parts.butchergui_populate_orders_tree.dialogs.please_select_a_status', default="Please select a status."))
            return
        try:
            from education_system.systems.university.plugins.campus_commerce.domain.butcher.services.butcher_core import OrderManager
            orders = OrderManager.get_orders_by_status(status)
            self._populate_orders_tree(orders)
            if not orders:
                messagebox.showinfo(_t("common.info"), f"No orders with status '{status}'.")
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def lookup_customer_orders(self):
        """Look up all orders for a given customer ID."""
        customer_id = simpledialog.askstring(_t("butcher.btn.customer_orders"),
                                             _t('gui.operations.commerce.butcher.butcher_gui_parts.butchergui_populate_orders_tree.dialogs.customer_id', default="Customer ID:"), parent=self.parent)
        if not customer_id:
            return
        customer_id = customer_id.strip()
        try:
            from education_system.systems.university.plugins.campus_commerce.domain.butcher.services.butcher_core import OrderManager
            orders = OrderManager.get_customer_orders(customer_id)
            self._populate_orders_tree(orders)
            if not orders:
                messagebox.showinfo(_t("common.info"), f"No orders found for customer '{customer_id}'.")
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def load_todays_orders(self):
        """Load today's orders into the order history."""
        try:
            from education_system.systems.university.plugins.campus_commerce.domain.butcher.services.butcher_core import OrderManager
            orders = OrderManager.get_todays_orders()
            self._populate_orders_tree(orders)
            if not orders:
                messagebox.showinfo(_t("common.info"), _t('gui.operations.commerce.butcher.butcher_gui_parts.butchergui_populate_orders_tree.dialogs.no_orders_for_today', default="No orders for today."))
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def show_daily_sales(self):
        """Show a one-tap daily sales summary for today."""
        try:
            from education_system.systems.university.plugins.campus_commerce.domain.butcher.services.butcher_core import TransactionManager
            sales = TransactionManager.get_daily_sales()
            details = (
                f"Daily Sales for {sales['date']}\n"
                f"{'=' * 30}\n"
                f"Transactions: {sales['transaction_count']}\n"
                f"Total Sales:  £{sales['total_sales']:.2f}\n"
                f"Refunds:      £{sales['total_refunds']:.2f}\n"
                f"Net Sales:    £{sales['net_sales']:.2f}"
            )
            messagebox.showinfo(_t("butcher.btn.daily_sales"), details)
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def _load_inventory(self):
        """Load inventory into the treeview - Function 13"""
        for item in self.inventory_tree.get_children():
            self.inventory_tree.delete(item)

        low_stock_count = 0

        try:
            with get_db_connection() as conn:
                rows = conn.execute('''
                    SELECT * FROM products WHERE source_type = 'butcher' AND is_available = 1
                    ORDER BY category, name
                ''').fetchall()

                categories = self._get_categories()
                for row in rows:
                    cat_name = categories.get(row['category'], row['category'])
                    stock_status = 'OK'
                    if row['stock_quantity'] <= row['min_stock_level']:
                        stock_status = 'LOW'
                        low_stock_count += 1

                    self.inventory_tree.insert('', tk.END, values=(
                        row['product_id'],
                        row['name'],
                        cat_name,
                        f"{row['stock_quantity']:.1f}",
                        f"{row['min_stock_level']:.1f}",
                        row['unit_type'],
                        stock_status
                    ), tags=('low',) if stock_status == 'LOW' else ())

                self.inventory_tree.tag_configure('low', foreground='red')

                if low_stock_count > 0:
                    self.low_stock_label.config(
                        text=_t("butcher.warnings.low_stock_count").format(count=low_stock_count)
                    )
                else:
                    self.low_stock_label.config(text=_t("butcher.messages.stock_levels_ok"))

        except Exception as e:
            logger.error(f"Error loading inventory: {e}")

    def add_product(self):
        """Add a new product - Function 14"""
        name = self.product_name_var.get().strip()
        category_display = self.product_category_var.get()
        price_str = self.product_price_var.get().strip()
        unit = self.product_unit_var.get()
        stock_str = self.product_stock_var.get().strip()
        description = self.product_desc_text.get("1.0", tk.END).strip()

        if not name or not category_display or not price_str:
            messagebox.showerror(_t("common.error"), _t("butcher.errors.fill_required"))
            return

        try:
            price = float(price_str)
            stock = float(stock_str) if stock_str else 0

            # Get category key from display value
            categories = self._get_categories()
            category = next((k for k, v in categories.items() if v == category_display), 'beef')

            from education_system.systems.university.plugins.campus_commerce.domain.butcher.services.butcher_core import ProductManager
            product_id = ProductManager.add_product(
                name=name, category=category, price_per_unit=price,
                unit_type=unit, stock_quantity=stock, description=description
            )

            log_activity('create', 'butcher_product',
                        details={'product_id': product_id, 'user_id': self.current_user.get('user_id')})

            messagebox.showinfo(_t("common.success"), _t("butcher.messages.product_added").format(name=name))
            self._clear_product_form()
            self._load_products()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("butcher.errors.invalid_number"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("butcher.errors.add_failed").format(error=str(e)))

    def update_product(self):
        """Update selected product - Function 15"""
        selected = self.products_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("butcher.errors.select_product"))
            return

        item = self.products_tree.item(selected[0])
        product_id = item['values'][0]

        name = self.product_name_var.get().strip()
        category_display = self.product_category_var.get()
        price_str = self.product_price_var.get().strip()
        unit = self.product_unit_var.get()
        stock_str = self.product_stock_var.get().strip()

        if not name or not price_str:
            messagebox.showerror(_t("common.error"), _t("butcher.errors.fill_required"))
            return

        try:
            price = float(price_str)
            stock = float(stock_str) if stock_str else 0

            categories = self._get_categories()
            category = next((k for k, v in categories.items() if v == category_display), 'beef')

            from education_system.systems.university.plugins.campus_commerce.domain.butcher.services.butcher_core import ProductManager
            ProductManager.update_product(
                product_id, name=name, category=category,
                price_per_unit=price, unit_type=unit, stock_quantity=stock
            )

            log_activity('update', 'butcher_product',
                        details={'product_id': product_id, 'user_id': self.current_user.get('user_id')})

            messagebox.showinfo(_t("common.success"), _t("butcher.messages.product_updated"))
            self._load_products()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("butcher.errors.invalid_number"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("butcher.errors.update_failed").format(error=str(e)))

    def _clear_product_form(self):
        """Clear the product form - Function 16"""
        self.product_name_var.set("")
        self.product_category_var.set("")
        self.product_price_var.set("")
        self.product_unit_var.set("kg")
        self.product_stock_var.set("0")
        self.product_desc_text.delete("1.0", tk.END)

    def add_item_to_order(self):
        """Add item to current order - Function 17"""
        product_str = self.order_product_combo.get()
        qty_str = self.order_quantity.get().strip()
        special_cut = self.order_special_cut.get().strip()

        if not product_str or not qty_str:
            messagebox.showwarning(_t("common.warning"), _t("butcher.errors.select_product_qty"))
            return

        try:
            product_id = int(product_str.split(':')[0])
            quantity = float(qty_str)

            with get_db_connection() as conn:
                product = conn.execute(
                    "SELECT * FROM products WHERE source_product_id = ? AND source_type = 'butcher'",
                    (product_id,)
                ).fetchone()

                if product:
                    total = product['price_per_unit'] * quantity
                    item = {
                        'product_id': product_id,
                        'name': product['name'],
                        'quantity': quantity,
                        'unit': product['unit_type'],
                        'price': product['price_per_unit'],
                        'total': total,
                        'special_cut': special_cut
                    }
                    self.order_items.append(item)

                    self.order_items_tree.insert('', tk.END, values=(
                        product['name'],
                        f"{quantity} {product['unit_type']}",
                        f"£{product['price_per_unit']:.2f}",
                        f"£{total:.2f}"
                    ))

                    self._update_order_total()
                    self.order_quantity.set("1")
                    self.order_special_cut.set("")

        except (ValueError, IndexError):
            messagebox.showerror(_t("common.error"), _t("butcher.errors.invalid_selection", default="Invalid Selection."))

    def _update_order_total(self):
        """Update order total display - Function 18"""
        total = sum(item['total'] for item in self.order_items)
        self.order_total_var.set(f"£{total:.2f}")

    def clear_order(self):
        """Clear current order - Function 19"""
        self.order_items = []
        for item in self.order_items_tree.get_children():
            self.order_items_tree.delete(item)
        self._update_order_total()

    def submit_order(self):
        """Submit the order - Function 20"""
        if not self.order_items:
            messagebox.showwarning(_t("common.warning"), _t("butcher.errors.no_items"))
            return

        # Get current user details
        customer_name = self.current_user.get('first_name', '') + ' ' + self.current_user.get('last_name', '')
        if not customer_name.strip():
            customer_name = self.current_user.get('username', 'Customer')
        customer_email = self._get_user_email()

        # Calculate total
        total_amount = sum(item['total'] for item in self.order_items)

        # Show payment dialog
        payment_method = self._show_payment_dialog(total_amount, "Butcher Shop Order")
        if not payment_method:
            return  # User cancelled

        # Handle student account payment
        if payment_method == 'Student Account':
            if not self._deduct_from_student_account(total_amount):
                return  # Payment failed

        try:
            from education_system.systems.university.plugins.campus_commerce.domain.butcher.services.butcher_core import OrderManager

            customer_id = self.current_user.get('user_id', 'guest')
            order_id, order_number = OrderManager.create_order(
                customer_id=customer_id,
                customer_name=customer_name,
                customer_email=customer_email,
                processed_by=self.current_user.get('username')
            )

            for item in self.order_items:
                OrderManager.add_order_item(
                    order_id=order_id,
                    product_id=item['product_id'],
                    quantity=item['quantity'],
                    special_cut=item.get('special_cut')
                )

            # Mark order as paid and completed
            OrderManager.update_payment_status(order_id, 'paid', payment_method.lower().replace(' ', '_'))
            OrderManager.update_order_status(order_id, 'collected', self.current_user.get('user_id'))

            # Add to finance revenue
            self._add_to_revenue(total_amount, f"Butcher Order {order_number}", order_number)

            log_activity('create', 'butcher_order',
                        details={'order_id': order_id, 'order_number': order_number,
                                'amount': total_amount, 'payment_method': payment_method})

            messagebox.showinfo(_t("common.success"),
                              _t("butcher.messages.order_created").format(order_number=order_number))

            # Send receipt email
            if customer_email:
                items_list = "\n".join([f"  - {item['name']}: {item['quantity']} {item['unit']} @ £{item['price']:.2f} = £{item['total']:.2f}"
                                       for item in self.order_items])

                # Render email from template
                subject, body = render_template('commerce/butcher/order_receipt', {
                    'customer_name': customer_name,
                    'order_number': order_number,
                    'order_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'items_list': items_list,
                    'subtotal': f"£{total_amount:.2f}",
                    'tax': '£0.00',
                    'total_amount': f"£{total_amount:.2f}",
                    'payment_method': payment_method
                })

                # Fallback if template not found
                if not subject or not body:
                    subject = f"Butcher Shop Receipt - Order {order_number}"
                    body = f"Dear {customer_name},\n\nThank you for your order.\nTotal: £{total_amount:.2f}"

                if _send_butcher_email(customer_email, subject, body):
                    messagebox.showinfo(_t("butcher.window_title"), f"Receipt sent to {customer_email}")

            self.clear_order()
            self._load_orders()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("butcher.errors.order_failed").format(error=str(e)))

    def view_order_details(self):
        """View selected order details - Function 21"""
        selected = self.orders_tree.selection()
        if not selected:
            messagebox.showwarning(_t("butcher.msg_titles.warning"), _t('gui.operations.commerce.butcher.butcher_gui_parts.butchergui_populate_orders_tree.dialogs.please_select_an_order_first', default="Please select an order first"))
            return

        try:
            item = self.orders_tree.item(selected[0])
            order_number = item['values'][0]

            from education_system.systems.university.plugins.campus_commerce.domain.butcher.services.butcher_core import OrderManager
            order = OrderManager.get_order_by_number(order_number)

            if order:
                details = f"""Order Number: {order['order_number']}
Customer: {order['customer_name']}
Email: {order.get('customer_email', 'N/A')}
Status: {order['order_status']}
Payment Status: {order['payment_status']}
Date: {order['created_at']}

Items:
"""
                for itm in order.get('items', []):
                    unit_price = itm.get('unit_price', 0) or 0
                    subtotal = itm.get('subtotal', 0) or 0
                    details += f"  - {itm['item_name']}: {itm['quantity']} {itm['unit_type']} @ £{unit_price:.2f} = £{subtotal:.2f}\n"
                    if itm.get('special_cut'):
                        details += f"    ({itm['special_cut']})\n"

                total_amount = order.get('total_amount', 0) or 0
                details += f"\nTotal: £{total_amount:.2f}"

                messagebox.showinfo(_t("butcher.msg_titles.order_details"), details)
            else:
                messagebox.showerror(_t("butcher.msg_titles.error"), f"Order {order_number} not found in database")

        except Exception as e:
            messagebox.showerror(_t("butcher.msg_titles.error"), f"Failed to load order details: {str(e)}")
