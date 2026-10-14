"""Methods create_orders_tab through export_refunds_csv."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import butcher_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class ButcherGUI:
    def create_orders_tab(self):
        """Create the orders management tab - Function 7"""
        orders_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(orders_frame, text=_t("butcher.tabs.orders"))

        # Top - New order section
        new_order_frame = ttk.LabelFrame(orders_frame, text=_t("butcher.labels.new_order"), padding="10")
        new_order_frame.pack(fill=tk.X, pady=(0, 10))

        # Current user info display
        cust_frame = ttk.Frame(new_order_frame)
        cust_frame.pack(fill=tk.X, pady=5)

        # Get current user details
        user_name = self.current_user.get('first_name', '') + ' ' + self.current_user.get('last_name', '')
        if not user_name.strip():
            user_name = self.current_user.get('username', 'Unknown')
        user_email = self._get_user_email()

        ttk.Label(cust_frame, text=_t("butcher.labels.ordering_as"), font=('Helvetica', 10, 'bold')).pack(side=tk.LEFT)
        ttk.Label(cust_frame, text=f"{user_name} ({user_email})" if user_email else user_name).pack(side=tk.LEFT, padx=10)

        # Product selection
        prod_frame = ttk.Frame(new_order_frame)
        prod_frame.pack(fill=tk.X, pady=5)

        ttk.Label(prod_frame, text=_t("butcher.labels.product") + ":").pack(side=tk.LEFT)
        self.order_product_combo = ttk.Combobox(prod_frame, state="readonly", width=25)
        self.order_product_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(prod_frame, text=_t("butcher.labels.quantity") + ":").pack(side=tk.LEFT)
        self.order_quantity = tk.StringVar(value="1")
        ttk.Entry(prod_frame, textvariable=self.order_quantity, width=10).pack(side=tk.LEFT, padx=5)

        ttk.Label(prod_frame, text=_t("butcher.labels.special_cut") + ":").pack(side=tk.LEFT)
        self.order_special_cut = tk.StringVar()
        ttk.Entry(prod_frame, textvariable=self.order_special_cut, width=20).pack(side=tk.LEFT, padx=5)

        ttk.Button(prod_frame, text=_t("butcher.btn.add_to_order"),
                  command=self.add_item_to_order).pack(side=tk.LEFT, padx=10)

        # Order items list
        self.order_items = []
        self.order_items_tree = ttk.Treeview(new_order_frame, columns=('product', 'qty', 'price', 'total'),
                                             show='headings', height=5)
        self.order_items_tree.heading('product', text=_t("butcher.labels.product"))
        self.order_items_tree.heading('qty', text=_t("butcher.labels.quantity"))
        self.order_items_tree.heading('price', text=_t("butcher.labels.price"))
        self.order_items_tree.heading('total', text=_t("butcher.labels.total"))

        self.order_items_tree.column('product', width=200)
        self.order_items_tree.column('qty', width=80)
        self.order_items_tree.column('price', width=100)
        self.order_items_tree.column('total', width=100)
        self.order_items_tree.pack(fill=tk.X, pady=5)

        # Order total and submit
        total_frame = ttk.Frame(new_order_frame)
        total_frame.pack(fill=tk.X, pady=5)

        self.order_total_var = tk.StringVar(value="£0.00")
        ttk.Label(total_frame, text=_t("butcher.labels.order_total") + ":",
                 font=('Helvetica', 12, 'bold')).pack(side=tk.LEFT)
        ttk.Label(total_frame, textvariable=self.order_total_var,
                 font=('Helvetica', 12, 'bold')).pack(side=tk.LEFT, padx=10)

        ttk.Button(total_frame, text=_t("butcher.btn.submit_order"),
                  command=self.submit_order).pack(side=tk.RIGHT, padx=5)
        ttk.Button(total_frame, text=_t("butcher.btn.clear_order"),
                  command=self.clear_order).pack(side=tk.RIGHT, padx=5)

        # Bottom - Order history
        history_frame = ttk.LabelFrame(orders_frame, text=_t("butcher.labels.order_history"), padding="5")
        history_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('order_no', 'customer', 'total', 'status', 'payment', 'date')
        self.orders_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=10)

        self.orders_tree.heading('order_no', text=_t("butcher.labels.order_number"))
        self.orders_tree.heading('customer', text=_t("butcher.labels.customer"))
        self.orders_tree.heading('total', text=_t("butcher.labels.total"))
        self.orders_tree.heading('status', text=_t("butcher.labels.status"))
        self.orders_tree.heading('payment', text=_t("butcher.labels.payment_status"))
        self.orders_tree.heading('date', text=_t("butcher.labels.date"))

        scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=self.orders_tree.yview)
        self.orders_tree.configure(yscrollcommand=scrollbar.set)

        self.orders_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Double-click to view order details
        self.orders_tree.bind('<Double-1>', lambda e: self.view_order_details())

        # Order action buttons
        action_frame = ttk.Frame(orders_frame)
        action_frame.pack(fill=tk.X, pady=5)

        ttk.Button(action_frame, text=_t("butcher.btn.view_order"),
                  command=self.view_order_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t("butcher.btn.process_payment"),
                  command=self.process_order_payment).pack(side=tk.LEFT, padx=5)

        # Admin-only: Change Status button
        if self.current_user.get('role') == 'admin':
            ttk.Button(action_frame, text=_t("butcher.btn.change_status"),
                      command=self.show_change_status_dialog).pack(side=tk.LEFT, padx=5)

        # Lookups / filters row
        lookup_frame = ttk.Frame(orders_frame)
        lookup_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(lookup_frame, text=_t("butcher.labels.status") + ":").pack(side=tk.LEFT)
        from education_system.systems.university.plugins.campus_commerce.domain.butcher.services.butcher_core import ORDER_STATUSES
        self.orders_status_filter = ttk.Combobox(lookup_frame, state="readonly", width=15,
                                                 values=list(ORDER_STATUSES))
        self.orders_status_filter.pack(side=tk.LEFT, padx=5)
        ttk.Button(lookup_frame, text=_t("butcher.btn.filter_by_status"),
                  command=self.filter_orders_by_status).pack(side=tk.LEFT, padx=5)
        ttk.Button(lookup_frame, text=_t("butcher.btn.customer_orders"),
                  command=self.lookup_customer_orders).pack(side=tk.LEFT, padx=5)
        ttk.Button(lookup_frame, text=_t("butcher.btn.todays_orders"),
                  command=self.load_todays_orders).pack(side=tk.LEFT, padx=5)
        ttk.Button(lookup_frame, text=_t("butcher.btn.show_all_orders"),
                  command=self._load_orders).pack(side=tk.LEFT, padx=5)
        ttk.Button(lookup_frame, text=_t("butcher.btn.daily_sales"),
                  command=self.show_daily_sales).pack(side=tk.RIGHT, padx=5)

    def create_inventory_tab(self):
        """Create the inventory management tab - Function 8"""
        inventory_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(inventory_frame, text=_t("butcher.tabs.inventory"))

        # Stock adjustment section
        adjust_frame = ttk.LabelFrame(inventory_frame, text=_t("butcher.labels.stock_adjustment"), padding="10")
        adjust_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(adjust_frame, text=_t("butcher.labels.product") + ":").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.inv_product_combo = ttk.Combobox(adjust_frame, state="readonly", width=30)
        self.inv_product_combo.grid(row=0, column=1, pady=2, padx=5)

        ttk.Label(adjust_frame, text=_t("butcher.labels.adjustment") + ":").grid(row=0, column=2, sticky=tk.W, pady=2)
        self.inv_adjustment_var = tk.StringVar()
        ttk.Entry(adjust_frame, textvariable=self.inv_adjustment_var, width=10).grid(row=0, column=3, pady=2, padx=5)

        ttk.Label(adjust_frame, text=_t("butcher.labels.reason") + ":").grid(row=0, column=4, sticky=tk.W, pady=2)
        self.inv_reason_var = tk.StringVar()
        ttk.Entry(adjust_frame, textvariable=self.inv_reason_var, width=20).grid(row=0, column=5, pady=2, padx=5)

        ttk.Button(adjust_frame, text=_t("butcher.btn.adjust_stock"),
                  command=self.adjust_stock).grid(row=0, column=6, padx=10)

        # Current stock levels
        stock_frame = ttk.LabelFrame(inventory_frame, text=_t("butcher.labels.current_stock"), padding="5")
        stock_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ('id', 'name', 'category', 'stock', 'min_level', 'unit', 'status')
        self.inventory_tree = ttk.Treeview(stock_frame, columns=columns, show='headings', height=15)

        self.inventory_tree.heading('id', text=_t('butcher.columns.id'))
        self.inventory_tree.heading('name', text=_t("butcher.labels.product_name"))
        self.inventory_tree.heading('category', text=_t("butcher.labels.category"))
        self.inventory_tree.heading('stock', text=_t("butcher.labels.stock"))
        self.inventory_tree.heading('min_level', text=_t("butcher.labels.min_level"))
        self.inventory_tree.heading('unit', text=_t("butcher.labels.unit"))
        self.inventory_tree.heading('status', text=_t("butcher.labels.status"))

        scrollbar = ttk.Scrollbar(stock_frame, orient=tk.VERTICAL, command=self.inventory_tree.yview)
        self.inventory_tree.configure(yscrollcommand=scrollbar.set)

        self.inventory_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Low stock alerts
        alert_frame = ttk.LabelFrame(inventory_frame, text=_t("butcher.labels.low_stock_alerts"), padding="5")
        alert_frame.pack(fill=tk.X)

        self.low_stock_label = ttk.Label(alert_frame, text="", foreground="red")
        self.low_stock_label.pack(anchor=tk.W)

    def create_refunds_tab(self):
        """Create payment refunds management tab - Accessible to all staff and admin users"""
        refunds_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(refunds_frame, text=_t("butcher.tabs.refunds"))

        # Header
        header_frame = ttk.Frame(refunds_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        header_left = ttk.Frame(header_frame)
        header_left.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(header_left, text=_t("butcher.labels.refunds_title"),
                 font=('Arial', 12, 'bold')).pack(anchor=tk.W)

        # Show admin badge if user is admin
        if self.current_user.get('role') == 'admin':
            ttk.Label(header_left, text=_t("butcher.labels.admin_access"),
                     font=('Arial', 9, 'bold'), foreground='blue').pack(anchor=tk.W, pady=(2, 0))

        # Search frame
        search_frame = ttk.LabelFrame(refunds_frame, text=_t("butcher.labels.search_orders"), padding="10")
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text=_t("butcher.labels.search_by")).grid(row=0, column=0, sticky=tk.W, padx=5)
        self.refund_search_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.refund_search_var, width=40).grid(row=0, column=1, padx=5)

        # Transactions list frame
        list_frame = ttk.LabelFrame(refunds_frame, text=_t("butcher.labels.all_orders_title"), padding="5")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ('order_id', 'date', 'customer_name', 'customer_id', 'order_number', 'amount', 'method', 'status')
        self.refunds_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        self.refunds_tree.heading('order_id', text=_t('butcher.columns.order_id'))
        self.refunds_tree.heading('date', text=_t('butcher.columns.date_time'))
        self.refunds_tree.heading('customer_name', text=_t('butcher.columns.customer_name'))
        self.refunds_tree.heading('customer_id', text=_t('butcher.columns.customer_id'))
        self.refunds_tree.heading('order_number', text=_t('butcher.columns.order_number'))
        self.refunds_tree.heading('amount', text=_t('butcher.columns.amount_gbp'))
        self.refunds_tree.heading('method', text=_t('butcher.columns.payment_method'))
        self.refunds_tree.heading('status', text=_t('butcher.columns.status'))

        self.refunds_tree.column('order_id', width=70)
        self.refunds_tree.column('date', width=140)
        self.refunds_tree.column('customer_name', width=150)
        self.refunds_tree.column('customer_id', width=100)
        self.refunds_tree.column('order_number', width=140)
        self.refunds_tree.column('amount', width=90)
        self.refunds_tree.column('method', width=110)
        self.refunds_tree.column('status', width=90)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.refunds_tree.yview)
        self.refunds_tree.configure(yscrollcommand=scrollbar.set)
        self.refunds_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Button frame
        button_frame = ttk.Frame(refunds_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text=_t("butcher.btn.search"), command=self.refresh_refunds_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("butcher.btn.show_all"),
                  command=lambda: [self.refund_search_var.set(''), self.refresh_refunds_list()]).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("butcher.btn.process_refund"), command=self.process_butcher_refund).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("butcher.btn.view_details"), command=self.view_refund_transaction_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("butcher.btn.export_csv"), command=self.export_refunds_csv).pack(side=tk.LEFT, padx=5)

        # Initial load
        self.refresh_refunds_list()

    def refresh_refunds_list(self):
        """Refresh the refunds list from database with customer information.

        Queries orders table for all paid orders that can be refunded.
        """
        for item in self.refunds_tree.get_children():
            self.refunds_tree.delete(item)

        try:
            with get_connection() as conn:
                search_term = self.refund_search_var.get().strip()

                if search_term:
                    cursor = conn.execute('''
                        SELECT
                            bo.order_id,
                            bo.created_at,
                            bo.customer_name,
                            bo.customer_id,
                            bo.order_number,
                            bo.total_amount,
                            bo.payment_method,
                            bo.payment_status
                        FROM orders bo
                        WHERE bo.source_type = 'butcher' AND bo.payment_status != 'pending'
                          AND (CAST(bo.order_id AS TEXT) LIKE ?
                           OR bo.customer_id LIKE ?
                           OR bo.customer_name LIKE ?
                           OR bo.order_number LIKE ?)
                        ORDER BY bo.created_at DESC
                    ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%',
                          f'%{search_term}%'))
                else:
                    cursor = conn.execute('''
                        SELECT
                            bo.order_id,
                            bo.created_at,
                            bo.customer_name,
                            bo.customer_id,
                            bo.order_number,
                            bo.total_amount,
                            bo.payment_method,
                            bo.payment_status
                        FROM orders bo
                        WHERE bo.source_type = 'butcher' AND bo.payment_status != 'pending'
                        ORDER BY bo.created_at DESC
                        LIMIT 200
                    ''')

                for row in cursor.fetchall():
                    values = list(row)
                    # Ensure all 8 columns
                    while len(values) < 8:
                        values.append('N/A')
                    # Format amount (at index 5)
                    if values[5] and values[5] != 'N/A':
                        try:
                            values[5] = f"{float(values[5]):.2f}"
                        except (ValueError, TypeError):
                            pass
                    self.refunds_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_t("butcher.msg_titles.error"), f"Failed to load transactions: {e}")

    def view_refund_transaction_details(self):
        """View detailed order/transaction information."""
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("butcher.msg_titles.no_selection"), _t('gui.operations.commerce.butcher.butcher_gui_parts.butchergui_create_orders_tab.dialogs.please_select_an_order_to_view_details', default="Please select an order to view details"))
            return

        try:
            values = self.refunds_tree.item(selection[0])['values']
            if len(values) < 8:
                messagebox.showerror(_t("butcher.msg_titles.data_error"), _t('gui.operations.commerce.butcher.butcher_gui_parts.butchergui_create_orders_tab.dialogs.order_record_is_incomplete', default="Order record is incomplete"))
                return

            order_id = values[0]

            # Get full order details including items
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM orders WHERE order_id = ? AND source_type = 'butcher'
                ''', (order_id,))
                order = cursor.fetchone()

                # Get order items
                items_cursor = conn.execute('''
                    SELECT * FROM order_items
                    WHERE order_id = ? AND source_type = 'butcher'
                ''', (order_id,))
                items = items_cursor.fetchall()

            items_text = ""
            if items:
                items_text=_t("butcher.labels.order_items")
                for item in items:
                    items_text += f"\n  - {item['item_name']}: {item['quantity']} {item['unit_type']} @ GBP {item['unit_price']:.2f} = GBP {item['subtotal']:.2f}"
                    if item.get('special_cut'):
                        items_text += f"\n    Special cut: {item['special_cut']}"

            details = f"""ORDER DETAILS
