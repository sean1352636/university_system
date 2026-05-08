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
from education_system.university_system.modules.shared.utils.i18n import (
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
from education_system.university_system.infrastructure.exceptions import (
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


def ensure_payment_columns():
    """Ensure tip_amount and discount_amount columns exist in orders table"""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Check if columns exist
        cursor.execute("PRAGMA table_info(orders)")
        columns = [row[1] for row in cursor.fetchall()]

        # Add tip_amount if missing
        if 'tip_amount' not in columns:
            cursor.execute('''
                ALTER TABLE orders
                ADD COLUMN tip_amount REAL DEFAULT 0
            ''')
            print("✓ Added tip_amount column to orders")

        # Add discount_amount if missing
        if 'discount_amount' not in columns:
            cursor.execute('''
                ALTER TABLE orders
                ADD COLUMN discount_amount REAL DEFAULT 0
            ''')
            print("✓ Added discount_amount column to orders")

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(f"✗ Error ensuring payment columns: {e}")
        return False


def add_tip(self):
    """Add tip to completed order"""
    # Ensure columns exist
    ensure_payment_columns()
    """Add tip to completed order"""
    selection = self.orders_tree.selection()
    if not selection:
        messagebox.showwarning("No Selection", "Please select an order to add a tip")
        return
    item = self.orders_tree.item(selection[0])
    order_id = item['values'][0]
    # Create tip dialog
    tip_dialog = tk.Toplevel(self.root)
    tip_dialog.title("Add Tip")
    tip_dialog.geometry("400x300")
    tip_dialog.transient(self.root)
    tip_dialog.grab_set()
    main_frame = ttk.Frame(tip_dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text=f"Add Tip to Order #{order_id}",
             font=('Arial', 12, 'bold')).pack(pady=10)
    # Get current order details
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT total_amount, tip_amount, order_status
                FROM orders
                WHERE order_id = ?
            ''', (order_id,))
            order_data = cursor.fetchone()
            conn.close()
            if not order_data:
                messagebox.showerror("Error", "Order not found")
                tip_dialog.destroy()
                return
            current_total, current_tip, order_status_val = order_data
            if order_status_val != 'Paid':
                messagebox.showwarning("Cannot Add Tip", "Order must be paid before adding a tip")
                tip_dialog.destroy()
                return
            # Display current info
            info_frame = ttk.LabelFrame(main_frame, text="Order Information", padding=10)
            info_frame.pack(fill='x', pady=10)
            ttk.Label(info_frame, text=f"Current Total: £{current_total:.2f}").pack(anchor='w')
            ttk.Label(info_frame, text=f"Current Tip: £{current_tip or 0:.2f}").pack(anchor='w')
            # Tip entry
            tip_frame = ttk.LabelFrame(main_frame, text="Add Tip", padding=10)
            tip_frame.pack(fill='x', pady=10)
            ttk.Label(tip_frame, text="Tip Amount (£):").grid(row=0, column=0, sticky='w', pady=5)
            tip_amount_var = tk.DoubleVar(value=0.0)
            tip_entry = ttk.Entry(tip_frame, textvariable=tip_amount_var, width=20)
            tip_entry.grid(row=0, column=1, pady=5, padx=5)
            # Quick tip buttons
            quick_frame = ttk.Frame(tip_frame)
            quick_frame.grid(row=1, column=0, columnspan=2, pady=10)
            ttk.Label(quick_frame, text="Quick Select:").pack(side='left', padx=5)
            ttk.Button(quick_frame, text="10%",
                      command=lambda: tip_amount_var.set(round(current_total * 0.10, 2))).pack(side='left', padx=2)
            ttk.Button(quick_frame, text="15%",
                      command=lambda: tip_amount_var.set(round(current_total * 0.15, 2))).pack(side='left', padx=2)
            ttk.Button(quick_frame, text="20%",
                      command=lambda: tip_amount_var.set(round(current_total * 0.20, 2))).pack(side='left', padx=2)
            def save_tip():
                tip_amount = tip_amount_var.get()
                if tip_amount <= 0:
                    messagebox.showwarning("Invalid Amount", "Tip amount must be greater than 0")
                    return
                try:
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        new_tip_total = (current_tip or 0) + tip_amount
                        new_total = current_total + tip_amount
                        cursor.execute('''
                            UPDATE orders
                            SET tip_amount = ?, total_amount = ?
                            WHERE order_id = ?
                        ''', (new_tip_total, new_total, order_id))
                        conn.commit()
                        conn.close()
                        messagebox.showinfo("Success", f"Tip of £{tip_amount:.2f} added successfully!\n\nNew Total: £{new_total:.2f}")
                        tip_dialog.destroy()
                        self.view_orders_gui()  # Refresh
                except sqlite3.Error as e:
                    messagebox.showerror("Error", f"Failed to add tip: {e}")
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=10)
            ttk.Button(button_frame, text="Add Tip", command=save_tip).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=tip_dialog.destroy).pack(side='left', padx=5)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to load order: {e}")
        tip_dialog.destroy()

def refund_order(self):
    """Process refund for an order"""
    # Ensure columns exist
    ensure_payment_columns()

    selection = self.orders_tree.selection()
    if not selection:
        messagebox.showwarning("No Selection", "Please select an order to refund")
        return
    item = self.orders_tree.item(selection[0])
    order_id = item['values'][0]
    # Create refund dialog
    refund_dialog = tk.Toplevel(self.root)
    refund_dialog.title("Process Refund")
    refund_dialog.geometry("450x450")
    refund_dialog.transient(self.root)
    refund_dialog.grab_set()
    main_frame = ttk.Frame(refund_dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text=f"Process Refund for Order #{order_id}",
             font=('Arial', 12, 'bold')).pack(pady=10)
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT total_amount, order_status, payment_method
                FROM orders
                WHERE order_id = ?
            ''', (order_id,))
            order_data = cursor.fetchone()
            conn.close()
            if not order_data:
                messagebox.showerror("Error", "Order not found")
                refund_dialog.destroy()
                return
            total_price, order_status_val, payment_method = order_data
            if order_status_val != 'Paid':
                messagebox.showwarning("Cannot Refund", "Order must be paid before processing refund")
                refund_dialog.destroy()
                return
            # Display order info
            info_frame = ttk.LabelFrame(main_frame, text="Order Information", padding=10)
            info_frame.pack(fill='x', pady=10)
            ttk.Label(info_frame, text=f"Order Total: £{total_price:.2f}").pack(anchor='w')
            ttk.Label(info_frame, text=f"Payment Method: {payment_method}").pack(anchor='w')
            # Refund type
            refund_frame = ttk.LabelFrame(main_frame, text="Refund Details", padding=10)
            refund_frame.pack(fill='x', pady=10)
            refund_type_var = tk.StringVar(value="Full")
            ttk.Radiobutton(refund_frame, text="Full Refund", variable=refund_type_var,
                           value="Full").pack(anchor='w')
            ttk.Radiobutton(refund_frame, text="Partial Refund", variable=refund_type_var,
                           value="Partial").pack(anchor='w')
            ttk.Label(refund_frame, text="Refund Amount (£):").pack(anchor='w', pady=(10,0))
            refund_amount_var = tk.DoubleVar(value=total_price)
            refund_entry = ttk.Entry(refund_frame, textvariable=refund_amount_var, width=20)
            refund_entry.pack(anchor='w', padx=20)
            def update_refund_amount(*args):
                if refund_type_var.get() == "Full":
                    refund_amount_var.set(total_price)
                    refund_entry.config(state='disabled')
                else:
                    refund_entry.config(state='normal')
            refund_type_var.trace('w', update_refund_amount)
            update_refund_amount()
            # Reason
            ttk.Label(refund_frame, text="Refund Reason:").pack(anchor='w', pady=(10,0))
            reason_var = tk.StringVar()
            reason_combo = ttk.Combobox(refund_frame, textvariable=reason_var, width=30)
            reason_combo['values'] = ('Customer Request', 'Order Error', 'Quality Issue',
                                     'Late Delivery', 'Wrong Item', 'Other')
            reason_combo.pack(anchor='w', padx=20)
            ttk.Label(refund_frame, text="Additional Notes:").pack(anchor='w', pady=(10,0))
            notes_text = tk.Text(refund_frame, height=3, width=40)
            notes_text.pack(anchor='w', padx=20)
            def process_refund():
                refund_amount = refund_amount_var.get()
                if refund_amount <= 0 or refund_amount > total_price:
                    messagebox.showwarning("Invalid Amount",
                                         f"Refund amount must be between £0.01 and £{total_price:.2f}")
                    return
                reason = reason_var.get()
                if not reason:
                    messagebox.showwarning("Missing Information", "Please select a refund reason")
                    return
                notes = notes_text.get(1.0, tk.END).strip()
                # Confirm refund
                if not messagebox.askyesno("Confirm Refund",
                                          f"Process {refund_type_var.get()} refund of £{refund_amount:.2f}?\n\n" +
                                          f"Reason: {reason}\n" +
                                          f"This action cannot be undone."):
                    return
                try:
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        # Create unified refunds table if doesn't exist
                        cursor.execute('''
                            CREATE TABLE IF NOT EXISTS unified_refunds (
                                refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                source_type TEXT NOT NULL,
                                source_refund_id TEXT,
                                reference_type TEXT,
                                reference_id TEXT,
                                student_id TEXT,
                                customer_name TEXT,
                                customer_email TEXT,
                                amount DECIMAL(10,2) NOT NULL,
                                original_amount DECIMAL(10,2),
                                currency TEXT DEFAULT 'GBP',
                                refund_type TEXT,
                                refund_method TEXT,
                                refund_reference TEXT,
                                reason TEXT,
                                status TEXT DEFAULT 'pending',
                                department TEXT,
                                processed_by TEXT,
                                requested_by TEXT,
                                approved_by TEXT,
                                refund_date TEXT,
                                request_date TEXT,
                                approval_date TEXT,
                                notes TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')
                        # Insert refund record
                        cursor.execute('''
                            INSERT INTO unified_refunds (source_type, reference_type, reference_id, amount, refund_type, reason, notes, department, status, request_date)
                            VALUES ('restaurant', 'order', ?, ?, ?, ?, ?, 'restaurant', 'processed', datetime('now'))
                        ''', (order_id, refund_amount, refund_type_var.get(), reason, notes))
                        refund_row_id = cursor.lastrowid
                        # Update order status
                        new_status = 'Refunded' if refund_type_var.get() == 'Full' else 'Partially Refunded'
                        cursor.execute('''
                            UPDATE orders
                            SET order_status = ?, total_amount = total_amount - ?
                            WHERE order_id = ?
                        ''', (new_status, refund_amount, order_id))
                        conn.commit()
                        conn.close()

                        # Auto-post to GL (cash has moved). Never raises.
                        try:
                            from education_system.university_system.modules.domain.finance.ledger import notify_ledger
                            notify_ledger('refund', refund_row_id, posted_by='restaurant')
                        except Exception as _e:
                            import logging
                            logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

                        # Send refund receipt email
                        send_refund_receipt_email(order_id, refund_amount, payment_method,
                                                 refund_type_var.get(), reason)

                        messagebox.showinfo("Success",
                                          f"Refund processed successfully!\n\n" +
                                          f"Amount: £{refund_amount:.2f}\n" +
                                          f"Method: {payment_method}\n\n" +
                                          f"Funds will be returned to customer's {payment_method}.\n\n" +
                                          f"✓ Refund confirmation email sent")
                        refund_dialog.destroy()
                        self.view_orders_gui()  # Refresh
                except (sqlite3.Error, tk.TclError) as e:
                    messagebox.showerror("Error", f"Failed to process refund: {e}")
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=10)
            ttk.Button(button_frame, text="Process Refund", command=process_refund).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=refund_dialog.destroy).pack(side='left', padx=5)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to load order: {e}")
        refund_dialog.destroy()

def apply_discount(self):
    """Apply discount to an order"""
    # Ensure columns exist
    ensure_payment_columns()

    selection = self.orders_tree.selection()
    if not selection:
        messagebox.showwarning("No Selection", "Please select an order to apply discount")
        return
    item = self.orders_tree.item(selection[0])
    order_id = item['values'][0]
    # Create discount dialog
    discount_dialog = tk.Toplevel(self.root)
    discount_dialog.title("Apply Discount")
    discount_dialog.geometry("450x450")
    discount_dialog.transient(self.root)
    discount_dialog.grab_set()
    main_frame = ttk.Frame(discount_dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text=f"Apply Discount to Order #{order_id}",
             font=('Arial', 12, 'bold')).pack(pady=10)
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT total_amount, discount_amount, order_status
                FROM orders
                WHERE order_id = ?
            ''', (order_id,))
            order_data = cursor.fetchone()
            conn.close()
            if not order_data:
                messagebox.showerror("Error", "Order not found")
                discount_dialog.destroy()
                return
            original_total, current_discount, order_status_val = order_data
            # Display order info
            info_frame = ttk.LabelFrame(main_frame, text="Order Information", padding=10)
            info_frame.pack(fill='x', pady=10)
            ttk.Label(info_frame, text=f"Original Total: £{original_total:.2f}").pack(anchor='w')
            ttk.Label(info_frame, text=f"Current Discount: £{current_discount or 0:.2f}").pack(anchor='w')
            ttk.Label(info_frame, text=f"Current Total: £{original_total - (current_discount or 0):.2f}").pack(anchor='w')
            # Discount details
            discount_frame = ttk.LabelFrame(main_frame, text="Discount Details", padding=10)
            discount_frame.pack(fill='x', pady=10)
            discount_type_var = tk.StringVar(value="Percentage")
            ttk.Radiobutton(discount_frame, text="Percentage (%)", variable=discount_type_var,
                           value="Percentage").pack(anchor='w')
            ttk.Radiobutton(discount_frame, text="Fixed Amount (£)", variable=discount_type_var,
                           value="Fixed").pack(anchor='w')
            ttk.Label(discount_frame, text="Discount Value:").pack(anchor='w', pady=(10,0))
            discount_value_var = tk.DoubleVar(value=0.0)
            discount_entry = ttk.Entry(discount_frame, textvariable=discount_value_var, width=20)
            discount_entry.pack(anchor='w', padx=20)
            # Calculated discount display
            calculated_label = ttk.Label(discount_frame, text="Discount Amount: £0.00", foreground='blue')
            calculated_label.pack(anchor='w', padx=20, pady=5)
            def update_calculated_discount(*args):
                try:
                    value = discount_value_var.get()
                    if discount_type_var.get() == "Percentage":
                        discount_amount = (original_total * value) / 100
                        calculated_label.config(text=f"Discount Amount: £{discount_amount:.2f} ({value}%)")
                    else:
                        calculated_label.config(text=f"Discount Amount: £{value:.2f}")
                except (ValueError, TypeError, tk.TclError):
                    calculated_label.config(text="Discount Amount: £0.00")
            discount_value_var.trace('w', update_calculated_discount)
            discount_type_var.trace('w', update_calculated_discount)
            # Promotional code
            ttk.Label(discount_frame, text="Promo Code (optional):").pack(anchor='w', pady=(10,0))
            promo_var = tk.StringVar()
            ttk.Entry(discount_frame, textvariable=promo_var, width=20).pack(anchor='w', padx=20)
            # Reason
            ttk.Label(discount_frame, text="Discount Reason:").pack(anchor='w', pady=(10,0))
            reason_var = tk.StringVar()
            reason_combo = ttk.Combobox(discount_frame, textvariable=reason_var, width=30)
            reason_combo['values'] = ('Promotional Offer', 'Loyalty Reward', 'Compensation',
                                     'Staff Discount', 'Manager Discretion', 'Other')
            reason_combo.pack(anchor='w', padx=20)
            # Manager approval for large discounts
            approval_var = tk.BooleanVar(value=False)
            approval_check = ttk.Checkbutton(discount_frame, text="Manager Approval (for discounts > 20%)",
                                            variable=approval_var, state='disabled')
            approval_check.pack(anchor='w', pady=5)
            def check_approval_needed(*args):
                try:
                    value = discount_value_var.get()
                    if discount_type_var.get() == "Percentage" and value > 20:
                        approval_check.config(state='normal')
                    else:
                        approval_check.config(state='disabled')
                        approval_var.set(False)
                except (ValueError, TypeError, tk.TclError):
                    pass
            discount_value_var.trace('w', check_approval_needed)
            discount_type_var.trace('w', check_approval_needed)
            def apply_discount_action():
                value = discount_value_var.get()
                if value <= 0:
                    messagebox.showwarning("Invalid Value", "Discount value must be greater than 0")
                    return
                # Calculate discount amount
                if discount_type_var.get() == "Percentage":
                    if value > 100:
                        messagebox.showwarning("Invalid Percentage", "Percentage cannot exceed 100%")
                        return
                    discount_amount = (original_total * value) / 100
                    # Check for manager approval
                    if value > 20 and not approval_var.get():
                        messagebox.showwarning("Approval Required",
                                             "Manager approval required for discounts over 20%")
                        return
                else:
                    discount_amount = value
                    if discount_amount >= original_total:
                        messagebox.showwarning("Invalid Amount",
                                             f"Discount cannot exceed order total (£{original_total:.2f})")
                        return
                reason = reason_var.get()
                if not reason:
                    messagebox.showwarning("Missing Information", "Please select a discount reason")
                    return
                try:
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        # Create discounts table if doesn't exist
                        cursor.execute('''
                            CREATE TABLE IF NOT EXISTS order_discounts (
                                discount_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                order_id INTEGER,
                                discount_amount REAL,
                                discount_type TEXT,
                                discount_value REAL,
                                promo_code TEXT,
                                reason TEXT,
                                manager_approved BOOLEAN,
                                discount_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                                FOREIGN KEY (order_id) REFERENCES orders(order_id)
                            )
                        ''')
                        # Insert discount record
                        cursor.execute('''
                            INSERT INTO order_discounts
                            (order_id, discount_amount, discount_type, discount_value,
                             promo_code, reason, manager_approved)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (order_id, discount_amount, discount_type_var.get(), value,
                             promo_var.get() or None, reason, approval_var.get()))
                        # Update order
                        new_discount_total = (current_discount or 0) + discount_amount
                        new_total = original_total - new_discount_total
                        cursor.execute('''
                            UPDATE orders
                            SET discount_amount = ?, total_amount = ?
                            WHERE order_id = ?
                        ''', (new_discount_total, new_total, order_id))
                        conn.commit()
                        conn.close()
                        messagebox.showinfo("Success",
                                          f"Discount applied successfully!\n\n" +
                                          f"Discount: £{discount_amount:.2f}\n" +
                                          f"New Total: £{new_total:.2f}")
                        discount_dialog.destroy()
                        self.view_orders_gui()  # Refresh
                except sqlite3.Error as e:
                    messagebox.showerror("Error", f"Failed to apply discount: {e}")
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=10)
            ttk.Button(button_frame, text="Apply Discount", command=apply_discount_action).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=discount_dialog.destroy).pack(side='left', padx=5)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to load order: {e}")
        discount_dialog.destroy()

def process_cash_payment(self, order_id, total_amount):
    """Process cash payment with change calculation"""
    cash_dialog = tk.Toplevel(self.root)
    cash_dialog.title("Cash Payment")
    cash_dialog.geometry("400x350")
    cash_dialog.transient(self.root)
    cash_dialog.grab_set()
    main_frame = ttk.Frame(cash_dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Cash Payment", font=('Arial', 14, 'bold')).pack(pady=10)
    # Order info
    info_frame = ttk.LabelFrame(main_frame, text="Payment Details", padding=10)
    info_frame.pack(fill='x', pady=10)
    ttk.Label(info_frame, text=f"Order Total: £{total_amount:.2f}",
             font=('Arial', 12, 'bold'), foreground='blue').pack(anchor='w', pady=5)
    # Cash tendered
    ttk.Label(info_frame, text="Cash Tendered (£):").pack(anchor='w', pady=(10,0))
    cash_tendered_var = tk.DoubleVar(value=0.0)
    cash_entry = ttk.Entry(info_frame, textvariable=cash_tendered_var, width=20, font=('Arial', 12))
    cash_entry.pack(anchor='w', pady=5)
    cash_entry.focus()
    # Change display
    change_label = ttk.Label(info_frame, text="Change: £0.00",
                            font=('Arial', 12, 'bold'), foreground='green')
    change_label.pack(anchor='w', pady=10)
    def update_change(*args):
        try:
            tendered = cash_tendered_var.get()
            change = tendered - total_amount
            if change >= 0:
                change_label.config(text=f"Change: £{change:.2f}", foreground='green')
            else:
                change_label.config(text=f"Insufficient: £{abs(change):.2f} short", foreground='red')
        except (ValueError, TypeError, tk.TclError):
            change_label.config(text="Change: £0.00", foreground='green')
    cash_tendered_var.trace('w', update_change)
    # Quick amount buttons
    quick_frame = ttk.Frame(main_frame)
    quick_frame.pack(pady=10)
    ttk.Label(quick_frame, text="Quick Amounts:").pack(side='left', padx=5)
    for amount in [10, 20, 50, 100]:
        ttk.Button(quick_frame, text=f"£{amount}",
                  command=lambda a=amount: cash_tendered_var.set(a)).pack(side='left', padx=2)
    def complete_payment():
        tendered = cash_tendered_var.get()
        if tendered < total_amount:
            messagebox.showwarning("Insufficient Cash",
                                 f"Cash tendered (£{tendered:.2f}) is less than order total (£{total_amount:.2f})")
            return
        change = tendered - total_amount
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                # Create cash transactions table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS cash_transactions (
                        transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        order_id INTEGER,
                        cash_tendered REAL,
                        change_given REAL,
                        transaction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (order_id) REFERENCES orders(order_id)
                    )
                ''')
                # Record cash transaction
                cursor.execute('''
                    INSERT INTO cash_transactions (order_id, cash_tendered, change_given)
                    VALUES (?, ?, ?)
                ''', (order_id, tendered, change))
                # Update order
                cursor.execute('''
                    UPDATE orders
                    SET order_status = 'Paid', payment_method = 'Cash'
                    WHERE order_id = ?
                ''', (order_id,))
                conn.commit()
                conn.close()

                # Send payment receipt email
                send_payment_receipt_email(order_id, total_amount, 'Cash',
                                          cash_tendered=tendered, change_given=change)

                messagebox.showinfo("Payment Complete",
                                  f"Cash payment processed successfully!\n\n" +
                                  f"Cash Tendered: £{tendered:.2f}\n" +
                                  f"Change: £{change:.2f}\n\n" +
                                  f"✓ Receipt email sent")
                cash_dialog.destroy()
                self.view_orders_gui()  # Refresh
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to process cash payment: {e}")
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=10)
    ttk.Button(button_frame, text="Complete Payment", command=complete_payment).pack(side='left', padx=5)
    ttk.Button(button_frame, text="Cancel", command=cash_dialog.destroy).pack(side='left', padx=5)

