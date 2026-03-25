import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
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
from education_system.university_system.modules.shared.utils.i18n import (
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


def create_product_context_menu(self):
    """Create context menu for product tree"""
    self.product_context_menu = tk.Menu(self.root, tearoff=0)
    self.product_context_menu.add_command(label="Add to Cart", command=self.add_selected_to_cart)
    self.product_context_menu.add_command(label="View Details", command=self.view_product_details)
    
    if self.current_user.get('role') in ['admin', 'staff', 'shop_manager']:
        self.product_context_menu.add_separator()
        self.product_context_menu.add_command(label="Edit Product", command=self.edit_selected_product)
        self.product_context_menu.add_command(label="Update Stock", command=self.update_selected_stock)
    
    # Bind right-click
    self.products_tree.bind('<Button-3>', self.show_product_context_menu)
    

def show_manage_products(self):
    """Display product management interface"""
    self.clear_content()
    self.update_status("Loading product management...")
    
    # Check permissions
    if self.current_user.get('role') not in ['admin', 'staff', 'shop_manager']:
        ttk.Label(self.content_frame, text="Access Denied", style='Error.TLabel').grid(row=0, column=0)
        ttk.Label(self.content_frame, text="You don't have permission to manage products").grid(row=1, column=0)
        return
    
    # Title and actions
    title_frame = ttk.Frame(self.content_frame)
    title_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
    title_frame.columnconfigure(1, weight=1)
    
    ttk.Label(title_frame, text="Product Management", style='Title.TLabel').grid(row=0, column=0, sticky=tk.W)
    
    action_frame = ttk.Frame(title_frame)
    action_frame.grid(row=0, column=1, sticky=tk.E)

    ttk.Button(action_frame, text="Quick Add", command=self.show_quick_add_product_dialog,
              style='Success.TButton').grid(row=0, column=0, padx=5)
    ttk.Button(action_frame, text="Add Product", command=self.show_add_product_dialog,
              style='Success.TButton').grid(row=0, column=1, padx=5)
    ttk.Button(action_frame, text="Import Products", command=self.import_products).grid(row=0, column=2, padx=5)
    ttk.Button(action_frame, text="Export Products", command=self.export_products).grid(row=0, column=3, padx=5)
    ttk.Button(action_frame, text="Backup DB", command=self.backup_shop_database).grid(row=0, column=4, padx=5)
    ttk.Button(action_frame, text="Cleanup Discounts", command=self.cleanup_expired_discounts).grid(row=0, column=5, padx=5)
    
    # Products table with management features
    products_frame = ttk.LabelFrame(self.content_frame, text="Products", padding="10")
    products_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    products_frame.columnconfigure(0, weight=1)
    products_frame.rowconfigure(0, weight=1)
    
    # Enhanced treeview with more columns
    mgmt_columns = ('ID', 'Name', 'Category', 'Price', 'Stock', 'Status', 'Created', 'Updated')
    self.mgmt_products_tree = ttk.Treeview(products_frame, columns=mgmt_columns, show='headings', height=15)
    
    # Configure columns
    for col in mgmt_columns:
        self.mgmt_products_tree.heading(col, text=col)
    
    self.mgmt_products_tree.column('ID', width=80)
    self.mgmt_products_tree.column('Name', width=200)
    self.mgmt_products_tree.column('Category', width=120)
    self.mgmt_products_tree.column('Price', width=80)
    self.mgmt_products_tree.column('Stock', width=60)
    self.mgmt_products_tree.column('Status', width=80)
    self.mgmt_products_tree.column('Created', width=100)
    self.mgmt_products_tree.column('Updated', width=100)
    
    # Scrollbars
    v_scroll_mgmt = ttk.Scrollbar(products_frame, orient='vertical', command=self.mgmt_products_tree.yview)
    h_scroll_mgmt = ttk.Scrollbar(products_frame, orient='horizontal', command=self.mgmt_products_tree.xview)
    self.mgmt_products_tree.configure(yscrollcommand=v_scroll_mgmt.set, xscrollcommand=h_scroll_mgmt.set)
    
    self.mgmt_products_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    v_scroll_mgmt.grid(row=0, column=1, sticky=(tk.N, tk.S))
    h_scroll_mgmt.grid(row=1, column=0, sticky=(tk.W, tk.E))
    
    # Context menu for management
    self.create_mgmt_context_menu()
    
    # Management action buttons
    mgmt_action_frame = ttk.Frame(self.content_frame)
    mgmt_action_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)
    
    ttk.Button(mgmt_action_frame, text="Edit Product", command=self.edit_selected_product).grid(row=0, column=0, padx=5)
    ttk.Button(mgmt_action_frame, text="Toggle Status", command=self.toggle_product_status, 
              style='Warning.TButton').grid(row=0, column=1, padx=5)
    ttk.Button(mgmt_action_frame, text="Delete Product", command=self.delete_selected_product, 
              style='Danger.TButton').grid(row=0, column=2, padx=5)
    ttk.Button(mgmt_action_frame, text="Bulk Price Update", command=self.bulk_price_update).grid(row=0, column=3, padx=5)
    
    # Load products for management
    self.load_products_for_management()
    self.update_status("Product management loaded")
    

