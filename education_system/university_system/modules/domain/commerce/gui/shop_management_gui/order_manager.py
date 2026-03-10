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


def show_order_history(self):
    """Display order history interface"""
    self.clear_content()
    self.update_status("Loading order history...")
    
    # Title
    ttk.Label(self.content_frame, text="Order History", style='Title.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 20))
    
    # Orders list
    orders_frame = ttk.LabelFrame(self.content_frame, text="Your Orders", padding="10")
    orders_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    orders_frame.columnconfigure(0, weight=1)
    orders_frame.rowconfigure(0, weight=1)
    
    # Create treeview for orders
    order_columns = ('Transaction ID', 'Date', 'Total', 'Payment Method', 'Status')
    self.orders_tree = ttk.Treeview(orders_frame, columns=order_columns, show='headings', height=15)
    
    # Configure columns
    for col in order_columns:
        self.orders_tree.heading(col, text=col)
    
    self.orders_tree.column('Transaction ID', width=150)
    self.orders_tree.column('Date', width=150)
    self.orders_tree.column('Total', width=100)
    self.orders_tree.column('Payment Method', width=150)
    self.orders_tree.column('Status', width=100)
    
    # Scrollbar
    orders_scrollbar = ttk.Scrollbar(orders_frame, orient='vertical', command=self.orders_tree.yview)
    self.orders_tree.configure(yscrollcommand=orders_scrollbar.set)
    
    self.orders_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    orders_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
    
    # Double-click to view details
    self.orders_tree.bind('<Double-1>', self.view_order_details)
    
    # Load orders
    self.load_order_history()
    
    # Action buttons
    action_frame = ttk.Frame(self.content_frame)
    action_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)
    
    ttk.Button(action_frame, text="View Details", command=self.view_order_details).grid(row=0, column=0, padx=5)
    ttk.Button(action_frame, text="Refresh", command=self.load_order_history).grid(row=0, column=1, padx=5)
    
    self.update_status("Order history loaded")
    

