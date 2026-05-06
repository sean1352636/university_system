"""Butchers Shop GUI Module

Provides a comprehensive GUI for butcher shop operations including
products, orders, inventory, and reporting with email and finance integration.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
from datetime import datetime, timedelta
from typing import Optional, List

from education_system.university_system.modules.shared.utils.i18n import get_text as _t
from education_system.university_system.infrastructure.database.db import get_db_connection, get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

# Email service import with fallback
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    from education_system.university_system.infrastructure.email.template_utils import render_template
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    def send_email(*args, **kwargs): return False
    render_template = None


def _send_butcher_email(recipient: str, subject: str, body: str, show_success: bool = False) -> bool:
    """Helper function to send emails with proper error handling and logging."""
    if not EMAIL_AVAILABLE:
        print(f"[Butcher] Email service not available - would send to {recipient}: {subject}")
        return False
    if not recipient:
        print(f"[Butcher] No recipient email provided for: {subject}")
        return False
    try:
        result = send_email(recipient, subject, body)
        if result:
            log_activity('email_sent', 'butcher', details={'to': recipient, 'subject': subject})
            print(f"[Butcher] Email sent successfully to {recipient}: {subject}")
            return True
        else:
            print(f"[Butcher] Email send returned False for {recipient}: {subject}")
            return False
    except Exception as e:
        print(f"[Butcher] Email send error for {recipient}: {e}")
        log_activity('email_failed', 'butcher', details={'to': recipient, 'subject': subject, 'error': str(e)})
        return False


class ButcherGUI:
    """Main GUI class for Butcher Shop operations"""

    def __init__(self, parent: tk.Toplevel, auth):
        """Initialize the Butcher Shop GUI - Function 1"""
        self.parent = parent
        self.auth = auth
        self.current_user = auth.current_user if auth else None

        if not self.current_user:
            messagebox.showerror(_t("butcher.window_title"), _t("butcher.errors.login_required"))
            if parent:
                parent.destroy()
            return

        self.parent.title(_t("butcher.window_title"))
        self.parent.geometry("1400x900")
        self.parent.minsize(1200, 800)

        # Initialize database
        self._init_database()

        # Create main interface
        self.create_widgets()

        # Load initial data
        self.refresh_all_data()

        log_activity('access', 'butcher_shop', user_id=self.current_user.get('user_id'))

    def create_widgets(self):
        """Create the main GUI widgets - Function 2"""
        # Header frame
        header_frame = ttk.Frame(self.parent, padding="10")
        header_frame.pack(fill=tk.X)

        ttk.Label(header_frame, text=_t("butcher.title"),
                 font=('Helvetica', 16, 'bold')).pack(side=tk.LEFT)

        user_info = f"{self.current_user.get('username')} ({self.current_user.get('role')})"
        ttk.Label(header_frame, text=user_info).pack(side=tk.RIGHT)

        # Main notebook for tabs
        self.notebook = ttk.Notebook(self.parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Create tabs
        self.create_products_tab()
        self.create_orders_tab()
        self.create_refunds_tab()
        self.create_inventory_tab()
        self.create_reports_tab()

        # Bottom buttons
        btn_frame = ttk.Frame(self.parent, padding="10")
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text=_t("common.refresh"),
                  command=self.refresh_all_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("butcher.btn.return_home"),
                  command=self.return_to_homescreen).pack(side=tk.RIGHT, padx=5)

    def _init_database(self):
        """Initialize database tables - Function 3"""
        from education_system.university_system.modules.domain.commerce.butcher.services.butcher_core import init_butcher_db
        try:
            init_butcher_db()
        except Exception as e:
            logger.error(f"Failed to initialize butcher database: {e}")

    def return_to_homescreen(self):
        """Return to the main homescreen - Function 4"""
        if messagebox.askyesno(_t("common.confirm"), _t("butcher.confirm.exit")):
            self.parent.destroy()

    def _get_user_email(self) -> str:
        """Fetch user email from the users table."""
        try:
            with get_connection() as conn:
                cursor = conn.execute(
                    "SELECT email FROM users WHERE username = ?",
                    (self.current_user.get('username'),)
                )
                row = cursor.fetchone()
                if row and row[0]:
                    return row[0]
        except Exception as e:
            print(f"Error fetching user email: {e}")
        return ''

    def _get_student_account_balance(self) -> Optional[float]:
        """Get student's finance account balance."""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT balance FROM student_finance_accounts
                    WHERE student_id = ? AND account_status = 'active'
                ''', (self.current_user.get('username'),))
                row = cursor.fetchone()
                return float(row[0]) if row else None
        except Exception as e:
            print(f"Error getting student balance: {e}")
            return None

    def _deduct_from_student_account(self, amount: float) -> bool:
        """Deduct amount from student's finance account."""
        try:
            with transaction() as conn:
                # Get account details
                cursor = conn.execute('''
                    SELECT account_id, balance FROM student_finance_accounts
                    WHERE student_id = ? AND account_status = 'active'
                ''', (self.current_user.get('username'),))
                row = cursor.fetchone()
                if not row:
                    messagebox.showerror(_t("butcher.window_title"), "No active student finance account found.")
                    return False

                account_id = row[0]
                current_balance = float(row[1])

                if current_balance < amount:
                    messagebox.showerror(_t("butcher.window_title"),
                                        f"Insufficient balance. Available: GBP {current_balance:.2f}")
                    return False

                new_balance = current_balance - amount

                # Update balance
                conn.execute('''
                    UPDATE student_finance_accounts
                    SET balance = ?, updated_at = ?
                    WHERE account_id = ?
                ''', (new_balance, datetime.now().isoformat(), account_id))

                # Record transaction
                conn.execute('''
                    INSERT INTO transactions
                    (source_type, account_id, student_id, transaction_type, amount, balance_before, balance_after,
                     description, reference_id, processed_by, created_at)
                    VALUES ('student_finance', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (account_id, self.current_user.get('username'), 'debit', amount,
                      current_balance, new_balance, 'Butcher Shop Purchase',
                      f"BUTCHER-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                      self.current_user.get('username'), datetime.now().isoformat()))

                return True
        except Exception as e:
            print(f"Error deducting from student account: {e}")
            return False

    def _add_to_revenue(self, amount: float, description: str, reference: str):
        """Add payment to central finance revenue.

        8.117.104: routed through unified record_payment() with
        ``source_type='butcher'``.
        """
        try:
            student_id = self.current_user.get('student_id') or self.current_user.get('username')
            from education_system.university_system.modules.domain.finance.core.unified_payments import (
                record_payment,
            )
            record_payment(
                student_id=student_id,
                amount=amount,
                payment_method='butcher_shop',
                source_type='butcher',
                source_payment_id=reference,
                payment_type='revenue',
                department='butcher',
                description=description,
                created_by=self.current_user.get('username'),
            )
            with transaction() as conn:

                # Try to add to finance revenue tracking if table exists
                try:
                    conn.execute('''
                        INSERT INTO finance_revenue (source, amount, category, description,
                                                    recorded_by, recorded_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', ('butcher_shop', amount, 'food_services', description,
                          self.current_user.get('username'), datetime.now().isoformat()))
                except Exception:
                    pass  # Table may not exist

                log_activity('revenue', 'butcher_shop',
                            details={'amount': amount, 'reference': reference})
        except Exception as e:
            print(f"Finance integration error: {e}")

    def _show_payment_dialog(self, amount: float, description: str) -> Optional[str]:
        """Show payment method selection dialog."""
        result = {'method': None}

        dialog = tk.Toplevel(self.parent)
        dialog.title(_t("butcher.labels.payment_method"))
        dialog.geometry("400x350")
        dialog.transient(self.parent)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = self.parent.winfo_x() + (self.parent.winfo_width() - 400) // 2
        y = self.parent.winfo_y() + (self.parent.winfo_height() - 350) // 2
        dialog.geometry(f"+{x}+{y}")

        # Header
        ttk.Label(dialog, text=_t("butcher.labels.select_payment_method"),
                 font=('Helvetica', 14, 'bold')).pack(pady=15)

        # Amount display
        ttk.Label(dialog, text=description,
                 font=('Helvetica', 10)).pack(pady=5)
        ttk.Label(dialog, text=f"Total: GBP {amount:.2f}",
                 font=('Helvetica', 16, 'bold'), foreground='green').pack(pady=10)

        # Payment options frame
        options_frame = ttk.LabelFrame(dialog, text=_t("butcher.labels.payment_options"), padding="15")
        options_frame.pack(fill=tk.X, padx=20, pady=10)

        payment_var = tk.StringVar(value="Card")

        # Cash option
        ttk.Radiobutton(options_frame, text=_t("butcher.btn.cash"), variable=payment_var,
                       value="Cash").pack(anchor=tk.W, pady=5)

        # Card option
        ttk.Radiobutton(options_frame, text=_t("butcher.btn.card"), variable=payment_var,
                       value="Card").pack(anchor=tk.W, pady=5)

        # Student Account option with balance
        student_balance = self._get_student_account_balance()
        if student_balance is not None:
            balance_text = f"Student Account (Balance: GBP {student_balance:.2f})"
            if student_balance < amount:
                balance_text += " - INSUFFICIENT"
            rb = ttk.Radiobutton(options_frame, text=balance_text, variable=payment_var,
                                value="Student Account")
            rb.pack(anchor=tk.W, pady=5)
            if student_balance < amount:
                rb.configure(state='disabled')
        else:
            ttk.Label(options_frame, text=_t("butcher.labels.student_account_na"),
                     foreground='gray').pack(anchor=tk.W, pady=5)

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=20)

        def confirm():
            result['method'] = payment_var.get()
            dialog.destroy()

        def cancel():
            dialog.destroy()

        ttk.Button(btn_frame, text=_t("butcher.btn.confirm_payment"), command=confirm).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text=_t("butcher.btn.cancel"), command=cancel).pack(side=tk.LEFT, padx=10)

        dialog.wait_window()
        return result['method']

    def _get_admin_emails(self) -> List[str]:
        """Get email addresses of all admin users."""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT email FROM users
                    WHERE role = 'admin' AND email IS NOT NULL AND email != ''
                ''')
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting admin emails: {e}")
            return []

    def refresh_all_data(self):
        """Refresh all data in the GUI - Function 5"""
        try:
            self._load_products()
            self._load_orders()
            self._load_inventory()
        except Exception as e:
            logger.error(f"Error refreshing data: {e}")

    def create_products_tab(self):
        """Create the products management tab - Function 6"""
        products_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(products_frame, text=_t("butcher.tabs.products"))

        # Left side - Product list
        list_frame = ttk.LabelFrame(products_frame, text=_t("butcher.labels.product_list"), padding="5")
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # Category filter
        filter_frame = ttk.Frame(list_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(filter_frame, text=_t("butcher.labels.category") + ":").pack(side=tk.LEFT)
        self.category_filter = ttk.Combobox(filter_frame, state="readonly", width=20)
        self.category_filter['values'] = ['All'] + list(self._get_categories().values())
        self.category_filter.set('All')
        self.category_filter.pack(side=tk.LEFT, padx=5)
        self.category_filter.bind('<<ComboboxSelected>>', lambda e: self._load_products())

        # Products treeview
        columns = ('id', 'name', 'category', 'price', 'stock', 'unit')
        self.products_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        self.products_tree.heading('id', text=_t('butcher.columns.id'))
        self.products_tree.heading('name', text=_t("butcher.labels.product_name"))
        self.products_tree.heading('category', text=_t("butcher.labels.category"))
        self.products_tree.heading('price', text=_t("butcher.labels.price"))
        self.products_tree.heading('stock', text=_t("butcher.labels.stock"))
        self.products_tree.heading('unit', text=_t("butcher.labels.unit"))

        self.products_tree.column('id', width=50)
        self.products_tree.column('name', width=150)
        self.products_tree.column('category', width=100)
        self.products_tree.column('price', width=80)
        self.products_tree.column('stock', width=80)
        self.products_tree.column('unit', width=60)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.products_tree.yview)
        self.products_tree.configure(yscrollcommand=scrollbar.set)

        self.products_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Right side - Add/Edit product
        edit_frame = ttk.LabelFrame(products_frame, text=_t("butcher.labels.add_product"), padding="10")
        edit_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        # Product form fields
        ttk.Label(edit_frame, text=_t("butcher.labels.product_name") + ":").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.product_name_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.product_name_var, width=25).grid(row=0, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("butcher.labels.category") + ":").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.product_category_var = ttk.Combobox(edit_frame, state="readonly", width=22)
        self.product_category_var['values'] = list(self._get_categories().values())
        self.product_category_var.grid(row=1, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("butcher.labels.price") + " (£):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.product_price_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.product_price_var, width=25).grid(row=2, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("butcher.labels.unit") + ":").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.product_unit_var = ttk.Combobox(edit_frame, state="readonly", width=22)
        self.product_unit_var['values'] = ['kg', 'g', 'lb', 'oz', 'each', 'pack']
        self.product_unit_var.set('kg')
        self.product_unit_var.grid(row=3, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("butcher.labels.stock") + ":").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.product_stock_var = tk.StringVar(value="0")
        ttk.Entry(edit_frame, textvariable=self.product_stock_var, width=25).grid(row=4, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("butcher.labels.description") + ":").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.product_desc_text = tk.Text(edit_frame, width=25, height=3)
        self.product_desc_text.grid(row=5, column=1, pady=2)

        # Buttons
        btn_frame = ttk.Frame(edit_frame)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=10)

        ttk.Button(btn_frame, text=_t("butcher.btn.add_product"),
                  command=self.add_product).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_t("butcher.btn.update_product"),
                  command=self.update_product).pack(side=tk.LEFT, padx=2)

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
            messagebox.showwarning(_t("butcher.msg_titles.no_selection"), "Please select an order to view details")
            return

        try:
            values = self.refunds_tree.item(selection[0])['values']
            if len(values) < 8:
                messagebox.showerror(_t("butcher.msg_titles.data_error"), "Order record is incomplete")
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

    def process_butcher_refund(self):
        """Process a refund with cash/card/student account options.

        Available to: Butcher staff and Admin users
        """
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("butcher.msg_titles.no_selection"), "Please select an order to refund")
            return

        try:
            values = self.refunds_tree.item(selection[0])['values']
            if len(values) < 8:
                messagebox.showerror(_t("butcher.msg_titles.data_error"), "Order record is incomplete")
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
            messagebox.showinfo(_t("butcher.msg_titles.already_refunded"), "This order has already been refunded")
            return

        if payment_status == 'pending':
            messagebox.showinfo(_t("butcher.msg_titles.cannot_refund"), "Cannot refund unpaid orders")
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
                    conn.execute('''
                        INSERT INTO unified_refunds
                        (source_type, reference_id, reference_type, amount, refund_method,
                         refund_reference, student_id, customer_name, refund_date, processed_by)
                        VALUES ('butcher', ?, 'order', ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                    ''', (str(order_id), amount, refund_method, refund_ref, customer_id, customer_name,
                          self.current_user.get('username', 'system')))

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
            messagebox.showerror(_t("butcher.msg_titles.refund_failed"), "Failed to process student account refund")

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
        from education_system.university_system.modules.domain.commerce.butcher.services.butcher_core import MEAT_CATEGORIES
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

            from education_system.university_system.modules.domain.commerce.butcher.services.butcher_core import ProductManager
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

            from education_system.university_system.modules.domain.commerce.butcher.services.butcher_core import ProductManager
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
            messagebox.showerror(_t("common.error"), _t("butcher.errors.invalid_selection"))

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
            from education_system.university_system.modules.domain.commerce.butcher.services.butcher_core import OrderManager

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
            messagebox.showwarning(_t("butcher.msg_titles.warning"), "Please select an order first")
            return

        try:
            item = self.orders_tree.item(selected[0])
            order_number = item['values'][0]

            from education_system.university_system.modules.domain.commerce.butcher.services.butcher_core import OrderManager
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

        from education_system.university_system.modules.domain.commerce.butcher.services.butcher_core import OrderManager, TransactionManager
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
            from education_system.university_system.infrastructure.email.email_service import send_email

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

            from education_system.university_system.modules.domain.commerce.butcher.services.butcher_core import TransactionManager
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
            from education_system.university_system.modules.domain.commerce.butcher.services.butcher_core import OrderManager
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
            from education_system.university_system.modules.domain.commerce.butcher.services.butcher_core import OrderManager
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
            messagebox.showwarning(_t("butcher.msg_titles.warning"), "Please select an order first")
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
                from education_system.university_system.modules.domain.commerce.butcher.services.butcher_core import OrderManager
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

            from education_system.university_system.modules.domain.commerce.butcher.services.butcher_core import ProductManager
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
            from education_system.university_system.modules.domain.commerce.butcher.services.butcher_core import ReportManager
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
            messagebox.showwarning(_t("common.warning"), "Email service not available")
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


def launch_butcher_gui(parent=None, auth=None):
    """Launch the Butcher Shop GUI"""
    return ButcherGUI(parent, auth)