def create_mgmt_context_menu(self):
    """Create context menu for product management"""
    self.mgmt_context_menu = tk.Menu(self.root, tearoff=0)
    self.mgmt_context_menu.add_command(label="Edit Product", command=self.edit_selected_product)
    self.mgmt_context_menu.add_command(label="Toggle Status", command=self.toggle_product_status)
    self.mgmt_context_menu.add_separator()
    self.mgmt_context_menu.add_command(label="Update Stock", command=self.update_selected_stock)
    self.mgmt_context_menu.add_command(label="View Sales", command=self.view_product_sales)
    self.mgmt_context_menu.add_separator()
    self.mgmt_context_menu.add_command(label="Delete Product", command=self.delete_selected_product)
    
    # Bind right-click
    self.mgmt_products_tree.bind('<Button-3>', self.show_mgmt_context_menu)
    

def show_mgmt_context_menu(self, event):
    """Show management context menu"""
    item = self.mgmt_products_tree.identify_row(event.y)
    if item:
        self.mgmt_products_tree.selection_set(item)
        self.mgmt_context_menu.post(event.x_root, event.y_root)
        

def load_products_for_management(self):
    """Load products for management view"""
    try:
        # Clear existing items
        for item in self.mgmt_products_tree.get_children():
            self.mgmt_products_tree.delete(item)
        
        if 'get_connection' in globals():
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT p.source_product_id as product_id, p.name, p.description, p.price, p.category,
                       p.created_at, p.updated_at, p.tax_rate, p.is_active, i.quantity
                FROM products p
                JOIN shop_inventory i ON p.source_product_id = i.product_id
                WHERE p.source_type = 'shop'
                ORDER BY p.created_at DESC
            """)
            
            products = cursor.fetchall()
            
            for product in products:
                status = "Active" if product['is_active'] else "Inactive"
                created = product['created_at'][:10] if product['created_at'] else 'N/A'
                updated = product['updated_at'][:10] if product['updated_at'] else 'N/A'
                
                self.mgmt_products_tree.insert('', 'end', values=(
                    product['product_id'],
                    product['name'],
                    product['category'],
                    f"£{product['price']:.2f}",
                    product['quantity'],
                    status,
                    created,
                    updated
                ))
            
            conn.close()
            
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load products: {e}")
        

def show_add_product_dialog(self):
    """Show dialog for adding new product"""
    # Create add product window
    add_window = tk.Toplevel(self.root)
    add_window.title("Add New Product")
    add_window.geometry("500x600")
    add_window.resizable(False, False)
    
    # Make it modal
    add_window.transient(self.root)
    add_window.grab_set()
    
    main_frame = ttk.Frame(add_window, padding="20")
    main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    
    # Form fields
    ttk.Label(main_frame, text="Product Name*:").grid(row=0, column=0, sticky=tk.W, pady=5)
    name_var = tk.StringVar()
    ttk.Entry(main_frame, textvariable=name_var, width=40).grid(row=0, column=1, pady=5, padx=(10, 0))
    
    ttk.Label(main_frame, text="Description:").grid(row=1, column=0, sticky=(tk.W, tk.N), pady=5)
    desc_text = tk.Text(main_frame, height=4, width=40)
    desc_text.grid(row=1, column=1, pady=5, padx=(10, 0))
    
    ttk.Label(main_frame, text="Price (£)*:").grid(row=2, column=0, sticky=tk.W, pady=5)
    price_var = tk.StringVar()
    ttk.Entry(main_frame, textvariable=price_var, width=40).grid(row=2, column=1, pady=5, padx=(10, 0))
    
    ttk.Label(main_frame, text="Category*:").grid(row=3, column=0, sticky=tk.W, pady=5)
    category_var = tk.StringVar()
    category_entry = ttk.Entry(main_frame, textvariable=category_var, width=40)
    category_entry.grid(row=3, column=1, pady=5, padx=(10, 0))
    
    ttk.Label(main_frame, text="Initial Stock*:").grid(row=4, column=0, sticky=tk.W, pady=5)
    stock_var = tk.StringVar(value="10")
    ttk.Entry(main_frame, textvariable=stock_var, width=40).grid(row=4, column=1, pady=5, padx=(10, 0))
    
    ttk.Label(main_frame, text="Restock Threshold:").grid(row=5, column=0, sticky=tk.W, pady=5)
    threshold_var = tk.StringVar(value="5")
    ttk.Entry(main_frame, textvariable=threshold_var, width=40).grid(row=5, column=1, pady=5, padx=(10, 0))
    
    ttk.Label(main_frame, text="Tax Rate (%):").grid(row=6, column=0, sticky=tk.W, pady=5)
    tax_var = tk.StringVar(value="20")
    ttk.Entry(main_frame, textvariable=tax_var, width=40).grid(row=6, column=1, pady=5, padx=(10, 0))
    
    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.grid(row=7, column=0, columnspan=2, pady=20)
    
    def save_product():
        try:
            # Validate inputs
            if not all([name_var.get().strip(), price_var.get().strip(), 
                       category_var.get().strip(), stock_var.get().strip()]):
                messagebox.showerror("Error", "Please fill in all required fields (*)")
                return
            
            # Create product
            product_data = {
                'name': name_var.get().strip(),
                'description': desc_text.get('1.0', 'end-1c').strip(),
                'price': float(price_var.get()),
                'category': category_var.get().strip(),
                'initial_stock': int(stock_var.get()),
                'restock_threshold': int(threshold_var.get()),
                'tax_rate': float(tax_var.get()) / 100
            }
            
            self.create_product(product_data)
            add_window.destroy()
            self.load_products_for_management()
            messagebox.showinfo("Success", "Product added successfully!")
            
        except ValueError as e:
            messagebox.showerror("Error", "Please enter valid numeric values")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add product: {e}")
    
    ttk.Button(button_frame, text="Save Product", command=save_product, 
              style='Success.TButton').grid(row=0, column=0, padx=5)
    ttk.Button(button_frame, text="Cancel", command=add_window.destroy).grid(row=0, column=1, padx=5)
    

def create_product(self, product_data):
    """Create a new product in the database"""
    try:
        if 'get_connection' in globals():
            conn = get_connection()
            cursor = conn.cursor()
            
            # Generate product ID
            cursor.execute("SELECT MAX(SUBSTR(source_product_id, 2)) FROM products WHERE source_type = 'shop' AND source_product_id LIKE 'P%'")
            result = cursor.fetchone()
            
            try:
                if result[0]:
                    next_id = int(result[0]) + 1
                else:
                    next_id = 1
                product_id = f"P{next_id:03d}"
            except (ValueError, TypeError):
                product_id = f"P{int(time.time())}"
            
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Insert product
            cursor.execute("""
                INSERT INTO products
                (source_product_id, source_type, name, description, price, category, created_at, updated_at, tax_rate, is_active)
                VALUES (?, 'shop', ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                product_id,
                product_data['name'],
                product_data['description'],
                product_data['price'],
                product_data['category'],
                now,
                now,
                product_data['tax_rate'],
                1
            ])
            
            # Insert inventory
            cursor.execute("""
                INSERT INTO shop_inventory
                (product_id, quantity, last_restock_date, restock_threshold)
                VALUES (?, ?, ?, ?)
            """, [
                product_id,
                product_data['initial_stock'],
                now,
                product_data['restock_threshold']
            ])
            
            conn.commit()
            conn.close()
            
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        raise Exception(f"Database error: {e}")


