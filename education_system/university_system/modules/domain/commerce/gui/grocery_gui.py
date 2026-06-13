"""
Grocery Shop GUI for University Management System
Campus convenience store interface
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH, get_connection

# Import i18n for language support
from education_system.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

from education_system.university_system.modules.domain.commerce.services.grocery.grocery_service import (
    init_grocery_db,
    get_categories,
    get_products,
    add_to_cart,
    update_cart_quantity,
    view_cart,
    clear_cart,
    checkout,
    get_purchase_history,
    get_transaction_details,
    get_low_stock_products,
    restock_product,
)

# Email integration
from education_system.university_system.infrastructure.email.email_service import send_email

# Finance integration for account details and revenue recording
from education_system.university_system.modules.shared.utils.finance_integration import (
    get_student_info,
    get_student_finance_account_balance,
    process_student_finance_account_payment,
    record_revenue_to_finance,
)

# For database path
from education_system.university_system.core import paths

class GroceryGUI:
    """Grocery shop GUI"""

    def __init__(self, root, auth=None, return_to_main=None):
        # Initialize i18n for language support
        init_i18n()

        self.root = root
        self.return_to_main = return_to_main

        self.auth = auth if auth is not None else get_auth()
        if self.auth is None:
            self.auth = get_global_auth()

        if self.auth is None:
            messagebox.showerror(
                _t("common.error"),
                _t("grocery.error.auth_not_available")
            )
            return

        if not init_grocery_db():
            messagebox.showerror(_t("common.error"), _t("grocery.error.db_init_failed"))
            return

        self.current_user = None
        self.setup_current_user()

    def setup_current_user(self):
        """Setup current user from auth"""
        if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
            self.current_user = self.auth.current_user
        else:
            self.current_user = {'id': 0, 'username': 'Guest', 'role': 'guest'}

    def get_user_identifier(self):
        """
        Get the correct identifier for finance lookups.
        Uses student_id if available, otherwise username.
        """
        # Try student_id first (for student users)
        student_id = self.current_user.get('student_id')
        if student_id:
            return str(student_id)

        # Fall back to username (for admin/staff users)
        username = self.current_user.get('username')
        if username:
            return username

        # Last resort: use numeric id
        return str(self.current_user.get('id', 0))

    def get_user_finance_balance(self, user_id):
        """Get user's finance account balance for display."""
        balance = get_student_finance_account_balance(user_id)
        return balance if balance is not None else 0.0

    def send_grocery_receipt_email(self, transaction, items):
        """
        Send grocery purchase receipt email to the user.

        Args:
            transaction: Dict with transaction info
            items: List of purchased items
        """
        try:
            # Get user identifier
            user_identifier = self.get_user_identifier()

            # Get student/user info
            student_info = get_student_info(user_identifier)
            if not student_info or not student_info.get('email'):
                print(f"Cannot send receipt: No email found for user {user_identifier}")
                return False

            student_email = student_info['email']
            student_name = student_info.get('full_name', 'Valued Customer')

            # Format items list
            items_text = ""
            for item in items:
                items_text += f"  - {item['product_name']} x{item['quantity']} - £{item['subtotal']:.2f}\n"

            # Prepare template variables
            from education_system.university_system.infrastructure.email.template_utils import render_template

            template_vars = {
                'student_name': student_name,
                'receipt_number': transaction['receipt_number'],
                'transaction_date': transaction['transaction_date'],
                'items_text': items_text,
                'total_amount': f"{transaction['total_amount']:.2f}",
                'payment_method': transaction['payment_method'].replace('_', ' ').title()
            }

            subject, body = render_template('commerce/grocery_purchase_receipt', template_vars)
            if not subject or not body:
                print("Failed to render email template")
                return False

            result = send_email(student_email, subject, body)
            if result:
                print(f"Receipt email sent to {student_email}")
                return True
            else:
                print(f"Failed to send receipt email to {student_email}")
                return False

        except Exception as e:
            print(f"Error sending receipt email: {e}")
            return False

    def open_grocery_gui(self):
        """Open the grocery shop window"""
        self.grocery_window = tk.Toplevel(self.root)
        self.grocery_window.title(_t("grocery.title"))
        self.grocery_window.geometry("1400x900+%d+%d" % ((self.grocery_window.winfo_screenwidth() - 1400) // 2, (self.grocery_window.winfo_screenheight() - 900) // 2))
        self.grocery_window.minsize(1200, 800)
        self.grocery_window.transient(self.root)

        # Main container with PanedWindow
        self.paned = ttk.PanedWindow(self.grocery_window, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left panel - Categories and Products
        left_frame = ttk.Frame(self.paned)
        self.paned.add(left_frame, weight=3)

        # Right panel - Cart
        right_frame = ttk.Frame(self.paned)
        self.paned.add(right_frame, weight=1)

        self.setup_products_panel(left_frame)
        self.setup_cart_panel(right_frame)

        self.refresh_products()
        self.refresh_cart()

    def setup_products_panel(self, parent):
        """Setup the products browsing panel"""
        # Header
        header = ttk.Frame(parent)
        header.pack(fill=tk.X, pady=5)

        ttk.Label(header, text=_t("grocery.header_title"), font=('Arial', 16, 'bold')).pack(side=tk.LEFT)

        ttk.Button(header, text=_t("grocery.btn.purchase_history"), command=self.show_purchase_history).pack(side=tk.RIGHT, padx=5)

        # Add Management button for staff/admin users
        if self.current_user and self.current_user.get('role') in ['admin', 'staff']:
            ttk.Button(header, text="Management", command=self.open_management_interface).pack(side=tk.RIGHT, padx=5)

        # Search bar
        search_frame = ttk.Frame(parent)
        search_frame.pack(fill=tk.X, pady=5)

        ttk.Label(search_frame, text=_t("common.search") + ":").pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind('<Return>', lambda e: self.search_products())

        ttk.Button(search_frame, text=_t("common.search"), command=self.search_products).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text=_t("common.clear"), command=self.clear_search).pack(side=tk.LEFT, padx=5)

        # Category filter
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill=tk.X, pady=5)

        ttk.Label(filter_frame, text=_t("grocery.category") + ":").pack(side=tk.LEFT, padx=5)
        self.category_combo = ttk.Combobox(filter_frame, state='readonly', width=25)
        self.category_combo.pack(side=tk.LEFT, padx=5)
        self.category_combo.bind('<<ComboboxSelected>>', lambda e: self.filter_by_category())

        self.load_categories()

        # Products treeview
        products_frame = ttk.Frame(parent)
        products_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ('name', 'brand', 'category', 'price', 'stock', 'discount')
        self.product_tree = ttk.Treeview(products_frame, columns=columns, show='headings', height=20)

        self.product_tree.heading('name', text=_t("grocery.col.product"))
        self.product_tree.heading('brand', text=_t("grocery.col.brand"))
        self.product_tree.heading('category', text=_t("grocery.col.category"))
        self.product_tree.heading('price', text=_t("grocery.col.price"))
        self.product_tree.heading('stock', text=_t("grocery.col.stock"))
        self.product_tree.heading('discount', text=_t("grocery.col.discount"))

        self.product_tree.column('name', width=200)
        self.product_tree.column('brand', width=100)
        self.product_tree.column('category', width=120)
        self.product_tree.column('price', width=80)
        self.product_tree.column('stock', width=60)
        self.product_tree.column('discount', width=70)

        scrollbar = ttk.Scrollbar(products_frame, orient=tk.VERTICAL, command=self.product_tree.yview)
        self.product_tree.configure(yscrollcommand=scrollbar.set)

        self.product_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.product_tree.bind('<Double-1>', self.add_selected_to_cart)

        # Add to cart controls
        add_frame = ttk.Frame(parent)
        add_frame.pack(fill=tk.X, pady=5)

        ttk.Label(add_frame, text=_t("grocery.quantity") + ":").pack(side=tk.LEFT, padx=5)
        self.qty_spinbox = ttk.Spinbox(add_frame, from_=1, to=99, width=5)
        self.qty_spinbox.set(1)
        self.qty_spinbox.pack(side=tk.LEFT, padx=5)

        ttk.Button(add_frame, text=_t("grocery.btn.add_to_cart"), command=self.add_selected_to_cart).pack(side=tk.LEFT, padx=10)
        ttk.Button(add_frame, text=_t("common.close"), command=self.grocery_window.destroy).pack(side=tk.RIGHT, padx=5)

    def setup_cart_panel(self, parent):
        """Setup the shopping cart panel"""
        ttk.Label(parent, text=_t("grocery.shopping_cart"), font=('Arial', 14, 'bold')).pack(pady=10)

        # Cart items
        cart_frame = ttk.Frame(parent)
        cart_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('product', 'qty', 'price', 'total')
        self.cart_tree = ttk.Treeview(cart_frame, columns=columns, show='headings', height=15)

        self.cart_tree.heading('product', text=_t("grocery.col.item"))
        self.cart_tree.heading('qty', text=_t("grocery.col.qty"))
        self.cart_tree.heading('price', text=_t("grocery.col.price"))
        self.cart_tree.heading('total', text=_t("grocery.col.total"))

        self.cart_tree.column('product', width=120)
        self.cart_tree.column('qty', width=40)
        self.cart_tree.column('price', width=60)
        self.cart_tree.column('total', width=60)

        scrollbar = ttk.Scrollbar(cart_frame, orient=tk.VERTICAL, command=self.cart_tree.yview)
        self.cart_tree.configure(yscrollcommand=scrollbar.set)

        self.cart_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Cart totals
        totals_frame = ttk.Frame(parent)
        totals_frame.pack(fill=tk.X, pady=10)

        self.subtotal_label = ttk.Label(totals_frame, text=_t("grocery.subtotal") + ": £0.00", font=('Arial', 11, 'bold'))
        self.subtotal_label.pack()

        # Cart buttons
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame, text=_t("grocery_gui.remove_selected"), command=self.remove_from_cart).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text=_t("grocery_gui.clear_cart"), command=self.clear_cart_action).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text=_t("grocery_gui.checkout"), command=self.process_checkout).pack(fill=tk.X, pady=5)

    def load_categories(self):
        """Load categories into combobox"""
        categories = get_categories()
        all_cats = _t("grocery.all_categories")
        cat_names = [all_cats] + [c['name'] for c in categories]
        self.category_combo['values'] = cat_names
        self.category_combo.set(all_cats)

        # Store category mapping
        self.category_map = {all_cats: None}
        for c in categories:
            self.category_map[c['name']] = c['category_id']

    def refresh_products(self, category_id=None, search=None):
        """Refresh the products list"""
        for item in self.product_tree.get_children():
            self.product_tree.delete(item)

        products = get_products(category_id, search)

        for p in products:
            price_display = f"£{p['price']:.2f}"
            if p['discount_percentage'] > 0:
                discounted = p['price'] * (1 - p['discount_percentage'] / 100)
                price_display = f"£{discounted:.2f}"

            stock_display = str(p['stock_quantity'])
            if p['stock_quantity'] <= 0:
                stock_display = "OUT"
            elif p['stock_quantity'] <= 5:
                stock_display = f"{p['stock_quantity']} LOW"

            discount_display = f"{p['discount_percentage']}%" if p['discount_percentage'] > 0 else "-"

            self.product_tree.insert('', tk.END, values=(
                p['name'],
                p['brand'] or '-',
                p['category_name'],
                price_display,
                stock_display,
                discount_display
            ), tags=(p['source_product_id'],))

    def filter_by_category(self):
        """Filter products by selected category"""
        selected = self.category_combo.get()
        category_id = self.category_map.get(selected)
        self.refresh_products(category_id)

    def search_products(self):
        """Search for products"""
        search_term = self.search_var.get().strip()
        if search_term:
            self.category_combo.set(_t("grocery.all_categories"))
            self.refresh_products(search=search_term)

    def clear_search(self):
        """Clear search and show all products"""
        self.search_var.set('')
        self.category_combo.set(_t("grocery.all_categories"))
        self.refresh_products()

    def add_selected_to_cart(self, event=None):
        """Add selected product to cart"""
        selection = self.product_tree.selection()
        if not selection:
            messagebox.showinfo(_t("grocery.select_product"), _t("grocery.please_select_product"))
            return

        item = self.product_tree.item(selection[0])
        product_id = item['tags'][0]
        product_name = item['values'][0]
        stock_str = str(item['values'][4])

        if 'OUT' in stock_str:
            messagebox.showwarning(_t("grocery.out_of_stock"), _t("grocery.product_out_of_stock").format(product=product_name))
            return

        try:
            quantity = int(self.qty_spinbox.get())
        except ValueError:
            quantity = 1

        user_id = self.current_user.get('id', 0)

        if add_to_cart(user_id, product_id, quantity):
            messagebox.showinfo(_t("grocery.added"), _t("grocery.added_to_cart").format(qty=quantity, product=product_name))
            self.refresh_cart()
        else:
            messagebox.showerror(_t("common.error"), _t("grocery.add_to_cart_failed"))

    def refresh_cart(self):
        """Refresh the cart display"""
        for item in self.cart_tree.get_children():
            self.cart_tree.delete(item)

        user_id = self.current_user.get('id', 0)
        items, subtotal = view_cart(user_id)

        for item in items:
            price = item['price']
            if item['discount_percentage'] > 0:
                price = price * (1 - item['discount_percentage'] / 100)
            total = price * item['quantity']

            self.cart_tree.insert('', tk.END, values=(
                item['name'][:20],
                item['quantity'],
                f"£{price:.2f}",
                f"£{total:.2f}"
            ), tags=(item['product_id'],))

        self.subtotal_label.config(text=f"{_t('grocery.subtotal')}: £{subtotal:.2f}")

    def remove_from_cart(self):
        """Remove selected item from cart"""
        selection = self.cart_tree.selection()
        if not selection:
            messagebox.showinfo(_t("grocery.select_item"), _t("grocery.please_select_item_remove"))
            return

        item = self.cart_tree.item(selection[0])
        product_id = item['tags'][0]
        user_id = self.current_user.get('id', 0)

        update_cart_quantity(user_id, product_id, 0)
        self.refresh_cart()

    def clear_cart_action(self):
        """Clear the entire cart"""
        user_id = self.current_user.get('id', 0)
        items, _ = view_cart(user_id)

        if not items:
            return

        if messagebox.askyesno(_t("grocery.clear_cart_title"), _t("grocery.clear_cart_confirm")):
            clear_cart(user_id)
            self.refresh_cart()

    def process_checkout(self):
        """Process checkout with finance integration"""
        user_id = self.current_user.get('id', 0)
        user_identifier = self.get_user_identifier()
        cart_items, subtotal = view_cart(user_id)

        if not cart_items:
            messagebox.showinfo(_t("grocery.empty_cart"), _t("grocery.cart_is_empty"))
            return

        # Checkout dialog with scrollbar
        checkout_window = tk.Toplevel(self.grocery_window)
        checkout_window.title(_t("grocery.checkout"))
        checkout_window.geometry("450x500")
        checkout_window.transient(self.grocery_window)
        checkout_window.grab_set()

        # Create scrollable container
        container = ttk.Frame(checkout_window)
        container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        main_frame = ttk.Frame(canvas, padding=15)

        main_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=main_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Enable mousewheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # Unbind mousewheel when window closes
        def on_close():
            canvas.unbind_all("<MouseWheel>")
            checkout_window.destroy()

        checkout_window.protocol("WM_DELETE_WINDOW", on_close)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Label(main_frame, text=_t("grocery.checkout"), font=('Arial', 14, 'bold')).pack(pady=10)

        # Order summary
        summary_frame = ttk.LabelFrame(main_frame, text=_t("grocery.order_summary"), padding=10)
        summary_frame.pack(fill=tk.X, pady=5)

        ttk.Label(summary_frame, text=_t("grocery.items_count").format(count=len(cart_items))).pack(anchor='w')
        ttk.Label(summary_frame, text=_t("grocery.total_amount").format(amount=subtotal), font=('Arial', 11, 'bold')).pack(anchor='w')

        # Payment method with finance account balance
        payment_frame = ttk.LabelFrame(main_frame, text=_t("grocery.payment_method"), padding=10)
        payment_frame.pack(fill=tk.X, pady=10)

        payment_method = tk.StringVar(value="card")

        # Get finance account balance
        finance_balance = self.get_user_finance_balance(user_identifier)

        ttk.Radiobutton(payment_frame, text=_t("grocery.payment_card"), variable=payment_method, value="card").pack(anchor='w')

        student_acc_text = _t("grocery.student_account_balance").format(balance=finance_balance)
        if finance_balance < subtotal:
            student_acc_text += " - " + _t("grocery.insufficient_funds")
        ttk.Radiobutton(payment_frame, text=student_acc_text, variable=payment_method, value="student_account").pack(anchor='w')

        ttk.Radiobutton(payment_frame, text=_t("grocery.payment_cash"), variable=payment_method, value="cash").pack(anchor='w')

        def complete_checkout():
            selected_payment = payment_method.get()

            # If using student account, process payment first
            if selected_payment == "student_account":
                # Check balance
                current_balance = self.get_user_finance_balance(user_identifier)
                if current_balance < subtotal:
                    messagebox.showerror(
                        _t("grocery.insufficient_balance_title"),
                        _t("grocery.insufficient_balance_msg").format(balance=current_balance, total=subtotal)
                    )
                    return

                # Process payment from student finance account
                payment_result = process_student_finance_account_payment(
                    student_id=user_identifier,
                    amount=subtotal,
                    description=_t("grocery.purchase_description"),
                    transaction_source="Grocery",
                    transaction_ref=f"GR_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    processed_by=self.current_user.get('username', 'System')
                )

                if not payment_result.get('success'):
                    messagebox.showerror(_t("grocery.payment_failed"), payment_result.get('message', _t("grocery.payment_process_failed")))
                    return

            # Complete the checkout
            transaction_id = checkout(user_id, selected_payment)

            if transaction_id:
                # Record revenue to finance system
                record_revenue_to_finance(
                    student_id=user_identifier,
                    amount=subtotal,
                    revenue_category="Grocery Sales",
                    transaction_source="Grocery",
                    transaction_ref=str(transaction_id),
                    payment_method=selected_payment.replace('_', ' ').title(),
                    notes="Campus Grocery Shop purchase"
                )

                on_close()
                self.refresh_cart()
                self.refresh_products()

                # Get transaction details for receipt
                transaction, receipt_items = get_transaction_details(transaction_id)

                if transaction:
                    # Send email receipt
                    self.send_grocery_receipt_email(transaction, receipt_items)

                    # Show success message
                    success_msg = _t("grocery.purchase_complete_msg").format(receipt=transaction['receipt_number'])
                    if selected_payment == "student_account":
                        new_balance = payment_result.get('new_balance', 0)
                        success_msg += "\n\n" + _t("grocery.payment_deducted").format(amount=subtotal, balance=new_balance)
                    success_msg += "\n\n" + _t("grocery.receipt_sent_email")

                    messagebox.showinfo(_t("grocery.purchase_complete"), success_msg)

                    # Show receipt window
                    self.show_receipt(transaction, receipt_items)
            else:
                messagebox.showerror(_t("common.error"), _t("grocery.checkout_failed"))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=15)

        ttk.Button(btn_frame, text=_t("grocery.complete_purchase"), command=complete_checkout).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.cancel"), command=on_close).pack(side=tk.RIGHT, padx=5)

    def show_receipt(self, transaction, items):
        """Show purchase receipt"""
        receipt_window = tk.Toplevel(self.grocery_window)
        receipt_window.title(_t("grocery.receipt"))
        receipt_window.geometry("350x450")
        receipt_window.transient(self.grocery_window)

        main_frame = ttk.Frame(receipt_window, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        ttk.Label(main_frame, text=_t("grocery.campus_grocery"), font=('Arial', 14, 'bold')).pack()
        ttk.Label(main_frame, text=_t("grocery.receipt").upper(), font=('Arial', 12)).pack()
        ttk.Separator(main_frame, orient='horizontal').pack(fill=tk.X, pady=5)

        ttk.Label(main_frame, text=_t("grocery.receipt_number").format(number=transaction['receipt_number'])).pack(anchor='w')
        ttk.Label(main_frame, text=_t("grocery.date").format(date=transaction['transaction_date'])).pack(anchor='w')
        ttk.Separator(main_frame, orient='horizontal').pack(fill=tk.X, pady=5)

        # Items
        for item in items:
            item_frame = ttk.Frame(main_frame)
            item_frame.pack(fill=tk.X)
            ttk.Label(item_frame, text=f"{item['product_name']}").pack(side=tk.LEFT)
            ttk.Label(item_frame, text=f"x{item['quantity']}").pack(side=tk.LEFT, padx=10)
            ttk.Label(item_frame, text=f"£{item['subtotal']:.2f}").pack(side=tk.RIGHT)

        ttk.Separator(main_frame, orient='horizontal').pack(fill=tk.X, pady=5)

        # Total
        total_frame = ttk.Frame(main_frame)
        total_frame.pack(fill=tk.X)
        ttk.Label(total_frame, text=_t("grocery.total").upper() + ":", font=('Arial', 11, 'bold')).pack(side=tk.LEFT)
        ttk.Label(total_frame, text=f"£{transaction['total_amount']:.2f}",
                 font=('Arial', 11, 'bold')).pack(side=tk.RIGHT)

        ttk.Label(main_frame, text="\n" + _t("grocery.payment").format(method=transaction['payment_method'].title())).pack(anchor='w')

        ttk.Label(main_frame, text="\n" + _t("grocery.thank_you"),
                 font=('Arial', 10, 'italic')).pack(pady=10)

        ttk.Button(main_frame, text=_t("common.close"), command=receipt_window.destroy).pack(pady=10)

    def show_purchase_history(self):
        """Show purchase history"""
        user_id = self.current_user.get('id', 0)
        transactions = get_purchase_history(user_id)

        history_window = tk.Toplevel(self.grocery_window)
        history_window.title(_t("grocery.purchase_history"))
        history_window.geometry("600x400")
        history_window.transient(self.grocery_window)

        main_frame = ttk.Frame(history_window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("grocery.purchase_history"), font=('Arial', 14, 'bold')).pack(pady=5)

        if not transactions:
            ttk.Label(main_frame, text=_t("grocery.no_purchase_history")).pack(pady=50)
            ttk.Button(main_frame, text=_t("common.close"), command=history_window.destroy).pack()
            return

        columns = ('receipt', 'date', 'total', 'payment', 'status')
        tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=12)

        tree.heading('receipt', text=_t("grocery.col.receipt"))
        tree.heading('date', text=_t("grocery.col.date"))
        tree.heading('total', text=_t("grocery.col.total"))
        tree.heading('payment', text=_t("grocery.col.payment"))
        tree.heading('status', text=_t("grocery.col.status"))

        tree.column('receipt', width=140)
        tree.column('date', width=150)
        tree.column('total', width=80)
        tree.column('payment', width=100)
        tree.column('status', width=80)

        for t in transactions:
            tree.insert('', tk.END, values=(
                t['receipt_number'],
                t['transaction_date'],
                f"£{t['total_amount']:.2f}",
                t['payment_method'].title(),
                t['payment_status'].title()
            ), tags=(t['transaction_id'],))

        tree.pack(fill=tk.BOTH, expand=True)

        def view_details():
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                transaction_id = item['tags'][0]
                transaction, items = get_transaction_details(transaction_id)
                if transaction:
                    self.show_receipt(transaction, items)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        ttk.Button(btn_frame, text=_t("grocery.view_details"), command=view_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("common.close"), command=history_window.destroy).pack(side=tk.RIGHT, padx=5)

    def open_management_interface(self):
        """Open the management interface - to be overridden by GroceryManagementGUI"""
        messagebox.showinfo("Management", "Management features are not available in this view.")

