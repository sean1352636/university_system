import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.post_18.university_system.core.paths import DEFAULT_DB_PATH
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
from education_system.post_18.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.post_18.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

try:
    from education_system.post_18.university_system.modules.domain.commerce.services.shop_management import (
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
from education_system.post_18.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.post_18.university_system.infrastructure.shared_context import get_auth

# Import finance integration for student finance account payments
try:
    from education_system.post_18.university_system.modules.shared.utils.finance_integration import (
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


def show_manage_discounts(self):
    """Show discount management interface"""
    # Clear content area
    for widget in self.content_frame.winfo_children():
        widget.destroy()

    # Title
    title_label = ttk.Label(self.content_frame, text="Manage Discounts", style='Heading.TLabel')
    title_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 20))

    # Button frame
    button_frame = ttk.Frame(self.content_frame)
    button_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

    ttk.Button(button_frame, text="Add New Discount", command=self.create_new_discount).pack(side=tk.LEFT, padx=(0, 5))
    ttk.Button(button_frame, text="Edit Selected", command=self.edit_selected_discount).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Toggle Status", command=self.toggle_discount_status).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Refresh", command=self.load_discounts).pack(side=tk.LEFT, padx=5)

    # Discounts frame
    discounts_frame = ttk.LabelFrame(self.content_frame, text="Current Discounts", padding="10")
    discounts_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

    # Create Treeview for discounts
    tree_frame = ttk.Frame(discounts_frame)
    tree_frame.pack(fill=tk.BOTH, expand=True)

    self.discounts_tree = ttk.Treeview(tree_frame,
                                     columns=('Type', 'Value', 'Status', 'Start Date', 'End Date', 'Description'),
                                     show='tree headings')
    self.discounts_tree.heading('#0', text='Discount ID')
    self.discounts_tree.heading('Type', text='Type')
    self.discounts_tree.heading('Value', text='Value')
    self.discounts_tree.heading('Status', text='Status')
    self.discounts_tree.heading('Start Date', text='Start Date')
    self.discounts_tree.heading('End Date', text='End Date')
    self.discounts_tree.heading('Description', text='Description')

    self.discounts_tree.column('#0', width=100)
    self.discounts_tree.column('Type', width=80)
    self.discounts_tree.column('Value', width=80)
    self.discounts_tree.column('Status', width=80)
    self.discounts_tree.column('Start Date', width=100)
    self.discounts_tree.column('End Date', width=100)
    self.discounts_tree.column('Description', width=200)

    scrollbar_v = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.discounts_tree.yview)
    scrollbar_h = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.discounts_tree.xview)
    self.discounts_tree.configure(yscrollcommand=scrollbar_v.set, xscrollcommand=scrollbar_h.set)

    self.discounts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar_v.pack(side=tk.RIGHT, fill=tk.Y)
    scrollbar_h.pack(side=tk.BOTTOM, fill=tk.X)

    # Bind double-click to edit
    self.discounts_tree.bind('<Double-1>', lambda e: self.edit_selected_discount())

    # Configure grid weights
    self.content_frame.grid_rowconfigure(2, weight=1)
    self.content_frame.grid_columnconfigure(0, weight=1)

    # Load discounts
    self.load_discounts()


