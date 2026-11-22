
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH
import time
import os
import re
import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import csv
from threading import Thread
import webbrowser
from tkinter import font

# Import i18n for language support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

try:
    from education_system.systems.university.plugins.campus_commerce.domain.services.shop_management import (
        auth, add_to_shopping_cart, browse_products, checkout_process,
        display_product_management_menu, display_shop_menu,
        get_customer_analytics, get_inventory_valuation, init_shop_db,
        print_product_labels, search_products, set_auth,
        toggle_discount_status, toggle_product_status, view_purchase_history
    )
except Exception:
    try:
        from shop_management import (
            auth, add_to_shopping_cart, browse_products, checkout_process,
            display_product_management_menu, display_shop_menu,
            get_customer_analytics, get_inventory_valuation, init_shop_db,
            print_product_labels, search_products, set_auth,
            toggle_discount_status, toggle_product_status, view_purchase_history
        )
    except Exception:
        # If running standalone, we'll define the essential fallback functions
        def get_customer_analytics():
            return None

        def get_inventory_valuation():
            return {'total_value': 0, 'product_count': 0, 'total_quantity': 0}

        def print_product_labels(product_ids=None):
            print("Label printing functionality not available")

        # Note: get_low_stock_items is implemented as a class method in UniversityShopGUI

# Import authentication - REQUIRED (no fallback for security)
from education_system.systems.university.infrastructure.auth import UserAuth, get_global_auth
from education_system.systems.university.infrastructure.shared_context import get_auth

# Import finance integration for student finance account payments
try:
    from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

# Initialize logger
logger = logging.getLogger(__name__)


def show_payment_methods_report(self, start_date, end_date):
    """Show payment methods analysis report"""
    # Clear report display
    for widget in self.report_display_frame.winfo_children():
        widget.destroy()

    try:
        # Get payment methods data
        payment_data = self.get_payment_methods_data(start_date, end_date)

        # Report title
        ttk.Label(self.report_display_frame, text=f"Payment Methods Analysis: {start_date} to {end_date}",
                 style='Heading.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 10))

        # Payment methods table
        payment_frame = ttk.Frame(self.report_display_frame)
        payment_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=10)
        payment_frame.columnconfigure(0, weight=1)
        payment_frame.rowconfigure(0, weight=1)

        columns = ('Payment Method', 'Transactions', 'Total Amount', 'Avg Transaction', 'Usage %', 'Revenue %')
        pay_tree = ttk.Treeview(payment_frame, columns=columns, show='headings', height=8)

        for col in columns:
            pay_tree.heading(col, text=col)

        pay_scrollbar = ttk.Scrollbar(payment_frame, orient='vertical', command=pay_tree.yview)
        pay_tree.configure(yscrollcommand=pay_scrollbar.set)

        pay_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        pay_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # Calculate totals for percentages
        total_transactions = sum(method['transaction_count'] for method in payment_data)
        total_amount = sum(method['total_amount'] for method in payment_data)

        # Populate payment data
        for method in payment_data:
            avg_transaction = method['total_amount'] / method['transaction_count'] if method['transaction_count'] > 0 else 0
            usage_pct = (method['transaction_count'] / total_transactions * 100) if total_transactions > 0 else 0
            revenue_pct = (method['total_amount'] / total_amount * 100) if total_amount > 0 else 0

            pay_tree.insert('', 'end', values=(
                method['payment_method'],
                method['transaction_count'],
                f"£{method['total_amount']:.2f}",
                f"£{avg_transaction:.2f}",
                f"{usage_pct:.1f}%",
                f"{revenue_pct:.1f}%"
            ))

    except Exception as e:
        ttk.Label(self.report_display_frame, text=f"Error loading payment methods: {e}",
                 style='Error.TLabel').grid(row=1, column=0)


