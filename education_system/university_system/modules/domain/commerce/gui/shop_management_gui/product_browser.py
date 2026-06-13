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


def show_browse_products(self):
    """Display product browsing interface"""
    self.clear_content()
    self.update_status("Loading products...")

    # Title and search
    title_frame = ttk.Frame(self.content_frame)
    title_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
    title_frame.columnconfigure(1, weight=1)

    ttk.Label(title_frame, text="Browse Products", style='Title.TLabel').grid(row=0, column=0, sticky=tk.W)

    # Search and filter frame
    search_frame = ttk.Frame(title_frame)
    search_frame.grid(row=0, column=1, sticky=tk.E)

    ttk.Label(search_frame, text="Search:").grid(row=0, column=0, padx=(0, 5))
    self.search_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=20)
    search_entry.grid(row=0, column=1, padx=5)

    ttk.Button(search_frame, text="🔍 Search", command=self.search_products).grid(row=0, column=2, padx=5)
    ttk.Button(search_frame, text="🔄 Refresh", command=self.refresh_products).grid(row=0, column=3, padx=5)

    # Filter frame
    filter_frame = ttk.LabelFrame(self.content_frame, text="Filters", padding="10")
    filter_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

    ttk.Label(filter_frame, text="Category:").grid(row=0, column=0, padx=(0, 5))
    self.category_var = tk.StringVar(value="All")
    self.category_combo = ttk.Combobox(filter_frame, textvariable=self.category_var,
                                      values=["All"], state="readonly", width=15)
    self.category_combo.grid(row=0, column=1, padx=5)

    ttk.Label(filter_frame, text="Price Range:").grid(row=0, column=2, padx=(10, 5))
    self.min_price_var = tk.StringVar()
    ttk.Entry(filter_frame, textvariable=self.min_price_var, width=10).grid(row=0, column=3, padx=2)
    ttk.Label(filter_frame, text="to").grid(row=0, column=4, padx=2)
    self.max_price_var = tk.StringVar()
    ttk.Entry(filter_frame, textvariable=self.max_price_var, width=10).grid(row=0, column=5, padx=2)

    ttk.Button(filter_frame, text="Apply Filters", command=self.apply_filters).grid(row=0, column=6, padx=10)

    # Products display area
    products_frame = ttk.LabelFrame(self.content_frame, text="Products", padding="10")
    products_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    products_frame.columnconfigure(0, weight=1)
    products_frame.rowconfigure(0, weight=1)

    # Create treeview for products
    columns = ('ID', 'Name', 'Category', 'Price', 'Stock', 'Description')
    self.products_tree = ttk.Treeview(products_frame, columns=columns, show='headings', height=15)

    # Configure columns
    self.products_tree.heading('ID', text='Product ID')
    self.products_tree.heading('Name', text='Name')
    self.products_tree.heading('Category', text='Category')
    self.products_tree.heading('Price', text='Price (£)')
    self.products_tree.heading('Stock', text='Stock')
    self.products_tree.heading('Description', text='Description')

    # Configure column widths
    self.products_tree.column('ID', width=80)
    self.products_tree.column('Name', width=200)
    self.products_tree.column('Category', width=120)
    self.products_tree.column('Price', width=80)
    self.products_tree.column('Stock', width=60)
    self.products_tree.column('Description', width=300)

    # Scrollbars
    v_scrollbar = ttk.Scrollbar(products_frame, orient='vertical', command=self.products_tree.yview)
    h_scrollbar = ttk.Scrollbar(products_frame, orient='horizontal', command=self.products_tree.xview)
    self.products_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

    self.products_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
    h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))

    # Double-click to view details
    self.products_tree.bind('<Double-1>', self.on_product_double_click)

    # Context menu
    self.create_product_context_menu()

    # Action buttons
    action_frame = ttk.Frame(self.content_frame)
    action_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=10)

    ttk.Button(action_frame, text="Add to Cart", command=self.add_selected_to_cart,
              style='Primary.TButton').grid(row=0, column=0, padx=5)
    ttk.Button(action_frame, text="View Details", command=self.view_product_details).grid(row=0, column=1, padx=5)

    # Load initial data
    self.load_products()
    self.update_status("Products loaded")


