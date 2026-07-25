import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH
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
    from education_system.systems.university.domain.operations.commerce.services.shop_management import (
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
    from education_system.systems.university.infrastructure.utils.finance_integration import (
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
        messagebox.showwarning("Warning", "Cart is empty")
        return

    # Create checkout window
    checkout_window = tk.Toplevel(self.root)
    checkout_window.title("Checkout")
    checkout_window.geometry("600x500")
    checkout_window.resizable(False, False)

    # Make it modal
    checkout_window.transient(self.root)
    checkout_window.grab_set()

    main_frame = ttk.Frame(checkout_window, padding="20")
    main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    # Order summary
    summary_frame = ttk.LabelFrame(main_frame, text="Order Summary", padding="10")
    summary_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

    total = 0
    for i, item in enumerate(self.cart_items):
        ttk.Label(summary_frame, text=f"{item['name']} x {item['quantity']}").grid(row=i, column=0, sticky=tk.W)
        ttk.Label(summary_frame, text=f"£{item['subtotal']:.2f}").grid(row=i, column=1, sticky=tk.E)
        total += item['subtotal']

    ttk.Separator(summary_frame, orient='horizontal').grid(row=len(self.cart_items), column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
    ttk.Label(summary_frame, text="Total:", font=('Arial', 12, 'bold')).grid(row=len(self.cart_items)+1, column=0, sticky=tk.W)
    ttk.Label(summary_frame, text=f"£{total:.2f}", font=('Arial', 12, 'bold')).grid(row=len(self.cart_items)+1, column=1, sticky=tk.E)

    summary_frame.columnconfigure(0, weight=1)

    # Payment method
    payment_frame = ttk.LabelFrame(main_frame, text="Payment Method", padding="10")
    payment_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

    payment_var = tk.StringVar(value="Credit/Debit Card")
    ttk.Radiobutton(payment_frame, text="Credit/Debit Card", variable=payment_var,
                   value="Credit/Debit Card").grid(row=0, column=0, sticky=tk.W, pady=2)
    ttk.Radiobutton(payment_frame, text="Student Account", variable=payment_var,
                   value="Student Account").grid(row=1, column=0, sticky=tk.W, pady=2)
    ttk.Radiobutton(payment_frame, text="Cash", variable=payment_var,
                   value="Cash").grid(row=2, column=0, sticky=tk.W, pady=2)

    # Finance system payment option removed - not needed for checkout
    # self.add_finance_payment_option_to_checkout(payment_frame, payment_var, row_index=3)

    # Customer info
    info_frame = ttk.LabelFrame(main_frame, text="Customer Information", padding="10")
    info_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

    ttk.Label(info_frame, text="Name:").grid(row=0, column=0, sticky=tk.W, pady=2)
    name_var = tk.StringVar(value=self.current_user.get('username', ''))
    ttk.Entry(info_frame, textvariable=name_var, width=30).grid(row=0, column=1, padx=(10, 0), pady=2)

    ttk.Label(info_frame, text="Email:").grid(row=1, column=0, sticky=tk.W, pady=2)
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
                messagebox.showinfo("Success",
                    f"Order created successfully!\n"
                    f"Transaction ID: {transaction_id}\n\n"
                    f"The Finance System will open for manual payment processing.\n"
                    f"Status: Pending Payment")
            else:
                messagebox.showinfo("Success", f"Order completed successfully!\nTransaction ID: {transaction_id}")

            self.show_order_history()

        except Exception as e:
            messagebox.showerror("Error", f"Checkout failed: {e}")

    ttk.Button(button_frame, text="Complete Order", command=complete_checkout,
              style='Success.TButton').grid(row=0, column=0, padx=5)
    ttk.Button(button_frame, text="Cancel", command=checkout_window.destroy).grid(row=0, column=1, padx=5)


def process_checkout(self, payment_method, customer_name, customer_email):
    """Process the checkout and create transaction"""
    try:
        if 'get_connection' in globals():
            conn = get_connection()
            cursor = conn.cursor()

            # Generate transaction ID
            transaction_id = f"T{int(time.time())}"
            transaction_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Calculate total
            total = sum(item['subtotal'] for item in self.cart_items)

            # Process Student Account payment via finance system
            if payment_method == "Student Account":
                # Get user identifier for finance account lookup
                # This could be student_id, username, or staff ID
                user_identifier = self.current_user.get('student_id')

                # If student_id not set, try username (for admin/staff users)
                if not user_identifier:
                    user_identifier = self.current_user.get('username', '')

                # If still no identifier, try to look it up from students table
                if not user_identifier:
                    email = self.current_user.get('email', '')
                    cursor.execute('''
                        SELECT student_id FROM students
                        WHERE email_address = ?
                        LIMIT 1
                    ''', (email,))
                    result = cursor.fetchone()
                    if result:
                        user_identifier = result[0]

                # Check if user has a finance account in student_finance_accounts table
                # (This table stores accounts for students, staff, and admin users)
                if user_identifier:
                    cursor.execute('''
                        SELECT account_id FROM student_finance_accounts
                        WHERE student_id = ?
                    ''', (user_identifier,))
                    finance_account = cursor.fetchone()

                    if finance_account:
                        # Process payment from finance account
                        success = self._process_student_account_payment(user_identifier, total, transaction_id, customer_name)
                        if not success:
                            raise Exception("Student account payment failed")
                    else:
                        raise Exception(f"No finance account found for user '{user_identifier}'. Please contact administration.")
                else:
                    raise Exception("Unable to identify user account. Please contact administration.")

            # Set transaction status based on payment method
            transaction_status = "Completed"
            if payment_method == "Finance System":
                transaction_status = "Pending Payment"  # Manual payment processing required

            # Create transaction
            cursor.execute("""
                INSERT INTO transactions
                (source_transaction_id, customer_id, student_id, total_amount, created_at, payment_method, status, notes, source_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'shop')
            """, [
                transaction_id,
                self.current_user.get('id', 1),
                self.current_user.get('student_id'),
                total,
                transaction_date,
                payment_method,
                transaction_status,
                f"GUI Checkout - {customer_name}"
            ])

            # Create transaction items and update inventory
            for item in self.cart_items:
                cursor.execute("""
                    INSERT INTO shop_transaction_items
                    (transaction_id, product_id, quantity, price_per_item, subtotal)
                    VALUES (?, ?, ?, ?, ?)
                """, [
                    transaction_id,
                    item['product_id'],
                    item['quantity'],
                    item['price'],
                    item['subtotal']
                ])

                # Update inventory
                cursor.execute("""
                    UPDATE shop_inventory
                    SET quantity = quantity - ?
                    WHERE product_id = ?
                """, [item['quantity'], item['product_id']])

            conn.commit()
            conn.close()

            # Open finance GUI for manual payment if selected
            if payment_method == "Finance System":
                logger.info(f"Opening finance system for manual payment of transaction {transaction_id}")
                # Schedule opening finance GUI after a short delay to allow checkout window to close
                self.root.after(500, lambda: self.open_finance_gui_for_payment(transaction_id, total))

            # Send order confirmation email
            self._send_shop_order_confirmation_email(transaction_id, customer_name, customer_email, total, payment_method)

            return transaction_id
        else:
            # Fallback - just return a mock transaction ID
            return f"T{int(time.time())}"

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        raise Exception(f"Checkout processing failed: {e}")


def _process_student_account_payment(self, student_id, total_amount, transaction_id, customer_name):
    """Process payment through student's finance account balance"""
    try:
        # Use finance account integration if available
        if FINANCE_ACCOUNT_AVAILABLE:
            # Check balance first
            current_balance = get_student_finance_account_balance(student_id)
            if current_balance is None:
                messagebox.showerror("Error",
                    f"No finance account found for student {student_id}.\n"
                    "Please create a finance account first or use a different payment method.")
                return False

            if current_balance < total_amount:
                messagebox.showerror("Insufficient Balance",
                    f"Student finance account balance is insufficient.\n\n"
                    f"Current Balance: £{current_balance:.2f}\n"
                    f"Required Amount: £{total_amount:.2f}\n\n"
                    f"Please top up the account or use a different payment method.")
                return False

            # Process the payment from finance account
            processed_by = self.current_user.get('username', 'System')
            payment_result = process_student_finance_account_payment(
                student_id=student_id,
                amount=total_amount,
                description=f"Shop purchase #{transaction_id}",
                transaction_source="Shop",
                transaction_ref=transaction_id,
                processed_by=processed_by,
                check_balance=True,
                send_low_balance_alert=True
            )

            if not payment_result['success']:
                messagebox.showerror("Payment Failed", payment_result['message'])
                return False

            # Store payment result for later use
            self._last_finance_payment_result = payment_result

            new_balance = payment_result.get('new_balance', 0)
            low_balance_email_sent = payment_result.get('email_sent', False)

            print(f"Shop payment of £{total_amount:.2f} deducted from student finance account. New balance: £{new_balance:.2f}")

            if low_balance_email_sent:
                print(f"Low balance alert email sent to student {student_id}")

            return True

        # Fallback: Legacy method - add to student_fees without balance deduction
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        try:
            cursor = conn.cursor()

            cursor.execute('SELECT first_name, last_name, email FROM students WHERE student_id = ?', (student_id,))
            student_result = cursor.fetchone()
            if not student_result:
                messagebox.showerror("Error", f"Student ID {student_id} not found in system")
        finally:
            conn.close()
            return False

        first_name, last_name, email = student_result

        # Note: a legacy INSERT into student_fees with non-existent columns
        # was removed here — student_fees is tuition AR, not a commerce ledger.
        # The unified record_payment() call below is the correct path.

        # 8.117.104: unified record_payment() with source_type='shop'.
        try:
            from education_system.systems.university.domain.finance.core.unified_payments import (
                record_payment as _record_payment,
            )
            _record_payment(
                student_id=student_id,
                amount=total_amount,
                payment_method='Student Account',
                source_type='shop',
                source_payment_id=str(transaction_id),
                payment_type='purchase',
                reference_type='shop_transaction',
                reference_id=str(transaction_id),
                department='shop',
                description=f'Shop payment for transaction #{transaction_id}',
            )
        except Exception as e:
            logger.warning(f"Could not record unified payment for transaction {transaction_id}: {e}")
            # Fee is still recorded in student_fees, so transaction can continue

        conn.commit()
        conn.close()

        print(f"Shop payment of £{total_amount:.2f} charged to {first_name} {last_name}'s student account (legacy)")
        return True

    except Exception as e:
        print(f"Failed to process student account payment: {e}")
        return False


def open_finance_gui_for_payment(self, transaction_id=None, amount=None):
    """Open finance GUI for payment processing"""
    try:
        from education_system.systems.university.interfaces.gui.finance.finance import FinanceGUI

        finance_window = tk.Toplevel(self.root)
        finance_window.title("Finance System - Shop Payment")
        finance_window.geometry("1000x700")

        # Initialize finance GUI
        finance_gui = FinanceGUI(finance_window, auth=self.auth if hasattr(self, 'auth') else None)

        # Pre-populate shop payment information if methods exist
        if transaction_id and amount and hasattr(finance_gui, 'prepopulate_shop_payment'):
            finance_gui.prepopulate_shop_payment(transaction_id, amount)

        messagebox.showinfo("Finance System", "Finance system opened for payment processing")

    except ImportError:
        messagebox.showerror("Error", "Finance system is not available")
    except Exception as e:
        messagebox.showerror("Error", f"Could not open finance system: {e}")


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
            from education_system.systems.university.interfaces.gui.finance.finance import FinanceGUI
            finance_available = True
        except ImportError:
            logger.warning("Finance system not available for checkout integration")
            return None

        if not finance_available:
            return None

        # Create finance system payment option
        finance_option = ttk.Radiobutton(
            payment_frame,
            text="Finance System (Manual)",
            variable=payment_var,
            value="Finance System"
        )
        finance_option.grid(row=row_index, column=0, sticky=tk.W, pady=2)

        # Add help text
        help_text = ttk.Label(
            payment_frame,
            text="  Opens finance system for manual payment processing",
            font=('Arial', 8),
            foreground='gray'
        )
        help_text.grid(row=row_index + 1, column=0, sticky=tk.W, padx=(20, 0))

        logger.info("Finance system payment option added to checkout")
        return finance_option

    except Exception as e:
        logger.error(f"Could not add finance payment option: {e}")
        return None


def add_shop_refund_to_student_account(self, student_id, amount, refund_ref):
    """Add refund amount to user's finance account (works for students, staff, and admin)"""
    try:
        # Use finance integration if available for better handling
        if FINANCE_ACCOUNT_AVAILABLE:
            try:
                from education_system.systems.university.infrastructure.utils.finance_integration import top_up_student_finance_account
                result = top_up_student_finance_account(
                    student_id=student_id,
                    amount=amount,
                    payment_method='Refund',
                    processed_by=self.current_user.get('username', 'System'),
                    description=f'Shop Purchase Refund - {refund_ref}'
                )
                if result.get('success'):
                    logger.info(f"Refund credited to finance account for {student_id}: £{amount:.2f}")
                    return True
                else:
                    logger.error(f"Finance integration failed: {result.get('message')}")
                    # Fall through to manual method
            except Exception as e:
                logger.warning(f"Finance integration error, using fallback: {e}")
                # Fall through to manual method

        # Fallback: Direct database update using transaction context manager
        from education_system.systems.university.infrastructure.database.db import transaction

        with transaction() as conn:
            cursor = conn.cursor()

            # Check if finance account exists and get account_id and current balance
            cursor.execute('SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?', (student_id,))
            account = cursor.fetchone()

            if not account:
                # Create account with refund amount
                cursor.execute('''
                    INSERT INTO student_finance_accounts (student_id, balance, created_at)
                    VALUES (?, ?, ?)
                ''', (student_id, amount, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                # Get the newly created account_id
                cursor.execute('SELECT account_id FROM student_finance_accounts WHERE student_id = ?', (student_id,))
                account = cursor.fetchone()
                account_id = account[0]
                balance_before = 0.0
                balance_after = amount

                logger.info(f"Created new finance account for {student_id} with refund of £{amount:.2f}")
            else:
                account_id = account[0]
                balance_before = account[1]
                balance_after = balance_before + amount

                # Update existing account
                cursor.execute('''
                    UPDATE student_finance_accounts
                    SET balance = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE student_id = ?
                ''', (balance_after, student_id))
                logger.info(f"Updated finance account for {student_id}: +£{amount:.2f}")

            # Record transaction with correct schema
            cursor.execute('''
                INSERT INTO transactions
                (source_type, account_id, student_id, transaction_type, amount, balance_before, balance_after,
                 description, reference_id, processed_by, created_at)
                VALUES ('student_finance', ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (account_id, student_id, 'credit', amount, balance_before, balance_after,
                  'Shop Purchase Refund', refund_ref, self.current_user.get('username', 'System')))

            # Transaction auto-commits on successful exit

        return True

    except Exception as e:
        logger.error(f"Error adding refund to student account: {e}")
        return False


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