==================
Order ID: {values[0]}
Order Number: {values[4]}
Date/Time: {values[1]}
Customer Name: {values[2]}
Customer ID: {values[3]}
Amount: GBP {values[5]}
Payment Method: {values[6]}
Payment Status: {values[7]}
{items_text}
"""
            messagebox.showinfo(_t("butcher.msg_titles.order_details"), details)
        except Exception as e:
            messagebox.showerror(_t("butcher.msg_titles.error"), f"Error viewing order details: {e}")

    def export_refunds_csv(self):
        """Export orders/transactions to CSV file."""
        try:
            import csv
            from tkinter import filedialog

            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"orders_{datetime.now().strftime('%Y%m%d')}.csv"
            )

            if filepath:
                with open(filepath, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Order ID', 'Date/Time', 'Customer Name', 'Customer ID',
                                   'Order Number', 'Amount', 'Payment Method', 'Payment Status'])

                    for item in self.refunds_tree.get_children():
                        values = self.refunds_tree.item(item)['values']
                        writer.writerow(values)

                messagebox.showinfo(_t("butcher.msg_titles.export_successful"), f"Orders exported to:\n{filepath}")
        except Exception as e:
            messagebox.showerror(_t("butcher.msg_titles.export_error"), f"Failed to export orders: {e}")
