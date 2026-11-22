"""Methods create_inventory_tab through complete_purchase."""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import musicshop_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class MusicShopGUI:
    def create_inventory_tab(self):
        """Create the inventory management tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("musicshop.tabs.inventory"))

        # Left - Product form
        left_frame = ttk.LabelFrame(tab, text=_t("musicshop.labels.manage_products"), padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        fields = [
            ("sku", _t("musicshop.labels.sku")),
            ("title", _t("musicshop.labels.title")),
            ("artist", _t("musicshop.labels.artist")),
            ("label", _t("musicshop.labels.label")),
            ("release_year", _t("musicshop.labels.release_year")),
            ("price", _t("musicshop.labels.price")),
            ("cost_price", _t("musicshop.labels.cost_price")),
            ("stock_quantity", _t("musicshop.labels.stock"))
        ]

        self.product_entries = {}
        for i, (field, label) in enumerate(fields):
            ttk.Label(left_frame, text=label + ":").grid(row=i, column=0, sticky=tk.W, pady=2)
            entry = ttk.Entry(left_frame, width=25)
            entry.grid(row=i, column=1, pady=2, padx=5)
            self.product_entries[field] = entry

        row = len(fields)
        ttk.Label(left_frame, text=_t("musicshop.labels.category") + ":").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.new_product_category = ttk.Combobox(left_frame, values=MUSIC_CATEGORIES, width=22)
        self.new_product_category.grid(row=row, column=1, pady=2, padx=5)

        ttk.Label(left_frame, text=_t("musicshop.labels.genre") + ":").grid(row=row+1, column=0, sticky=tk.W, pady=2)
        self.new_product_genre = ttk.Combobox(left_frame, values=GENRES, width=22)
        self.new_product_genre.grid(row=row+1, column=1, pady=2, padx=5)

        ttk.Label(left_frame, text=_t("musicshop.labels.condition") + ":").grid(row=row+2, column=0, sticky=tk.W, pady=2)
        self.new_product_condition = ttk.Combobox(left_frame, values=CONDITION_TYPES, width=22)
        self.new_product_condition.set('new')
        self.new_product_condition.grid(row=row+2, column=1, pady=2, padx=5)

        self.is_rare_var = tk.BooleanVar()
        ttk.Checkbutton(left_frame, text=_t("musicshop.labels.rare_collectible"),
                        variable=self.is_rare_var).grid(row=row+3, column=0, columnspan=2, sticky=tk.W, pady=5)

        btn_frame = ttk.Frame(left_frame)
        btn_frame.grid(row=row+4, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text=_t("musicshop.btn.add_product"), command=self.add_product).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("musicshop.btn.update_product"), command=self.update_product).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.clear"), command=self._clear_product_form).pack(side=tk.LEFT, padx=5)

        # Right - Low stock & rare items
        right_frame = ttk.Frame(tab)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Low stock
        low_stock_frame = ttk.LabelFrame(right_frame, text=_t("musicshop.labels.low_stock_alerts"), padding="5")
        low_stock_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        self.low_stock_tree = ttk.Treeview(low_stock_frame, columns=('id', 'title', 'stock'), show='headings', height=6)
        self.low_stock_tree.heading('id', text=_t('musicshop.columns.id'))
        self.low_stock_tree.heading('title', text=_t("musicshop.labels.title"))
        self.low_stock_tree.heading('stock', text=_t("musicshop.labels.stock"))
        self.low_stock_tree.column('id', width=40)
        self.low_stock_tree.column('title', width=180)
        self.low_stock_tree.column('stock', width=50)
        self.low_stock_tree.pack(fill=tk.BOTH, expand=True)

        # Rare items
        rare_frame = ttk.LabelFrame(right_frame, text=_t("musicshop.labels.rare_items"), padding="5")
        rare_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        self.rare_tree = ttk.Treeview(rare_frame, columns=('id', 'title', 'artist', 'price'), show='headings', height=6)
        self.rare_tree.heading('id', text=_t('musicshop.columns.id'))
        self.rare_tree.heading('title', text=_t("musicshop.labels.title"))
        self.rare_tree.heading('artist', text=_t("musicshop.labels.artist"))
        self.rare_tree.heading('price', text=_t("musicshop.labels.price"))
        self.rare_tree.column('id', width=40)
        self.rare_tree.column('title', width=150)
        self.rare_tree.column('artist', width=100)
        self.rare_tree.column('price', width=70)
        self.rare_tree.pack(fill=tk.BOTH, expand=True)

        ttk.Button(right_frame, text=_t("musicshop.btn.refresh_alerts"), command=self._load_alerts).pack(pady=5)

    def create_reports_tab(self):
        """Create the reports tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("musicshop.tabs.reports"))

        # Left - Report options
        left_frame = ttk.LabelFrame(tab, text=_t("musicshop.labels.report_options"), padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        ttk.Button(left_frame, text=_t("musicshop.btn.sales_summary"), command=self.show_sales_summary, width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("musicshop.btn.inventory_report"), command=self.show_inventory_report, width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("musicshop.btn.top_products"), command=self.show_top_products, width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("musicshop.btn.top_artists"), command=self.show_top_artists, width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("musicshop.btn.genre_analysis"), command=self.show_genre_analysis, width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("musicshop.btn.generate_admin_report"), command=self.generate_admin_report, width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("musicshop.btn.email_admin_report"), command=self.email_admin_report, width=25).pack(pady=5)

        # Right - Report display
        right_frame = ttk.LabelFrame(tab, text=_t("musicshop.labels.report_output"), padding="10")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.report_text = tk.Text(right_frame, wrap=tk.WORD, font=('Courier', 10))
        scrollbar = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.report_text.yview)
        self.report_text.configure(yscrollcommand=scrollbar.set)
        self.report_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _load_products(self):
        """Load products into the treeview"""
        for item in self.products_tree.get_children():
            self.products_tree.delete(item)

        category = self.product_category_filter.get()
        if category == 'All':
            products = ProductManager.get_all_products()
        else:
            products = ProductManager.get_products_by_category(category)

        for p in products:
            self.products_tree.insert('', tk.END, values=(
                p['product_id'], p['sku'], p.get('title') or p.get('name', ''), p.get('artist', ''),
                p['category'], p.get('genre', ''), f"£{p['price']:.2f}", p['stock_quantity']
            ))

    def _filter_by_genre(self):
        """Filter products by genre"""
        genre = self.genre_filter.get()
        if genre == 'All':
            self._load_products()
            return

        for item in self.products_tree.get_children():
            self.products_tree.delete(item)

        products = ProductManager.get_products_by_genre(genre)
        for p in products:
            self.products_tree.insert('', tk.END, values=(
                p['product_id'], p['sku'], p.get('title') or p.get('name', ''), p.get('artist', ''),
                p['category'], p.get('genre', ''), f"£{p['price']:.2f}", p['stock_quantity']
            ))

    def _load_orders(self):
        """Load orders into the treeview"""
        for item in self.orders_tree.get_children():
            self.orders_tree.delete(item)

        status = self.order_status_filter.get()
        orders = [] if status == 'All' else OrderManager.get_orders_by_status(status)
        if status == 'All':
            for s in ORDER_STATUSES:
                orders.extend(OrderManager.get_orders_by_status(s))

        for o in orders:
            self.orders_tree.insert('', tk.END, values=(
                o['order_id'], o['order_number'], o['customer_name'],
                f"£{o['total_amount']:.2f}", o['status'], o['payment_status'],
                o['created_at'][:16] if o['created_at'] else ''
            ))

    def _load_wishlist(self):
        """Load user's wishlist"""
        self.wishlist_listbox.delete(0, tk.END)
        customer_id = self.current_user.get('user_id', '')
        wishlist = WishlistManager.get_wishlist(customer_id)
        for item in wishlist:
            self.wishlist_listbox.insert(tk.END, f"{item['title']} - £{item['price']:.2f}")

    def _load_alerts(self):
        """Load low stock and rare item alerts"""
        # Low stock
        for item in self.low_stock_tree.get_children():
            self.low_stock_tree.delete(item)
        for p in ProductManager.get_low_stock_products():
            self.low_stock_tree.insert('', tk.END, values=(p['product_id'], p['title'], p['stock_quantity']))

        # Rare items
        for item in self.rare_tree.get_children():
            self.rare_tree.delete(item)
        for p in ProductManager.get_rare_items():
            self.rare_tree.insert('', tk.END, values=(p['product_id'], p['title'], p.get('artist', ''), f"£{p['price']:.2f}"))

    def _on_product_select(self, event):
        """Handle product selection"""
        selected = self.products_tree.selection()
        if selected:
            values = self.products_tree.item(selected[0])['values']
            self.selected_product_id = values[0]
            self.selected_product_var.set(f"{values[2]}\nby {values[3]}\n£{values[6]}")

    def search_products(self):
        """Search products"""
        query = self.search_entry.get().strip()
        if not query:
            self._load_products()
            return

        for item in self.products_tree.get_children():
            self.products_tree.delete(item)

        for p in ProductManager.search_products(query):
            self.products_tree.insert('', tk.END, values=(
                p['product_id'], p['sku'], p['title'], p.get('artist', ''),
                p['category'], p.get('genre', ''), f"£{p['price']:.2f}", p['stock_quantity']
            ))

    def add_to_cart(self):
        """Add selected product to cart"""
        if not self.selected_product_id:
            messagebox.showwarning(_t("common.warning"), _t("musicshop.errors.no_product_selected"))
            return

        product = ProductManager.get_product(self.selected_product_id)
        if not product:
            return

        quantity = int(self.quantity_spinbox.get())
        if quantity > product['stock_quantity']:
            messagebox.showerror(_t("common.error"), _t("musicshop.errors.insufficient_stock"))
            return

        for item in self.cart:
            if item['product_id'] == self.selected_product_id:
                item['quantity'] += quantity
                messagebox.showinfo(_t("common.success"), _t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_create_inventory_tab.dialogs.cart_updated_click_view_shopping_cart_to_see_your_items', default="Cart updated! Click 'View Shopping Cart' to see your items."))
                return

        self.cart.append({
            'product_id': self.selected_product_id,
            'product_title': product['title'],
            'artist': product.get('artist', ''),
            'unit_price': product['price'],
            'quantity': quantity
        })
        messagebox.showinfo(_t("common.success"), _t("musicshop.messages.added_to_cart") + " Click 'View Shopping Cart' to see your items.")

    def add_to_wishlist(self):
        """Add selected product to wishlist"""
        if not self.selected_product_id:
            messagebox.showwarning(_t("common.warning"), _t("musicshop.errors.no_product_selected"))
            return

        customer_id = self.current_user.get('user_id', '')
        if WishlistManager.add_to_wishlist(customer_id, self.selected_product_id):
            messagebox.showinfo(_t("common.success"), _t("musicshop.messages.added_to_wishlist"))
            self._load_wishlist()

    def add_wishlist_to_cart(self):
        """Add selected wishlist item to cart"""
        selection = self.wishlist_listbox.curselection()
        if not selection:
            return

        customer_id = self.current_user.get('user_id', '')
        wishlist = WishlistManager.get_wishlist(customer_id)
        if selection[0] < len(wishlist):
            product = wishlist[selection[0]]
            self.selected_product_id = product['product_id']
            self.add_to_cart()

    def _update_cart_display(self):
        """Update the cart display - legacy method kept for compatibility"""
        # This method is kept for any legacy code that might call it
        pass

    def show_payment_window(self):
        """Show payment window with payment options"""
        if not self.cart:
            messagebox.showwarning(_t("common.warning"), _t("musicshop.errors.empty_cart"))
            return

        # Get shipping address if set from cart window
        shipping_address = ""
        if hasattr(self, 'temp_shipping_entry') and self.temp_shipping_entry:
            try:
                shipping_address = self.temp_shipping_entry.get()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

        # Create payment dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_create_inventory_tab.windows.complete_purchase', default="Complete Purchase"))
        dialog.geometry("400x500")
        dialog.transient(self.root)
        dialog.grab_set()

        # Order summary
        ttk.Label(dialog, text=_t("musicshop.labels.order_summary"), font=('Helvetica', 14, 'bold')).pack(pady=10)

        info_frame = ttk.Frame(dialog, padding="10")
        info_frame.pack(fill=tk.X, padx=20)

        ttk.Label(info_frame, text=f"Customer: {self.checkout_customer_name}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Items in cart: {len(self.cart)}").pack(anchor=tk.W)

        # Shipping address
        ttk.Label(info_frame, text=_t("musicshop.labels.shipping_address")).pack(anchor=tk.W, pady=(10, 0))
        shipping_entry = ttk.Entry(info_frame, width=40)
        shipping_entry.insert(0, shipping_address)
        shipping_entry.pack(fill=tk.X, pady=(0, 5))

        # Totals
        ttk.Separator(dialog, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=20, pady=10)

        totals_frame = ttk.Frame(dialog, padding="10")
        totals_frame.pack(fill=tk.X, padx=20)

        subtotal = sum(item['unit_price'] * item['quantity'] for item in self.cart)
        tax = subtotal * 0.20
        total = subtotal + tax

        ttk.Label(totals_frame, text=f"Subtotal: £{subtotal:.2f}").pack(anchor=tk.W)
        ttk.Label(totals_frame, text=f"Tax (20%): £{tax:.2f}").pack(anchor=tk.W)
        ttk.Label(totals_frame, text=f"TOTAL: £{total:.2f}", font=('Helvetica', 12, 'bold')).pack(anchor=tk.W, pady=(10, 0))

        # Payment method
        ttk.Separator(dialog, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=20, pady=10)

        payment_frame = ttk.Frame(dialog, padding="10")
        payment_frame.pack(fill=tk.X, padx=20)

        ttk.Label(payment_frame, text=_t("musicshop.labels.payment_method")).pack(anchor=tk.W)

        # Check student finance account balance
        customer_id = (self.current_user.get('student_id') or
                      self.current_user.get('username') or
                      self.current_user.get('id') or 'GUEST')
        balance = get_student_finance_account_balance(customer_id)

        payment_options = ['Cash', 'Card']
        if balance is not None:
            balance_text = f"Student Account (Balance: £{balance:.2f})"
            payment_options.append(balance_text)

        payment_method_var = tk.StringVar(value=_t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_create_inventory_tab.values.card', default='Card'))
        for option in payment_options:
            ttk.Radiobutton(payment_frame, text=option, variable=payment_method_var, value=option).pack(anchor=tk.W)

        def confirm_purchase():
            method = payment_method_var.get()
            actual_method = 'finance_account' if 'Student Account' in method else method.lower()

            # Check balance for student account
            if actual_method == 'finance_account':
                if balance is None or balance < total:
                    messagebox.showerror(_t("common.error"), _t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_create_inventory_tab.dialogs.insufficient_balance_in_student_account', default="Insufficient balance in student account"))
                    return

            # Create order
            order_id = OrderManager.create_order(
                customer_id=customer_id,
                customer_name=self.checkout_customer_name,
                items=self.cart,
                customer_email=self.checkout_customer_email,
                shipping_address=shipping_entry.get(),
                payment_method=actual_method,
                created_by=self.current_user.get('username')
            )

            if order_id:
                # Record payment (the service posts the sale to Finance)
                TransactionManager.record_payment(order_id, customer_id, total, actual_method,
                                                   processed_by=self.current_user.get('username'))

                # Automatically mark order as delivered
                OrderManager.update_order_status(order_id, 'delivered')

                # Send receipt
                self.send_receipt_email(order_id)

                order = OrderManager.get_order(order_id)
                messagebox.showinfo(_t("common.success"),
                    f"Order {order['order_number']} completed! Payment of £{total:.2f} processed.\nOrder status: Delivered")

                self.cart = []
                dialog.destroy()
                self.refresh_all_data()
            else:
                messagebox.showerror(_t("common.error"), _t("musicshop.errors.order_failed", default="Order Failed"))

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text=_t("musicshop.btn.confirm_pay"), command=confirm_purchase).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t("musicshop.btn.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def complete_purchase(self):
        """Complete the purchase (legacy - redirects to show_payment_window)"""
        self.show_payment_window()
