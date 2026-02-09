import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from university_system.infrastructure.database.db import sqlite3, get_connection
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
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
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

try:
    from university_system.modules.domain.commerce.services.shop_management import (
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
from university_system.infrastructure.auth import UserAuth, get_global_auth
from university_system.infrastructure.shared_context import get_auth

# Import finance integration for student finance account payments
try:
    from university_system.modules.shared.utils.finance_integration import (
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


def add_selected_to_cart(self):
    """Add selected product to cart"""
    selection = self.products_tree.selection()
    if not selection:
        messagebox.showwarning("Warning", "Please select a product first")
        return
    
    item = self.products_tree.item(selection[0])
    values = item['values']
    
    if not values:
        return
    
    product_id = values[0]
    
    # Ask for quantity
    quantity = simpledialog.askinteger("Quantity", "Enter quantity to add to cart:", 
                                     initialvalue=1, minvalue=1, maxvalue=100)
    
    if quantity:
        try:
            self.add_to_cart(product_id, quantity)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add to cart: {e}")
            

def add_to_cart(self, product_id, quantity):
    """Add product to shopping cart"""
    try:
        # Get product details
        product_details = self.get_product_details(product_id)

        if not product_details:
            raise Exception(f"Product not found (ID: {product_id}). The product may not exist in inventory.")

        # Check stock
        if quantity > product_details['quantity']:
            raise Exception(f"Insufficient stock. Only {product_details['quantity']} available.")

        # Check if already in cart
        for item in self.cart_items:
            if item['product_id'] == product_id:
                item['quantity'] += quantity
                item['subtotal'] = item['price'] * item['quantity']
                break
        else:
            # Add new item to cart
            cart_item = {
                'product_id': product_id,
                'name': product_details['name'],
                'price': product_details['price'],
                'quantity': quantity,
                'subtotal': product_details['price'] * quantity
            }
            self.cart_items.append(cart_item)

        # Update status
        self.update_status(f"Added {quantity} x {product_details['name']} to cart")
        messagebox.showinfo("Success", f"Added {quantity} x {product_details['name']} to cart")

    except Exception as e:
        print(f"Error in add_to_cart: {e}")
        raise Exception(f"Failed to add to cart: {e}")
        

def show_shopping_cart(self):
    """Display shopping cart interface"""
    self.clear_content()
    self.update_status("Loading shopping cart...")
    
    # Title
    title_frame = ttk.Frame(self.content_frame)
    title_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
    title_frame.columnconfigure(1, weight=1)
    
    ttk.Label(title_frame, text="Shopping Cart", style='Title.TLabel').grid(row=0, column=0, sticky=tk.W)
    
    # Cart summary
    summary_label = ttk.Label(title_frame, text=f"Items in cart: {len(self.cart_items)}")
    summary_label.grid(row=0, column=1, sticky=tk.E)
    
    if not self.cart_items:
        # Empty cart message
        empty_frame = ttk.Frame(self.content_frame)
        empty_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        ttk.Label(empty_frame, text="Your cart is empty", style='Heading.TLabel').grid(row=0, column=0, pady=20)
        ttk.Label(empty_frame, text="Browse products to add items to your cart").grid(row=1, column=0, pady=10)
        ttk.Button(empty_frame, text="Browse Products", command=self.show_browse_products, 
                  style='Primary.TButton').grid(row=2, column=0, pady=10)
    else:
        # Cart items
        cart_frame = ttk.LabelFrame(self.content_frame, text="Cart Items", padding="10")
        cart_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        cart_frame.columnconfigure(0, weight=1)
        cart_frame.rowconfigure(0, weight=1)
        
        # Create treeview for cart items
        cart_columns = ('Product ID', 'Name', 'Price', 'Quantity', 'Subtotal')
        self.cart_tree = ttk.Treeview(cart_frame, columns=cart_columns, show='headings', height=10)
        
        # Configure columns
        for col in cart_columns:
            self.cart_tree.heading(col, text=col)
        
        self.cart_tree.column('Product ID', width=100)
        self.cart_tree.column('Name', width=250)
        self.cart_tree.column('Price', width=80)
        self.cart_tree.column('Quantity', width=80)
        self.cart_tree.column('Subtotal', width=100)
        
        # Scrollbar
        cart_scrollbar = ttk.Scrollbar(cart_frame, orient='vertical', command=self.cart_tree.yview)
        self.cart_tree.configure(yscrollcommand=cart_scrollbar.set)
        
        self.cart_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        cart_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Populate cart
        total = 0
        for item in self.cart_items:
            self.cart_tree.insert('', 'end', values=(
                item['product_id'],
                item['name'],
                f"£{item['price']:.2f}",
                item['quantity'],
                f"£{item['subtotal']:.2f}"
            ))
            total += item['subtotal']
        
        # Cart actions
        action_frame = ttk.Frame(self.content_frame)
        action_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)
        
        ttk.Button(action_frame, text="Update Quantity", command=self.update_cart_quantity).grid(row=0, column=0, padx=5)
        ttk.Button(action_frame, text="Remove Item", command=self.remove_cart_item, 
                  style='Warning.TButton').grid(row=0, column=1, padx=5)
        ttk.Button(action_frame, text="Clear Cart", command=self.clear_cart, 
                  style='Danger.TButton').grid(row=0, column=2, padx=5)
        
        # Total and checkout
        total_frame = ttk.LabelFrame(self.content_frame, text="Order Summary", padding="10")
        total_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=10)
        
        ttk.Label(total_frame, text=f"Total: £{total:.2f}", font=('Arial', 14, 'bold')).grid(row=0, column=0, sticky=tk.W)
        
        checkout_frame = ttk.Frame(total_frame)
        checkout_frame.grid(row=0, column=1, sticky=tk.E)
        
        ttk.Button(checkout_frame, text="Continue Shopping", command=self.show_browse_products).grid(row=0, column=0, padx=5)
        ttk.Button(checkout_frame, text="Checkout", command=self.show_checkout, 
                  style='Success.TButton').grid(row=0, column=1, padx=5)
    
    self.update_status("Cart loaded")
    