def show_quick_add_product_dialog(self):
    """Show quick add product dialog with minimal inputs"""
    # Create quick add window
    quick_window = tk.Toplevel(self.root)
    quick_window.title("Quick Add Product")
    quick_window.geometry("400x350")
    quick_window.resizable(False, False)

    # Make it modal
    quick_window.transient(self.root)
    quick_window.grab_set()

    main_frame = ttk.Frame(quick_window, padding="20")
    main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    # Title
    ttk.Label(main_frame, text="Quick Add Product", style='Heading.TLabel').grid(
        row=0, column=0, columnspan=2, pady=(0, 15))

    # Info label
    info_label = ttk.Label(main_frame,
        text="Streamlined product entry with auto-filled defaults",
        foreground='gray', font=('Arial', 9, 'italic'))
    info_label.grid(row=1, column=0, columnspan=2, pady=(0, 15))

    # Form fields - minimal inputs
    ttk.Label(main_frame, text="Product Name*:").grid(row=2, column=0, sticky=tk.W, pady=5)
    name_var = tk.StringVar()
    ttk.Entry(main_frame, textvariable=name_var, width=30).grid(row=2, column=1, pady=5, padx=(10, 0))

    ttk.Label(main_frame, text="Price (£)*:").grid(row=3, column=0, sticky=tk.W, pady=5)
    price_var = tk.StringVar()
    ttk.Entry(main_frame, textvariable=price_var, width=30).grid(row=3, column=1, pady=5, padx=(10, 0))

    ttk.Label(main_frame, text="Category:").grid(row=4, column=0, sticky=tk.W, pady=5)
    category_var = tk.StringVar(value="General")
    ttk.Entry(main_frame, textvariable=category_var, width=30).grid(row=4, column=1, pady=5, padx=(10, 0))

    ttk.Label(main_frame, text="Initial Stock:").grid(row=5, column=0, sticky=tk.W, pady=5)
    stock_var = tk.StringVar(value="10")
    ttk.Entry(main_frame, textvariable=stock_var, width=30).grid(row=5, column=1, pady=5, padx=(10, 0))

    # Defaults info
    defaults_label = ttk.Label(main_frame,
        text="Auto-defaults: Description='Quick-added', Tax=20%, Threshold=auto",
        foreground='gray', font=('Arial', 8))
    defaults_label.grid(row=6, column=0, columnspan=2, pady=(15, 5))

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.grid(row=7, column=0, columnspan=2, pady=20)

    def quick_save_product():
        try:
            # Validate minimal required inputs
            if not name_var.get().strip() or not price_var.get().strip():
                messagebox.showerror("Error", "Please fill in Product Name and Price")
                return

            price = float(price_var.get())
            stock = int(stock_var.get())

            if price < 0:
                messagebox.showerror("Error", "Price must be >= 0")
                return
            if stock < 0:
                messagebox.showerror("Error", "Stock must be >= 0")
                return

            # Create product with auto-defaults
            product_data = {
                'name': name_var.get().strip(),
                'description': f"Quick-added product: {name_var.get().strip()}",
                'price': price,
                'category': category_var.get().strip() or "General",
                'initial_stock': stock,
                'restock_threshold': max(5, stock // 4),  # Auto-calculated
                'tax_rate': 0.20  # Default 20%
            }

            self.create_product(product_data)
            quick_window.destroy()
            self.load_products_for_management()
            messagebox.showinfo("Success", f"Product '{product_data['name']}' added quickly!")

        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers for Price and Stock")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to quick add product: {e}")

    ttk.Button(button_frame, text="Quick Save", command=quick_save_product,
              style='Success.TButton').grid(row=0, column=0, padx=5)
    ttk.Button(button_frame, text="Cancel", command=quick_window.destroy).grid(row=0, column=1, padx=5)