def load_order_history(self):
    """Load order history from database"""
    try:
        # Clear existing items
        for item in self.orders_tree.get_children():
            self.orders_tree.delete(item)
        
        if 'get_connection' in globals():
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT transaction_id, transaction_date, total_amount, payment_method, status
                FROM shop_transactions
                WHERE user_id = ?
                ORDER BY transaction_date DESC
            """, [self.current_user.get('id', 1)])
            
            orders = cursor.fetchall()
            
            for order in orders:
                self.orders_tree.insert('', 'end', values=(
                    order['transaction_id'],
                    order['transaction_date'],
                    f"£{order['total_amount']:.2f}",
                    order['payment_method'],
                    order['status']
                ))
            
            conn.close()
        else:
            # Sample data
            sample_orders = [
                ("T1234567890", "2024-01-15 14:30:00", "£45.98", "Credit Card", "Completed"),
                ("T1234567891", "2024-01-10 10:15:00", "£29.99", "Cash", "Completed"),
            ]
            
            for order in sample_orders:
                self.orders_tree.insert('', 'end', values=order)
                
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load order history: {e}")
        

def view_order_details(self, event=None):
    """View detailed order information"""
    selection = self.orders_tree.selection()
    if not selection:
        messagebox.showwarning("Warning", "Please select an order first")
        return
    
    item = self.orders_tree.item(selection[0])
    values = item['values']
    transaction_id = values[0]
    
    # Create details window
    details_window = tk.Toplevel(self.root)
    details_window.title(f"Order Details - {transaction_id}")
    details_window.geometry("600x500")
    details_window.resizable(True, True)

    # Make it modal
    details_window.transient(self.root)
    details_window.update_idletasks()  # Ensure window is fully initialized before grab_set
    details_window.grab_set()
    
    main_frame = ttk.Frame(details_window, padding="20")
    main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    main_frame.columnconfigure(0, weight=1)
    main_frame.rowconfigure(1, weight=1)
    
    # Order info
    info_frame = ttk.LabelFrame(main_frame, text="Order Information", padding="10")
    info_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
    
    try:
        order_data = self.get_order_details(transaction_id)
        
        if order_data:
            ttk.Label(info_frame, text=f"Transaction ID: {order_data['transaction']['transaction_id']}").grid(row=0, column=0, sticky=tk.W)
            ttk.Label(info_frame, text=f"Date: {order_data['transaction']['transaction_date']}").grid(row=1, column=0, sticky=tk.W)
            ttk.Label(info_frame, text=f"Total: £{order_data['transaction']['total_amount']:.2f}").grid(row=2, column=0, sticky=tk.W)
            ttk.Label(info_frame, text=f"Payment: {order_data['transaction']['payment_method']}").grid(row=3, column=0, sticky=tk.W)
            ttk.Label(info_frame, text=f"Status: {order_data['transaction']['status']}").grid(row=4, column=0, sticky=tk.W)
    
    except Exception as e:
        ttk.Label(info_frame, text=f"Error loading order details: {e}", style='Error.TLabel').grid(row=0, column=0)
    
    # Items list
    items_frame = ttk.LabelFrame(main_frame, text="Order Items", padding="10")
    items_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    items_frame.columnconfigure(0, weight=1)
    items_frame.rowconfigure(0, weight=1)
    
    # Create treeview for items
    item_columns = ('Product ID', 'Name', 'Price', 'Quantity', 'Subtotal')
    items_tree = ttk.Treeview(items_frame, columns=item_columns, show='headings')
    
    for col in item_columns:
        items_tree.heading(col, text=col)
    
    items_scrollbar = ttk.Scrollbar(items_frame, orient='vertical', command=items_tree.yview)
    items_tree.configure(yscrollcommand=items_scrollbar.set)
    
    items_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    items_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
    
    # Load items
    try:
        if order_data and 'items' in order_data:
            for item in order_data['items']:
                items_tree.insert('', 'end', values=(
                    item['product_id'],
                    item['name'],
                    f"£{item['price_per_item']:.2f}",
                    item['quantity'],
                    f"£{item['subtotal']:.2f}"
                ))
    except Exception as e:
        logger.error(f"Failed to load order items for transaction {transaction_id}: {e}")
        # Insert error message in the tree
        items_tree.insert('', 'end', values=('Error', 'Failed to load items', '', '', ''))
    
    # Close button
    ttk.Button(main_frame, text="Close", command=details_window.destroy).grid(row=2, column=0, pady=10)
    

def get_order_details(self, transaction_id):
    """Get detailed order information"""
    try:
        if 'get_connection' in globals():
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get transaction
            cursor.execute("""
                SELECT * FROM shop_transactions
                WHERE transaction_id = ?
            """, [transaction_id])
            
            transaction = cursor.fetchone()
            
            if not transaction:
                return None
            
            # Get items
            cursor.execute("""
                SELECT ti.*, p.name
                FROM shop_transaction_items ti
                JOIN shop_products p ON ti.product_id = p.product_id
                WHERE ti.transaction_id = ?
            """, [transaction_id])
            
            items = cursor.fetchall()
            
            conn.close()
            
            return {
                'transaction': dict(transaction),
                'items': [dict(item) for item in items]
            }
        
        return None
        
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        raise Exception(f"Database error: {e}")
        
# Management interfaces (for admin/staff users)

def show_all_transactions(self):
    """Display all transactions interface"""
    self.clear_content()
    self.update_status("Loading transactions...")
    
    # Check permissions
    if self.current_user.get('role') not in ['admin', 'staff', 'shop_manager']:
        ttk.Label(self.content_frame, text="Access Denied", style='Error.TLabel').grid(row=0, column=0)
        return
    
    # Title and filters
    title_frame = ttk.Frame(self.content_frame)
    title_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
    title_frame.columnconfigure(1, weight=1)
    
    ttk.Label(title_frame, text="Transaction Management", style='Title.TLabel').grid(row=0, column=0, sticky=tk.W)
    
    # Quick stats
    stats_frame = ttk.Frame(title_frame)
    stats_frame.grid(row=0, column=1, sticky=tk.E)
    
    self.transaction_stats_label = ttk.Label(stats_frame, text="Loading...")
    self.transaction_stats_label.grid(row=0, column=0)
    
    # Filters
    filter_frame = ttk.LabelFrame(self.content_frame, text="Filters", padding="10")
    filter_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
    
    ttk.Label(filter_frame, text="Date Range:").grid(row=0, column=0)
    self.trans_start_date = tk.StringVar(value=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    ttk.Entry(filter_frame, textvariable=self.trans_start_date, width=12).grid(row=0, column=1, padx=5)
    ttk.Label(filter_frame, text="to").grid(row=0, column=2)
    self.trans_end_date = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
    ttk.Entry(filter_frame, textvariable=self.trans_end_date, width=12).grid(row=0, column=3, padx=5)
    
    ttk.Button(filter_frame, text="Apply Filter", command=self.load_transactions).grid(row=0, column=4, padx=10)
    ttk.Button(filter_frame, text="Export", command=self.export_transactions).grid(row=0, column=5, padx=5)
    
    # Transactions table
    trans_frame = ttk.LabelFrame(self.content_frame, text="Transactions", padding="10")
    trans_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    trans_frame.columnconfigure(0, weight=1)
    trans_frame.rowconfigure(0, weight=1)
    
    # Create treeview
    trans_columns = ('Transaction ID', 'Date', 'Customer', 'Total', 'Payment Method', 'Status')
    self.trans_tree = ttk.Treeview(trans_frame, columns=trans_columns, show='headings', height=15)
    
    for col in trans_columns:
        self.trans_tree.heading(col, text=col)
    
    self.trans_tree.column('Transaction ID', width=150)
    self.trans_tree.column('Date', width=150)
    self.trans_tree.column('Customer', width=120)
    self.trans_tree.column('Total', width=100)
    self.trans_tree.column('Payment Method', width=120)
    self.trans_tree.column('Status', width=80)
    
    # Scrollbars
    trans_v_scroll = ttk.Scrollbar(trans_frame, orient='vertical', command=self.trans_tree.yview)
    self.trans_tree.configure(yscrollcommand=trans_v_scroll.set)
    
    self.trans_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    trans_v_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
    
    # Double-click to view details
    self.trans_tree.bind('<Double-1>', self.view_transaction_details)
    
    # Load initial data
    self.load_transactions()
    
    self.update_status("Transactions loaded")
    

def load_transactions(self):
    """Load transactions based on filters"""
    try:
        # Clear existing items
        for item in self.trans_tree.get_children():
            self.trans_tree.delete(item)
        
        start_date = self.trans_start_date.get()
        end_date = self.trans_end_date.get()
        
        if 'get_connection' in globals():
            conn = get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT t.transaction_id, t.transaction_date, u.username, t.total_amount, 
                       t.payment_method, t.status
                FROM shop_transactions t
                LEFT JOIN users u ON t.user_id = u.id
                WHERE DATE(t.transaction_date) BETWEEN ? AND ?
                ORDER BY t.transaction_date DESC
            """, [start_date, end_date])
            
            transactions = cursor.fetchall()
            
            total_amount = 0
            for trans in transactions:
                self.trans_tree.insert('', 'end', values=(
                    trans['transaction_id'],
                    trans['transaction_date'],
                    trans['username'] or 'Unknown',
                    f"£{trans['total_amount']:.2f}",
                    trans['payment_method'],
                    trans['status']
                ))
                total_amount += trans['total_amount']
            
            # Update stats
            stats_text = f"Transactions: {len(transactions)} | Total: £{total_amount:.2f}"
            self.transaction_stats_label.config(text=stats_text)
            
            conn.close()
            
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load transactions: {e}")
        

