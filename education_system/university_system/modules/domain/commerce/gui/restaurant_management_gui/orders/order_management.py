from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import threading
import sys
import os

# Import centralized authentication system
# Import authentication - REQUIRED (no fallback for security)
from education_system.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Import finance integration for student finance account payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

# Import custom exceptions for proper error handling
from education_system.university_system.core.exceptions import (
    DatabaseError,
    DatabaseConnectionError,
    QueryError,
    ValidationError,
    InvalidInputError
)

# Attempt to import the enhanced restaurant DB initializer from the CLI version.
# If available, calling this will create the full set of tables defined in
# services/restaurant_management.py. Alias the import to avoid naming
# conflicts with this module's own init_db function.
try:
    from education_system.university_system.modules.domain.commerce.services.restaurant_management import init_db as init_enhanced_restaurant_db
except ImportError:
    init_enhanced_restaurant_db = None

# Database configuration
# Always point to the central student_records.db in refactored/db_files.
try:
    from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH as DATABASE_FILE
except ImportError:
    # Fallback to local file if refactored.database.db is unavailable
    DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import get_db_connection from main_gui
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.core.main_gui import get_db_connection


def view_orders_gui(self):
    """Display orders in the treeview"""
    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror(_t("common.error"), _t("common.database_error", error="Connection failed"))
            return

        cursor = conn.cursor()
        cursor.execute('''
            SELECT o.order_id, COALESCE(c.name, 'Walk-in'), o.order_date,
                   o.total_amount, o.order_status, o.payment_method
            FROM orders o
            LEFT JOIN restaurant_customers c ON o.customer_id = c.customer_id
            ORDER BY o.order_date DESC
            LIMIT 50
        ''')
        orders = cursor.fetchall()

        for item in self.orders_tree.get_children():
            self.orders_tree.delete(item)

        for order in orders:
            order_time = order[2][:16] if order[2] else 'N/A'

            self.orders_tree.insert('', 'end', values=(
                order[0], order[1], order_time, f"£{order[3]:.2f}",
                order[4], order[5] or 'N/A'
            ))

        conn.close()
        messagebox.showinfo(_t("common.success"), _t("restaurant.orders.loaded_count", count=len(orders)))

    except sqlite3.Error as e:
        messagebox.showerror(_t("common.error"), _t("restaurant.orders.load_failed", error=str(e)))

def update_order_status_dialog(self):
    """Show dialog to update order status"""
    selection = self.orders_tree.selection()
    if not selection:
        messagebox.showwarning(_t("common.warning"), _t("restaurant.orders.select_to_update"))
        return

    item_values = self.orders_tree.item(selection[0])['values']
    order_id = item_values[0]

    dialog = OrderStatusDialog(self.root, order_id)
    if dialog.result:
        self.view_orders_gui()

def process_payment_dialog(self):
    """Show payment processing dialog"""
    selection = self.orders_tree.selection()
    if not selection:
        messagebox.showwarning(_t("common.warning"), _t("restaurant.orders.select_for_payment"))
        return

    item_values = self.orders_tree.item(selection[0])['values']
    order_id = item_values[0]

    dialog = PaymentDialog(self.root, order_id)
    if dialog.result:
        self.view_orders_gui()

def show_order_analytics(self):
    """Show order analytics"""
    try:
        analytics_window = tk.Toplevel(self.root)
        analytics_window.title(_t("restaurant.orders.analytics_title"))
        analytics_window.geometry("800x600")

        text_area = ScrolledText(analytics_window, height=30, width=80)
        text_area.pack(fill='both', expand=True, padx=10, pady=10)

        analytics_text = self.generate_order_analytics()
        text_area.insert('1.0', analytics_text)
        text_area.config(state='disabled')

    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror(_t("common.error"), _t("restaurant.orders.analytics_failed", error=str(e)))

def generate_order_analytics(self):
    """Generate order analytics text"""
    try:
        conn = get_db_connection()
        if not conn:
            return _t("common.database_error", error="Connection failed")

        cursor = conn.cursor()

        text = _t("restaurant.orders.analytics_header") + "\n"
        text += "=" * 50 + "\n\n"

        cursor.execute('''
            SELECT COUNT(*) as total_orders, AVG(total_amount) as avg_value
            FROM orders
            WHERE status = 'Completed'
        ''')

        stats = cursor.fetchone()

        if stats:
            text += _t("restaurant.orders.total_orders", count=stats[0]) + "\n"
            text += _t("restaurant.orders.avg_order_value", value=f"£{stats[1]:.2f}") + "\n" if stats[1] else _t("common.na") + "\n"

        conn.close()
        return text

    except sqlite3.Error as e:
        return _t("restaurant.orders.analytics_error", error=str(e))

class OrderStatusDialog:
    def __init__(self, parent, order_id):
        self.result = False
        self.order_id = order_id

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("restaurant.orders.update_status_title"))
        self.dialog.geometry("300x200")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=_t("restaurant.orders.order_id_label", id=self.order_id)).pack(pady=10)
        ttk.Label(main_frame, text=_t("restaurant.orders.new_status")).pack(pady=5)

        self.status_var = tk.StringVar()
        status_combo = ttk.Combobox(main_frame, textvariable=self.status_var,
                                   values=['Pending', 'Preparing', 'Ready', 'Completed', 'Cancelled'])
        status_combo.pack(pady=10)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text=_t("common.update"), command=self.update_status).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_t("common.cancel"), command=self.cancel).pack(side='left', padx=10)

    def update_status(self):
        """Update the order status"""
        if not self.status_var.get():
            messagebox.showerror(_t("common.error"), _t("restaurant.orders.select_status"))
            return

        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE orders SET order_status = ? WHERE order_id = ?',
                              (self.status_var.get(), self.order_id))
                conn.commit()
                conn.close()

            self.result = True
            self.dialog.destroy()
            messagebox.showinfo(_t("common.success"), _t("restaurant.orders.status_updated"))

        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("restaurant.orders.update_failed", error=str(e)))

    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy()


