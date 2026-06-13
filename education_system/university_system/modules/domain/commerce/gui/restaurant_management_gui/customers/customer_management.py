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


def view_customers_gui(self):
    """Display customers in the treeview"""
    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror(_t("common.error"), _t("commerce.customers.database_connection_failed"))
            return

        cursor = conn.cursor()
        cursor.execute('''
            SELECT customer_id, name, email, phone, loyalty_tier, loyalty_points, total_spent
            FROM restaurant_customers
            ORDER BY name
        ''')
        customers = cursor.fetchall()

        for item in self.customers_tree.get_children():
            self.customers_tree.delete(item)

        for customer in customers:
            self.customers_tree.insert('', 'end', values=(
                customer[0], customer[1], customer[2] or 'N/A',
                customer[3] or 'N/A', customer[4], customer[5], f"£{customer[6]:.2f}"
            ))

        conn.close()
        messagebox.showinfo(_t("common.success"), _t("commerce.customers.loaded_customers", count=len(customers)))

    except sqlite3.Error as e:
        messagebox.showerror(_t("common.error"), _t("commerce.customers.failed_load_customers", error=str(e)))

def add_customer_dialog(self):
    """Show dialog to add new customer"""
    dialog = CustomerDialog(self.root, _t("commerce.customers.add_customer"))
    if dialog.result:
        self.view_customers_gui()

def update_customer_dialog(self):
    """Show dialog to update customer"""
    selection = self.customers_tree.selection()
    if not selection:
        messagebox.showwarning(_t("commerce.customers.no_selection"), _t("commerce.customers.select_customer_to_update"))
        return

    item_values = self.customers_tree.item(selection[0])['values']
    customer_id = item_values[0]

    dialog = CustomerDialog(self.root, _t("commerce.customers.update_customer"), customer_id)
    if dialog.result:
        self.view_customers_gui()

class CustomerDialog:
    def __init__(self, parent, title, customer_id=None):
        self.result = False
        self.customer_id = customer_id

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

        if customer_id:
            self.load_customer_data()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=_t("commerce.customers.name_required")).grid(row=0, column=0, sticky='w', pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var, width=40).grid(row=0, column=1, pady=5)

        ttk.Label(main_frame, text=_t("commerce.customers.email")).grid(row=1, column=0, sticky='w', pady=5)
        self.email_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.email_var, width=40).grid(row=1, column=1, pady=5)

        ttk.Label(main_frame, text=_t("commerce.customers.phone")).grid(row=2, column=0, sticky='w', pady=5)
        self.phone_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.phone_var, width=40).grid(row=2, column=1, pady=5)

        ttk.Label(main_frame, text=_t("commerce.customers.loyalty_tier")).grid(row=3, column=0, sticky='w', pady=5)
        self.tier_var = tk.StringVar()
        tier_combo = ttk.Combobox(main_frame, textvariable=self.tier_var,
                                 values=[_t("commerce.customers.tier_bronze"), _t("commerce.customers.tier_silver"), _t("commerce.customers.tier_gold"), _t("commerce.customers.tier_platinum")])
        tier_combo.grid(row=3, column=1, pady=5)
        tier_combo.current(0)

        ttk.Label(main_frame, text=_t("commerce.customers.loyalty_points")).grid(row=4, column=0, sticky='w', pady=5)
        self.points_var = tk.StringVar(value="0")
        ttk.Entry(main_frame, textvariable=self.points_var, width=40).grid(row=4, column=1, pady=5)

        ttk.Label(main_frame, text=_t("commerce.customers.total_spent")).grid(row=5, column=0, sticky='w', pady=5)
        self.spent_var = tk.StringVar(value="0.00")
        ttk.Entry(main_frame, textvariable=self.spent_var, width=40).grid(row=5, column=1, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text=_t("common.save"), command=self.save).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_t("common.cancel"), command=self.cancel).pack(side='left', padx=10)

    def load_customer_data(self):
        """Load existing customer data for editing"""
        try:
            conn = get_db_connection()
            if not conn:
                return

            cursor = conn.cursor()
            cursor.execute('SELECT * FROM restaurant_customers WHERE customer_id = ?', (self.customer_id,))
            customer = cursor.fetchone()

            if customer:
                self.name_var.set(customer[1])
                self.email_var.set(customer[2] or '')
                self.phone_var.set(customer[3] or '')
                self.tier_var.set(customer[4])
                self.points_var.set(str(customer[5]))
                self.spent_var.set(f"{customer[6]:.2f}")

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("commerce.customers.failed_load_customer_data", error=str(e)))

    def save(self):
        """Save the customer"""
        try:
            if not self.name_var.get().strip():
                messagebox.showerror(_t("common.error"), _t("commerce.customers.name_is_required"))
                return

            try:
                points = int(self.points_var.get())
                spent = float(self.spent_var.get())
            except ValueError:
                messagebox.showerror(_t("common.error"), _t("commerce.customers.invalid_points_or_spent"))
                return

            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()

                if self.customer_id:
                    cursor.execute('''
                        UPDATE restaurant_customers
                        SET name=?, email=?, phone=?, loyalty_tier=?, loyalty_points=?, total_spent=?
                        WHERE customer_id=?
                    ''', (self.name_var.get(), self.email_var.get(), self.phone_var.get(),
                          self.tier_var.get(), points, spent, self.customer_id))
                else:
                    cursor.execute('''
                        INSERT INTO restaurant_customers (name, email, phone, loyalty_tier, loyalty_points, total_spent)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (self.name_var.get(), self.email_var.get(), self.phone_var.get(),
                          self.tier_var.get(), points, spent))

                conn.commit()
                conn.close()

            messagebox.showinfo(_t("common.success"), _t("commerce.customers.customer_saved"))
            self.result = True
            self.dialog.destroy()

        except sqlite3.Error as e:
            messagebox.showerror(_t("common.error"), _t("commerce.customers.failed_save_customer", error=str(e)))

    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy()