def search_products(self):
    """Search products based on search term"""
    search_term = self.search_var.get().strip()
    if not search_term:
        self.load_products()
        return

    try:
        # Clear existing items
        for item in self.products_tree.get_children():
            self.products_tree.delete(item)

        if 'get_connection' in globals():
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT p.source_product_id as product_id, p.name, p.category, p.price, p.description, i.quantity
                FROM products p
                JOIN shop_inventory i ON p.source_product_id = i.product_id
                WHERE p.source_type = 'shop' AND p.is_active = 1
                AND (p.name LIKE ? OR p.description LIKE ? OR p.product_id LIKE ?)
                ORDER BY p.category, p.name
            """, [f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'])

            products = cursor.fetchall()

            for product in products:
                price_str = f"£{product['price']:.2f}"
                self.products_tree.insert('', 'end', values=(
                    product['product_id'],
                    product['name'],
                    product['category'],
                    price_str,
                    product['quantity'],
                    product['description'][:50] + "..." if len(product['description']) > 50 else product['description']
                ))

            conn.close()

        self.update_status(f"Found {len(self.products_tree.get_children())} products matching '{search_term}'")

    except Exception as e:
        messagebox.showerror("Error", f"Search failed: {e}")


def apply_filters(self):
    """Apply category and price filters"""
    category = self.category_var.get()
    min_price = self.min_price_var.get().strip()
    max_price = self.max_price_var.get().strip()

    try:
        # Clear existing items
        for item in self.products_tree.get_children():
            self.products_tree.delete(item)

        if 'get_connection' in globals():
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Build query
            query = """
                SELECT p.source_product_id as product_id, p.name, p.category, p.price, p.description, i.quantity
                FROM products p
                JOIN shop_inventory i ON p.source_product_id = i.product_id
                WHERE p.source_type = 'shop' AND p.is_active = 1
            """
            params = []

            if category != "All":
                query += " AND p.category = ?"
                params.append(category)

            if min_price:
                query += " AND p.price >= ?"
                params.append(float(min_price))

            if max_price:
                query += " AND p.price <= ?"
                params.append(float(max_price))

            query += " ORDER BY p.category, p.name"

            cursor.execute(query, params)
            products = cursor.fetchall()

            for product in products:
                price_str = f"£{product['price']:.2f}"
                self.products_tree.insert('', 'end', values=(
                    product['product_id'],
                    product['name'],
                    product['category'],
                    price_str,
                    product['quantity'],
                    product['description'][:50] + "..." if len(product['description']) > 50 else product['description']
                ))

            conn.close()

        self.update_status(f"Applied filters - {len(self.products_tree.get_children())} products shown")

    except ValueError:
        messagebox.showerror("Error", "Invalid price range")
    except Exception as e:
        messagebox.showerror("Error", f"Filter failed: {e}")


def refresh_products(self):
    """Refresh product list"""
    self.category_var.set("All")
    self.min_price_var.set("")
    self.max_price_var.set("")
    self.search_var.set("")
    self.load_products()
    self.update_status("Products refreshed")


def on_product_double_click(self, event):
    """Handle double-click on product"""
    self.view_product_details()


def view_product_details(self):
    """Show detailed product information"""
    selection = self.products_tree.selection()
    if not selection:
        messagebox.showwarning("Warning", "Please select a product first")
        return

    item = self.products_tree.item(selection[0])
    values = item['values']

    if not values:
        return

    product_id = values[0]

    # Create details window
    details_window = tk.Toplevel(self.root)
    details_window.title(f"Product Details - {product_id}")
    details_window.geometry("500x400")
    details_window.resizable(False, False)

    # Make it modal (set transient first)
    details_window.transient(self.root)

    # Create content
    main_frame = ttk.Frame(details_window, padding="20")
    main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    # Product info
    info_frame = ttk.LabelFrame(main_frame, text="Product Information", padding="10")
    info_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

    try:
        product_data = self.get_product_details(product_id)

        if product_data:
            ttk.Label(info_frame, text="Product ID:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=2)
            ttk.Label(info_frame, text=product_data.get('product_id', 'N/A')).grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=2)

            ttk.Label(info_frame, text="Name:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=2)
            ttk.Label(info_frame, text=product_data.get('name', 'N/A')).grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=2)

            ttk.Label(info_frame, text="Category:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky=tk.W, pady=2)
            ttk.Label(info_frame, text=product_data.get('category', 'N/A')).grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=2)

            ttk.Label(info_frame, text="Price:", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky=tk.W, pady=2)
            ttk.Label(info_frame, text=f"£{product_data.get('price', 0):.2f}").grid(row=3, column=1, sticky=tk.W, padx=(10, 0), pady=2)

            ttk.Label(info_frame, text="Stock:", font=('Arial', 10, 'bold')).grid(row=4, column=0, sticky=tk.W, pady=2)
            stock_color = 'red' if product_data.get('quantity', 0) <= product_data.get('restock_threshold', 5) else 'green'
            stock_label = ttk.Label(info_frame, text=str(product_data.get('quantity', 0)), foreground=stock_color)
            stock_label.grid(row=4, column=1, sticky=tk.W, padx=(10, 0), pady=2)

            ttk.Label(info_frame, text="Description:", font=('Arial', 10, 'bold')).grid(row=5, column=0, sticky=(tk.W, tk.N), pady=2)

            # Description text widget
            desc_text = tk.Text(info_frame, height=4, width=40, wrap=tk.WORD, state='disabled')
            desc_text.grid(row=5, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
            desc_text.configure(state='normal')
            desc_text.insert('1.0', product_data.get('description', 'No description available'))
            desc_text.configure(state='disabled')

    except Exception as e:
        ttk.Label(info_frame, text=f"Error loading details: {e}", style='Error.TLabel').grid(row=0, column=0, columnspan=2)

    # Add to cart section
    cart_frame = ttk.LabelFrame(main_frame, text="Add to Cart", padding="10")
    cart_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

    ttk.Label(cart_frame, text="Quantity:").grid(row=0, column=0, sticky=tk.W)
    quantity_var = tk.IntVar(value=1)
    quantity_spin = ttk.Spinbox(cart_frame, from_=1, to=100, textvariable=quantity_var, width=10)
    quantity_spin.grid(row=0, column=1, padx=(10, 0))

    def add_to_cart_action():
        try:
            self.add_to_cart(product_id, quantity_var.get())
            details_window.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add to cart: {e}")

    ttk.Button(cart_frame, text="Add to Cart", command=add_to_cart_action,
              style='Primary.TButton').grid(row=0, column=2, padx=10)

    # Close button
    ttk.Button(main_frame, text="Close", command=details_window.destroy).grid(row=2, column=0, pady=10)

    # Now that window is fully created, make it modal
    details_window.update_idletasks()  # Ensure window is rendered
    details_window.grab_set()  # Now safe to grab focus


def get_product_details(self, product_id):
    """Get detailed product information"""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT p.source_product_id as product_id, p.name, p.description, p.price, p.category,
                   p.created_at, p.updated_at, p.tax_rate, p.is_active, i.quantity, i.restock_threshold
            FROM products p
            JOIN shop_inventory i ON p.source_product_id = i.product_id
            WHERE p.source_type = 'shop' AND p.source_product_id = ?
        """, [product_id])

        result = cursor.fetchone()
        conn.close()

        if result:
            return dict(result)

        # If no result found, log and return None
        print(f"Warning: Product {product_id} not found in database")
        return None

    except Exception as e:
        print(f"Error getting product details for {product_id}: {e}")
        raise Exception(f"Database error: {e}")