class PaymentDialog:
    """Dialog for processing payment for an existing order"""

    def __init__(self, parent, order_id):
        self.result = False
        self.order_id = order_id
        self.order_total = 0

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Process Payment")
        self.dialog.geometry("450x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.load_order_details()
        self.create_widgets()

    def load_order_details(self):
        """Load order details from database"""
        try:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                self.dialog.destroy()
                return

            cursor = conn.cursor()
            cursor.execute('''
                SELECT total_amount, order_status, payment_method
                FROM orders
                WHERE order_id = ?
            ''', (self.order_id,))

            result = cursor.fetchone()
            conn.close()

            if result:
                self.order_total = result[0] or 0
                self.order_status = result[1] or 'Pending'
                self.current_payment_method = result[2]

                # Check if already paid
                if self.order_status == 'Paid' or self.current_payment_method:
                    messagebox.showinfo("Already Paid",
                                      f"Order #{self.order_id} has already been paid.\n"
                                      f"Payment method: {self.current_payment_method}")
                    self.dialog.destroy()
            else:
                messagebox.showerror("Error", f"Order #{self.order_id} not found")
                self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load order: {e}")
            self.dialog.destroy()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Order info
        ttk.Label(main_frame, text=f"Order #{self.order_id}",
                 font=('Arial', 12, 'bold')).pack(pady=5)
        ttk.Label(main_frame, text=f"Total Amount: £{self.order_total:.2f}",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        # Payment method selection
        ttk.Label(main_frame, text="Select Payment Method:",
                 font=('Arial', 10, 'bold')).pack(pady=(10, 5))

        self.payment_var = tk.StringVar(value="Cash")

        payment_methods = [
            ("Cash", "Cash"),
            ("Card", "Card"),
            ("Finance Account", "Finance Account")
        ]

        for text, value in payment_methods:
            ttk.Radiobutton(main_frame, text=text, variable=self.payment_var,
                          value=value).pack(anchor=tk.W, pady=3, padx=20)

        # Student account balance (if applicable)
        if FINANCE_ACCOUNT_AVAILABLE:
            balance_frame = ttk.Frame(main_frame)
            balance_frame.pack(pady=10)

            ttk.Button(balance_frame, text="Check Student Balance",
                      command=self.check_student_balance).pack()

            self.balance_label = ttk.Label(balance_frame, text="",
                                          font=('Arial', 9))
            self.balance_label.pack(pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Process Payment",
                  command=self.process_payment).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Cancel",
                  command=self.dialog.destroy).pack(side=tk.LEFT, padx=10)

    def check_student_balance(self):
        """Check student account balance"""
        if not FINANCE_ACCOUNT_AVAILABLE:
            messagebox.showwarning("Not Available",
                                 "Student finance integration not available")
            return

        student_id = simpledialog.askstring("Student ID",
                                           "Enter Student ID to check balance:")
        if not student_id:
            return

        try:
            balance = get_student_finance_account_balance(student_id)
            if balance is not None:
                self.balance_label.config(
                    text=f"Student {student_id} Balance: £{balance:.2f}",
                    foreground='green' if balance >= self.order_total else 'red'
                )
                self.last_checked_student_id = student_id
            else:
                self.balance_label.config(
                    text=f"Student {student_id} - No account found",
                    foreground='red'
                )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to check balance: {e}")

    def process_payment(self):
        """Process the payment"""
        payment_method = self.payment_var.get()

        # Confirm payment
        if not messagebox.askyesno("Confirm Payment",
                                  f"Process payment of £{self.order_total:.2f}\n"
                                  f"Payment method: {payment_method}?"):
            return

        try:
            # Handle student account payment
            if payment_method == "Finance Account":
                if not FINANCE_ACCOUNT_AVAILABLE:
                    messagebox.showerror("Error",
                                       "Student finance integration not available")
                    return

                # Get student ID
                student_id = getattr(self, 'last_checked_student_id', None)
                if not student_id:
                    student_id = simpledialog.askstring("Student ID",
                                                       "Enter Student ID for payment:")
                    if not student_id:
                        return

                # Process student account payment
                result = process_student_finance_account_payment(
                    student_id=student_id,
                    amount=self.order_total,
                    description=f"Restaurant Order #{self.order_id}",
                    transaction_source='Restaurant',
                    transaction_ref=f"ORDER-{self.order_id}",
                    processed_by='restaurant_system'
                )

                if not result.get('success'):
                    messagebox.showerror("Payment Failed",
                                       result.get('message', 'Payment failed'))
                    return

            # Update order in database
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return

            cursor = conn.cursor()
            cursor.execute('''
                UPDATE orders
                SET payment_method = ?, order_status = 'Paid'
                WHERE order_id = ?
            ''', (payment_method, self.order_id))

            conn.commit()
            conn.close()

            self.result = True
            self.dialog.destroy()

            messagebox.showinfo("Success",
                              f"Payment of £{self.order_total:.2f} processed successfully!\n\n"
                              f"Order #{self.order_id}\n"
                              f"Payment method: {payment_method}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to process payment:\n{e}")