def get_payment_methods_data(self, start_date, end_date):
    """Get payment methods data"""
    try:
        if 'get_connection' not in globals():
            return []

        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT payment_method,
                   COUNT(*) as transaction_count,
                   SUM(total_amount) as total_amount
            FROM transactions
            WHERE source_type = 'shop' AND DATE(created_at) BETWEEN ? AND ?
            GROUP BY payment_method
            ORDER BY total_amount DESC
        """, [start_date, end_date])

        methods = cursor.fetchall()
        conn.close()

        return [dict(method) for method in methods]

    except Exception:
        return []


def show_checkout(self):
    """Display checkout interface"""
    if not self.cart_items:
        messagebox.showwarning(_t('gui.operations.commerce.shop_management_gui.checkout_manager.dialogs.warning', default="Warning"), _t('gui.operations.commerce.shop_management_gui.checkout_manager.dialogs.cart_is_empty', default="Cart is empty"))
        return

    # Create checkout window
    checkout_window = tk.Toplevel(self.root)
    checkout_window.title(_t('gui.operations.commerce.shop_management_gui.checkout_manager.windows.checkout', default="Checkout"))
    checkout_window.geometry("600x500")
    checkout_window.resizable(False, False)

    # Make it modal
    checkout_window.transient(self.root)
    checkout_window.grab_set()

    main_frame = ttk.Frame(checkout_window, padding="20")
    main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    # Order summary
    summary_frame = ttk.LabelFrame(main_frame, text=_t('gui.operations.commerce.shop_management_gui.checkout_manager.labels.order_summary', default="Order Summary"), padding="10")
    summary_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

    total = 0
    for i, item in enumerate(self.cart_items):
        ttk.Label(summary_frame, text=f"{item['name']} x {item['quantity']}").grid(row=i, column=0, sticky=tk.W)
        ttk.Label(summary_frame, text=f"£{item['subtotal']:.2f}").grid(row=i, column=1, sticky=tk.E)
        total += item['subtotal']

    ttk.Separator(summary_frame, orient='horizontal').grid(row=len(self.cart_items), column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
    ttk.Label(summary_frame, text=_t('gui.operations.commerce.shop_management_gui.checkout_manager.labels.total', default="Total:"), font=('Arial', 12, 'bold')).grid(row=len(self.cart_items)+1, column=0, sticky=tk.W)
    ttk.Label(summary_frame, text=f"£{total:.2f}", font=('Arial', 12, 'bold')).grid(row=len(self.cart_items)+1, column=1, sticky=tk.E)

    summary_frame.columnconfigure(0, weight=1)

    # Payment method
    payment_frame = ttk.LabelFrame(main_frame, text=_t('gui.operations.commerce.shop_management_gui.checkout_manager.labels.payment_method', default="Payment Method"), padding="10")
    payment_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

    payment_var = tk.StringVar(value=_t('gui.operations.commerce.shop_management_gui.checkout_manager.values.credit_debit_card', default="Credit/Debit Card"))
    ttk.Radiobutton(payment_frame, text=_t('gui.operations.commerce.shop_management_gui.checkout_manager.buttons.credit_debit_card', default="Credit/Debit Card"), variable=payment_var,
                   value="Credit/Debit Card").grid(row=0, column=0, sticky=tk.W, pady=2)
    ttk.Radiobutton(payment_frame, text=_t('gui.operations.commerce.shop_management_gui.checkout_manager.buttons.student_account', default="Student Account"), variable=payment_var,
                   value="Student Account").grid(row=1, column=0, sticky=tk.W, pady=2)
    ttk.Radiobutton(payment_frame, text=_t('gui.operations.commerce.shop_management_gui.checkout_manager.buttons.cash', default="Cash"), variable=payment_var,
                   value="Cash").grid(row=2, column=0, sticky=tk.W, pady=2)

    # Finance system payment option removed - not needed for checkout
    # self.add_finance_payment_option_to_checkout(payment_frame, payment_var, row_index=3)

    # Customer info
    info_frame = ttk.LabelFrame(main_frame, text=_t('gui.operations.commerce.shop_management_gui.checkout_manager.labels.customer_information', default="Customer Information"), padding="10")
    info_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

    ttk.Label(info_frame, text=_t('gui.operations.commerce.shop_management_gui.checkout_manager.labels.name', default="Name:")).grid(row=0, column=0, sticky=tk.W, pady=2)
    name_var = tk.StringVar(value=self.current_user.get('username', ''))
    ttk.Entry(info_frame, textvariable=name_var, width=30).grid(row=0, column=1, padx=(10, 0), pady=2)

    ttk.Label(info_frame, text=_t('gui.operations.commerce.shop_management_gui.checkout_manager.labels.email', default="Email:")).grid(row=1, column=0, sticky=tk.W, pady=2)
    email_var = tk.StringVar(value=self.current_user.get('email', ''))
    ttk.Entry(info_frame, textvariable=email_var, width=30).grid(row=1, column=1, padx=(10, 0), pady=2)

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.grid(row=3, column=0, pady=20)

    def complete_checkout():
        try:
            # Process checkout
            selected_payment = payment_var.get()
            transaction_id = self.process_checkout(selected_payment, name_var.get(), email_var.get())

            checkout_window.destroy()
            self.cart_items.clear()

            # Show appropriate message based on payment method
            if selected_payment == "Finance System":
                messagebox.showinfo(_t('gui.operations.commerce.shop_management_gui.checkout_manager.dialogs.success', default="Success"),
                    f"Order created successfully!\n"
                    f"Transaction ID: {transaction_id}\n\n"
                    f"The Finance System will open for manual payment processing.\n"
                    f"Status: Pending Payment")
            else:
                messagebox.showinfo(_t('gui.operations.commerce.shop_management_gui.checkout_manager.dialogs.success', default="Success"), f"Order completed successfully!\nTransaction ID: {transaction_id}")

            self.show_order_history()

        except Exception as e:
            messagebox.showerror(_t('gui.operations.commerce.shop_management_gui.checkout_manager.dialogs.error', default="Error"), f"Checkout failed: {e}")

    ttk.Button(button_frame, text=_t('gui.operations.commerce.shop_management_gui.checkout_manager.buttons.complete_order', default="Complete Order"), command=complete_checkout,
              style='Success.TButton').grid(row=0, column=0, padx=5)
    ttk.Button(button_frame, text=_t('gui.operations.commerce.shop_management_gui.checkout_manager.buttons.cancel', default="Cancel"), command=checkout_window.destroy).grid(row=0, column=1, padx=5)


def process_checkout(self, payment_method, customer_name, customer_email):
    """Process the checkout and create transaction.

    The local write, the student-account debit and the Finance posting all
    happen in ``shop_management.sales.record_shop_sale`` (shared with the
    CLI); this method only resolves the user and reports the outcome.
    """
    from education_system.systems.university.plugins.campus_commerce.domain.services.shop_management.sales import (
        record_shop_sale,
    )
    try:
        total = sum(item['subtotal'] for item in self.cart_items)

        # Identifier the finance hub keys the account on: student_id, else
        # username, else the student record matched by email.
        user_identifier = self.current_user.get('student_id') or self.current_user.get('username', '')
        if not user_identifier and self.current_user.get('email'):
            with get_connection() as conn:
                row = conn.execute(
                    'SELECT student_id FROM students WHERE email_address = ? LIMIT 1',
                    (self.current_user.get('email', ''),)).fetchone()
                if row:
                    user_identifier = row[0]

        if payment_method == "Student Account":
            if not user_identifier:
                raise Exception("Unable to identify user account. Please contact administration.")
            current_balance = get_student_finance_account_balance(user_identifier) if FINANCE_ACCOUNT_AVAILABLE else None
            if current_balance is None:
                raise Exception(f"No finance account found for user '{user_identifier}'. Please contact administration.")
            if current_balance < total:
                messagebox.showerror(_t('gui.operations.commerce.shop_management_gui.checkout_manager.dialogs.insufficient_balance', default="Insufficient Balance"),
                    f"Student finance account balance is insufficient.\n\n"
                    f"Current Balance: £{current_balance:.2f}\n"
                    f"Required Amount: £{total:.2f}\n\n"
                    f"Please top up the account or use a different payment method.")
                raise Exception("Student account payment failed")

        outcome = record_shop_sale(
            self.current_user.get('id', 1),
            [{'product_id': it['product_id'], 'quantity': it['quantity'], 'price': it['price']}
             for it in self.cart_items],
            total,
            payment_method,
            student_id=self.current_user.get('student_id'),
            finance_user_id=user_identifier or None,
            processed_by=self.current_user.get('username', 'System'),
            notes=f"GUI Checkout - {customer_name}",
        )
        transaction_id = outcome['transaction_id']
        if not transaction_id:
            raise Exception(outcome.get('error') or "Checkout failed")
        if outcome.get('account_result'):
            self._last_finance_payment_result = outcome['account_result']

        # Open finance GUI for manual payment if selected
        if payment_method == "Finance System":
            logger.info(f"Opening finance system for manual payment of transaction {transaction_id}")
            # Schedule opening finance GUI after a short delay to allow checkout window to close
            self.root.after(500, lambda: self.open_finance_gui_for_payment(transaction_id, total))

        # Send order confirmation email
        self._send_shop_order_confirmation_email(transaction_id, customer_name, customer_email, total, payment_method)

        return transaction_id

    except Exception as e:
        raise Exception(f"Checkout processing failed: {e}")


def open_finance_gui_for_payment(self, transaction_id=None, amount=None):
    """Open finance GUI for payment processing"""
    try:
        from education_system.systems.university.domains.finance.interfaces.gui.finance import FinanceGUI

        finance_window = tk.Toplevel(self.root)
        finance_window.title(_t('gui.operations.commerce.shop_management_gui.checkout_manager.windows.finance_system_shop_payment', default="Finance System - Shop Payment"))
        finance_window.geometry("1000x700")

        # Initialize finance GUI
        finance_gui = FinanceGUI(finance_window, auth=self.auth if hasattr(self, 'auth') else None)

        # Pre-populate shop payment information if methods exist
        if transaction_id and amount and hasattr(finance_gui, 'prepopulate_shop_payment'):
            finance_gui.prepopulate_shop_payment(transaction_id, amount)

        messagebox.showinfo(_t('gui.operations.commerce.shop_management_gui.checkout_manager.dialogs.finance_system', default="Finance System"), _t('gui.operations.commerce.shop_management_gui.checkout_manager.dialogs.finance_system_opened_for_payment_processing', default="Finance system opened for payment processing"))

    except ImportError:
        messagebox.showerror(_t('gui.operations.commerce.shop_management_gui.checkout_manager.dialogs.error', default="Error"), _t('gui.operations.commerce.shop_management_gui.checkout_manager.dialogs.finance_system_is_not_available', default="Finance system is not available"))
    except Exception as e:
        messagebox.showerror(_t('gui.operations.commerce.shop_management_gui.checkout_manager.dialogs.error', default="Error"), f"Could not open finance system: {e}")


def add_finance_payment_option_to_checkout(self, payment_frame, payment_var, row_index=3):
    """
    Add finance system payment option to checkout dialog

    Args:
        payment_frame: The ttk.Frame containing payment options
        payment_var: The tk.StringVar tracking selected payment method
        row_index: The row index to place the new option (default: 3)

    Returns:
        ttk.Radiobutton: The created finance system payment option widget

    Example:
        In show_checkout method:
        >>> finance_option = self.add_finance_payment_option_to_checkout(
        ...     payment_frame, payment_var, row_index=3
        ... )
    """
    try:
        # Check if finance system is available
        finance_available = False
        try:
            from education_system.systems.university.domains.finance.interfaces.gui.finance import FinanceGUI
            finance_available = True
        except ImportError:
            logger.warning("Finance system not available for checkout integration")
            return None

        if not finance_available:
            return None

        # Create finance system payment option
        finance_option = ttk.Radiobutton(
            payment_frame,
            text=_t('gui.operations.commerce.shop_management_gui.checkout_manager.buttons.finance_system_manual', default="Finance System (Manual)"),
            variable=payment_var,
            value="Finance System"
        )
        finance_option.grid(row=row_index, column=0, sticky=tk.W, pady=2)

        # Add help text
        help_text = ttk.Label(
            payment_frame,
            text=_t('gui.operations.commerce.shop_management_gui.checkout_manager.labels.opens_finance_system_for_manual_payment_processing', default="  Opens finance system for manual payment processing"),
            font=('Arial', 8),
            foreground='gray'
        )
        help_text.grid(row=row_index + 1, column=0, sticky=tk.W, padx=(20, 0))

        logger.info("Finance system payment option added to checkout")
        return finance_option

    except Exception as e:
        logger.error(f"Could not add finance payment option: {e}")
        return None


def notify_shop_finance_gui(self, transaction_id, amount, method, refund_ref, student_id):
    """Notify finance GUI about the refund"""
    try:
        from education_system.systems.university.infrastructure.database.db import transaction

        with transaction() as conn:
            cursor = conn.cursor()

            # Refund already recorded in unified_refunds table
            logger.info(f"[Shop] Refund {refund_ref} recorded in unified_refunds")

    except Exception as e:
        logger.error(f"Error notifying finance GUI: {e}")


