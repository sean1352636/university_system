import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.core.paths import DEFAULT_DB_PATH
import time
import os
import re
import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import csv
import pandas as pd
from threading import Thread
import webbrowser
from tkinter import font

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

try:
    from education_system.university_system.modules.domain.commerce.services.shop_management import (
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
from education_system.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.university_system.infrastructure.shared_context import get_auth

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

# Initialize logger
logger = logging.getLogger(__name__)


def bulk_restock(self):
    """Bulk restock low stock items"""
    try:
        # Get low stock items
        low_stock_items = self.get_low_stock_items()

        if not low_stock_items:
            messagebox.showinfo("Info", "No items need restocking at this time.")
            return

        # Create bulk restock window
        restock_window = tk.Toplevel(self.root)
        restock_window.title("Bulk Restock")
        restock_window.geometry("600x500")
        restock_window.resizable(True, True)

        # Make it modal
        restock_window.transient(self.root)
        restock_window.grab_set()

        main_frame = ttk.Frame(restock_window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Title
        ttk.Label(main_frame, text="Bulk Restock Low Stock Items",
                 style='Title.TLabel').grid(row=0, column=0, pady=(0, 10))

        # Items list
        items_frame = ttk.LabelFrame(main_frame, text="Items to Restock", padding="10")
        items_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        items_frame.columnconfigure(0, weight=1)
        items_frame.rowconfigure(0, weight=1)

        # Create treeview
        columns = ('Product ID', 'Name', 'Current Stock', 'Threshold', 'Suggested Restock')
        items_tree = ttk.Treeview(items_frame, columns=columns, show='headings')

        for col in columns:
            items_tree.heading(col, text=col)

        # Scrollbar
        items_scrollbar = ttk.Scrollbar(items_frame, orient='vertical', command=items_tree.yview)
        items_tree.configure(yscrollcommand=items_scrollbar.set)

        items_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        items_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # Populate items with suggested restock amounts
        restock_data = {}
        for item in low_stock_items:
            suggested = max(item['restock_threshold'] * 2 - item['quantity'], item['restock_threshold'])
            items_tree.insert('', 'end', values=(
                item['product_id'],
                item['name'],
                item['quantity'],
                item['restock_threshold'],
                suggested
            ))
            restock_data[item['product_id']] = {
                'current': item['quantity'],
                'suggested': suggested
            }

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, pady=20)

        def execute_restock():
            try:
                conn = get_connection()
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                updated_count = 0

                for product_id, data in restock_data.items():
                    new_stock = data['current'] + data['suggested']
                    cursor.execute("""
                        UPDATE shop_inventory
                        SET quantity = ?, last_restock_date = ?
                        WHERE product_id = ?
                    """, [new_stock, now, product_id])
                    updated_count += 1

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"Restocked {updated_count} products successfully!")
                restock_window.destroy()

                # Refresh inventory view if it's currently shown
                if hasattr(self, 'inventory_tree'):
                    self.load_inventory_data()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to restock items: {e}")

        ttk.Button(button_frame, text="Execute Restock", command=execute_restock,
                  style='Success.TButton').grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="Cancel", command=restock_window.destroy).grid(row=0, column=1, padx=5)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to prepare bulk restock: {e}")


def set_restock_threshold(self):
    """Set restock threshold for selected product"""
    if not hasattr(self, 'inventory_tree'):
        return

    selection = self.inventory_tree.selection()
    if not selection:
        messagebox.showwarning("Warning", "Please select a product")
        return

    item = self.inventory_tree.item(selection[0])
    values = item['values']
    product_id = values[0]
    product_name = values[1]
    current_threshold = values[4]

    # Ask for new threshold
    new_threshold = simpledialog.askinteger("Set Restock Threshold",
                                           f"Enter new restock threshold for {product_name}:",
                                           initialvalue=current_threshold, minvalue=0, maxvalue=1000)

    if new_threshold is not None:
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE shop_inventory
                SET restock_threshold = ?
                WHERE product_id = ?
            """, [new_threshold, product_id])

            conn.commit()
            conn.close()

            # Refresh inventory display
            self.load_inventory_data()
            self.update_status(f"Updated restock threshold for {product_id}: {new_threshold}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update threshold: {e}")


def restock_selected_item(self):
    """Restock selected inventory item"""
    if not hasattr(self, 'inventory_tree'):
        return

    selection = self.inventory_tree.selection()
    if not selection:
        messagebox.showwarning("Warning", "Please select a product")
        return

    item = self.inventory_tree.item(selection[0])
    values = item['values']
    product_id = values[0]
    product_name = values[1]
    current_stock = values[3]
    threshold = values[4]

    # Calculate suggested restock amount
    suggested = max(threshold * 2 - current_stock, threshold)

    # Ask for restock amount
    restock_amount = simpledialog.askinteger("Restock Item",
                                           f"Enter amount to add to {product_name} stock:\n"
                                           f"Current stock: {current_stock}\n"
                                           f"Suggested amount: {suggested}",
                                           initialvalue=suggested, minvalue=1, maxvalue=10000)

    if restock_amount:
        try:
            new_stock = current_stock + restock_amount

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE shop_inventory
                SET quantity = ?, last_restock_date = ?
                WHERE product_id = ?
            """, [new_stock, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), product_id])

            conn.commit()
            conn.close()

            # Refresh inventory display
            self.load_inventory_data()
            self.update_status(f"Restocked {product_id}: +{restock_amount} (new total: {new_stock})")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to restock item: {e}")


