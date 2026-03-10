"""Phone Shop GUI Module - 25 functions with full integrations"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
from datetime import datetime

from education_system.university_system.modules.shared.utils.i18n import get_text as _t
from education_system.university_system.infrastructure.database.db import get_db_connection
from education_system.university_system.modules.domain.phoneshop.services.phoneshop_core import (
    ProductManager, OrderManager, TransactionManager, ReportManager,
    init_phoneshop_db, PHONE_CATEGORIES, ORDER_STATUSES
)
from education_system.university_system.modules.shared.utils.finance_integration import (
    record_payment_to_finance,
    process_student_finance_account_payment,
    get_student_finance_account_balance
)

logger = logging.getLogger(__name__)


class PhoneShopGUI:
    """Phone Shop GUI - 25 functions with email, finance, and i18n integration"""

    def __init__(self, root, auth):
        """Initialize the Phone Shop GUI"""
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth else None
        self.cart = []
        self.cart_total = 0.0

        if not self.current_user:
            messagebox.showerror(_t("phoneshop.window_title"), _t("phoneshop.errors.login_required"))
            root.destroy()
            return

        self.root.title(_t("phoneshop.window_title"))
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)

        self._init_database()
        self.create_widgets()
        self.refresh_all_data()

    def _init_database(self):
        """Initialize the phone shop database"""
        try:
            init_phoneshop_db()
            logger.info("Phone shop database initialized")
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

        ttk.Label(header_frame, text=_t("phoneshop.title"),
                  font=('Helvetica', 16, 'bold')).pack(side=tk.LEFT)

        ttk.Button(header_frame, text=_t("common.refresh"),
                   command=self.refresh_all_data).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text=_t("common.back"),
                   command=self.return_to_homescreen).pack(side=tk.RIGHT)

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.create_products_tab()
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

    def create_products_tab(self):
        """Create the products browsing tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("phoneshop.tabs.products"))

        # Left panel - Product list
        left_frame = ttk.LabelFrame(tab, text=_t("phoneshop.labels.product_catalog"), padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Filter frame
        filter_frame = ttk.Frame(left_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(filter_frame, text=_t("phoneshop.labels.category") + ":").pack(side=tk.LEFT)
        self.product_category_filter = ttk.Combobox(filter_frame, values=['All'] + PHONE_CATEGORIES, width=15)
        self.product_category_filter.set('All')
        self.product_category_filter.pack(side=tk.LEFT, padx=5)
        self.product_category_filter.bind('<<ComboboxSelected>>', lambda e: self._load_products())

        ttk.Label(filter_frame, text=_t("phoneshop.labels.search") + ":").pack(side=tk.LEFT, padx=(20, 5))
        self.search_entry = ttk.Entry(filter_frame, width=20)
        self.search_entry.pack(side=tk.LEFT)
        ttk.Button(filter_frame, text=_t("common.search"), command=self.search_products).pack(side=tk.LEFT, padx=5)

        # Products treeview
        columns = ('id', 'sku', 'name', 'brand', 'category', 'price', 'stock')
        self.products_tree = ttk.Treeview(left_frame, columns=columns, show='headings', height=18)

        self.products_tree.heading('id', text=_t('phoneshop.columns.id'))
        self.products_tree.heading('sku', text=_t("phoneshop.labels.sku"))
        self.products_tree.heading('name', text=_t("phoneshop.labels.name"))
        self.products_tree.heading('brand', text=_t("phoneshop.labels.brand"))
        self.products_tree.heading('category', text=_t("phoneshop.labels.category"))
        self.products_tree.heading('price', text=_t("phoneshop.labels.price"))
        self.products_tree.heading('stock', text=_t("phoneshop.labels.stock"))

        self.products_tree.column('id', width=40)
        self.products_tree.column('sku', width=80)
        self.products_tree.column('name', width=180)
        self.products_tree.column('brand', width=100)
        self.products_tree.column('category', width=100)
        self.products_tree.column('price', width=80)
        self.products_tree.column('stock', width=60)

        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.products_tree.yview)
        self.products_tree.configure(yscrollcommand=scrollbar.set)
        self.products_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Right panel - Add to cart
        right_frame = ttk.LabelFrame(tab, text=_t("phoneshop.labels.add_to_cart"), padding="10")
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        ttk.Label(right_frame, text=_t("phoneshop.labels.selected_product") + ":").pack(anchor=tk.W)
        self.selected_product_var = tk.StringVar()
        ttk.Label(right_frame, textvariable=self.selected_product_var, font=('Helvetica', 10, 'bold'), wraplength=200).pack(pady=5)
        self.selected_product_id = None

        ttk.Label(right_frame, text=_t("phoneshop.labels.quantity") + ":").pack(anchor=tk.W, pady=(10, 0))
        self.quantity_spinbox = ttk.Spinbox(right_frame, from_=1, to=99, width=10)
        self.quantity_spinbox.set(1)
        self.quantity_spinbox.pack(pady=5)

        ttk.Button(right_frame, text=_t("phoneshop.btn.add_to_cart"),
                   command=self.add_to_cart).pack(pady=10)

        ttk.Button(right_frame, text=_t("phoneshop.btn.view_cart"),
                   command=self.open_cart_window).pack(pady=5)

        self.products_tree.bind('<Double-1>', self._on_product_select)

    # Removed create_cart_tab - replaced with cart window dialog

    def create_orders_tab(self):
        """Create the orders management tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("phoneshop.tabs.orders"))

        # Filter frame
        filter_frame = ttk.Frame(tab)
        filter_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(filter_frame, text=_t("phoneshop.labels.status") + ":").pack(side=tk.LEFT)
        self.order_status_filter = ttk.Combobox(filter_frame, values=['All'] + ORDER_STATUSES, width=15)
        self.order_status_filter.set('All')
        self.order_status_filter.pack(side=tk.LEFT, padx=5)
        self.order_status_filter.bind('<<ComboboxSelected>>', lambda e: self._load_orders())

        # Orders treeview
        columns = ('id', 'order_num', 'customer', 'total', 'status', 'payment', 'date')
        self.orders_tree = ttk.Treeview(tab, columns=columns, show='headings', height=20)

        self.orders_tree.heading('id', text=_t('phoneshop.columns.id'))
        self.orders_tree.heading('order_num', text=_t("phoneshop.labels.order_number"))
        self.orders_tree.heading('customer', text=_t("phoneshop.labels.customer"))
        self.orders_tree.heading('total', text=_t("phoneshop.labels.total"))
        self.orders_tree.heading('status', text=_t("phoneshop.labels.status"))
        self.orders_tree.heading('payment', text=_t("phoneshop.labels.payment"))
        self.orders_tree.heading('date', text=_t("phoneshop.labels.date"))

        self.orders_tree.column('id', width=40)
        self.orders_tree.column('order_num', width=140)
        self.orders_tree.column('customer', width=150)
        self.orders_tree.column('total', width=80)
        self.orders_tree.column('status', width=100)
        self.orders_tree.column('payment', width=100)
        self.orders_tree.column('date', width=120)

        self.orders_tree.pack(fill=tk.BOTH, expand=True)

        # Action buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text=_t("phoneshop.btn.view_order"), command=self.view_order_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("phoneshop.btn.cancel_order"), command=self.cancel_order).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("phoneshop.btn.process_refund"), command=self.process_refund).pack(side=tk.LEFT, padx=5)

    def create_inventory_tab(self):
        """Create the inventory management tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("phoneshop.tabs.inventory"))

        # Left - Product management
        left_frame = ttk.LabelFrame(tab, text=_t("phoneshop.labels.manage_products"), padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        fields = [
            ("sku", _t("phoneshop.labels.sku")),
            ("name", _t("phoneshop.labels.name")),
            ("brand", _t("phoneshop.labels.brand")),
            ("model", _t("phoneshop.labels.model")),
            ("price", _t("phoneshop.labels.price")),
            ("cost_price", _t("phoneshop.labels.cost_price")),
            ("stock_quantity", _t("phoneshop.labels.stock")),
            ("warranty_months", _t("phoneshop.labels.warranty_months"))
        ]

        self.product_entries = {}
        for i, (field, label) in enumerate(fields):
            ttk.Label(left_frame, text=label + ":").grid(row=i, column=0, sticky=tk.W, pady=2)
            entry = ttk.Entry(left_frame, width=25)
            entry.grid(row=i, column=1, pady=2, padx=5)
            self.product_entries[field] = entry

        row = len(fields)
        ttk.Label(left_frame, text=_t("phoneshop.labels.category") + ":").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.new_product_category = ttk.Combobox(left_frame, values=PHONE_CATEGORIES, width=22)
        self.new_product_category.grid(row=row, column=1, pady=2, padx=5)

        ttk.Label(left_frame, text=_t("phoneshop.labels.description") + ":").grid(row=row+1, column=0, sticky=tk.NW, pady=2)
        self.product_description = tk.Text(left_frame, width=25, height=3)
        self.product_description.grid(row=row+1, column=1, pady=2, padx=5)

        btn_frame = ttk.Frame(left_frame)
        btn_frame.grid(row=row+2, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text=_t("phoneshop.btn.add_product"), command=self.add_product).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("phoneshop.btn.update_product"), command=self.update_product).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.clear"), command=self._clear_product_form).pack(side=tk.LEFT, padx=5)

        # Right - Low stock alerts
        right_frame = ttk.LabelFrame(tab, text=_t("phoneshop.labels.low_stock_alerts"), padding="10")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        columns = ('id', 'name', 'stock', 'min_level')
        self.low_stock_tree = ttk.Treeview(right_frame, columns=columns, show='headings', height=15)

        self.low_stock_tree.heading('id', text=_t('phoneshop.columns.id'))
        self.low_stock_tree.heading('name', text=_t("phoneshop.labels.product"))
        self.low_stock_tree.heading('stock', text=_t("phoneshop.labels.current_stock"))
        self.low_stock_tree.heading('min_level', text=_t("phoneshop.labels.min_level"))

        self.low_stock_tree.pack(fill=tk.BOTH, expand=True)

        ttk.Button(right_frame, text=_t("phoneshop.btn.refresh_alerts"),
                   command=self._load_low_stock).pack(pady=10)

    def create_reports_tab(self):
        """Create the reports tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("phoneshop.tabs.reports"))

        # Left - Report options
        left_frame = ttk.LabelFrame(tab, text=_t("phoneshop.labels.report_options"), padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        ttk.Button(left_frame, text=_t("phoneshop.btn.sales_summary"), command=self.show_sales_summary, width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("phoneshop.btn.inventory_report"), command=self.show_inventory_report, width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("phoneshop.btn.top_products"), command=self.show_top_products, width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("phoneshop.btn.generate_admin_report"), command=self.generate_admin_report, width=25).pack(pady=5)
        ttk.Button(left_frame, text=_t("phoneshop.btn.email_admin_report"), command=self.email_admin_report, width=25).pack(pady=5)

        # Right - Report display
        right_frame = ttk.LabelFrame(tab, text=_t("phoneshop.labels.report_output"), padding="10")
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
                p['product_id'], p['sku'], p['name'], p.get('brand', ''),
                p['category'], f"£{p['price']:.2f}", p['stock_quantity']
            ))

    def _load_orders(self):
        """Load orders into the treeview"""
        for item in self.orders_tree.get_children():
            self.orders_tree.delete(item)

        status = self.order_status_filter.get()
        if status == 'All':
            # Get all orders
            orders = []
            for s in ORDER_STATUSES:
                orders.extend(OrderManager.get_orders_by_status(s))
        else:
            orders = OrderManager.get_orders_by_status(status)

        for o in orders:
            self.orders_tree.insert('', tk.END, values=(
                o['order_id'], o['order_number'], o['customer_name'],
                f"£{o['total_amount']:.2f}", o['status'], o['payment_status'],
                o['created_at'][:16] if o['created_at'] else ''
            ))

    def _load_low_stock(self):
        """Load low stock products"""
        for item in self.low_stock_tree.get_children():
            self.low_stock_tree.delete(item)

        products = ProductManager.get_low_stock_products()
        for p in products:
            self.low_stock_tree.insert('', tk.END, values=(
                p['product_id'], p['name'], p['stock_quantity'], p['min_stock_level']
            ))

    def _on_product_select(self, event):
        """Handle product selection"""
        selected = self.products_tree.selection()
        if selected:
            values = self.products_tree.item(selected[0])['values']
            self.selected_product_id = values[0]
            self.selected_product_var.set(f"{values[2]} - £{values[5]}")

    def search_products(self):
        """Search products"""
        query = self.search_entry.get().strip()
        if not query:
            self._load_products()
            return

        for item in self.products_tree.get_children():
            self.products_tree.delete(item)

        products = ProductManager.search_products(query)
        for p in products:
            self.products_tree.insert('', tk.END, values=(
                p['product_id'], p['sku'], p['name'], p.get('brand', ''),
                p['category'], f"£{p['price']:.2f}", p['stock_quantity']
            ))

    def add_to_cart(self):
        """Add selected product to cart"""
        if not self.selected_product_id:
            messagebox.showwarning(_t("common.warning"), _t("phoneshop.errors.no_product_selected"))
            return

        product = ProductManager.get_product(self.selected_product_id)
        if not product:
            return

        quantity = int(self.quantity_spinbox.get())
        if quantity > product['stock_quantity']:
            messagebox.showerror(_t("common.error"), _t("phoneshop.errors.insufficient_stock"))
            return

        # Check if already in cart
        for item in self.cart:
            if item['product_id'] == self.selected_product_id:
                item['quantity'] += quantity
                self._update_cart_display()
                messagebox.showinfo(_t("common.success"), _t("phoneshop.messages.cart_updated"))
                return

        self.cart.append({
            'product_id': self.selected_product_id,
            'product_name': product['name'],
            'unit_price': product['price'],
            'quantity': quantity
        })
        self._update_cart_display()
        messagebox.showinfo(_t("common.success"), _t("phoneshop.messages.added_to_cart"))

    def open_cart_window(self):
        """Open shopping cart in a new window"""
        cart_dialog = tk.Toplevel(self.root)
        cart_dialog.title("Shopping Cart")
        cart_dialog.geometry("1000x750")
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
        ttk.Label(main_frame, text=_t("phoneshop.labels.shopping_cart"), font=('Helvetica', 14, 'bold')).pack(pady=(0, 10))

        # Cart items display
        cart_frame = ttk.LabelFrame(main_frame, text=_t("phoneshop.labels.cart_items"), padding="10")
        cart_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ('product_id', 'name', 'price', 'quantity', 'subtotal')
        cart_tree = ttk.Treeview(cart_frame, columns=columns, show='headings', height=10)

        cart_tree.heading('product_id', text=_t('phoneshop.columns.id'))
        cart_tree.heading('name', text=_t('phoneshop.columns.product'))
        cart_tree.heading('price', text=_t('phoneshop.columns.price'))
        cart_tree.heading('quantity', text=_t('phoneshop.columns.quantity'))
        cart_tree.heading('subtotal', text=_t('phoneshop.columns.subtotal'))

        cart_tree.column('product_id', width=60)
        cart_tree.column('name', width=350)
        cart_tree.column('price', width=120)
        cart_tree.column('quantity', width=100)
        cart_tree.column('subtotal', width=120)

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
                item['product_id'], item['product_name'],
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
                messagebox.showwarning(_t("phoneshop.msg_titles.warning"), "Please select an item to remove")
                return
            product_id = cart_tree.item(selected[0])['values'][0]
            self.cart = [item for item in self.cart if item['product_id'] != product_id]
            cart_dialog.destroy()
            messagebox.showinfo(_t("phoneshop.msg_titles.success"), "Item removed from cart")

        def clear_all():
            if messagebox.askyesno(_t("phoneshop.msg_titles.confirm"), "Clear all items from cart?"):
                self.cart = []
                cart_dialog.destroy()
                messagebox.showinfo(_t("phoneshop.msg_titles.success"), "Cart cleared")

        ttk.Button(action_frame, text=_t("phoneshop.btn.remove_selected"), command=remove_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t("phoneshop.btn.clear_cart"), command=clear_all).pack(side=tk.LEFT, padx=5)

        # Checkout section
        checkout_frame = ttk.LabelFrame(main_frame, text=_t("phoneshop.labels.checkout"), padding="10")
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

        ttk.Label(left_checkout, text=_t("phoneshop.labels.shipping_address"), font=('Helvetica', 10, 'bold')).pack(anchor=tk.W, pady=(10, 2))
        shipping_entry = ttk.Entry(left_checkout, width=40)
        shipping_entry.pack(fill=tk.X, pady=(0, 5))

        # Right side - Totals
        ttk.Label(right_checkout, text=_t("phoneshop.labels.order_summary"), font=('Helvetica', 11, 'bold')).pack(anchor=tk.W, pady=(0, 5))

        totals_frame = ttk.Frame(right_checkout)
        totals_frame.pack(fill=tk.X)

        ttk.Label(totals_frame, text=_t("phoneshop.labels.subtotal"), font=('Helvetica', 10)).grid(row=0, column=0, sticky=tk.W, pady=3, padx=(0, 10))
        ttk.Label(totals_frame, text=f"£{subtotal:.2f}", font=('Helvetica', 10)).grid(row=0, column=1, sticky=tk.E, pady=3)

        ttk.Label(totals_frame, text=_t("phoneshop.labels.tax"), font=('Helvetica', 10)).grid(row=1, column=0, sticky=tk.W, pady=3, padx=(0, 10))
        ttk.Label(totals_frame, text=f"£{tax:.2f}", font=('Helvetica', 10)).grid(row=1, column=1, sticky=tk.E, pady=3)

        ttk.Separator(totals_frame, orient=tk.HORIZONTAL).grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=5)

        ttk.Label(totals_frame, text=_t("phoneshop.labels.total"), font=('Helvetica', 12, 'bold')).grid(row=3, column=0, sticky=tk.W, pady=3, padx=(0, 10))
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
                messagebox.showwarning(_t("phoneshop.msg_titles.warning"), "Cart is empty")
                return
            cart_dialog.destroy()
            self.show_payment_window()

        ttk.Button(btn_frame, text=_t("phoneshop.btn.proceed_to_payment"), command=proceed_to_payment, width=25).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t("phoneshop.btn.continue_shopping"), command=cart_dialog.destroy, width=25).pack(side=tk.LEFT, padx=10)

        # Pack the canvas and scrollbar
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _update_cart_display(self):
        """Update the cart display - legacy method kept for compatibility"""
        # This method is kept for any legacy code that might call it
        pass

    # Removed remove_from_cart and clear_cart - now handled in cart window dialog

    def show_payment_window(self):
        """Show payment window with payment options"""
        if not self.cart:
            messagebox.showwarning(_t("common.warning"), _t("phoneshop.errors.empty_cart"))
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
        ttk.Label(dialog, text=_t("phoneshop.labels.order_summary"), font=('Helvetica', 14, 'bold')).pack(pady=10)

        info_frame = ttk.Frame(dialog, padding="10")
        info_frame.pack(fill=tk.X, padx=20)

        ttk.Label(info_frame, text=f"Customer: {self.checkout_customer_name}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Items in cart: {len(self.cart)}").pack(anchor=tk.W)

        # Shipping address
        ttk.Label(info_frame, text=_t("phoneshop.labels.shipping_address")).pack(anchor=tk.W, pady=(10, 0))
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

        ttk.Label(payment_frame, text=_t("phoneshop.labels.payment_method")).pack(anchor=tk.W)

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
                    description="Phone Shop purchase",
                    transaction_source='PhoneShop',
                    transaction_ref=f"PHO-{datetime.now().strftime('%Y%m%d%H%M%S')}",
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
                TransactionManager.record_payment(
                    order_id=order_id,
                    customer_id=customer_id,
                    amount=total,
                    payment_method=actual_method,
                    processed_by=self.current_user.get('username')
                )

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
                messagebox.showerror(_t("common.error"), _t("phoneshop.errors.order_failed"))

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text=_t("phoneshop.btn.confirm_pay"), command=confirm_purchase).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t("phoneshop.btn.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def complete_purchase(self):
        """Complete the purchase (legacy - redirects to show_payment_window)"""
        self.show_payment_window()

    def view_order_details(self):
        """View order details"""
        selected = self.orders_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("phoneshop.errors.no_order_selected"))
            return

        order_id = self.orders_tree.item(selected[0])['values'][0]
        order = OrderManager.get_order(order_id)
        if not order:
            return

        details = f"""
