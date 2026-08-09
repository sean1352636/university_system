"""Methods __init__ through create_orders_tab."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import musicshop_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class MusicShopGUI:
    def __init__(self, root, auth):
        """Initialize the Music Shop GUI"""
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth else None
        self.cart = []
        self.cart_total = 0.0

        if not self.current_user:
            messagebox.showerror(_t("musicshop.window_title"), _t("musicshop.errors.login_required"))
            root.destroy()
            return

        self.root.title(_t("musicshop.window_title"))
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)

        self._init_database()
        self.create_widgets()
        self.refresh_all_data()

    def _init_database(self):
        """Initialize the music shop database"""
        try:
            init_musicshop_db()
            logger.info("Music shop database initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            messagebox.showerror(_t("common.error"), str(e))

    def _get_user_details_from_db(self):
        """Fetch user name and email from the users table"""
        try:
            user_id = self.current_user.get('id')
            username = self.current_user.get('username')

            with get_db_connection() as conn:
                cursor = conn.execute(
                    """SELECT first_name, last_name, email
                       FROM users WHERE id = ? OR username = ?""",
                    (user_id, username)
                )
                row = cursor.fetchone()

            if row:
                first_name = row[0] or ''
                last_name = row[1] or ''
                email = row[2] or ''
                full_name = f"{first_name} {last_name}".strip() or username or 'Unknown'
                return full_name, email
            else:
                return username or 'Unknown', ''
        except Exception as e:
            logger.error(f"Error fetching user details: {e}")
            return self.current_user.get('username', 'Unknown'), ''

    def create_widgets(self):
        """Create the main GUI widgets"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(header_frame, text=_t("musicshop.title"),
                  font=('Helvetica', 16, 'bold')).pack(side=tk.LEFT)

        ttk.Button(header_frame, text=_t("common.refresh"),
                   command=self.refresh_all_data).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text=_t("common.back"),
                   command=self.return_to_homescreen).pack(side=tk.RIGHT)

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.create_catalog_tab()
        self.create_orders_tab()
        self.create_inventory_tab()
        self.create_reports_tab()
        self.create_refunds_tab()

    def return_to_homescreen(self):
        """Return to the main homescreen"""
        self.root.destroy()

    def refresh_all_data(self):
        """Refresh all data in all tabs"""
        self._load_products()
        self._load_orders()
        self._load_wishlist()

    def create_catalog_tab(self):
        """Create the music catalog browsing tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("musicshop.tabs.catalog"))

        # Left panel - Product list
        left_frame = ttk.LabelFrame(tab, text=_t("musicshop.labels.music_catalog"), padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Filter frame
        filter_frame = ttk.Frame(left_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(filter_frame, text=_t("musicshop.labels.category") + ":").pack(side=tk.LEFT)
        self.product_category_filter = ttk.Combobox(filter_frame, values=['All'] + MUSIC_CATEGORIES, width=12)
        self.product_category_filter.set('All')
        self.product_category_filter.pack(side=tk.LEFT, padx=5)
        self.product_category_filter.bind('<<ComboboxSelected>>', lambda e: self._load_products())

        ttk.Label(filter_frame, text=_t("musicshop.labels.genre") + ":").pack(side=tk.LEFT, padx=(10, 0))
        self.genre_filter = ttk.Combobox(filter_frame, values=['All'] + GENRES, width=10)
        self.genre_filter.set('All')
        self.genre_filter.pack(side=tk.LEFT, padx=5)
        self.genre_filter.bind('<<ComboboxSelected>>', lambda e: self._filter_by_genre())

        ttk.Label(filter_frame, text=_t("musicshop.labels.search") + ":").pack(side=tk.LEFT, padx=(10, 5))
        self.search_entry = ttk.Entry(filter_frame, width=15)
        self.search_entry.pack(side=tk.LEFT)
        ttk.Button(filter_frame, text=_t("common.search"), command=self.search_products).pack(side=tk.LEFT, padx=5)

        # Products treeview
        columns = ('id', 'sku', 'title', 'artist', 'category', 'genre', 'price', 'stock')
        self.products_tree = ttk.Treeview(left_frame, columns=columns, show='headings', height=16)

        self.products_tree.heading('id', text=_t('musicshop.columns.id'))
        self.products_tree.heading('sku', text=_t("musicshop.labels.sku"))
        self.products_tree.heading('title', text=_t("musicshop.labels.title"))
        self.products_tree.heading('artist', text=_t("musicshop.labels.artist"))
        self.products_tree.heading('category', text=_t("musicshop.labels.category"))
        self.products_tree.heading('genre', text=_t("musicshop.labels.genre"))
        self.products_tree.heading('price', text=_t("musicshop.labels.price"))
        self.products_tree.heading('stock', text=_t("musicshop.labels.stock"))

        self.products_tree.column('id', width=35)
        self.products_tree.column('sku', width=70)
        self.products_tree.column('title', width=150)
        self.products_tree.column('artist', width=120)
        self.products_tree.column('category', width=80)
        self.products_tree.column('genre', width=70)
        self.products_tree.column('price', width=60)
        self.products_tree.column('stock', width=45)

        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.products_tree.yview)
        self.products_tree.configure(yscrollcommand=scrollbar.set)
        self.products_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Right panel - Add to cart & wishlist
        right_frame = ttk.LabelFrame(tab, text=_t("musicshop.labels.selected_item"), padding="10")
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        self.selected_product_var = tk.StringVar()
        ttk.Label(right_frame, textvariable=self.selected_product_var, font=('Helvetica', 10, 'bold'), wraplength=180).pack(pady=5)
        self.selected_product_id = None

        ttk.Label(right_frame, text=_t("musicshop.labels.quantity") + ":").pack(anchor=tk.W, pady=(10, 0))
        self.quantity_spinbox = ttk.Spinbox(right_frame, from_=1, to=99, width=10)
        self.quantity_spinbox.set(1)
        self.quantity_spinbox.pack(pady=5)

        ttk.Button(right_frame, text=_t("musicshop.btn.add_to_cart"),
                   command=self.add_to_cart).pack(pady=5, fill=tk.X)

        ttk.Button(right_frame, text=_t("musicshop.btn.view_cart"),
                   command=self.open_cart_window).pack(pady=5, fill=tk.X)

        ttk.Button(right_frame, text=_t("musicshop.btn.add_to_wishlist"),
                   command=self.add_to_wishlist).pack(pady=5, fill=tk.X)

        # Wishlist section
        ttk.Separator(right_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(right_frame, text=_t("musicshop.labels.my_wishlist"), font=('Helvetica', 10, 'bold')).pack()

        self.wishlist_listbox = tk.Listbox(right_frame, width=25, height=8)
        self.wishlist_listbox.pack(pady=5, fill=tk.BOTH, expand=True)

        ttk.Button(right_frame, text=_t("musicshop.btn.add_wishlist_to_cart"),
                   command=self.add_wishlist_to_cart).pack(pady=2, fill=tk.X)

        self.products_tree.bind('<Double-1>', self._on_product_select)

    def open_cart_window(self):
        """Open shopping cart in a new window"""
        cart_dialog = tk.Toplevel(self.root)
        cart_dialog.title(_t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_init.windows.shopping_cart', default="Shopping Cart"))
        cart_dialog.geometry("1100x750")
        cart_dialog.transient(self.root)
        cart_dialog.grab_set()

        # Create a canvas with scrollbar for the main content
        canvas = tk.Canvas(cart_dialog)
        scrollbar = ttk.Scrollbar(cart_dialog, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        main_frame = ttk.Frame(scrollable_frame, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        ttk.Label(main_frame, text=_t("musicshop.labels.shopping_cart"), font=('Helvetica', 14, 'bold')).pack(pady=(0, 10))

        # Cart items display
        cart_frame = ttk.LabelFrame(main_frame, text=_t("musicshop.labels.cart_items"), padding="10")
        cart_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ('product_id', 'title', 'artist', 'price', 'quantity', 'subtotal')
        cart_tree = ttk.Treeview(cart_frame, columns=columns, show='headings', height=10)

        cart_tree.heading('product_id', text=_t('musicshop.columns.id'))
        cart_tree.heading('title', text=_t('musicshop.columns.title'))
        cart_tree.heading('artist', text=_t('musicshop.columns.artist'))
        cart_tree.heading('price', text=_t('musicshop.columns.price'))
        cart_tree.heading('quantity', text=_t('musicshop.columns.quantity'))
        cart_tree.heading('subtotal', text=_t('musicshop.columns.subtotal'))

        cart_tree.column('product_id', width=50)
        cart_tree.column('title', width=280)
        cart_tree.column('artist', width=200)
        cart_tree.column('price', width=100)
        cart_tree.column('quantity', width=80)
        cart_tree.column('subtotal', width=100)

        tree_scrollbar = ttk.Scrollbar(cart_frame, orient=tk.VERTICAL, command=cart_tree.yview)
        cart_tree.configure(yscrollcommand=tree_scrollbar.set)
        cart_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Populate cart
        subtotal = 0
        for item in self.cart:
            item_subtotal = item['unit_price'] * item['quantity']
            subtotal += item_subtotal
            cart_tree.insert('', tk.END, values=(
                item['product_id'], item['product_title'],
                item.get('artist', 'N/A'),
                f"£{item['unit_price']:.2f}", item['quantity'], f"£{item_subtotal:.2f}"
            ))

        tax = subtotal * 0.20
        total = subtotal + tax

        # Cart actions
        action_frame = ttk.Frame(cart_frame)
        action_frame.pack(fill=tk.X, pady=(10, 0))

        def remove_selected():
            selected = cart_tree.selection()
            if not selected:
                messagebox.showwarning(_t("musicshop.msg_titles.warning"), _t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_init.dialogs.please_select_an_item_to_remove', default="Please select an item to remove"))
                return
            product_id = cart_tree.item(selected[0])['values'][0]
            self.cart = [item for item in self.cart if item['product_id'] != product_id]
            cart_dialog.destroy()
            messagebox.showinfo(_t("musicshop.msg_titles.success"), _t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_init.dialogs.item_removed_from_cart', default="Item removed from cart"))

        def clear_all():
            if messagebox.askyesno(_t("musicshop.msg_titles.confirm"), _t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_init.dialogs.clear_all_items_from_cart', default="Clear all items from cart?")):
                self.cart = []
                cart_dialog.destroy()
                messagebox.showinfo(_t("musicshop.msg_titles.success"), _t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_init.dialogs.cart_cleared', default="Cart cleared"))

        ttk.Button(action_frame, text=_t("musicshop.btn.remove_selected"), command=remove_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t("musicshop.btn.clear_cart"), command=clear_all).pack(side=tk.LEFT, padx=5)

        # Checkout section
        checkout_frame = ttk.LabelFrame(main_frame, text=_t("musicshop.btn.checkout"), padding="10")
        checkout_frame.pack(fill=tk.X, pady=(0, 10))

        # Get user details
        user_name, user_email = self._get_user_details_from_db()
        display_email = user_email if user_email and '@' in user_email else 'Not set'

        # Create two columns for better layout
        left_checkout = ttk.Frame(checkout_frame)
        left_checkout.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        right_checkout = ttk.Frame(checkout_frame)
        right_checkout.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Left side - Customer info and shipping
        ttk.Label(left_checkout, text=f"Customer: {user_name}", font=('Helvetica', 10)).pack(anchor=tk.W, pady=2)
        ttk.Label(left_checkout, text=f"Email: {display_email}", font=('Helvetica', 10)).pack(anchor=tk.W, pady=2)

        ttk.Label(left_checkout, text=_t("musicshop.labels.shipping_address"), font=('Helvetica', 10, 'bold')).pack(anchor=tk.W, pady=(10, 2))
        shipping_entry = ttk.Entry(left_checkout, width=40)
        shipping_entry.pack(fill=tk.X, pady=(0, 5))

        # Right side - Totals
        ttk.Label(right_checkout, text=_t("musicshop.labels.order_summary"), font=('Helvetica', 11, 'bold')).pack(anchor=tk.W, pady=(0, 5))

        totals_frame = ttk.Frame(right_checkout)
        totals_frame.pack(fill=tk.X)

        ttk.Label(totals_frame, text=_t("musicshop.labels.subtotal"), font=('Helvetica', 10)).grid(row=0, column=0, sticky=tk.W, pady=3, padx=(0, 10))
        ttk.Label(totals_frame, text=f"£{subtotal:.2f}", font=('Helvetica', 10)).grid(row=0, column=1, sticky=tk.E, pady=3)

        ttk.Label(totals_frame, text=_t("musicshop.labels.tax"), font=('Helvetica', 10)).grid(row=1, column=0, sticky=tk.W, pady=3, padx=(0, 10))
        ttk.Label(totals_frame, text=f"£{tax:.2f}", font=('Helvetica', 10)).grid(row=1, column=1, sticky=tk.E, pady=3)

        ttk.Separator(totals_frame, orient=tk.HORIZONTAL).grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=5)

        ttk.Label(totals_frame, text=_t("musicshop.labels.total"), font=('Helvetica', 12, 'bold')).grid(row=3, column=0, sticky=tk.W, pady=3, padx=(0, 10))
        ttk.Label(totals_frame, text=f"£{total:.2f}", font=('Helvetica', 12, 'bold')).grid(row=3, column=1, sticky=tk.E, pady=3)

        totals_frame.columnconfigure(1, weight=1)

        # Store shipping entry and user details for checkout
        self.temp_shipping_entry = shipping_entry
        self.checkout_customer_name = user_name
        self.checkout_customer_email = user_email if user_email and '@' in user_email else None

        # Buttons - Fixed at the bottom
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(15, 10))

        def proceed_to_payment():
            if not self.cart:
                messagebox.showwarning(_t("musicshop.msg_titles.warning"), _t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_init.dialogs.cart_is_empty', default="Cart is empty"))
                return
            cart_dialog.destroy()
            self.show_payment_window()

        ttk.Button(btn_frame, text=_t("musicshop.btn.proceed_to_payment"), command=proceed_to_payment, width=25).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t("musicshop.btn.continue_shopping"), command=cart_dialog.destroy, width=25).pack(side=tk.LEFT, padx=10)

        # Pack the canvas and scrollbar
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_orders_tab(self):
        """Create the orders management tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("musicshop.tabs.orders"))

        # Filter
        filter_frame = ttk.Frame(tab)
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(filter_frame, text=_t("musicshop.labels.status") + ":").pack(side=tk.LEFT)
        self.order_status_filter = ttk.Combobox(filter_frame, values=['All'] + ORDER_STATUSES, width=15)
        self.order_status_filter.set('All')
        self.order_status_filter.pack(side=tk.LEFT, padx=5)
        self.order_status_filter.bind('<<ComboboxSelected>>', lambda e: self._load_orders())

        # Orders treeview
        columns = ('id', 'order_num', 'customer', 'total', 'status', 'payment', 'date')
        self.orders_tree = ttk.Treeview(tab, columns=columns, show='headings', height=18)

        for col in columns:
            self.orders_tree.heading(col, text=col.replace('_', ' ').title())

        self.orders_tree.column('id', width=40)
        self.orders_tree.column('order_num', width=140)
        self.orders_tree.column('customer', width=150)
        self.orders_tree.column('total', width=80)
        self.orders_tree.column('status', width=100)
        self.orders_tree.column('payment', width=100)
        self.orders_tree.column('date', width=120)

        self.orders_tree.pack(fill=tk.BOTH, expand=True)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text=_t("musicshop.btn.view_order"), command=self.view_order_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("musicshop.btn.cancel_order"), command=self.cancel_order).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("musicshop.btn.process_refund"), command=self.process_refund).pack(side=tk.LEFT, padx=5)