class GroceryManagementGUI(GroceryGUI):
    """Extended GUI with management features for staff/admin"""

    def open_management_interface(self):
        """Override to open management GUI when button is clicked"""
        self.open_management_gui()

    def open_management_gui(self):
        """Open the management interface"""
        self.mgmt_window = tk.Toplevel(self.root)
        self.mgmt_window.title(_t("grocery.management_title"))
        self.mgmt_window.geometry("800x600")
        self.mgmt_window.transient(self.root)

        notebook = ttk.Notebook(self.mgmt_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Inventory tab
        inventory_frame = ttk.Frame(notebook)
        notebook.add(inventory_frame, text=_t("grocery.tab_inventory"))
        self.setup_inventory_tab(inventory_frame)

        # Low stock tab
        lowstock_frame = ttk.Frame(notebook)
        notebook.add(lowstock_frame, text=_t("grocery.tab_low_stock"))
        self.setup_lowstock_tab(lowstock_frame)

        # Refunds tab
        refunds_frame = ttk.Frame(notebook)
        notebook.add(refunds_frame, text="Refunds")
        self.setup_refunds_tab(refunds_frame)

    def setup_inventory_tab(self, parent):
        """Setup inventory management tab"""
        header = ttk.Frame(parent)
        header.pack(fill=tk.X, pady=10)

        ttk.Label(header, text=_t("grocery.inventory_management"), font=('Arial', 14, 'bold')).pack(side=tk.LEFT, padx=10)
        ttk.Button(header, text=_t("common.refresh"), command=lambda: self.refresh_inventory_list()).pack(side=tk.RIGHT, padx=10)

        # Products list
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10)

        columns = ('id', 'name', 'category', 'stock', 'min_level', 'status')
        self.inventory_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        self.inventory_tree.heading('id', text=_t("grocery.col.id"))
        self.inventory_tree.heading('name', text=_t("grocery.col.product"))
        self.inventory_tree.heading('category', text=_t("grocery.col.category"))
        self.inventory_tree.heading('stock', text=_t("grocery.col.stock"))
        self.inventory_tree.heading('min_level', text=_t("grocery.col.min_level"))
        self.inventory_tree.heading('status', text=_t("grocery.col.status"))

        self.inventory_tree.column('id', width=80)
        self.inventory_tree.column('name', width=200)
        self.inventory_tree.column('category', width=120)
        self.inventory_tree.column('stock', width=80)
        self.inventory_tree.column('min_level', width=80)
        self.inventory_tree.column('status', width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.inventory_tree.yview)
        self.inventory_tree.configure(yscrollcommand=scrollbar.set)

        self.inventory_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Restock controls
        restock_frame = ttk.LabelFrame(parent, text=_t("grocery.restock_product"), padding=10)
        restock_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(restock_frame, text=_t("grocery.quantity_to_add")).pack(side=tk.LEFT, padx=5)
        self.restock_qty = ttk.Entry(restock_frame, width=10)
        self.restock_qty.pack(side=tk.LEFT, padx=5)

        ttk.Button(restock_frame, text=_t("grocery.restock_selected"), command=self.restock_selected).pack(side=tk.LEFT, padx=10)

        self.refresh_inventory_list()

    def refresh_inventory_list(self):
        """Refresh the inventory list"""
        for item in self.inventory_tree.get_children():
            self.inventory_tree.delete(item)

        products = get_products()

        for p in products:
            status = "OK"
            if p['stock_quantity'] <= 0:
                status = "OUT"
            elif p['stock_quantity'] <= p['min_stock_level']:
                status = "LOW"

            self.inventory_tree.insert('', tk.END, values=(
                p['source_product_id'],
                p['name'],
                p['category_name'],
                p['stock_quantity'],
                p['min_stock_level'],
                status
            ), tags=(p['source_product_id'],))

    def restock_selected(self):
        """Restock the selected product"""
        selection = self.inventory_tree.selection()
        if not selection:
            messagebox.showinfo(_t("grocery.select_product"), _t("grocery.please_select_restock"))
            return

        try:
            quantity = int(self.restock_qty.get())
            if quantity <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror(_t("grocery.invalid_quantity"), _t("grocery.enter_valid_quantity"))
            return

        item = self.inventory_tree.item(selection[0])
        product_id = item['tags'][0]
        product_name = item['values'][1]

        user_id = self.current_user.get('id', 0)

        if restock_product(product_id, quantity, user_id=user_id):
            messagebox.showinfo(_t("common.success"), _t("grocery.restocked_success").format(qty=quantity, product=product_name))
            self.refresh_inventory_list()
            self.restock_qty.delete(0, tk.END)
        else:
            messagebox.showerror(_t("common.error"), _t("grocery.restock_failed"))

    def setup_lowstock_tab(self, parent):
        """Setup low stock alerts tab"""
        header = ttk.Frame(parent)
        header.pack(fill=tk.X, pady=10)

        ttk.Label(header, text=_t("grocery.low_stock_alerts"), font=('Arial', 14, 'bold')).pack(side=tk.LEFT, padx=10)
        ttk.Button(header, text=_t("common.refresh"), command=lambda: self.refresh_lowstock_list()).pack(side=tk.RIGHT, padx=10)

        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10)

        columns = ('id', 'name', 'category', 'stock', 'min_level', 'needed')
        self.lowstock_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        self.lowstock_tree.heading('id', text=_t("grocery.col.id"))
        self.lowstock_tree.heading('name', text=_t("grocery.col.product"))
        self.lowstock_tree.heading('category', text=_t("grocery.col.category"))
        self.lowstock_tree.heading('stock', text=_t("grocery.col.current"))
        self.lowstock_tree.heading('min_level', text=_t("grocery.col.min_level"))
        self.lowstock_tree.heading('needed', text=_t("grocery.col.needed"))

        self.lowstock_tree.pack(fill=tk.BOTH, expand=True)

        self.refresh_lowstock_list()

    def refresh_lowstock_list(self):
        """Refresh the low stock list"""
        for item in self.lowstock_tree.get_children():
            self.lowstock_tree.delete(item)

        products = get_low_stock_products()

        for p in products:
            needed = max(0, p['min_stock_level'] * 2 - p['stock_quantity'])

            self.lowstock_tree.insert('', tk.END, values=(
                p['product_id'],
                p['name'],
                p['category_name'],
                p['stock_quantity'],
                p['min_stock_level'],
                needed
            ))

    def setup_refunds_tab(self, parent):
        """Setup payment refunds management tab - Accessible to all staff and admin users"""
        # Header
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill=tk.X, pady=(10, 10))

        header_left = ttk.Frame(header_frame)
        header_left.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

        ttk.Label(header_left, text="Grocery Shop Payment Refunds",
                 font=('Arial', 12, 'bold')).pack(anchor=tk.W)

        # Show admin badge if user is admin
        if self.current_user and self.current_user.get('role') == 'admin':
            ttk.Label(header_left, text="[ADMIN ACCESS]",
                     font=('Arial', 9, 'bold'), foreground='blue').pack(anchor=tk.W, pady=(2, 0))

        # Search frame
        search_frame = ttk.LabelFrame(parent, text="Search Transactions", padding="10")
        search_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(search_frame, text="Transaction ID, Receipt #, Customer Name, or Student ID:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.refund_search_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.refund_search_var, width=45).grid(row=0, column=1, padx=5)

        # Transactions list frame
        list_frame = ttk.LabelFrame(parent, text="All Grocery Transactions", padding="5")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        columns = ('trans_id', 'date', 'receipt', 'customer_name', 'student_id', 'total', 'method', 'status')
        self.refunds_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        self.refunds_tree.heading('trans_id', text='Transaction ID')
        self.refunds_tree.heading('date', text='Date/Time')
        self.refunds_tree.heading('receipt', text='Receipt #')
        self.refunds_tree.heading('customer_name', text='Customer Name')
        self.refunds_tree.heading('student_id', text='Student ID')
        self.refunds_tree.heading('total', text='Total (GBP)')
        self.refunds_tree.heading('method', text='Payment Method')
        self.refunds_tree.heading('status', text='Status')

        self.refunds_tree.column('trans_id', width=110)
        self.refunds_tree.column('date', width=140)
        self.refunds_tree.column('receipt', width=110)
        self.refunds_tree.column('customer_name', width=140)
        self.refunds_tree.column('student_id', width=90)
        self.refunds_tree.column('total', width=80)
        self.refunds_tree.column('method', width=110)
        self.refunds_tree.column('status', width=90)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.refunds_tree.yview)
        self.refunds_tree.configure(yscrollcommand=scrollbar.set)
        self.refunds_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Button frame
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Search", command=self.refresh_refunds_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Show All",
                  command=lambda: [self.refund_search_var.set(''), self.refresh_refunds_list()]).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Process Refund", command=self.process_grocery_refund).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="View Details", command=self.view_refund_transaction_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Export to CSV", command=self.export_refunds_csv).pack(side=tk.LEFT, padx=5)

        # Initial load
        self.refresh_refunds_list()

    def refresh_refunds_list(self):
        """Refresh the refunds list from database with customer information."""
        for item in self.refunds_tree.get_children():
            self.refunds_tree.delete(item)

        try:
            conn = get_connection()
            cursor = conn.cursor()
            search_term = self.refund_search_var.get().strip()

            if search_term:
                cursor.execute('''
                    SELECT
                        gt.transaction_id,
                        gt.created_at,
                        COALESCE(gt.receipt_number, 'N/A') as receipt_number,
                        COALESCE(u.first_name || ' ' || u.last_name, u.username, gt.student_id, 'Guest') as customer_name,
                        COALESCE(gt.student_id, 'N/A') as student_id,
                        gt.total_amount,
                        COALESCE(gt.payment_method, 'Cash') as payment_method,
                        COALESCE(gt.status, 'completed') as payment_status
                    FROM transactions gt
                    LEFT JOIN users u ON gt.customer_id = u.id OR gt.student_id = u.username OR gt.student_id = u.student_id
                    WHERE gt.source_type = 'grocery' AND (gt.source_transaction_id LIKE ?
                       OR gt.student_id LIKE ?
                       OR gt.receipt_number LIKE ?
                       OR u.first_name LIKE ?
                       OR u.last_name LIKE ?
                       OR u.username LIKE ?)
                    ORDER BY gt.created_at DESC
                ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%',
                      f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
            else:
                cursor.execute('''
                    SELECT
                        gt.transaction_id,
                        gt.created_at,
                        COALESCE(gt.receipt_number, 'N/A') as receipt_number,
                        COALESCE(u.first_name || ' ' || u.last_name, u.username, gt.student_id, 'Guest') as customer_name,
                        COALESCE(gt.student_id, 'N/A') as student_id,
                        gt.total_amount,
                        COALESCE(gt.payment_method, 'Cash') as payment_method,
                        COALESCE(gt.status, 'completed') as payment_status
                    FROM transactions gt
                    LEFT JOIN users u ON gt.customer_id = u.id OR gt.student_id = u.username OR gt.student_id = u.student_id
                    WHERE gt.source_type = 'grocery'
                    ORDER BY gt.created_at DESC
                    LIMIT 200
                ''')

            for row in cursor.fetchall():
                values = list(row)
                # Ensure all 8 columns (now includes customer_name)
                while len(values) < 8:
                    values.append('N/A')
                # Format amount (now at index 5)
                if values[5] and values[5] != 'N/A':
                    try:
                        values[5] = f"{float(values[5]):.2f}"
                    except (ValueError, TypeError):
                        pass
                self.refunds_tree.insert('', tk.END, values=values)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load transactions: {e}")

    def view_refund_transaction_details(self):
        """View detailed transaction information."""
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a transaction to view details")
            return

        try:
            values = self.refunds_tree.item(selection[0])['values']
            if len(values) < 8:
                messagebox.showerror("Data Error", "Transaction record is incomplete")
                return

            trans_id = values[0]

            # Get full transaction details including items
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT product_name, quantity, unit_price, subtotal
                FROM grocery_transaction_items
                WHERE transaction_id = ?
            ''', (trans_id,))
            items = cursor.fetchall()

            conn.close()

            items_text = ""
            if items:
                items_text = "\n\nPurchased Items:"
                for item in items:
                    # Access Row object directly by column name
                    items_text += f"\n  - {item['product_name']} x{item['quantity']} @ GBP {item['unit_price']:.2f} = GBP {item['subtotal']:.2f}"

            details = f"""TRANSACTION DETAILS
==================
Transaction ID: {values[0]}
Date/Time: {values[1]}
Receipt Number: {values[2]}
Customer Name: {values[3]}
Student ID: {values[4]}
Total Amount: GBP {values[5]}
Payment Method: {values[6]}
Status: {values[7]}
{items_text}
"""
            messagebox.showinfo("Transaction Details", details)
        except Exception as e:
            messagebox.showerror("Error", f"Error viewing transaction details: {e}")

    def export_refunds_csv(self):
        """Export transactions to CSV file."""
        try:
            import csv
            from tkinter import filedialog

            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"grocery_transactions_{datetime.now().strftime('%Y%m%d')}.csv"
            )

            if filepath:
                with open(filepath, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Transaction ID', 'Date/Time', 'Receipt #', 'Customer Name',
                                   'Student ID', 'Total', 'Payment Method', 'Status'])

                    for item in self.refunds_tree.get_children():
                        values = self.refunds_tree.item(item)['values']
                        writer.writerow(values)

                messagebox.showinfo("Export Successful", f"Transactions exported to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export transactions: {e}")

    def process_grocery_refund(self):
        """Process a refund with cash/card/student account options.

        Available to: Grocery staff and Admin users
        """
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a transaction to refund")
            return

        try:
            values = self.refunds_tree.item(selection[0])['values']
            if len(values) < 8:
                messagebox.showerror("Data Error", "Transaction record is incomplete")
                return

            trans_id = values[0]
            trans_date = values[1]
            receipt_number = values[2]
            customer_name = values[3]
            student_id = values[4] if values[4] != 'N/A' else None
            amount = float(values[5])
            payment_method = values[6]
            status = values[7]
        except (IndexError, ValueError) as e:
            messagebox.showerror("Error", f"Error reading transaction data: {e}")
            return

        if status == 'refunded':
            messagebox.showinfo("Already Refunded", "This transaction has already been refunded")
            return

        # Confirm refund
        if not messagebox.askyesno("Confirm Refund",
                                   f"Refund GBP {amount:.2f} for Transaction {trans_id}?\n\n"
                                   f"Customer: {customer_name}\n"
                                   f"Receipt: {receipt_number}\n"
                                   f"Date: {trans_date}\n"
                                   f"Payment Method: {payment_method}"):
            return

        # Show refund method selection dialog
        refund_method = self.show_grocery_refund_method_dialog(amount, trans_id, student_id, customer_name)
        if not refund_method:
            return

        # Process based on method
        success = False

        if refund_method == 'Student Account':
            if not student_id:
                # Try to retrieve student_id from the transaction's user_id
                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    # Get user_id from transaction
                    cursor.execute('''
                        SELECT customer_id, student_id FROM transactions
                        WHERE source_type = 'grocery' AND source_transaction_id = ?
                    ''', (trans_id,))
                    trans_row = cursor.fetchone()

                    if trans_row:
                        trans_student_id = trans_row['student_id']
                        user_id = trans_row['user_id']

                        # First check if transaction has student_id
                        if trans_student_id and trans_student_id != 'N/A':
                            student_id = trans_student_id
                        elif user_id:
                            # Look up student_id from users table
                            cursor.execute('''
                                SELECT student_id, username FROM users WHERE id = ?
                            ''', (user_id,))
                            user_row = cursor.fetchone()
                            if user_row:
                                # Use student_id if available, otherwise username
                                student_id = user_row['student_id'] if user_row['student_id'] else user_row['username']

                    conn.close()
                except Exception as e:
                    print(f"Error retrieving student ID: {e}")

                # Last resort: prompt for student ID
                if not student_id:
                    from tkinter import simpledialog
                    student_id = simpledialog.askstring("Student ID",
                        "Unable to automatically determine Student ID.\nPlease enter Student ID for refund:")
                    if not student_id:
                        return

            success = self.add_grocery_refund_to_student_account(student_id, amount, trans_id)
        else:
            # For cash/card, just record the refund
            success = True

        if success:
            # Update transaction status to refunded
            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE transactions
                    SET status = 'refunded'
                    WHERE source_type = 'grocery' AND source_transaction_id = ?
                ''', (trans_id,))

                # Generate refund reference
                import uuid
                refund_ref = f"GROC-REFUND-{uuid.uuid4().hex[:12].upper()}"

                # Record refund in unified_refunds table
                cursor.execute('''
                    INSERT INTO unified_refunds
                    (source_type, reference_id, reference_type, amount, refund_method, refund_reference, student_id, refund_date, status)
                    VALUES ('grocery', ?, 'transaction', ?, ?, ?, ?, CURRENT_TIMESTAMP, 'processed')
                ''', (trans_id, amount, refund_method, refund_ref, student_id))
                refund_row_id = cursor.lastrowid

                conn.commit()
                conn.close()

                # Auto-post to GL (cash has moved). Never raises.
                try:
                    from education_system.university_system.modules.domain.finance.ledger import notify_ledger
                    notify_ledger('refund', refund_row_id, posted_by='grocery')
                except Exception as _e:
                    import logging
                    logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

                # Send refund receipt email
                self.send_grocery_refund_receipt(trans_id, receipt_number, amount, refund_method, refund_ref, student_id)

                # Notify finance GUI
                self.notify_grocery_finance_gui(trans_id, amount, refund_method, refund_ref, student_id)

                messagebox.showinfo("Refund Processed",
                                  f"Refund of GBP {amount:.2f} processed successfully\n\n"
                                  f"Method: {refund_method}\n"
                                  f"Refund Reference: {refund_ref}")

                self.refresh_refunds_list()
            except Exception as e:
                messagebox.showerror("Refund Error", f"Failed to process refund: {e}")
        else:
            messagebox.showerror("Refund Failed", "Failed to process student account refund")

    def show_grocery_refund_method_dialog(self, amount: float, trans_id: str, student_id=None, customer_name=None):
        """Show refund method selection dialog."""
        dialog = tk.Toplevel(self.mgmt_window)
        dialog.title("Select Refund Method")
        dialog.geometry("450x450")
        dialog.transient(self.mgmt_window)
        dialog.grab_set()

        result = {'method': None}

        # Refund info frame
        info_frame = ttk.LabelFrame(dialog, text="Refund Details", padding="10")
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(info_frame, text=f"Transaction ID: {trans_id}").pack(anchor=tk.W)
        if customer_name:
            ttk.Label(info_frame, text=f"Customer: {customer_name}",
                     font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(2, 0))
        ttk.Label(info_frame, text=f"Refund Amount: GBP {amount:.2f}",
                 font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=(5, 0))

        # Student account balance if available
        if student_id:
            balance = get_student_finance_account_balance(student_id)
            if balance is not None:
                ttk.Label(info_frame, text=f"Student ID: {student_id}").pack(anchor=tk.W, pady=(5, 0))
                ttk.Label(info_frame, text=f"Current Account Balance: GBP {balance:.2f}").pack(
                    anchor=tk.W, pady=(5, 0))
                ttk.Label(info_frame, text=f"Balance After Refund: GBP {balance + amount:.2f}",
                         foreground='green').pack(anchor=tk.W)

        # Refund method selection
        method_frame = ttk.LabelFrame(dialog, text="Select Refund Method", padding="10")
        method_frame.pack(fill=tk.X, padx=10, pady=10)

        def select_method(method):
            result['method'] = method
            dialog.destroy()

        # Cash button
        ttk.Button(method_frame, text="Cash", width=30,
                  command=lambda: select_method('Cash')).pack(pady=5)

        # Card button
        ttk.Button(method_frame, text="Card (Original Payment Method)", width=30,
                  command=lambda: select_method('Card')).pack(pady=5)

        # Student Account button
        ttk.Button(method_frame, text="Student Finance Account", width=30,
                  command=lambda: select_method('Student Account')).pack(pady=5)

        # Cancel button
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack(pady=10)

        dialog.wait_window()
        return result['method']

    def add_grocery_refund_to_student_account(self, student_id: str, amount: float, trans_id: str):
        """Add refund amount to student's finance account."""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get account_id and balance
            cursor.execute('''
                SELECT account_id, balance FROM student_finance_accounts
                WHERE student_id = ? AND account_status = 'active'
            ''', (student_id,))
            row = cursor.fetchone()

            if not row:
                # Try to create account if it doesn't exist
                cursor.execute('''
                    INSERT INTO student_finance_accounts
                    (student_id, balance, account_status)
                    VALUES (?, ?, 'active')
                ''', (student_id, amount))

                # Get the newly created account_id
                cursor.execute('''
                    SELECT account_id FROM student_finance_accounts
                    WHERE student_id = ?
                ''', (student_id,))
                account_id = cursor.fetchone()[0]
                balance_before = 0.00
                balance_after = amount
            else:
                account_id = row[0]
                balance_before = float(row[1])
                balance_after = balance_before + amount

                # Add to balance
                cursor.execute('''
                    UPDATE student_finance_accounts
                    SET balance = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE account_id = ?
                ''', (balance_after, account_id))

            # Record transaction
            cursor.execute('''
                INSERT INTO transactions
                (source_type, account_id, student_id, transaction_type, amount, balance_before,
                 balance_after, description, reference_id, processed_by)
                VALUES ('student_finance', ?, ?, 'credit', ?, ?, ?, ?, ?, ?)
            ''', (account_id, student_id, amount, balance_before, balance_after,
                  f'Grocery Shop Refund - Transaction: {trans_id}',
                  f'GROCERY-REFUND-{trans_id}',
                  self.current_user.get('username', 'system') if self.current_user else 'system'))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error adding to student account: {e}")
            return False

    def send_grocery_refund_receipt(self, trans_id: str, receipt_number: str, amount: float,
                                    method: str, refund_ref: str, student_id=None):
        """Send refund receipt email."""
        try:
            # Get customer email
            if not student_id:
                return

            student_info = get_student_info(student_id)
            if not student_info or not student_info.get('email'):
                print(f"[Grocery] No email found for student {student_id}")
                return

            email = student_info['email']
            customer_name = student_info.get('full_name', student_id)

            # Prepare account balance info (conditional)
            account_balance_info = ""
            if method == 'Student Account':
                balance = get_student_finance_account_balance(student_id)
                if balance is not None:
                    account_balance_info = f"Your new Student Finance Account balance: GBP {balance:.2f}"

            # Prepare template variables
            from education_system.university_system.infrastructure.email.template_utils import render_template

            template_vars = {
                'customer_name': customer_name,
                'refund_ref': refund_ref,
                'trans_id': trans_id,
                'receipt_number': receipt_number,
                'amount': f"{amount:.2f}",
                'method': method,
                'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'account_balance_info': account_balance_info
            }

            subject, body = render_template('commerce/grocery_payment_refund_receipt', template_vars)
            if not subject or not body:
                print("Failed to render email template")
                return

            send_email(email, subject, body)
            print(f"[Grocery] Refund receipt sent to {email}")
        except Exception as e:
            print(f"Error sending refund receipt: {e}")

    def notify_grocery_finance_gui(self, trans_id: str, amount: float, method: str,
                                   refund_ref: str, student_id=None):
        """Notify finance GUI of grocery refund - already recorded in unified_refunds."""
        try:
            print(f"[Grocery] Refund recorded in finance system: {refund_ref}")
        except Exception as e:
            print(f"Error notifying finance system: {e}")