def update_selected_stock(self):
    """Update stock for selected product"""
    if not hasattr(self, 'mgmt_products_tree'):
        return

    # Check if widget still exists
    try:
        if not self.mgmt_products_tree.winfo_exists():
            return
    except tk.TclError:
        return

    selection = self.mgmt_products_tree.selection()
    if not selection:
        messagebox.showwarning("Warning", "Please select a product")
        return

    item = self.mgmt_products_tree.item(selection[0])
    values = item['values']
    product_id = values[0]
    current_stock = int(values[4])

    new_stock = simpledialog.askinteger("Update Stock",
                                       f"Enter new stock level for {values[1]}:",
                                       initialvalue=current_stock, minvalue=0, maxvalue=10000)

    if new_stock is not None:
        try:
            self.update_product_stock(product_id, new_stock)
            self.load_products_for_management()
            self.update_status(f"Stock updated for {product_id}: {new_stock}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update stock: {e}")


def show_manage_inventory(self):
    """Display inventory management interface"""
    self.clear_content()
    self.update_status("Loading inventory management...")

    # Check permissions
    if self.current_user.get('role') not in ['admin', 'staff', 'shop_manager']:
        ttk.Label(self.content_frame, text="Access Denied", style='Error.TLabel').grid(row=0, column=0)
        return

    # Title and quick actions
    title_frame = ttk.Frame(self.content_frame)
    title_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
    title_frame.columnconfigure(1, weight=1)

    ttk.Label(title_frame, text="Inventory Management", style='Title.TLabel').grid(row=0, column=0, sticky=tk.W)

    quick_frame = ttk.Frame(title_frame)
    quick_frame.grid(row=0, column=1, sticky=tk.E)

    ttk.Button(quick_frame, text="Bulk Restock", command=self.bulk_restock,
              style='Success.TButton').grid(row=0, column=0, padx=5)
    ttk.Button(quick_frame, text="Low Stock Report", command=self.show_low_stock_report,
              style='Warning.TButton').grid(row=0, column=1, padx=5)

    # Inventory table
    inventory_frame = ttk.LabelFrame(self.content_frame, text="Inventory Status", padding="10")
    inventory_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    inventory_frame.columnconfigure(0, weight=1)
    inventory_frame.rowconfigure(0, weight=1)

    # Create treeview for inventory
    inv_columns = ('Product ID', 'Name', 'Category', 'Current Stock', 'Threshold', 'Status', 'Last Restock')
    self.inventory_tree = ttk.Treeview(inventory_frame, columns=inv_columns, show='headings', height=15)

    # Configure columns
    for col in inv_columns:
        self.inventory_tree.heading(col, text=col)

    self.inventory_tree.column('Product ID', width=100)
    self.inventory_tree.column('Name', width=200)
    self.inventory_tree.column('Category', width=120)
    self.inventory_tree.column('Current Stock', width=100)
    self.inventory_tree.column('Threshold', width=80)
    self.inventory_tree.column('Status', width=80)
    self.inventory_tree.column('Last Restock', width=120)

    # Scrollbars
    inv_v_scroll = ttk.Scrollbar(inventory_frame, orient='vertical', command=self.inventory_tree.yview)
    inv_h_scroll = ttk.Scrollbar(inventory_frame, orient='horizontal', command=self.inventory_tree.xview)
    self.inventory_tree.configure(yscrollcommand=inv_v_scroll.set, xscrollcommand=inv_h_scroll.set)

    self.inventory_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    inv_v_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
    inv_h_scroll.grid(row=1, column=0, sticky=(tk.W, tk.E))

    # Load inventory data
    self.load_inventory_data()

    # Action buttons
    inv_action_frame = ttk.Frame(self.content_frame)
    inv_action_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)

    ttk.Button(inv_action_frame, text="Update Stock", command=self.update_selected_stock).grid(row=0, column=0, padx=5)
    ttk.Button(inv_action_frame, text="Set Threshold", command=self.set_restock_threshold).grid(row=0, column=1, padx=5)
    ttk.Button(inv_action_frame, text="Restock Item", command=self.restock_selected_item,
              style='Success.TButton').grid(row=0, column=2, padx=5)

    self.update_status("Inventory management loaded")


def load_inventory_data(self):
    """Load inventory data into treeview"""
    try:
        # Clear existing items
        for item in self.inventory_tree.get_children():
            self.inventory_tree.delete(item)

        if 'get_connection' in globals():
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT p.source_product_id as product_id, p.name, p.category, i.quantity, i.restock_threshold, i.last_restock_date
                FROM products p
                JOIN shop_inventory i ON p.source_product_id = i.product_id
                WHERE p.source_type = 'shop' AND p.is_active = 1
                ORDER BY (i.quantity <= i.restock_threshold) DESC, p.category, p.name
            """)

            items = cursor.fetchall()

            for item in items:
                # Determine status
                if item['quantity'] <= item['restock_threshold']:
                    status = "Low Stock"
                    tag = "low_stock"
                elif item['quantity'] <= item['restock_threshold'] * 1.5:
                    status = "Warning"
                    tag = "warning"
                else:
                    status = "OK"
                    tag = "ok"

                last_restock = item['last_restock_date'][:10] if item['last_restock_date'] else 'Never'

                item_id = self.inventory_tree.insert('', 'end', values=(
                    item['product_id'],
                    item['name'],
                    item['category'],
                    item['quantity'],
                    item['restock_threshold'],
                    status,
                    last_restock
                ), tags=(tag,))

            # Configure tags for coloring
            self.inventory_tree.tag_configure('low_stock', background='#ffcccc')
            self.inventory_tree.tag_configure('warning', background='#ffffcc')
            self.inventory_tree.tag_configure('ok', background='#ccffcc')

            conn.close()

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load inventory: {e}")