def update_cart_quantity(self):
    """Update quantity of selected cart item"""
    if not hasattr(self, 'cart_tree'):
        return
        
    selection = self.cart_tree.selection()
    if not selection:
        messagebox.showwarning("Warning", "Please select an item to update")
        return
    
    item = self.cart_tree.item(selection[0])
    values = item['values']
    product_id = values[0]
    
    # Find item in cart
    cart_item = None
    for item in self.cart_items:
        if item['product_id'] == product_id:
            cart_item = item
            break
    
    if not cart_item:
        return
    
    # Ask for new quantity
    new_quantity = simpledialog.askinteger("Update Quantity", 
                                         f"Enter new quantity for {cart_item['name']}:", 
                                         initialvalue=cart_item['quantity'], 
                                         minvalue=1, maxvalue=100)
    
    if new_quantity:
        try:
            # Check stock
            product_details = self.get_product_details(product_id)
            if new_quantity > product_details['quantity']:
                messagebox.showerror("Error", f"Insufficient stock. Only {product_details['quantity']} available.")
                return
            
            cart_item['quantity'] = new_quantity
            cart_item['subtotal'] = cart_item['price'] * new_quantity
            
            self.show_shopping_cart()  # Refresh display
            self.update_status(f"Updated quantity for {cart_item['name']}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update quantity: {e}")
            

def remove_cart_item(self):
    """Remove selected item from cart"""
    if not hasattr(self, 'cart_tree'):
        return
        
    selection = self.cart_tree.selection()
    if not selection:
        messagebox.showwarning("Warning", "Please select an item to remove")
        return
    
    item = self.cart_tree.item(selection[0])
    values = item['values']
    product_id = values[0]
    
    # Find and remove item from cart
    for i, cart_item in enumerate(self.cart_items):
        if cart_item['product_id'] == product_id:
            if messagebox.askyesno("Confirm", f"Remove {cart_item['name']} from cart?"):
                del self.cart_items[i]
                self.show_shopping_cart()  # Refresh display
                self.update_status(f"Removed {cart_item['name']} from cart")
            break
            

def clear_cart(self):
    """Clear all items from cart"""
    if self.cart_items and messagebox.askyesno("Confirm", "Clear all items from cart?"):
        self.cart_items.clear()
        self.show_shopping_cart()  # Refresh display
        self.update_status("Cart cleared")
        

