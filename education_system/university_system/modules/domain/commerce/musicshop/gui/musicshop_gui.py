"""Music Shop GUI Module - 25 functions with full integrations"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
from datetime import datetime

from education_system.university_system.core.i18n import get_text as _t
from education_system.university_system.infrastructure.database.db import get_db_connection
from education_system.university_system.modules.domain.commerce.musicshop.services.musicshop_core import (
    ProductManager, OrderManager, TransactionManager, ReportManager, WishlistManager,
    init_musicshop_db, MUSIC_CATEGORIES, GENRES, ORDER_STATUSES, CONDITION_TYPES
)
from education_system.university_system.modules.shared.utils.finance_integration import (
    record_payment_to_finance,
    process_student_finance_account_payment,
    get_student_finance_account_balance
)

logger = logging.getLogger(__name__)


class MusicShopGUI:
    """Music Shop GUI - 25 functions with email, finance, and i18n integration"""

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

    # Removed create_cart_tab - replaced with cart window dialog

    def open_cart_window(self):
        """Open shopping cart in a new window"""
        cart_dialog = tk.Toplevel(self.root)
        cart_dialog.title("Shopping Cart")
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
                messagebox.showwarning(_t("musicshop.msg_titles.warning"), "Please select an item to remove")
                return
            product_id = cart_tree.item(selected[0])['values'][0]
            self.cart = [item for item in self.cart if item['product_id'] != product_id]
            cart_dialog.destroy()
            messagebox.showinfo(_t("musicshop.msg_titles.success"), "Item removed from cart")

        def clear_all():
            if messagebox.askyesno(_t("musicshop.msg_titles.confirm"), "Clear all items from cart?"):
                self.cart = []
                cart_dialog.destroy()
                messagebox.showinfo(_t("musicshop.msg_titles.success"), "Cart cleared")

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
                messagebox.showwarning(_t("musicshop.msg_titles.warning"), "Cart is empty")
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
                messagebox.showinfo(_t("common.success"), "Cart updated! Click 'View Shopping Cart' to see your items.")
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

    # Removed remove_from_cart and clear_cart - now handled in cart window dialog

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
                pass

        # Create payment dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Complete Purchase")
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

        payment_method_var = tk.StringVar(value='Card')
        for option in payment_options:
            ttk.Radiobutton(payment_frame, text=option, variable=payment_method_var, value=option).pack(anchor=tk.W)

        def confirm_purchase():
            method = payment_method_var.get()
            actual_method = 'finance_account' if 'Student Account' in method else method.lower()

            # Check balance for student account
            if actual_method == 'finance_account':
                if balance is None or balance < total:
                    messagebox.showerror(_t("common.error"), "Insufficient balance in student account")
                    return

                # Process student account payment
                result = process_student_finance_account_payment(
                    student_id=customer_id,
                    amount=total,
                    description="Music Shop purchase",
                    transaction_source='MusicShop',
                    transaction_ref=f"MUS-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    processed_by=self.current_user.get('username')
                )
                if not result.get('success'):
                    messagebox.showerror(_t("common.error"), result.get('message', 'Payment failed'))
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
                # Record payment
                TransactionManager.record_payment(order_id, customer_id, total, actual_method,
                                                   processed_by=self.current_user.get('username'))

                # Automatically mark order as delivered
                OrderManager.update_order_status(order_id, 'delivered')

                # Record revenue to finance
                self.record_revenue_to_finance(order_id, total, actual_method)

                # Send receipt
                self.send_receipt_email(order_id)

                order = OrderManager.get_order(order_id)
                messagebox.showinfo(_t("common.success"),
                    f"Order {order['order_number']} completed! Payment of £{total:.2f} processed.\nOrder status: Delivered")

                self.cart = []
                dialog.destroy()
                self.refresh_all_data()
            else:
                messagebox.showerror(_t("common.error"), _t("musicshop.errors.order_failed"))

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text=_t("musicshop.btn.confirm_pay"), command=confirm_purchase).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t("musicshop.btn.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def complete_purchase(self):
        """Complete the purchase (legacy - redirects to show_payment_window)"""
        self.show_payment_window()

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

    # Removed update_order_status - status is now automatically updated to delivered/refunded

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
            messagebox.showwarning(_t("common.warning"), "Please select an order to refund")
            return

        values = self.orders_tree.item(selected[0])['values']
        order_id = values[0]
        amount = float(values[3].replace('£', ''))

        # Get order details
        order = OrderManager.get_order(order_id)
        if not order:
            messagebox.showerror(_t("common.error"), "Order not found")
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
                                             "Refund recorded but failed to credit student account. Please credit manually.")

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
                messagebox.showerror(_t("common.error"), "Failed to process refund")
        except Exception as e:
            logger.error(f"Error processing refund: {e}")
            messagebox.showerror(_t("common.error"), f"Error processing refund: {e}")

    def show_refund_method_dialog(self, amount, order_number, customer_id):
        """Show dialog to select refund method for order refunds"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Refund Method")
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
                messagebox.showerror(_t("musicshop.msg_titles.error"), "No customer ID associated with this order.")
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
            from education_system.university_system.infrastructure.email.email_service import send_email

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
            from education_system.university_system.infrastructure.email.email_service import send_email

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
            messagebox.showwarning(_t("musicshop.msg_titles.no_selection"), "Please select a transaction to refund.")
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']

        if len(values) < 7:
            messagebox.showerror(_t("musicshop.msg_titles.error"), "Invalid transaction data.")
            return

        transaction_id = values[0]
        order_id = values[1]
        amount_str = values[4].replace('£', '').strip()
        try:
            amount = float(amount_str)
        except ValueError:
            messagebox.showerror(_t("musicshop.msg_titles.error"), "Invalid amount format.")
            return

        status = values[6]

        # Check if already refunded
        if status == 'REFUNDED':
            messagebox.showinfo(_t("musicshop.msg_titles.already_refunded"), "This transaction has already been refunded.")
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
                    messagebox.showerror(_t("musicshop.msg_titles.error"), "Transaction not found in database.")
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

        # Process refund
        try:
            with get_db_connection() as conn:
                # Update transaction status to refunded
                conn.execute('''
                    UPDATE transactions
                    SET status = 'refunded'
                    WHERE transaction_id = ? AND source_type = 'music_shop'
                ''', (transaction_id,))

                # Generate refund reference
                refund_ref = f"MUSIC-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

                # Insert refund record into unified_refunds table
                processed_by = self.current_user.get('username', 'System') if self.current_user else 'System'
                cur = conn.execute('''
                    INSERT INTO unified_refunds
                    (source_type, reference_id, reference_type, refund_date, amount,
                     refund_method, refund_reference, student_id, processed_by, notes, status)
                    VALUES ('music_shop', ?, 'order', ?, ?, ?, ?, ?, ?, ?, 'processed')
                ''', (str(order_id), datetime.now().strftime('%Y-%m-%d %H:%M:%S'), amount, refund_method,
                      refund_ref, customer_id, processed_by, f'musicshop_transaction_{transaction_id}'))
                refund_row_id = cur.lastrowid

                conn.commit()

            # Auto-post to GL (cash has moved). Never raises.
            try:
                from education_system.university_system.modules.domain.finance.ledger import notify_ledger
                notify_ledger('refund', refund_row_id, posted_by=processed_by)
            except Exception as _e:
                import logging
                logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

            # Automatically mark order as refunded
            if order_id:
                OrderManager.update_order_status(order_id, 'refunded')

            # If student account refund, add to their account
            if refund_method == 'Student Account':
                success = self.add_musicshop_refund_to_student_account(customer_id, amount, refund_ref)
                if not success:
                    messagebox.showwarning(_t("musicshop.msg_titles.partial_success"),
                                         "Refund recorded but failed to credit student account. Please credit manually.")

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
        dialog.title("Select Refund Method")
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
                messagebox.showerror(_t("musicshop.msg_titles.error"), "No customer ID associated with this transaction.")
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

    def add_musicshop_refund_to_student_account(self, customer_id, amount, refund_ref):
        """Add refund amount to student finance account"""
        try:
            with get_db_connection() as conn:
                # Check if student finance account exists
                cursor = conn.execute(
                    'SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?',
                    (customer_id,)
                )
                account = cursor.fetchone()

                if not account:
                    # Create account with refund amount
                    conn.execute('''
                        INSERT INTO student_finance_accounts (student_id, balance, created_at)
                        VALUES (?, ?, ?)
                    ''', (customer_id, amount, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                    # Get the new account_id
                    cursor = conn.execute(
                        'SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?',
                        (customer_id,)
                    )
                    account = cursor.fetchone()
                    account_id = account[0]
                    balance_before = 0
                    balance_after = amount
                else:
                    # Update existing account
                    account_id = account[0]
                    balance_before = account[1]
                    balance_after = balance_before + amount

                    conn.execute('''
                        UPDATE student_finance_accounts
                        SET balance = balance + ?
                        WHERE student_id = ?
                    ''', (amount, customer_id))

                # Record transaction
                processed_by = self.current_user.get('username', 'System') if self.current_user else 'System'
                conn.execute('''
                    INSERT INTO transactions
                    (source_type, account_id, student_id, transaction_type, amount, balance_before,
                     balance_after, description, reference_id, processed_by)
                    VALUES ('student_finance', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (account_id, customer_id, 'credit', amount, balance_before, balance_after,
                      'Music Shop Purchase Refund', refund_ref, processed_by))

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error adding refund to student account: {e}")
            return False

    def send_musicshop_refund_receipt(self, transaction_id, customer_id, amount, method, refund_ref):
        """Send refund receipt email to customer"""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_email
            from education_system.university_system.modules.shared.utils.finance_integration import get_student_info
            from education_system.university_system.infrastructure.email.template_utils import render_template

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
            subject, body = render_template('commerce/musicshop/refund_receipt', {
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

    def notify_musicshop_finance_gui(self, transaction_id, amount, method, refund_ref, customer_id):
        """Notify finance GUI about the refund - already recorded in unified_refunds."""
        try:
            logger.info(f"[Music Shop] Refund {refund_ref} recorded in unified_refunds")
        except Exception as e:
            logger.error(f"Error notifying finance GUI: {e}")

    def view_refund_transaction_details(self):
        """View detailed information for selected transaction"""
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("musicshop.msg_titles.no_selection"), "Please select a transaction to view details.")
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']

        if len(values) < 7:
            messagebox.showerror(_t("musicshop.msg_titles.error"), "Invalid transaction data.")
            return

        transaction_id = values[0]
        order_id = values[1]

        try:
            with get_db_connection() as conn:
                # Get transaction details
                cursor = conn.execute('''
                    SELECT t.*, o.shipping_address, o.status as order_status
                    FROM transactions t
                    LEFT JOIN orders o ON t.reference_id = o.id AND t.reference_type = 'order' AND o.source_type = 'music_shop'
                    WHERE t.source_type = 'music_shop' AND t.transaction_id = ?
                ''', (transaction_id,))

                trans = cursor.fetchone()

                if not trans:
                    messagebox.showerror(_t("musicshop.msg_titles.error"), "Transaction not found.")
                    return

                # Get order items
                cursor = conn.execute('''
                    SELECT oi.product_id, p.name, p.artist, p.genre, oi.quantity, oi.unit_price, oi.subtotal
                    FROM order_items oi
                    LEFT JOIN products p ON oi.product_id = p.id AND p.source_type = 'music_shop'
                    WHERE oi.order_id = ?
                ''', (order_id,))

                items = cursor.fetchall()

            # Create details window
            details_window = tk.Toplevel(self.root)
            details_window.title(f"Transaction Details - {transaction_id}")
            details_window.geometry("600x600")
            details_window.transient(self.root)

            main_frame = ttk.Frame(details_window, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Transaction information
            from tkinter.scrolledtext import ScrolledText
            info_text = ScrolledText(main_frame, width=70, height=30, wrap=tk.WORD)
            info_text.pack(fill=tk.BOTH, expand=True)

            # Format order items
            items_text = ""
            if items:
                for item in items:
                    product_id, title, artist, genre, quantity, unit_price, subtotal = item
                    items_text += f"\n{title} - {artist}\n"
                    if genre:
                        items_text += f"  Genre: {genre}\n"
                    items_text += f"  Quantity: {quantity} x £{unit_price:.2f} = £{subtotal:.2f}\n"

            details = f"""TRANSACTION DETAILS
═══════════════════════════════════════════════════════

Transaction ID:     {trans[0]}
Order ID:           {trans[1]}
Customer ID:        {trans[2]}
Transaction Type:   {trans[3]}
Payment Method:     {trans[5] or 'N/A'}
Reference Number:   {trans[6] or 'N/A'}
Status:             {trans[7].upper()}
Processed By:       {trans[8] or 'System'}
Date:               {trans[9]}

Shipping Address:   {trans[10] if len(trans) > 10 and trans[10] else 'N/A'}
Order Status:       {trans[11].upper() if len(trans) > 11 and trans[11] else 'N/A'}

═══════════════════════════════════════════════════════
ORDER ITEMS
═══════════════════════════════════════════════════════
{items_text}

═══════════════════════════════════════════════════════
TOTAL:              £{trans[4]:.2f}
═══════════════════════════════════════════════════════
"""

            info_text.insert('1.0', details)
            info_text.config(state='disabled')

            ttk.Button(main_frame, text=_t("musicshop.btn.close"), command=details_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t("musicshop.msg_titles.database_error"), f"Error loading transaction details: {e}")
            logger.error(f"Error loading transaction details: {e}")

    def export_refunds_to_csv(self):
        """Export refunds list to CSV file"""
        try:
            from tkinter import filedialog
            import csv

            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"musicshop_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )

            if not filename:
                return

            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow(['Transaction ID', 'Order ID', 'Date', 'Customer',
                               'Amount', 'Payment Method', 'Status'])

                # Write data
                for item in self.refunds_tree.get_children():
                    values = self.refunds_tree.item(item)['values']
                    writer.writerow(values)

            messagebox.showinfo(_t("musicshop.msg_titles.export_successful"), f"Data exported to:\n{filename}")

        except Exception as e:
            messagebox.showerror(_t("musicshop.msg_titles.export_error"), f"Error exporting data: {e}")
            logger.error(f"Error exporting data: {e}")


def launch_musicshop_gui(parent=None, auth=None):
    """Launch the Music Shop GUI"""
    if parent:
        window = tk.Toplevel(parent)
    else:
        window = tk.Tk()

    app = MusicShopGUI(window, auth)

    if not parent:
        window.mainloop()

    return app