def process_card_payment(self, order_id, total_amount):
    """Process card payment"""
    card_dialog = tk.Toplevel(self.root)
    card_dialog.title("Card Payment")
    card_dialog.geometry("400x400")
    card_dialog.transient(self.root)
    card_dialog.grab_set()
    main_frame = ttk.Frame(card_dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Card Payment", font=('Arial', 14, 'bold')).pack(pady=10)
    # Order info
    info_frame = ttk.LabelFrame(main_frame, text="Payment Details", padding=10)
    info_frame.pack(fill='x', pady=10)
    ttk.Label(info_frame, text=f"Order Total: £{total_amount:.2f}",
             font=('Arial', 12, 'bold'), foreground='blue').pack(anchor='w', pady=5)
    # Card type
    ttk.Label(info_frame, text="Card Type:").pack(anchor='w', pady=(10,0))
    card_type_var = tk.StringVar(value="Credit Card")
    card_type_combo = ttk.Combobox(info_frame, textvariable=card_type_var, width=25, state='readonly')
    card_type_combo['values'] = ('Credit Card', 'Debit Card', 'Contactless')
    card_type_combo.pack(anchor='w', pady=5)
    # Card last 4 digits (optional)
    ttk.Label(info_frame, text="Card Last 4 Digits (optional):").pack(anchor='w', pady=(10,0))
    card_last4_var = tk.StringVar()
    ttk.Entry(info_frame, textvariable=card_last4_var, width=10).pack(anchor='w', pady=5)
    # Transaction ID
    ttk.Label(info_frame, text="Transaction ID:").pack(anchor='w', pady=(10,0))
    import random
    transaction_id = f"TXN{random.randint(100000, 999999)}"
    transaction_id_var = tk.StringVar(value=transaction_id)
    ttk.Entry(info_frame, textvariable=transaction_id_var, width=25, state='readonly').pack(anchor='w', pady=5)
    # Status display
    status_label = ttk.Label(main_frame, text="Ready to process payment",
                            font=('Arial', 10), foreground='blue')
    status_label.pack(pady=10)
    def authorize_payment():
        card_type = card_type_var.get()
        card_last4 = card_last4_var.get()
        if card_last4 and (not card_last4.isdigit() or len(card_last4) != 4):
            messagebox.showwarning("Invalid Input", "Card last 4 digits must be exactly 4 digits")
            return
        # Simulate payment authorization
        status_label.config(text="Authorizing payment...", foreground='orange')
        card_dialog.update()
        import time
        time.sleep(1)  # Simulate processing
        # Simulate success (95% success rate for demo)
        import random
        success = random.random() < 0.95
        if success:
            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    # Create card transactions table
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS card_transactions (
                            transaction_id TEXT PRIMARY KEY,
                            order_id INTEGER,
                            card_type TEXT,
                            card_last4 TEXT,
                            amount REAL,
                            authorization_code TEXT,
                            transaction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (order_id) REFERENCES orders(order_id)
                        )
                    ''')
                    # Generate authorization code
                    auth_code = f"AUTH{random.randint(100000, 999999)}"
                    # Record card transaction
                    cursor.execute('''
                        INSERT INTO card_transactions
                        (transaction_id, order_id, card_type, card_last4, amount, authorization_code)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (transaction_id, order_id, card_type, card_last4 or None, total_amount, auth_code))
                    # Update order
                    cursor.execute('''
                        UPDATE orders
                        SET order_status = 'Paid', payment_method = ?
                        WHERE order_id = ?
                    ''', (card_type, order_id))
                    conn.commit()
                    conn.close()
                    status_label.config(text="Payment Authorized!", foreground='green')

                    # Send payment receipt email
                    send_payment_receipt_email(order_id, total_amount, card_type,
                                              transaction_id=transaction_id, auth_code=auth_code)

                    messagebox.showinfo("Payment Complete",
                                      f"Card payment processed successfully!\n\n" +
                                      f"Card Type: {card_type}\n" +
                                      f"Amount: £{total_amount:.2f}\n" +
                                      f"Transaction ID: {transaction_id}\n" +
                                      f"Authorization Code: {auth_code}\n\n" +
                                      f"✓ Receipt email sent")
                    card_dialog.destroy()
                    self.view_orders_gui()  # Refresh
            except (sqlite3.Error, tk.TclError, ValueError, TypeError) as e:
                status_label.config(text="Payment Failed", foreground='red')
                messagebox.showerror("Error", f"Failed to process card payment: {e}")
        else:
            status_label.config(text="Payment Declined", foreground='red')
            messagebox.showerror("Payment Declined",
                               "Card payment was declined.\n\n" +
                               "Please try another payment method or contact your bank.")
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=10)
    ttk.Button(button_frame, text="Authorize Payment", command=authorize_payment).pack(side='left', padx=5)
    ttk.Button(button_frame, text="Cancel", command=card_dialog.destroy).pack(side='left', padx=5)