def update_product(self, product_id, updated_data):
    """Update product in database"""
    try:
        if 'get_connection' in globals():
            conn = get_connection()
            cursor = conn.cursor()
            
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute("""
                UPDATE products
                SET name = ?, description = ?, price = ?, category = ?,
                    tax_rate = ?, is_active = ?, updated_at = ?
                WHERE source_type = 'shop' AND source_product_id = ?
            """, [
                updated_data['name'],
                updated_data['description'],
                updated_data['price'],
                updated_data['category'],
                updated_data['tax_rate'],
                updated_data['is_active'],
                now,
                product_id
            ])
            
            conn.commit()
            conn.close()
            
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        raise Exception(f"Database error: {e}")
        

def delete_product(self, product_id):
    """Delete product from database"""
    try:
        if 'get_connection' in globals():
            conn = get_connection()
            cursor = conn.cursor()
            
            # Check if product has transactions
            cursor.execute("""
                SELECT COUNT(*) FROM shop_transaction_items WHERE product_id = ?
            """, [product_id])
            
            if cursor.fetchone()[0] > 0:
                raise Exception("Cannot delete product with existing transactions. Consider deactivating instead.")
            
            # Delete inventory first (foreign key constraint)
            cursor.execute("DELETE FROM shop_inventory WHERE product_id = ?", [product_id])
            
            # Delete product
            cursor.execute("DELETE FROM products WHERE source_type = 'shop' AND source_product_id = ?", [product_id])
            
            conn.commit()
            conn.close()
            
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        raise Exception(f"Database error: {e}")
        

def update_product_stock(self, product_id, new_stock):
    """Update product stock in database"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE shop_inventory
            SET quantity = ?, last_restock_date = ?
            WHERE product_id = ?
        """, [new_stock, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), product_id])

        conn.commit()
        conn.close()

        messagebox.showinfo("Success", f"Stock updated successfully for {product_id}")

    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        raise Exception(f"Database error: {e}")
        