Order: {order['order_number']}
Customer: {order['customer_name']}
Email: {order.get('customer_email', 'N/A')}
Phone: {order.get('customer_phone', 'N/A')}
Address: {order.get('shipping_address', 'N/A')}

Items:
"""
        for item in order.get('items', []):
            details += f"  - {item['product_name']} x{item['quantity']} = £{item['subtotal']:.2f}\n"

        details += f"""
Subtotal: £{order['subtotal']:.2f}
Tax: £{order['tax_amount']:.2f}
Total: £{order['total_amount']:.2f}

Status: {order['status']}
Payment: {order['payment_status']}
"""
        messagebox.showinfo(_t("phoneshop.labels.order_details"), details)

    # Removed update_order_status - status is now automatically updated to delivered/refunded

    def cancel_order(self):
        """Cancel an order"""
        selected = self.orders_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("phoneshop.errors.no_order_selected"))
            return

        order_id = self.orders_tree.item(selected[0])['values'][0]

        if messagebox.askyesno(_t("common.confirm"), _t("phoneshop.confirm.cancel_order")):
            if OrderManager.cancel_order(order_id, "Cancelled by staff"):
                messagebox.showinfo(_t("common.success"), _t("phoneshop.messages.order_cancelled"))
                self._load_orders()
                self._load_products()

    def process_refund(self):
        """Process a refund with method selection"""
        selected = self.orders_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("phoneshop.errors.no_order_selected"))
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
                    SELECT transaction_id FROM phoneshop_transactions
                    WHERE order_id = ? AND transaction_type = 'payment'
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
            if TransactionManager.process_refund(order_id, amount, f"Customer refund via {refund_method}",
                                                processed_by=self.current_user.get('username')):
                # Generate refund reference
                refund_ref = f"ORDER-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

                # Update transaction status if found
                if transaction_id:
                    with get_db_connection() as conn:
                        conn.execute('''
                            UPDATE phoneshop_transactions
                            SET status = 'refunded'
                            WHERE transaction_id = ?
                        ''', (transaction_id,))
                        conn.commit()

                # Automatically mark order as refunded
                OrderManager.update_order_status(order_id, 'refunded')

                # If student account refund, add to their account
                if refund_method == 'Student Account':
                    success = self.add_phoneshop_refund_to_student_account(customer_id, amount, refund_ref)
                    if not success:
                        messagebox.showwarning(_t("phoneshop.msg_titles.partial_success"),
                                             "Refund recorded but failed to credit student account. Please credit manually.")

                # Send refund receipt email
                if transaction_id:
                    self.send_phoneshop_refund_receipt(transaction_id, customer_id, amount, refund_method, refund_ref)

                # Notify finance GUI
                if transaction_id:
                    self.notify_phoneshop_finance_gui(transaction_id, amount, refund_method, refund_ref, customer_id)

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
                    balance_frame = ttk.LabelFrame(dialog, text=_t("phoneshop.btn.student_finance"), padding=10)
                    balance_frame.pack(pady=10, padx=20, fill=tk.X)

                    ttk.Label(balance_frame, text=f"Current Balance: £{current_balance:.2f}").pack(anchor='w')
                    ttk.Label(balance_frame, text=f"After Refund: £{new_balance:.2f}",
                            font=('Arial', 10, 'bold')).pack(anchor='w')
            except Exception as e:
                logger.error(f"Error getting balance: {e}")

        ttk.Label(dialog, text=_t("phoneshop.labels.select_refund_method"), font=('Arial', 10)).pack(pady=10)

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
                messagebox.showerror(_t("phoneshop.msg_titles.error"), "No customer ID associated with this order.")
                return
            result['method'] = 'Student Account'
            dialog.destroy()

        ttk.Button(button_frame, text=_t("phoneshop.btn.cash_refund"), command=select_cash, width=20).pack(pady=5)
        ttk.Button(button_frame, text=_t("phoneshop.btn.card_refund"), command=select_card, width=20).pack(pady=5)

        if customer_id and customer_id != 'GUEST':
            ttk.Button(button_frame, text=_t("phoneshop.btn.student_finance"), command=select_student_account, width=20).pack(pady=5)

        ttk.Button(button_frame, text=_t("phoneshop.btn.cancel"), command=dialog.destroy, width=20).pack(pady=10)

        dialog.wait_window()
        return result['method']

    def add_product(self):
        """Add a new product"""
        try:
            sku = self.product_entries['sku'].get().strip()
            name = self.product_entries['name'].get().strip()
            price = self.product_entries['price'].get().strip()
            category = self.new_product_category.get()

            if not all([sku, name, price, category]):
                messagebox.showerror(_t("common.error"), _t("phoneshop.errors.fill_required"))
                return

            product_id = ProductManager.add_product(
                sku=sku,
                name=name,
                category=category,
                price=float(price),
                brand=self.product_entries['brand'].get().strip() or None,
                model=self.product_entries['model'].get().strip() or None,
                cost_price=float(self.product_entries['cost_price'].get() or 0),
                stock_quantity=int(self.product_entries['stock_quantity'].get() or 0),
                warranty_months=int(self.product_entries['warranty_months'].get() or 12),
                description=self.product_description.get(1.0, tk.END).strip()
            )

            if product_id:
                messagebox.showinfo(_t("common.success"), _t("phoneshop.messages.product_added"))
                self._clear_product_form()
                self._load_products()
        except ValueError:
            messagebox.showerror(_t("common.error"), _t("phoneshop.errors.invalid_input"))

    def update_product(self):
        """Update selected product"""
        selected = self.products_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("phoneshop.errors.no_product_selected"))
            return

        product_id = self.products_tree.item(selected[0])['values'][0]

        updates = {}
        if self.product_entries['price'].get():
            updates['price'] = float(self.product_entries['price'].get())
        if self.product_entries['stock_quantity'].get():
            updates['stock_quantity'] = int(self.product_entries['stock_quantity'].get())

        if ProductManager.update_product(product_id, **updates):
            messagebox.showinfo(_t("common.success"), _t("phoneshop.messages.product_updated"))
            self._load_products()

    def _clear_product_form(self):
        """Clear product form"""
        for entry in self.product_entries.values():
            entry.delete(0, tk.END)
        self.new_product_category.set('')
        self.product_description.delete(1.0, tk.END)

    def record_revenue_to_finance(self, order_id: int, amount: float, payment_method: str):
        """Record phone shop revenue to the central finance system"""
        try:
            order = OrderManager.get_order(order_id)
            if not order:
                return

            payment_id = record_payment_to_finance(
                student_id=order.get('customer_id', 'EXTERNAL'),
                amount=amount,
                payment_method=payment_method,
                transaction_source='PhoneShop',
                transaction_ref=order.get('order_number', str(order_id)),
                notes="Phone shop purchase",
                created_by=self.current_user.get('username')
            )
            if payment_id:
                logger.info(f"Revenue recorded: £{amount:.2f} for order {order.get('order_number')}")
            return payment_id
        except Exception as e:
            logger.error(f"Failed to record revenue: {e}")
            return None

    def send_receipt_email(self, order_id: int):
        """Send receipt email to customer"""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_email

            order = OrderManager.get_order(order_id)
            if not order:
                return

            # Check for valid email (must contain @ symbol)
            customer_email = order.get('customer_email')
            if not customer_email or '@' not in customer_email:
                logger.info(f"No valid email for order {order.get('order_number', order_id)} - skipping receipt")
                return

            subject = _t("phoneshop.email.receipt_subject").format(order_num=order['order_number'])
            body = _t("phoneshop.email.receipt_body").format(
                customer=order['customer_name'],
                order_num=order['order_number'],
                total=order['total_amount']
            )

            send_email(customer_email, subject, body)
            logger.info(f"Receipt sent for order {order['order_number']}")
        except Exception as e:
            logger.error(f"Failed to send receipt: {e}")

    def show_sales_summary(self):
        """Show sales summary report"""
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
"""
        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)

    def show_top_products(self):
        """Show top selling products"""
        products = ReportManager.get_top_selling_products(10)
        report = "TOP SELLING PRODUCTS\n" + "=" * 30 + "\n\n"

        for i, p in enumerate(products, 1):
            report += f"{i}. {p['name']}\n"
            report += f"   Sold: {p.get('total_sold', 0)} | Revenue: £{p.get('total_revenue', 0):.2f}\n\n"

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
                send_email(result[0], _t("phoneshop.email.admin_report_subject"), report)
                messagebox.showinfo(_t("common.success"), _t("phoneshop.messages.report_emailed"))
            else:
                messagebox.showwarning(_t("common.warning"), _t("phoneshop.errors.no_admin_email"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def create_refunds_tab(self):
        """Create the refunds management tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Refunds")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(header_frame, text=_t("phoneshop.labels.transaction_refunds"),
                 font=('Helvetica', 14, 'bold')).pack(side=tk.LEFT)

        # Search frame
        search_frame = ttk.LabelFrame(tab, text=_t("phoneshop.labels.search_transactions"), padding="10")
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text=_t("phoneshop.labels.search_by")).pack(side=tk.LEFT, padx=5)
        self.refunds_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.refunds_search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(search_frame, text=_t("phoneshop.btn.search"), command=self.refresh_refunds_list).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_frame, text=_t("phoneshop.btn.show_all"), command=lambda: [self.refunds_search_var.set(''), self.refresh_refunds_list()]).pack(side=tk.LEFT, padx=2)

        # Transactions table
        trans_frame = ttk.Frame(tab)
        trans_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ('transaction_id', 'order_id', 'date', 'customer', 'amount', 'payment_method', 'status')
        self.refunds_tree = ttk.Treeview(trans_frame, columns=columns, show='headings', height=15)

        self.refunds_tree.heading('transaction_id', text=_t('phoneshop.columns.transaction_id'))
        self.refunds_tree.heading('order_id', text=_t('phoneshop.columns.order_id'))
        self.refunds_tree.heading('date', text=_t('phoneshop.columns.date'))
        self.refunds_tree.heading('customer', text=_t('phoneshop.columns.customer'))
        self.refunds_tree.heading('amount', text=_t('phoneshop.columns.amount'))
        self.refunds_tree.heading('payment_method', text=_t('phoneshop.columns.payment_method'))
        self.refunds_tree.heading('status', text=_t('phoneshop.columns.status'))

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

        ttk.Button(button_frame, text=_t("phoneshop.btn.process_refund"), command=self.process_phoneshop_refund).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("phoneshop.btn.view_details"), command=self.view_refund_transaction_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("phoneshop.btn.export_csv"), command=self.export_refunds_to_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("phoneshop.btn.refresh"), command=self.refresh_refunds_list).pack(side=tk.LEFT, padx=5)

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
                        SELECT transaction_id, order_id, created_at, customer_id,
                               amount, payment_method, status
                        FROM phoneshop_transactions
                        WHERE transaction_id LIKE ? OR order_id LIKE ? OR customer_id LIKE ?
                        ORDER BY created_at DESC
                        LIMIT 500
                    '''
                    search_pattern = f'%{search_term}%'
                    cursor = conn.execute(query, (search_pattern, search_pattern, search_pattern))
                else:
                    query = '''
                        SELECT transaction_id, order_id, created_at, customer_id,
                               amount, payment_method, status
                        FROM phoneshop_transactions
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
            messagebox.showerror(_t("phoneshop.msg_titles.database_error"), f"Error loading transactions: {e}")
            logger.error(f"Error loading transactions: {e}")

    def process_phoneshop_refund(self):
        """Process a refund for selected phone shop transaction"""
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("phoneshop.msg_titles.no_selection"), "Please select a transaction to refund.")
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']

        if len(values) < 7:
            messagebox.showerror(_t("phoneshop.msg_titles.error"), "Invalid transaction data.")
            return

        transaction_id = values[0]
        order_id = values[1]
        amount_str = values[4].replace('£', '').strip()
        try:
            amount = float(amount_str)
        except ValueError:
            messagebox.showerror(_t("phoneshop.msg_titles.error"), "Invalid amount format.")
            return

        status = values[6]

        # Check if already refunded
        if status == 'REFUNDED':
            messagebox.showinfo(_t("phoneshop.msg_titles.already_refunded"), _t("phoneshop.messages.already_refunded_msg"))
            return

        # Confirm refund
        if not messagebox.askyesno(_t("phoneshop.msg_titles.confirm_refund"), f"Process refund of £{amount:.2f} for transaction {transaction_id}?"):
            return

        # Get transaction details
        try:
            with get_db_connection() as conn:
                cursor = conn.execute('''
                    SELECT customer_id, payment_method
                    FROM phoneshop_transactions
                    WHERE transaction_id = ?
                ''', (transaction_id,))

                trans_data = cursor.fetchone()

                if not trans_data:
                    messagebox.showerror(_t("phoneshop.msg_titles.error"), "Transaction not found in database.")
                    return

                customer_id = trans_data[0]
                payment_method = trans_data[1]

        except Exception as e:
            messagebox.showerror(_t("phoneshop.msg_titles.database_error"), f"Error fetching transaction details: {e}")
            return

        # Show refund method dialog
        refund_method = self.show_phoneshop_refund_method_dialog(amount, transaction_id, customer_id)

        if not refund_method:
            return

        # Process refund
        try:
            with get_db_connection() as conn:
                # Update transaction status to refunded
                conn.execute('''
                    UPDATE phoneshop_transactions
                    SET status = 'refunded'
                    WHERE transaction_id = ?
                ''', (transaction_id,))

                # Generate refund reference
                refund_ref = f"PHONE-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

                # Create refunds table if it doesn't exist
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS phoneshop_refunds (
                        refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        transaction_id INTEGER NOT NULL,
                        order_id INTEGER,
                        refund_date TEXT NOT NULL,
                        refund_amount REAL NOT NULL,
                        refund_method TEXT NOT NULL,
                        refund_reference TEXT UNIQUE,
                        customer_id TEXT,
                        processed_by TEXT,
                        notes TEXT,
                        FOREIGN KEY (transaction_id) REFERENCES phoneshop_transactions (transaction_id)
                    )
                ''')

                # Insert refund record
                processed_by = self.current_user.get('username', 'System') if self.current_user else 'System'
                conn.execute('''
                    INSERT INTO phoneshop_refunds
                    (transaction_id, order_id, refund_date, refund_amount, refund_method, refund_reference, customer_id, processed_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (transaction_id, order_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), amount, refund_method,
                      refund_ref, customer_id, processed_by))

                conn.commit()

            # Automatically mark order as refunded
            if order_id:
                OrderManager.update_order_status(order_id, 'refunded')

            # If student account refund, add to their account
            if refund_method == 'Student Account':
                success = self.add_phoneshop_refund_to_student_account(customer_id, amount, refund_ref)
                if not success:
                    messagebox.showwarning(_t("phoneshop.msg_titles.partial_success"),
                                         "Refund recorded but failed to credit student account. Please credit manually.")

            # Send refund receipt email
            self.send_phoneshop_refund_receipt(transaction_id, customer_id, amount, refund_method, refund_ref)

            # Notify finance GUI
            self.notify_phoneshop_finance_gui(transaction_id, amount, refund_method, refund_ref, customer_id)

            messagebox.showinfo(_t("phoneshop.msg_titles.refund_processed"),
                              f"Refund of £{amount:.2f} processed successfully.\nRefund Reference: {refund_ref}\nOrder status updated to Refunded.")

            # Refresh the list
            self.refresh_refunds_list()

        except Exception as e:
            messagebox.showerror(_t("phoneshop.msg_titles.database_error"), f"Error processing refund: {e}")
            logger.error(f"Error processing refund: {e}")

    def show_phoneshop_refund_method_dialog(self, amount, transaction_id, customer_id):
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
                    balance_frame = ttk.LabelFrame(dialog, text=_t("phoneshop.btn.student_finance"), padding=10)
                    balance_frame.pack(pady=10, padx=20, fill=tk.X)

                    ttk.Label(balance_frame, text=f"Current Balance: £{current_balance:.2f}").pack(anchor='w')
                    ttk.Label(balance_frame, text=f"After Refund: £{new_balance:.2f}",
                            font=('Arial', 10, 'bold')).pack(anchor='w')
            except Exception as e:
                logger.error(f"Error getting balance: {e}")

        ttk.Label(dialog, text=_t("phoneshop.labels.select_refund_method"), font=('Arial', 10)).pack(pady=10)

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
                messagebox.showerror(_t("phoneshop.msg_titles.error"), "No customer ID associated with this transaction.")
                return
            result['method'] = 'Student Account'
            dialog.destroy()

        ttk.Button(button_frame, text=_t("phoneshop.btn.cash_refund"), command=select_cash, width=20).pack(pady=5)
        ttk.Button(button_frame, text=_t("phoneshop.btn.card_refund"), command=select_card, width=20).pack(pady=5)

        if customer_id:
            ttk.Button(button_frame, text=_t("phoneshop.btn.student_finance"), command=select_student_account, width=20).pack(pady=5)

        ttk.Button(button_frame, text=_t("phoneshop.btn.cancel"), command=dialog.destroy, width=20).pack(pady=10)

        dialog.wait_window()
        return result['method']

    def add_phoneshop_refund_to_student_account(self, customer_id, amount, refund_ref):
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
                    INSERT INTO student_finance_transactions
                    (account_id, student_id, transaction_type, amount, balance_before,
                     balance_after, description, reference_id, processed_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (account_id, customer_id, 'credit', amount, balance_before, balance_after,
                      'Phone Shop Purchase Refund', refund_ref, processed_by))

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error adding refund to student account: {e}")
            return False

    def send_phoneshop_refund_receipt(self, transaction_id, customer_id, amount, method, refund_ref):
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
            subject, body = render_template('commerce/phoneshop/refund_receipt', {
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

    def notify_phoneshop_finance_gui(self, transaction_id, amount, method, refund_ref, customer_id):
        """Notify finance GUI about the refund"""
        try:
            with get_db_connection() as conn:
                # Insert into finance_refunds table (table already exists)
                processed_by = self.current_user.get('username', 'System') if self.current_user else 'System'
                conn.execute('''
                    INSERT INTO finance_refunds
                    (transaction_id, refund_reference, department, amount, refund_method,
                     refund_date, student_id, processed_by, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (str(transaction_id), refund_ref, 'Phone Shop', amount, method,
                      datetime.now().strftime('%Y-%m-%d %H:%M:%S'), customer_id, processed_by,
                      'Phone Shop purchase refund'))

                conn.commit()

        except Exception as e:
            logger.error(f"Error notifying finance GUI: {e}")

    def view_refund_transaction_details(self):
        """View detailed information for selected transaction"""
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("phoneshop.msg_titles.no_selection"), "Please select a transaction to view details.")
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']

        if len(values) < 7:
            messagebox.showerror(_t("phoneshop.msg_titles.error"), "Invalid transaction data.")
            return

        transaction_id = values[0]
        order_id = values[1]

        try:
            with get_db_connection() as conn:
                # Get transaction details
                cursor = conn.execute('''
                    SELECT t.*, o.shipping_address, o.status as order_status
                    FROM phoneshop_transactions t
                    LEFT JOIN phoneshop_orders o ON t.order_id = o.order_id
                    WHERE t.transaction_id = ?
                ''', (transaction_id,))

                trans = cursor.fetchone()

                if not trans:
                    messagebox.showerror(_t("phoneshop.msg_titles.error"), "Transaction not found.")
                    return

                # Get order items
                cursor = conn.execute('''
                    SELECT oi.product_id, p.name, p.brand, p.model, oi.quantity, oi.unit_price, oi.subtotal
                    FROM phoneshop_order_items oi
                    LEFT JOIN phoneshop_products p ON oi.product_id = p.product_id
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
                    product_id, name, brand, model, quantity, unit_price, subtotal = item
                    items_text += f"\n{name} ({brand} {model})\n"
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

            ttk.Button(main_frame, text=_t("phoneshop.btn.close"), command=details_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t("phoneshop.msg_titles.database_error"), f"Error loading transaction details: {e}")
            logger.error(f"Error loading transaction details: {e}")

    def export_refunds_to_csv(self):
        """Export refunds list to CSV file"""
        try:
            from tkinter import filedialog
            import csv

            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"phoneshop_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
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

            messagebox.showinfo(_t("phoneshop.msg_titles.export_successful"), f"Data exported to:\n{filename}")

        except Exception as e:
            messagebox.showerror(_t("phoneshop.msg_titles.export_error"), f"Error exporting data: {e}")
            logger.error(f"Error exporting data: {e}")


def launch_phoneshop_gui(parent=None, auth=None):
    """Launch the Phone Shop GUI"""
    if parent:
        window = tk.Toplevel(parent)
    else:
        window = tk.Tk()

    app = PhoneShopGUI(window, auth)

    if not parent:
        window.mainloop()

    return app