def process_meal_plan_payment(self, order_id, total_amount):
    """Process meal plan payment"""
    meal_plan_dialog = tk.Toplevel(self.root)
    meal_plan_dialog.title("Meal Plan Payment")
    meal_plan_dialog.geometry("450x500")
    meal_plan_dialog.transient(self.root)
    meal_plan_dialog.grab_set()
    main_frame = ttk.Frame(meal_plan_dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Meal Plan Payment", font=('Arial', 14, 'bold')).pack(pady=10)
    # Order info
    info_frame = ttk.LabelFrame(main_frame, text="Payment Details", padding=10)
    info_frame.pack(fill='x', pady=10)
    ttk.Label(info_frame, text=f"Order Total: £{total_amount:.2f}",
             font=('Arial', 12, 'bold'), foreground='blue').pack(anchor='w', pady=5)
    # Student ID lookup
    ttk.Label(info_frame, text="Student ID:").pack(anchor='w', pady=(10,0))
    student_id_var = tk.StringVar()
    student_entry = ttk.Entry(info_frame, textvariable=student_id_var, width=20)
    student_entry.pack(anchor='w', pady=5)
    student_entry.focus()
    # Student info display
    student_info_frame = ttk.LabelFrame(main_frame, text="Student Information", padding=10)
    student_info_frame.pack(fill='x', pady=10)
    student_name_label = ttk.Label(student_info_frame, text="Name: -")
    student_name_label.pack(anchor='w')
    plan_type_label = ttk.Label(student_info_frame, text="Plan Type: -")
    plan_type_label.pack(anchor='w')
    balance_label = ttk.Label(student_info_frame, text="Balance: £0.00", foreground='gray')
    balance_label.pack(anchor='w')
    status_label = ttk.Label(student_info_frame, text="Status: Not Checked", foreground='gray')
    status_label.pack(anchor='w', pady=5)
    def check_meal_plan():
        student_id = student_id_var.get()
        if not student_id:
            messagebox.showwarning("Missing Information", "Please enter Student ID")
            return
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                # Create meal plans table if doesn't exist
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS student_meal_plans (
                        student_id TEXT PRIMARY KEY,
                        student_name TEXT,
                        plan_type TEXT,
                        balance REAL,
                        plan_start_date DATE,
                        plan_end_date DATE,
                        is_active BOOLEAN DEFAULT 1
                    )
                ''')
                # Check if student exists
                cursor.execute('''
                    SELECT student_name, plan_type, balance, is_active
                    FROM student_meal_plans
                    WHERE student_id = ?
                ''', (student_id,))
                student_data = cursor.fetchone()
                if not student_data:
                    # Create demo student for testing
                    messagebox.showinfo("Demo Mode",
                                      "Student not found. Creating demo meal plan for testing purposes.")
                    cursor.execute('''
                        INSERT INTO student_meal_plans
                        (student_id, student_name, plan_type, balance, is_active)
                        VALUES (?, ?, ?, ?, 1)
                    ''', (student_id, f"Student {student_id}", "Standard Plan", 500.00))
                    conn.commit()
                    student_data = (f"Student {student_id}", "Standard Plan", 500.00, 1)
                conn.close()
                student_name, plan_type, balance, is_active = student_data
                student_name_label.config(text=f"Name: {student_name}")
                plan_type_label.config(text=f"Plan Type: {plan_type}")
                balance_label.config(text=f"Balance: £{balance:.2f}",
                                    foreground='green' if balance >= total_amount else 'red')
                if not is_active:
                    status_label.config(text="Status: Plan Inactive", foreground='red')
                    messagebox.showwarning("Inactive Plan", "This meal plan is not active")
                elif balance < total_amount:
                    status_label.config(text="Status: Insufficient Balance", foreground='red')
                    messagebox.showwarning("Insufficient Balance",
                                         f"Current balance (£{balance:.2f}) is less than order total (£{total_amount:.2f})")
                else:
                    status_label.config(text="Status: Valid - Ready to Process", foreground='green')
        except (sqlite3.Error, tk.TclError) as e:
            messagebox.showerror("Error", f"Failed to check meal plan: {e}")
    ttk.Button(info_frame, text="Check Meal Plan", command=check_meal_plan).pack(pady=10)
    def process_payment():
        student_id = student_id_var.get()
        if not student_id:
            messagebox.showwarning("Missing Information", "Please enter Student ID")
            return
        if status_label.cget('text') != "Status: Valid - Ready to Process":
            messagebox.showwarning("Cannot Process", "Please check meal plan first and ensure it's valid")
            return
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                # Deduct from meal plan
                cursor.execute('''
                    UPDATE student_meal_plans
                    SET balance = balance - ?
                    WHERE student_id = ?
                ''', (total_amount, student_id))
                # NOTE: meal plan transactions now use the unified 'transactions' table
                # with source_type = 'meal_plan'
                # Record transaction
                cursor.execute('''
                    INSERT INTO transactions (source_type, reference_id, student_id, amount)
                    VALUES ('meal_plan', ?, ?, ?)
                ''', (order_id, student_id, total_amount))
                # Update order
                cursor.execute('''
                    UPDATE orders
                    SET order_status = 'Paid', payment_method = 'Meal Plan'
                    WHERE order_id = ?
                ''', (order_id,))
                # Get new balance
                cursor.execute('SELECT balance FROM student_meal_plans WHERE student_id = ?', (student_id,))
                new_balance = cursor.fetchone()[0]
                conn.commit()
                conn.close()

                # Send payment receipt email
                send_payment_receipt_email(order_id, total_amount, 'Meal Plan',
                                          student_id=student_id, new_balance=new_balance)

                messagebox.showinfo("Payment Complete",
                                  f"Meal plan payment processed successfully!\n\n" +
                                  f"Student ID: {student_id}\n" +
                                  f"Amount Deducted: £{total_amount:.2f}\n" +
                                  f"New Balance: £{new_balance:.2f}\n\n" +
                                  f"✓ Receipt email sent")
                meal_plan_dialog.destroy()
                self.view_orders_gui()  # Refresh
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to process meal plan payment: {e}")
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=10)
    ttk.Button(button_frame, text="Process Payment", command=process_payment).pack(side='left', padx=5)
    ttk.Button(button_frame, text="Cancel", command=meal_plan_dialog.destroy).pack(side='left', padx=5)

def open_finance_gui_for_payment(self, order_id=None, amount=None):
    """Open finance GUI for payment processing"""
    try:
        from education_system.university_system.modules.domain.finance.gui.finance import FinanceGUI
        finance_window = tk.Toplevel(self.root)
        finance_window.title("Finance System - Restaurant Payment")
        finance_window.geometry("1000x700")
        # Initialize finance GUI
        finance_gui = FinanceGUI(finance_window, auth=self.auth if hasattr(self, 'auth') else None)
        # Pre-populate restaurant payment information if methods exist
        if order_id and amount and hasattr(finance_gui, 'prepopulate_restaurant_payment'):
            finance_gui.prepopulate_restaurant_payment(order_id, amount)
        messagebox.showinfo("Finance System", "Finance system opened for payment processing")
    except ImportError:
        messagebox.showerror("Error", "Finance system is not available")
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Could not open finance system: {e}")

def add_finance_button_to_payment_options(self, parent_frame):
    """Add a 'Pay via Finance System' button to a payment options frame.

    Args:
        parent_frame: The tkinter frame to add the button to.
    """
    if not FINANCE_ACCOUNT_AVAILABLE:
        return

    try:
        def open_finance():
            # Get selected order if available
            order_id = None
            amount = None
            if hasattr(self, 'orders_tree') and self.orders_tree.selection():
                selected = self.orders_tree.item(self.orders_tree.selection()[0])['values']
                if selected:
                    order_id = selected[0]
                    # Try to get amount from the order
                    try:
                        conn = get_db_connection()
                        if conn:
                            cursor = conn.cursor()
                            cursor.execute('SELECT total_amount FROM orders WHERE order_id = ?', (order_id,))
                            result = cursor.fetchone()
                            if result:
                                amount = result[0]
                            conn.close()
                    except sqlite3.Error:
                        pass
            self.open_finance_gui_for_payment(order_id, amount)

        ttk.Button(
            parent_frame,
            text=_t("restaurant.payments.finance_system", default="Pay via Finance System"),
            command=open_finance,
        ).pack(side='left', padx=5)
    except tk.TclError as e:
        print(f"Could not add finance button: {e}")

class PaymentDialog:
    def __init__(self, parent, order_id):
        self.result = False
        self.order_id = order_id

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Process Payment")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"Order ID: {self.order_id}").pack(pady=10)

        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('SELECT total_amount FROM orders WHERE order_id = ?', (self.order_id,))
                result = cursor.fetchone()
                total = result[0] if result else 0
                conn.close()

                ttk.Label(main_frame, text=f"Total: £{total:.2f}").pack(pady=5)
            else:
                ttk.Label(main_frame, text="Total: Unknown").pack(pady=5)
        except sqlite3.Error:
            ttk.Label(main_frame, text="Total: Unknown").pack(pady=5)

        ttk.Label(main_frame, text="Payment Method:").pack(pady=5)

        self.payment_var = tk.StringVar()
        payment_combo = ttk.Combobox(main_frame, textvariable=self.payment_var,
                                    values=['Cash', 'Card', 'Meal Plan', 'Finance Account'])
        payment_combo.pack(pady=10)

        # Student ID field for student account payments
        ttk.Label(main_frame, text="Student ID (for Finance Account payments):").pack(pady=(10, 0))
        self.student_id_var = tk.StringVar()
        self.student_id_entry = ttk.Entry(main_frame, textvariable=self.student_id_var)
        self.student_id_entry.pack(pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Process", command=self.process_payment).pack(side='left', padx=10)
        ttk.Button(button_frame, text="💳 Finance System", command=self.open_finance_system).pack(side='left', padx=10)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side='left', padx=10)

    def process_payment(self):
        """Process the payment"""
        payment_method = self.payment_var.get()
        if not payment_method:
            messagebox.showerror("Error", "Please select a payment method")
            return

        # Validate student ID for Finance Account payments
        if payment_method == 'Finance Account':
            student_id = self.student_id_var.get().strip()
            if not student_id:
                messagebox.showerror("Error", "Please enter a Student ID for Finance Account payments")
                return

            # Process payment via finance system
            success = self._process_student_account_payment(student_id)
            if not success:
                return

        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE orders SET payment_method = ?, order_status = ? WHERE order_id = ?',
                              (payment_method, 'Completed', self.order_id))
                conn.commit()
                conn.close()

            self.result = True
            self.dialog.destroy()
            messagebox.showinfo("Success", "Payment processed successfully")

            # Send order confirmation email if using Finance Account
            if payment_method == 'Finance Account':
                self._send_order_confirmation_email(student_id)

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to process payment: {str(e)}")

    def _process_student_account_payment(self, student_id):
        """Process payment through student's finance account balance"""
        try:
            # Get order details
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return False

            cursor = conn.cursor()
            cursor.execute('SELECT total_amount FROM orders WHERE order_id = ?', (self.order_id,))
            result = cursor.fetchone()
            if not result:
                messagebox.showerror("Error", "Order not found")
                conn.close()
                return False

            total_amount = result[0]
            conn.close()

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
                payment_result = process_student_finance_account_payment(
                    student_id=student_id,
                    amount=total_amount,
                    description=f"Restaurant order #{self.order_id}",
                    transaction_source="Restaurant",
                    transaction_ref=str(self.order_id),
                    processed_by="System",
                    check_balance=True,
                    send_low_balance_alert=True
                )

                if not payment_result['success']:
                    messagebox.showerror("Payment Failed", payment_result['message'])
                    return False

                new_balance = payment_result.get('new_balance', 0)
                low_balance_email_sent = payment_result.get('email_sent', False)

                # Get student name for display
                student_info = get_student_info(student_id)
                student_name = student_info.get('full_name', student_id) if student_info else student_id

                success_msg = f"Payment of £{total_amount:.2f} deducted from {student_name}'s finance account.\nNew Balance: £{new_balance:.2f}"

                if low_balance_email_sent:
                    success_msg += "\n\n⚠ Low balance alert email sent to student"

                messagebox.showinfo("Finance Account Payment", success_msg)
                return True

            # Fallback: Legacy method - add to student_fees without balance deduction
            conn = get_db_connection()
            if not conn:
                messagebox.showerror("Error", "Database connection failed")
                return False

            cursor = conn.cursor()

            # Get student details
            cursor.execute('SELECT first_name, last_name, email FROM students WHERE student_id = ?', (student_id,))
            student_result = cursor.fetchone()
            if not student_result:
                messagebox.showerror("Error", f"Student ID {student_id} not found in system")
                conn.close()
                return False

            first_name, last_name, email = student_result

            # Note: a legacy INSERT into student_fees with non-existent columns
            # (fee_id, fee_type, description, paid_status, created_date) was
            # removed here — student_fees is tuition AR, not a commerce ledger.
            # The unified record_payment() call below is the correct path.

            # 8.117.104: unified record_payment() with source_type='restaurant'.
            try:
                from education_system.university_system.modules.domain.finance.core.unified_payments import (
                    record_payment as _record_payment,
                )
                _record_payment(
                    student_id=student_id,
                    amount=total_amount,
                    payment_method='Finance Account',
                    source_type='restaurant',
                    source_payment_id=str(self.order_id),
                    payment_type='purchase',
                    reference_type='restaurant_order',
                    reference_id=str(self.order_id),
                    department='restaurant',
                    description=f'Restaurant payment for order #{self.order_id}',
                )
            except Exception:
                pass

            conn.commit()
            conn.close()

            messagebox.showinfo("Finance Integration",
                f"Payment of £{total_amount:.2f} charged to {first_name} {last_name}'s student account (legacy)")

            return True

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to process student account payment: {e}")
            return False

    def _send_order_confirmation_email(self, student_id):
        """Send order confirmation email to student"""
        try:
            # Get student and order details
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()

            # Get student details
            cursor.execute('SELECT first_name, last_name, email FROM students WHERE student_id = ?', (student_id,))
            student_result = cursor.fetchone()
            if not student_result:
                conn.close()
                return

            first_name, last_name, email = student_result

            # Get order details
            cursor.execute('SELECT total_amount, order_date FROM orders WHERE order_id = ?', (self.order_id,))
            order_result = cursor.fetchone()
            if not order_result:
                conn.close()
                return

            total_amount, order_date = order_result

            conn.close()

            from education_system.university_system.infrastructure.email.template_utils import render_template

            result = render_template('restaurant_order_confirmation', {
                'first_name': first_name,
                'last_name': last_name,
                'student_id': student_id,
                'order_id': self.order_id,
                'order_date': order_date,
                'total_amount': f'{total_amount:.2f}',
                'signature': 'University Restaurant Team'
            })

            if result and isinstance(result, tuple):
                subject, message = result
            else:
                subject = "Order Confirmation - University Restaurant"
                message = (f"Dear {first_name} {last_name},\n\n"
                           f"Your restaurant order #{self.order_id} has been confirmed.\n"
                           f"Student ID: {student_id}\n"
                           f"Order Date: {order_date}\n"
                           f"Total: £{total_amount:.2f}\n\n"
                           f"University Restaurant Team")

            if not (subject and message):
                print("Failed to load restaurant order confirmation template")
                return

            # Try to send via email GUI
            success = self._send_email_via_gui(email, subject, message)

            if success:
                print(f"Restaurant order confirmation sent to {first_name} {last_name} ({email})")
            else:
                # Fallback: show email details
                self._show_restaurant_email_fallback(f"{first_name} {last_name}", email, subject, message)

        except (ValueError, TypeError) as e:
            print(f"Failed to send restaurant order confirmation email: {e}")

    def _send_email_via_gui(self, to_email, subject, message):
        """Try to send email via email GUI"""
        try:
            from education_system.university_system.modules.shared.gui.email.email_gui import EmailManagerGUI as EmailGUI
            email_gui = EmailGUI(self.dialog, None)  # May need auth parameter
            email_gui.send_email(to_email=to_email, subject=subject, message=message)
            return True
        except ImportError:
            return False
        except (sqlite3.Error, tk.TclError, ValueError, TypeError) as e:
            print(f"Error sending email via GUI: {e}")
            return False

    def _show_restaurant_email_fallback(self, student_name, email, subject, message):
        """Show fallback dialog for restaurant email"""
        try:
            fallback_window = tk.Toplevel(self.dialog)
            fallback_window.title("Restaurant Order Email - Manual Send")
            fallback_window.geometry("700x500")
            fallback_window.transient(self.dialog)

            ttk.Label(fallback_window,
                     text=f"Restaurant order confirmation for {student_name} - Please send manually:",
                     font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=10, pady=10)

            details_frame = ttk.LabelFrame(fallback_window, text="Email Details", padding=10)
            details_frame.pack(fill='both', expand=True, padx=10, pady=10)

            details_text = ScrolledText(details_frame, height=20, width=80)
            details_text.pack(fill='both', expand=True)

            email_details = f"To: {email}\nSubject: {subject}\n\nMessage:\n{message}"
            details_text.insert('1.0', email_details)
            details_text.config(state='disabled')

            ttk.Button(fallback_window, text="Close", command=fallback_window.destroy).pack(pady=10)
        except (sqlite3.Error, tk.TclError) as e:
            print(f"Failed to show restaurant email fallback: {e}")

    def open_finance_system(self):
        """Open finance system for payment processing"""
        try:
            from education_system.university_system.modules.domain.finance.gui.finance import FinanceGUI

            # Get order amount
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('SELECT total_amount FROM orders WHERE order_id = ?', (self.order_id,))
                result = cursor.fetchone()
                amount = result[0] if result else 0
                conn.close()
            else:
                amount = 0

            finance_window = tk.Toplevel(self.dialog)
            finance_window.title(f"Finance System - Order #{self.order_id}")
            finance_window.geometry("1000x700")

            # Initialize finance GUI
            finance_gui = FinanceGUI(finance_window)

            # Pre-populate restaurant payment information if methods exist
            if hasattr(finance_gui, 'prepopulate_restaurant_payment'):
                finance_gui.prepopulate_restaurant_payment(self.order_id, amount)

            messagebox.showinfo("Finance System", f"Finance system opened for order #{self.order_id} (£{amount:.2f})")

        except ImportError:
            messagebox.showerror("Error", "Finance system is not available")
        except (sqlite3.Error, tk.TclError) as e:
            messagebox.showerror("Error", f"Could not open finance system: {e}")

    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy()


def send_payment_receipt_email(order_id, amount, payment_method, **kwargs):
    """
    Send payment receipt email to customer.

    Args:
        order_id: Order ID
        amount: Payment amount
        payment_method: Payment method used (Cash, Card, Meal Plan, etc.)
        **kwargs: Additional payment details (transaction_id, auth_code, student_id, etc.)
    """
    try:
        from education_system.university_system.infrastructure.email.email_service import send_email
        from education_system.university_system.infrastructure.email.template_utils import render_template

        conn = get_db_connection()
        if not conn:
            print(f"[Restaurant] Could not send receipt - database connection failed")
            return False

        cursor = conn.cursor()

        # Get order details
        cursor.execute('''
            SELECT customer_id, order_date, total_amount FROM orders
            WHERE order_id = ?
        ''', (order_id,))
        order_row = cursor.fetchone()

        if not order_row:
            conn.close()
            print(f"[Restaurant] Order {order_id} not found")
            return False

        customer_id, order_date, total_price = order_row

        # Get customer email
        email = None
        customer_name = "Customer"

        # Try to get student email if student_id provided
        student_id = kwargs.get('student_id')
        if student_id:
            cursor.execute('''
                SELECT email, first_name, last_name FROM students
                WHERE student_id = ?
            ''', (student_id,))
            student_row = cursor.fetchone()
            if student_row and student_row[0]:
                email = student_row[0]
                customer_name = f"{student_row[1]} {student_row[2]}"

        # Fallback: get from customer table
        if not email and customer_id:
            cursor.execute('''
                SELECT email, name FROM restaurant_customers
                WHERE customer_id = ?
            ''', (customer_id,))
            customer_row = cursor.fetchone()
            if customer_row and customer_row[0]:
                email = customer_row[0]
                customer_name = customer_row[1] or "Customer"

        # Get order items
        cursor.execute('''
            SELECT item_name, quantity, unit_price, subtotal, special_instructions
            FROM order_items
            WHERE order_id = ?
        ''', (order_id,))
        order_items = cursor.fetchall()

        conn.close()

        if not email:
            print(f"[Restaurant] No email found for order {order_id}")
            return False

        # Build order items section
        items_text = ""
        for item_name, qty, price, subtotal, instructions in order_items:
            items_text += f"  {qty}x {item_name} - £{price:.2f} each = £{subtotal:.2f}\n"
            if instructions:
                items_text += f"     Note: {instructions}\n"

        # Build payment details section
        payment_details = f"Payment Method: {payment_method}\n"

        if payment_method == 'Cash':
            cash_tendered = kwargs.get('cash_tendered', 0)
            change_given = kwargs.get('change_given', 0)
            payment_details += f"Cash Tendered: £{cash_tendered:.2f}\n"
            payment_details += f"Change Given: £{change_given:.2f}\n"
        elif payment_method in ('Credit Card', 'Debit Card', 'Contactless'):
            transaction_id = kwargs.get('transaction_id', 'N/A')
            auth_code = kwargs.get('auth_code', 'N/A')
            payment_details += f"Transaction ID: {transaction_id}\n"
            payment_details += f"Authorization Code: {auth_code}\n"
        elif payment_method == 'Meal Plan':
            new_balance = kwargs.get('new_balance', 0)
            payment_details += f"Student ID: {student_id}\n"
            payment_details += f"New Meal Plan Balance: £{new_balance:.2f}\n"

        # Render email from template
        result = render_template('commerce/restaurant_payment_receipt', {
            'customer_name': customer_name,
            'order_id': order_id,
            'order_date': order_date,
            'items_text': items_text,
            'payment_details': payment_details,
            'amount': f"{amount:.2f}"
        })
        if result and isinstance(result, tuple):
            subject, body = result
        else:
            subject = "Payment Receipt - Restaurant"
            body = (f"Dear {customer_name},\n\n"
                    f"Payment received for Order #{order_id}.\n"
                    f"Order Date: {order_date}\n\n"
                    f"Items:\n{items_text}\n"
                    f"{payment_details}\n"
                    f"Amount Paid: £{amount:.2f}\n\n"
                    f"Thank you for your payment.")

        success = send_email(email, subject, body)

        if success:
            print(f"✓ Payment receipt sent to {email} for Order #{order_id}")
            return True
        else:
            print(f"✗ Failed to send payment receipt to {email}")
            return False

    except Exception as e:
        print(f"✗ Error sending payment receipt: {e}")
        return False


def send_refund_receipt_email(order_id, refund_amount, payment_method, refund_type, reason):
    """
    Send refund confirmation email to customer.

    Args:
        order_id: Order ID
        refund_amount: Refund amount
        payment_method: Original payment method
        refund_type: Full or Partial
        reason: Reason for refund
    """
    try:
        from education_system.university_system.infrastructure.email.email_service import send_email
        from education_system.university_system.infrastructure.email.template_utils import render_template

        conn = get_db_connection()
        if not conn:
            print(f"[Restaurant] Could not send refund receipt - database connection failed")
            return False

        cursor = conn.cursor()

        # Get order details
        cursor.execute('''
            SELECT customer_id, order_date, total_amount FROM orders
            WHERE order_id = ?
        ''', (order_id,))
        order_row = cursor.fetchone()

        if not order_row:
            conn.close()
            print(f"[Restaurant] Order {order_id} not found")
            return False

        customer_id, order_date, original_total = order_row

        # Get customer email
        email = None
        customer_name = "Customer"

        if customer_id:
            # Try to get student email via customer_id
            cursor.execute('''
                SELECT name FROM restaurant_customers
                WHERE customer_id = ?
            ''', (customer_id,))
            customer_row = cursor.fetchone()

            if customer_row:
                customer_name = customer_row[0] or "Customer"

                # Try to get email from students table
                cursor.execute('''
                    SELECT email, first_name, last_name FROM students
                    WHERE student_id = ?
                ''', (customer_name,))  # customer_name might be student_id
                student_row = cursor.fetchone()

                if student_row and student_row[0]:
                    email = student_row[0]
                    customer_name = f"{student_row[1]} {student_row[2]}"
                else:
                    # Get from customer email
                    cursor.execute('''
                        SELECT email FROM restaurant_customers
                        WHERE customer_id = ?
                    ''', (customer_id,))
                    cust_email = cursor.fetchone()
                    if cust_email and cust_email[0]:
                        email = cust_email[0]

        conn.close()

        if not email:
            print(f"[Restaurant] No email found for order {order_id}")
            return False

        # Render email from template
        result = render_template('commerce/restaurant_refund_confirmation', {
            'customer_name': customer_name,
            'order_id': order_id,
            'order_date': order_date,
            'original_total': f"{original_total:.2f}",
            'refund_type': refund_type,
            'refund_amount': f"{refund_amount:.2f}",
            'payment_method': payment_method,
            'reason': reason,
            'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        if result and isinstance(result, tuple):
            subject, body = result
        else:
            subject = "Refund Confirmation - Restaurant"
            body = (f"Dear {customer_name},\n\n"
                    f"A {refund_type.lower()} refund has been processed for Order #{order_id}.\n"
                    f"Original Total: £{original_total:.2f}\n"
                    f"Refund Amount: £{refund_amount:.2f}\n"
                    f"Payment Method: {payment_method}\n"
                    f"Reason: {reason}\n\n"
                    f"Thank you.")

        success = send_email(email, subject, body)

        if success:
            print(f"✓ Refund receipt sent to {email} for Order #{order_id}")
            return True
        else:
            print(f"✗ Failed to send refund receipt to {email}")
            return False

    except Exception as e:
        print(f"✗ Error sending refund receipt: {e}")
        return False