def view_transaction_details(self, event=None):
    """View detailed transaction information"""
    selection = self.trans_tree.selection()
    if not selection:
        return
    
    item = self.trans_tree.item(selection[0])
    values = item['values']
    transaction_id = values[0]
    
    # Use the existing order details function
    self.view_order_details_by_id(transaction_id)
    

def view_order_details_by_id(self, transaction_id):
    """View order details by transaction ID (for admin use)"""
    try:
        order_data = self.get_order_details(transaction_id)
        
        if not order_data:
            messagebox.showerror("Error", "Transaction not found")
            return
        
        # Create details window (reuse existing code)
        details_window = tk.Toplevel(self.root)
        details_window.title(f"Transaction Details - {transaction_id}")
        details_window.geometry("600x500")
        details_window.resizable(True, True)
        
        # Make it modal
        details_window.transient(self.root)
        details_window.grab_set()
        
        main_frame = ttk.Frame(details_window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Transaction info
        info_frame = ttk.LabelFrame(main_frame, text="Transaction Information", padding="10")
        info_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        transaction = order_data['transaction']
        ttk.Label(info_frame, text=f"Transaction ID: {transaction['transaction_id']}").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(info_frame, text=f"Date: {transaction['transaction_date']}").grid(row=1, column=0, sticky=tk.W)
        ttk.Label(info_frame, text=f"Total: £{transaction['total_amount']:.2f}").grid(row=2, column=0, sticky=tk.W)
        ttk.Label(info_frame, text=f"Payment: {transaction['payment_method']}").grid(row=3, column=0, sticky=tk.W)
        ttk.Label(info_frame, text=f"Status: {transaction['status']}").grid(row=4, column=0, sticky=tk.W)
        
        # Items list
        items_frame = ttk.LabelFrame(main_frame, text="Transaction Items", padding="10")
        items_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        items_frame.columnconfigure(0, weight=1)
        items_frame.rowconfigure(0, weight=1)
        
        # Create treeview for items
        item_columns = ('Product ID', 'Name', 'Price', 'Quantity', 'Subtotal')
        items_tree = ttk.Treeview(items_frame, columns=item_columns, show='headings')
        
        for col in item_columns:
            items_tree.heading(col, text=col)
        
        items_scrollbar = ttk.Scrollbar(items_frame, orient='vertical', command=items_tree.yview)
        items_tree.configure(yscrollcommand=items_scrollbar.set)
        
        items_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        items_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Load items
        for item in order_data['items']:
            items_tree.insert('', 'end', values=(
                item['product_id'],
                item['name'],
                f"£{item['price_per_item']:.2f}",
                item['quantity'],
                f"£{item['subtotal']:.2f}"
            ))
        
        # Close button
        ttk.Button(main_frame, text="Close", command=details_window.destroy).grid(row=2, column=0, pady=10)
        
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load transaction details: {e}")
        

def export_transactions(self):
    """Export transactions to CSV"""
    try:
        # Get date range
        start_date = self.trans_start_date.get()
        end_date = self.trans_end_date.get()
        
        # Ask for file location
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export Transactions"
        )
        
        if not filename:
            return
        
        if 'get_connection' not in globals():
            messagebox.showwarning("Warning", "Database not available for export")
            return
        
        # Get transaction data
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT t.transaction_id, t.transaction_date, u.username, u.email,
                   t.total_amount, t.payment_method, t.status, t.notes
            FROM shop_transactions t
            LEFT JOIN users u ON t.user_id = u.id
            WHERE DATE(t.transaction_date) BETWEEN ? AND ?
            ORDER BY t.transaction_date DESC
        """, [start_date, end_date])
        
        transactions = cursor.fetchall()
        conn.close()
        
        # Write to CSV
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Header
            writer.writerow(['Transaction ID', 'Date', 'Customer', 'Email', 'Total', 'Payment Method', 'Status', 'Notes'])
            
            # Data
            for trans in transactions:
                writer.writerow([
                    trans['transaction_id'],
                    trans['transaction_date'],
                    trans['username'] or 'Unknown',
                    trans['email'] or '',
                    trans['total_amount'],
                    trans['payment_method'],
                    trans['status'],
                    trans['notes'] or ''
                ])
        
        messagebox.showinfo("Success", f"Transactions exported to {filename}")
        
    except Exception as e:
        messagebox.showerror("Error", f"Failed to export transactions: {e}")
        

def view_refund_transaction_details(self):
    """View detailed information for selected transaction"""
    selection = self.refunds_tree.selection()
    if not selection:
        messagebox.showwarning("No Selection", "Please select a transaction to view details.")
        return

    item = self.refunds_tree.item(selection[0])
    values = item['values']

    if len(values) < 6:
        messagebox.showerror("Error", "Invalid transaction data.")
        return

    transaction_id = values[0]

    # Use the existing order details function
    self.view_order_details_by_id(transaction_id)