def load_discounts(self):
    """Load and display all discounts"""
    # Clear existing items
    for item in self.discounts_tree.get_children():
        self.discounts_tree.delete(item)

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM shop_discounts
            ORDER BY is_active DESC, end_date, start_date
        ''')

        discounts = cursor.fetchall()

        for discount in discounts:
            status = "Active" if discount['is_active'] else "Inactive"
            discount_type = "Percentage" if discount['discount_type'] == 'percentage' else "Fixed Amount"
            value_display = f"{discount['discount_value']}%" if discount['discount_type'] == 'percentage' else f"£{discount['discount_value']}"

            self.discounts_tree.insert('', 'end',
                                     text=discount['discount_id'],
                                     values=(discount_type,
                                           value_display,
                                           status,
                                           discount['start_date'] or 'N/A',
                                           discount['end_date'] or 'N/A',
                                           discount['description'] or ''))
        conn.close()

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load discounts: {str(e)}")


def create_new_discount(self):
    """Open dialog to create a new discount"""
    dialog = DiscountEditDialog(self.root, None)
    if dialog.result:
        self.load_discounts()


def edit_selected_discount(self):
    """Edit the selected discount"""
    selection = self.discounts_tree.selection()
    if not selection:
        messagebox.showwarning("No Selection", "Please select a discount to edit.")
        return

    discount_id = self.discounts_tree.item(selection[0])['text']
    dialog = DiscountEditDialog(self.root, discount_id)
    if dialog.result:
        self.load_discounts()


def cleanup_expired_discounts(self):
    """Deactivate all expired discounts"""
    try:
        from datetime import datetime

        if 'get_connection' in globals():
            conn = get_connection()
            cursor = conn.cursor()

            # Get current datetime
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Find expired discounts
            cursor.execute("""
                SELECT discount_id, name, end_date
                FROM shop_discounts
                WHERE end_date < ? AND is_active = 1
            """, (now,))

            expired_discounts = cursor.fetchall()

            if not expired_discounts:
                messagebox.showinfo("Cleanup Complete", "No expired discounts found.")
                conn.close()
                return

            # Deactivate expired discounts
            cursor.execute("""
                UPDATE shop_discounts
                SET is_active = 0
                WHERE end_date < ? AND is_active = 1
            """, (now,))

            count = cursor.rowcount
            conn.commit()
            conn.close()

            # Show details
            discount_list = "\n".join([f"- {d[1]} (expired: {d[2]})" for d in expired_discounts[:5]])
            if len(expired_discounts) > 5:
                discount_list += f"\n... and {len(expired_discounts) - 5} more"

            messagebox.showinfo("Cleanup Complete",
                f"Deactivated {count} expired discount(s):\n\n{discount_list}")

            # Refresh discounts view if visible
            if hasattr(self, 'load_discounts'):
                self.load_discounts()

    except Exception as e:
        messagebox.showerror("Cleanup Failed", f"Failed to cleanup expired discounts: {e}")


class DiscountEditDialog:
    def __init__(self, parent, discount_id=None):
        self.dialog = tk.Toplevel(parent)
        self.discount_id = discount_id
        self.result = False

        title = "Edit Discount" if discount_id else "Create New Discount"
        self.dialog.title(title)
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()
        if discount_id:
            self.load_discount_data()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Discount name
        ttk.Label(main_frame, text="Discount Name:").pack(anchor=tk.W)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var, width=50).pack(fill=tk.X, pady=(0, 10))

        # Description
        ttk.Label(main_frame, text="Description:").pack(anchor=tk.W)
        self.description_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.description_var, width=50).pack(fill=tk.X, pady=(0, 10))

        # Discount type
        ttk.Label(main_frame, text="Discount Type:").pack(anchor=tk.W)
        self.type_var = tk.StringVar(value="percentage")
        type_frame = ttk.Frame(main_frame)
        type_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Radiobutton(type_frame, text="Percentage (%)", variable=self.type_var, value="percentage").pack(side=tk.LEFT)
        ttk.Radiobutton(type_frame, text="Fixed Amount (£)", variable=self.type_var, value="fixed").pack(side=tk.LEFT, padx=(20, 0))

        # Discount value
        ttk.Label(main_frame, text="Discount Value:").pack(anchor=tk.W)
        self.value_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.value_var, width=20).pack(anchor=tk.W, pady=(0, 10))

        # Start date
        ttk.Label(main_frame, text="Start Date (YYYY-MM-DD, optional):").pack(anchor=tk.W)
        self.start_date_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.start_date_var, width=20).pack(anchor=tk.W, pady=(0, 10))

        # End date
        ttk.Label(main_frame, text="End Date (YYYY-MM-DD, optional):").pack(anchor=tk.W)
        self.end_date_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.end_date_var, width=20).pack(anchor=tk.W, pady=(0, 10))

        # Minimum purchase amount
        ttk.Label(main_frame, text="Minimum Purchase Amount (£):").pack(anchor=tk.W)
        self.min_purchase_var = tk.StringVar(value="0")
        ttk.Entry(main_frame, textvariable=self.min_purchase_var, width=20).pack(anchor=tk.W, pady=(0, 10))

        # Applicable products
        ttk.Label(main_frame, text="Applicable Products (comma-separated IDs, leave empty for all):").pack(anchor=tk.W)
        self.products_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.products_var, width=50).pack(fill=tk.X, pady=(0, 10))

        # Active status
        self.active_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(main_frame, text="Active", variable=self.active_var).pack(anchor=tk.W, pady=(0, 20))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text="Save", command=self.save_discount).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT)

    def load_discount_data(self):
        """Load existing discount data"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM shop_discounts WHERE discount_id = ?', (self.discount_id,))
            discount = cursor.fetchone()

            if discount:
                self.name_var.set(discount['name'])
                self.description_var.set(discount['description'] or '')
                self.type_var.set(discount['discount_type'])
                self.value_var.set(str(discount['discount_value']))
                self.start_date_var.set(discount['start_date'] or '')
                self.end_date_var.set(discount['end_date'] or '')
                self.min_purchase_var.set(str(discount['min_purchase_amount']))
                self.products_var.set(discount['applicable_products'] or '')
                self.active_var.set(bool(discount['is_active']))

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load discount: {str(e)}")

    def save_discount(self):
        """Save the discount"""
        name = self.name_var.get().strip()
        description = self.description_var.get().strip()
        discount_type = self.type_var.get()
        start_date = self.start_date_var.get().strip()
        end_date = self.end_date_var.get().strip()
        products = self.products_var.get().strip()

        if not name:
            messagebox.showerror("Validation Error", "Discount name is required.")
            return

        try:
            discount_value = float(self.value_var.get())
            min_purchase = float(self.min_purchase_var.get())
        except ValueError:
            messagebox.showerror("Validation Error", "Discount value and minimum purchase must be valid numbers.")
            return

        if discount_type == 'percentage' and (discount_value < 0 or discount_value > 100):
            messagebox.showerror("Validation Error", "Percentage discount must be between 0 and 100.")
            return

        if discount_value < 0:
            messagebox.showerror("Validation Error", "Discount value cannot be negative.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            if self.discount_id:
                # Update existing discount
                cursor.execute('''
                    UPDATE shop_discounts
                    SET name = ?, description = ?, discount_type = ?, discount_value = ?,
                        start_date = ?, end_date = ?, is_active = ?, applicable_products = ?,
                        min_purchase_amount = ?
                    WHERE discount_id = ?
                ''', (name, description, discount_type, discount_value, start_date or None,
                     end_date or None, self.active_var.get(), products or None, min_purchase, self.discount_id))
            else:
                # Create new discount
                # Generate discount ID
                cursor.execute("SELECT MAX(SUBSTR(discount_id, 2)) FROM shop_discounts WHERE discount_id LIKE 'D%'")
                result = cursor.fetchone()

                try:
                    if result[0]:
                        next_id = int(result[0]) + 1
                    else:
                        next_id = 1
                    discount_id = f"D{next_id:03d}"
                except (ValueError, TypeError):
                    discount_id = f"D{int(time.time())}"

                cursor.execute('''
                    INSERT INTO shop_discounts
                    (discount_id, name, description, discount_type, discount_value, start_date,
                     end_date, is_active, applicable_products, min_purchase_amount, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (discount_id, name, description, discount_type, discount_value, start_date or None,
                     end_date or None, self.active_var.get(), products or None, min_purchase,
                     datetime.now().isoformat()))

            conn.commit()
            conn.close()

            action = "updated" if self.discount_id else "created"
            messagebox.showinfo("Success", f"Discount {action} successfully.")
            self.result = True
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save discount: {str(e)}")


# Export important classes and functions for external use
__all__ = [
    'DiscountEditDialog',
]

