from university_system.infrastructure.database.db import sqlite3, DatabaseManager
import time
import os
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import csv
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
# Import logging helpers from the refactored utils module
from university_system.modules.shared.utils.simple_activity_logger import (
    log_activity,
    log_create,
    log_read,
    log_update,
    log_delete,
    log_search,
    log_export,
    log_menu_navigation,
    log_dynamic_activity,
)

from university_system.infrastructure.database.db import get_connection
from university_system.modules.shared.utils.finance_integration import record_payment_to_finance

# Global variables
# Import auth instance management from user_authentication
try:
    from university_system.infrastructure.auth.user_authentication import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)

def init_shop_db():
    """Initialize the shop database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Create products table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_products (
            product_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            category TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            tax_rate REAL DEFAULT 0.2,
            is_active BOOLEAN DEFAULT 1
        )
        ''')
        
        # Create inventory table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_inventory (
            inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            last_restock_date TEXT,
            restock_threshold INTEGER DEFAULT 5,
            FOREIGN KEY (product_id) REFERENCES shop_products (product_id)
        )
        ''')
        
        # Create transactions table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_transactions (
            transaction_id TEXT PRIMARY KEY,
            user_id INTEGER,
            student_id TEXT,
            total_amount REAL NOT NULL,
            transaction_date TEXT NOT NULL,
            payment_method TEXT,
            status TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # Create transaction items table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_transaction_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price_per_item REAL NOT NULL,
            subtotal REAL NOT NULL,
            FOREIGN KEY (transaction_id) REFERENCES shop_transactions (transaction_id),
            FOREIGN KEY (product_id) REFERENCES shop_products (product_id)
        )
        ''')
        
        # Create discounts table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_discounts (
            discount_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            discount_type TEXT NOT NULL,
            discount_value REAL NOT NULL,
            start_date TEXT,
            end_date TEXT,
            is_active BOOLEAN DEFAULT 1,
            applicable_products TEXT,
            min_purchase_amount REAL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        ''')
        
        # Create shopping cart table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_cart (
            cart_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            added_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (product_id) REFERENCES shop_products (product_id),
            UNIQUE(user_id, product_id)
        )
        ''')
        
        # Sample products (if no products exist)
        cursor.execute("SELECT COUNT(*) FROM shop_products")
        if cursor.fetchone()[0] == 0:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            products = [
                ('P001', 'University Hoodie', 'Comfortable hoodie with university logo', 29.99, 'Clothing', now, now, 0.2, 1),
                ('P002', 'University T-Shirt', 'Cotton t-shirt with university logo', 19.99, 'Clothing', now, now, 0.2, 1),
                ('P003', 'Notebook Pack', 'Set of 3 university branded notebooks', 12.99, 'Stationery', now, now, 0.2, 1),
                ('P004', 'Water Bottle', 'Stainless steel water bottle with university logo', 14.99, 'Accessories', now, now, 0.2, 1),
                ('P005', 'Coffee Mug', 'Ceramic mug with university logo', 9.99, 'Accessories', now, now, 0.2, 1),
                ('P006', 'Pen Set', 'Set of 5 high-quality pens', 7.99, 'Stationery', now, now, 0.2, 1),
                ('P007', 'Laptop Bag', 'Padded laptop bag with university logo', 34.99, 'Accessories', now, now, 0.2, 1),
                ('P008', 'USB Drive', '32GB USB flash drive with university logo', 15.99, 'Electronics', now, now, 0.2, 1),
                ('P009', 'Keychain', 'Metal keychain with university logo', 4.99, 'Accessories', now, now, 0.2, 1),
                ('P010', 'Baseball Cap', 'Adjustable cap with university logo', 16.99, 'Clothing', now, now, 0.2, 1)
            ]
            cursor.executemany(
                'INSERT INTO shop_products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                products
            )
            
            # Add inventory for sample products
            for product in products:
                product_id = product[0]
                cursor.execute(
                    'INSERT INTO shop_inventory (product_id, quantity, last_restock_date, restock_threshold) VALUES (?, ?, ?, ?)',
                    (product_id, 50, now, 10)
                )
            
            # Add sample discounts
            discounts = [
                ('D001', 'Student Discount', '10% off for all students', 'percentage', 10.0, 
                 now, None, 1, 'all', 0.0, now),
                ('D002', 'Bulk Purchase', '15% off when buying 5 or more items', 'percentage', 15.0, 
                 now, None, 1, 'all', 0.0, now),
                ('D003', 'Clothing Sale', '20% off all clothing items', 'percentage', 20.0, 
                 now, datetime.now().replace(year=datetime.now().year + 1).strftime('%Y-%m-%d %H:%M:%S'), 
                 1, 'Clothing', 0.0, now)
            ]
            cursor.executemany(
                'INSERT INTO shop_discounts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                discounts
            )
        
        conn.commit()
        conn.close()
        print("University shop database initialized successfully!")
        return True
        
    except sqlite3.Error as e:
        print(f"An error occurred while initializing the shop database: {e}")
        if 'conn' in locals():
            conn.close()
        return False
    except Exception as e:
        print(f"Unexpected error during shop database initialization: {e}")
        if 'conn' in locals():
            conn.close()
        return False

def setup_shop_permissions(auth_instance=None):
    """Setup permissions for the shop module"""
    global auth
    
    if auth_instance:
        auth = auth_instance
    
    if not auth:
        print("Authentication system not initialized.")
        return False
    
    try:
        # Connect to the database directly
        conn = get_connection()
        cursor = conn.cursor()
        
        # Define permissions
        shop_permissions = [
            # Customer permissions
            ('view_products', 'View available products in the shop'),
            ('make_purchase', 'Purchase items from the shop'),
            ('view_own_purchase_history', 'View own purchase history'),
            
            # Admin permissions
            ('manage_products', 'Add, update, or delete products'),
            ('manage_inventory', 'Manage product inventory levels'),
            ('view_all_transactions', 'View all shop transactions'),
            ('manage_discounts', 'Manage shop discounts and promotions'),
            ('generate_sales_reports', 'Generate and view sales reports')
        ]
        
        # Add permissions directly to the database if they don't exist
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for perm_name, perm_desc in shop_permissions:
            cursor.execute('SELECT COUNT(*) FROM permissions WHERE permission_name = ?', (perm_name,))
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                    (perm_name, perm_desc, timestamp)
                )
        
        conn.commit()
        
        # Define role-permission mapping
        role_permissions = {
            'student': ['view_products', 'make_purchase', 'view_own_purchase_history'],
            'staff': ['view_products', 'make_purchase', 'view_own_purchase_history', 
                      'view_all_transactions', 'generate_sales_reports'],
            'admin': ['view_products', 'make_purchase', 'view_own_purchase_history',
                      'manage_products', 'manage_inventory', 'view_all_transactions',
                      'manage_discounts', 'generate_sales_reports'],
            'shop_manager': ['view_products', 'make_purchase', 'view_own_purchase_history',
                            'manage_products', 'manage_inventory', 'view_all_transactions',
                            'manage_discounts', 'generate_sales_reports']
        }
        
        # For each role, get its ID and add the permissions
        for role_name, permissions in role_permissions.items():
            # Get role ID
            cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role_name,))
            role_data = cursor.fetchone()
            
            if not role_data and role_name == 'shop_manager':
                # Create the shop_manager role if it doesn't exist
                cursor.execute(
                    'INSERT INTO roles (role_name, description, created_at, updated_at) VALUES (?, ?, ?, ?)',
                    (role_name, 'Shop Manager role', timestamp, timestamp)
                )
                conn.commit()
                
                # Get the new role ID
                cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role_name,))
                role_data = cursor.fetchone()
            
            if role_data:
                role_id = role_data[0]
                
                # Get permission IDs and add them to the role
                for perm_name in permissions:
                    cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
                    perm_data = cursor.fetchone()
                    
                    if perm_data:
                        perm_id = perm_data[0]
                        
                        # Check if this role-permission combination already exists
                        cursor.execute(
                            'SELECT COUNT(*) FROM role_permissions WHERE role_id = ? AND permission_id = ?',
                            (role_id, perm_id)
                        )
                        if cursor.fetchone()[0] == 0:
                            # Add permission to role
                            cursor.execute(
                                'INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                                (role_id, perm_id)
                            )
        
        conn.commit()
        conn.close()
        
        print("Shop permissions setup successfully!")
        return True
        
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        print(f"Error setting up shop permissions: {e}")
        return False
    
@log_menu_navigation(description="Displaying shop main menu")
def display_shop_menu():
    """Display the main menu for the university shop"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to access the university shop.")
        return
    
    # Initialize database if needed
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shop_products'")
        if not cursor.fetchone():
            conn.close()
            print("Shop database not initialized. Initializing now...")
            if not init_shop_db():
                print("Failed to initialize shop database. Please contact system administrator.")
                return
        else:
            conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        print("Trying to initialize shop database...")
        if not init_shop_db():
            print("Failed to initialize shop database. Please contact system administrator.")
            return
    
    while True:
        print("\nUniversity Shop Menu:")
        print("======================")
        
        # Show options based on permissions
        options = []
        option_num = 1
        
        # Customer options
        if auth.check_permission('view_products'):
            print(f"{option_num}. Browse Products")
            options.append('browse_products')
            option_num += 1
        
        if auth.check_permission('make_purchase'):
            print(f"{option_num}. View Shopping Cart")
            options.append('view_cart')
            option_num += 1
            
            print(f"{option_num}. Checkout")
            options.append('checkout')
            option_num += 1
        
        if auth.check_permission('view_own_purchase_history'):
            print(f"{option_num}. View Purchase History")
            options.append('purchase_history')
            option_num += 1
        
        # Admin options
        if auth.check_permission('manage_products'):
            print(f"{option_num}. Manage Products")
            options.append('manage_products')
            option_num += 1
        
        if auth.check_permission('manage_inventory'):
            print(f"{option_num}. Manage Inventory")
            options.append('manage_inventory')
            option_num += 1
        
        if auth.check_permission('view_all_transactions'):
            print(f"{option_num}. View All Transactions")
            options.append('all_transactions')
            option_num += 1
        
        if auth.check_permission('manage_discounts'):
            print(f"{option_num}. Manage Discounts")
            options.append('manage_discounts')
            option_num += 1
        
        if auth.check_permission('generate_sales_reports'):
            print(f"{option_num}. Generate Sales Reports")
            options.append('sales_reports')
            option_num += 1
        
        print(f"{option_num}. Return to Main Menu")
        
        choice = input("\nEnter your choice: ")
        
        try:
            choice_num = int(choice)
            
            if choice_num > 0 and choice_num <= len(options):
                selected_option = options[choice_num - 1]
                
                if selected_option == 'browse_products':
                    browse_products()
                elif selected_option == 'view_cart':
                    view_shopping_cart()
                elif selected_option == 'checkout':
                    checkout_process()
                elif selected_option == 'purchase_history':
                    view_purchase_history()
                elif selected_option == 'manage_products':
                    display_product_management_menu()
                elif selected_option == 'manage_inventory':
                    display_inventory_management_menu()
                elif selected_option == 'all_transactions':
                    view_all_transactions()
                elif selected_option == 'manage_discounts':
                    display_discount_management_menu()
                elif selected_option == 'sales_reports':
                    display_sales_reports_menu()
            elif choice_num == option_num:
                print("Returning to main menu...")
                return
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Please enter a valid number.")

@log_read(module="shop", description="Browsing products")
def browse_products():
    """Display all available products for browsing"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to browse products.")
        return
    
    if not auth.check_permission('view_products'):
        print("You don't have permission to view products.")
        return
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row  # This allows accessing columns by name
        cursor = conn.cursor()
        
        # Get filter options
        print("\nFilter options:")
        print("1. View all products")
        print("2. Filter by category")
        print("3. Filter by price range")
        print("4. Search by name")
        
        filter_choice = input("Enter your choice (1-4): ").strip()
        
        query_params = []
        if filter_choice == '1':
            # View all products
            query = '''
            SELECT p.*, i.quantity 
            FROM shop_products p
            JOIN shop_inventory i ON p.product_id = i.product_id
            WHERE p.is_active = 1
            ORDER BY p.category, p.name
            '''
        elif filter_choice == '2':
            # Filter by category
            # First get available categories
            cursor.execute(
                'SELECT DISTINCT category FROM shop_products WHERE is_active = 1 ORDER BY category'
            )
            categories = cursor.fetchall()
            
            if not categories:
                print("No categories found.")
                conn.close()
                return
            
            print("\nAvailable categories:")
            for i, category in enumerate(categories):
                print(f"{i+1}. {category['category']}")
            
            try:
                cat_choice = int(input("Select a category number: "))
                if cat_choice < 1 or cat_choice > len(categories):
                    print("Invalid category selection.")
                    conn.close()
                    return
                
                selected_category = categories[cat_choice-1]['category']
                query = '''
                SELECT p.*, i.quantity 
                FROM shop_products p
                JOIN shop_inventory i ON p.product_id = i.product_id
                WHERE p.is_active = 1 AND p.category = ?
                ORDER BY p.name
                '''
                query_params = [selected_category]
            except ValueError:
                print("Invalid input. Please enter a number.")
                conn.close()
                return
            
        elif filter_choice == '3':
            # Filter by price range
            try:
                min_price = float(input("Enter minimum price: ").strip() or 0)
                max_price = float(input("Enter maximum price: ").strip() or 1000000)
                
                if min_price < 0 or max_price < 0 or min_price > max_price:
                    print("Invalid price range.")
                    conn.close()
                    return
                
                query = '''
                SELECT p.*, i.quantity 
                FROM shop_products p
                JOIN shop_inventory i ON p.product_id = i.product_id
                WHERE p.is_active = 1 AND p.price BETWEEN ? AND ?
                ORDER BY p.price
                '''
                query_params = [min_price, max_price]
            except ValueError:
                print("Invalid input. Please enter numeric values for prices.")
                conn.close()
                return
            
        elif filter_choice == '4':
            # Search by name
            search_term = input("Enter product name to search: ").strip()
            if not search_term:
                print("Search term cannot be empty.")
                conn.close()
                return
            
            query = '''
            SELECT p.*, i.quantity 
            FROM shop_products p
            JOIN shop_inventory i ON p.product_id = i.product_id
            WHERE p.is_active = 1 AND p.name LIKE ?
            ORDER BY p.name
            '''
            query_params = [f'%{search_term}%']
            
        else:
            print("Invalid choice. Showing all products.")
            query = '''
            SELECT p.*, i.quantity 
            FROM shop_products p
            JOIN shop_inventory i ON p.product_id = i.product_id
            WHERE p.is_active = 1
            ORDER BY p.category, p.name
            '''
        
        # Execute the query
        cursor.execute(query, query_params)
        products = cursor.fetchall()
        
        if not products:
            print("No products found matching your criteria.")
            conn.close()
            return
        
        # Display products
        print("\nProducts:")
        print(f"{'ID':<8} {'Name':<30} {'Price':<10} {'Category':<15} {'Stock':<8} {'Description'}")
        print("-" * 90)
        
        for product in products:
            price_formatted = f"£{product['price']:.2f}"
            print(f"{product['product_id']:<8} {product['name'][:28]:<30} {price_formatted:<10} {product['category'][:13]:<15} {product['quantity']:<8} {product['description'][:30]}...")
        
        # Option to add to cart
        if auth.check_permission('make_purchase'):
            while True:
                add_to_cart = input("\nWould you like to add a product to your cart? (y/n): ").strip().lower()
                if add_to_cart == 'y':
                    product_id = input("Enter the product ID to add to cart: ").strip().upper()
                    
                    # Check if product exists
                    cursor.execute(
                        '''
                        SELECT p.*, i.quantity 
                        FROM shop_products p
                        JOIN shop_inventory i ON p.product_id = i.product_id
                        WHERE p.product_id = ? AND p.is_active = 1
                        ''', 
                        [product_id]
                    )
                    product = cursor.fetchone()
                    
                    if not product:
                        print("Product not found or not available.")
                        continue
                    
                    try:
                        quantity = int(input(f"Enter quantity (available: {product['quantity']}): ").strip())
                        if quantity <= 0:
                            print("Quantity must be greater than 0.")
                            continue
                        
                        if quantity > product['quantity']:
                            print(f"Insufficient stock. Only {product['quantity']} available.")
                            continue
                        
                        # Add to cart
                        add_to_shopping_cart(product_id, quantity)
                    except ValueError:
                        print("Invalid quantity. Please enter a number.")
                        continue
                elif add_to_cart == 'n':
                    break
                else:
                    print("Invalid choice. Please enter 'y' or 'n'.")
        
        print("\nPress Enter to continue...")
        input()
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error browsing products: {e}")
        if 'conn' in locals():
            conn.close()

def add_to_shopping_cart(product_id, quantity):
    """Add a product to the user's shopping cart"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to add products to cart.")
        return False
    
    if not auth.check_permission('make_purchase'):
        print("You don't have permission to make purchases.")
        return False
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if product exists and has sufficient inventory
        cursor.execute(
            '''
            SELECT p.product_id, i.quantity 
            FROM shop_products p
            JOIN shop_inventory i ON p.product_id = i.product_id
            WHERE p.product_id = ? AND p.is_active = 1
            ''', 
            [product_id]
        )
        product = cursor.fetchone()
        
        if not product:
            print("Product not found or not available.")
            conn.close()
            return False
        
        if quantity > product[1]:
            print(f"Insufficient stock. Only {product[1]} available.")
            conn.close()
            return False
        
        # Check if product already in cart
        cursor.execute(
            '''
            SELECT quantity FROM shop_cart 
            WHERE user_id = ? AND product_id = ?
            ''', 
            [auth.current_user['id'], product_id]
        )
        cart_item = cursor.fetchone()
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if cart_item:
            # Update quantity if already in cart
            new_quantity = cart_item[0] + quantity
            cursor.execute(
                '''
                UPDATE shop_cart 
                SET quantity = ?, added_at = ?
                WHERE user_id = ? AND product_id = ?
                ''', 
                [new_quantity, now, auth.current_user['id'], product_id]
            )
            print(f"Updated cart: {product_id} (quantity: {new_quantity})")
        else:
            # Add new item to cart
            cursor.execute(
                '''
                INSERT INTO shop_cart (user_id, product_id, quantity, added_at) 
                VALUES (?, ?, ?, ?)
                ''', 
                [auth.current_user['id'], product_id, quantity, now]
            )
            print(f"Added to cart: {product_id} (quantity: {quantity})")
        
        conn.commit()
        conn.close()
        return True
        
    except sqlite3.Error as e:
        print(f"Database error adding to cart: {e}")
        if 'conn' in locals():
            conn.close()
        return False
    except Exception as e:
        print(f"Error adding to cart: {e}")
        if 'conn' in locals():
            conn.close()
        return False

@log_read(module="shop", description="Viewing shopping cart")
def view_shopping_cart():
    """View the current user's shopping cart"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view your shopping cart.")
        return
    
    if not auth.check_permission('make_purchase'):
        print("You don't have permission to make purchases.")
        return
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get cart items with product details
        cursor.execute(
            '''
            SELECT c.cart_id, c.product_id, p.name, p.price, c.quantity, 
                   p.price * c.quantity AS subtotal
            FROM shop_cart c
            JOIN shop_products p ON c.product_id = p.product_id
            WHERE c.user_id = ?
            ORDER BY c.added_at DESC
            ''', 
            [auth.current_user['id']]
        )
        
        cart_items = cursor.fetchall()
        
        if not cart_items:
            print("\nYour shopping cart is empty.")
            conn.close()
            return
        
        # Display cart items
        print("\nYour Shopping Cart:")
        print(f"{'ID':<8} {'Product':<30} {'Price':<10} {'Quantity':<10} {'Subtotal':<12}")
        print("-" * 70)
        
        total = 0
        for item in cart_items:
            price_formatted = f"£{item['price']:.2f}"
            subtotal_formatted = f"£{item['subtotal']:.2f}"
            print(f"{item['product_id']:<8} {item['name'][:28]:<30} {price_formatted:<10} {item['quantity']:<10} {subtotal_formatted:<12}")
            total += item['subtotal']
        
        print("-" * 70)
        print(f"Total: £{total:.2f}")
        
        # Cart management options
        while True:
            print("\nCart Options:")
            print("1. Update item quantity")
            print("2. Remove item from cart")
            print("3. Empty cart")
            print("4. Proceed to checkout")
            print("5. Return to shop menu")
            
            choice = input("Enter your choice (1-5): ").strip()
            
            if choice == '1':
                # Update quantity
                product_id = input("Enter product ID to update: ").strip().upper()
                
                # Check if product in cart
                cursor.execute(
                    "SELECT cart_id FROM shop_cart WHERE user_id = ? AND product_id = ?", 
                    [auth.current_user['id'], product_id]
                )
                
                if not cursor.fetchone():
                    print(f"Product {product_id} not found in your cart.")
                    continue
                
                try:
                    new_quantity = int(input("Enter new quantity: ").strip())
                    if new_quantity <= 0:
                        print("Invalid quantity. Use 'Remove item' to remove from cart.")
                        continue
                    
                    # Check inventory
                    cursor.execute(
                        "SELECT quantity FROM shop_inventory WHERE product_id = ?", 
                        [product_id]
                    )
                    available = cursor.fetchone()['quantity']
                    
                    if new_quantity > available:
                        print(f"Cannot update: only {available} available in stock.")
                        continue
                    
                    # Update quantity
                    cursor.execute(
                        '''
                        UPDATE shop_cart 
                        SET quantity = ?, added_at = ?
                        WHERE user_id = ? AND product_id = ?
                        ''', 
                        [new_quantity, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                         auth.current_user['id'], product_id]
                    )
                    
                    conn.commit()
                    print(f"Updated quantity for {product_id} to {new_quantity}.")
                    
                    # Refresh cart view
                    view_shopping_cart()
                    return
                    
                except ValueError:
                    print("Invalid quantity. Please enter a number.")
                
            elif choice == '2':
                # Remove item
                product_id = input("Enter product ID to remove: ").strip().upper()
                
                cursor.execute(
                    "DELETE FROM shop_cart WHERE user_id = ? AND product_id = ?", 
                    [auth.current_user['id'], product_id]
                )
                
                if cursor.rowcount > 0:
                    conn.commit()
                    print(f"Removed {product_id} from cart.")
                    
                    # Refresh cart view
                    view_shopping_cart()
                    return
                else:
                    print(f"Product {product_id} not found in your cart.")
                
            elif choice == '3':
                # Empty cart
                confirm = input("Are you sure you want to empty your cart? (y/n): ").strip().lower()
                if confirm == 'y':
                    cursor.execute(
                        "DELETE FROM shop_cart WHERE user_id = ?", 
                        [auth.current_user['id']]
                    )
                    conn.commit()
                    print("Cart emptied successfully.")
                    conn.close()
                    return
                
            elif choice == '4':
                # Proceed to checkout
                conn.close()
                checkout_process()
                return
                
            elif choice == '5':
                # Return to shop menu
                conn.close()
                return
                
            else:
                print("Invalid choice. Please try again.")
        
    except sqlite3.Error as e:
        print(f"Database error viewing cart: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error viewing cart: {e}")
        if 'conn' in locals():
            conn.close()

@log_create(module="shop", description="Processing checkout")
def checkout_process():
    """Process the checkout for items in the shopping cart"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to checkout.")
        return
    
    if not auth.check_permission('make_purchase'):
        print("You don't have permission to make purchases.")
        return
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get cart items with product details
        cursor.execute(
            '''
            SELECT c.cart_id, c.product_id, p.name, p.price, c.quantity, 
                   p.price * c.quantity AS subtotal,
                   i.quantity AS available_stock
            FROM shop_cart c
            JOIN shop_products p ON c.product_id = p.product_id
            JOIN shop_inventory i ON p.product_id = i.product_id
            WHERE c.user_id = ?
            ''', 
            [auth.current_user['id']]
        )
        
        cart_items = cursor.fetchall()
        
        if not cart_items:
            print("\nYour shopping cart is empty. Nothing to checkout.")
            conn.close()
            return
        
        # Check stock availability
        out_of_stock_items = []
        for item in cart_items:
            if item['quantity'] > item['available_stock']:
                out_of_stock_items.append((item['product_id'], item['name'], item['available_stock']))
        
        if out_of_stock_items:
            print("\nSome items in your cart are no longer available in the requested quantity:")
            for product_id, name, available in out_of_stock_items:
                print(f"- {name} (ID: {product_id}): Only {available} available")
            
            print("\nPlease update your cart before proceeding with checkout.")
            conn.close()
            return
        
        # Display order summary
        print("\nOrder Summary:")
        print(f"{'Product':<30} {'Price':<10} {'Quantity':<10} {'Subtotal':<12}")
        print("-" * 70)
        
        total = 0
        for item in cart_items:
            price_formatted = f"£{item['price']:.2f}"
            subtotal_formatted = f"£{item['subtotal']:.2f}"
            print(f"{item['name'][:28]:<30} {price_formatted:<10} {item['quantity']:<10} {subtotal_formatted:<12}")
            total += item['subtotal']
        
        print("-" * 70)
        print(f"Total: £{total:.2f}")
        
        # Get student ID if available
        student_id = None
        cursor.execute(
            "SELECT student_id FROM users WHERE id = ?", 
            [auth.current_user['id']]
        )
        user_data = cursor.fetchone()
        if user_data and user_data['student_id']:
            student_id = user_data['student_id']
            
            # Check for student discount
            cursor.execute(
                '''
                SELECT * FROM shop_discounts 
                WHERE name = 'Student Discount' AND is_active = 1
                AND (end_date IS NULL OR end_date > ?)
                ''',
                [datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
            )
            student_discount = cursor.fetchone()
            
            if student_discount:
                discount_value = student_discount['discount_value']
                discount_amount = total * (discount_value / 100)
                discounted_total = total - discount_amount
                
                print(f"Student Discount ({discount_value}%): -£{discount_amount:.2f}")
                print(f"Discounted Total: £{discounted_total:.2f}")
                total = discounted_total
        
        # Confirm purchase
        confirm = input("\nConfirm purchase? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Checkout cancelled.")
            conn.close()
            return
        
        # Get payment method
        print("\nPayment Methods:")
        print("1. Credit/Debit Card")
        print("2. Student Account")
        print("3. PayPal")
        
        payment_method = None
        while not payment_method:
            choice = input("Select payment method (1-3): ").strip()
            if choice == '1':
                payment_method = "Credit/Debit Card"
            elif choice == '2':
                if not student_id:
                    print("Student Account payment is only available for students.")
                    continue
                payment_method = "Student Account"
            elif choice == '3':
                payment_method = "PayPal"
            else:
                print("Invalid choice. Please select a valid payment method.")
        
        # Generate transaction ID
        transaction_id = f"T{int(time.time())}"
        transaction_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Create transaction record
        cursor.execute(
            '''
            INSERT INTO shop_transactions 
            (transaction_id, user_id, student_id, total_amount, transaction_date, payment_method, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            [transaction_id, auth.current_user['id'], student_id, total, 
             transaction_date, payment_method, "Completed", None]
        )
        
        # Create transaction items
        for item in cart_items:
            cursor.execute(
                '''
                INSERT INTO shop_transaction_items
                (transaction_id, product_id, quantity, price_per_item, subtotal)
                VALUES (?, ?, ?, ?, ?)
                ''',
                [transaction_id, item['product_id'], item['quantity'], 
                 item['price'], item['price'] * item['quantity']]
            )
            
            # Update inventory
            cursor.execute(
                '''
                UPDATE shop_inventory
                SET quantity = quantity - ?
                WHERE product_id = ?
                ''',
                [item['quantity'], item['product_id']]
            )
        
        # Clear shopping cart
        cursor.execute(
            "DELETE FROM shop_cart WHERE user_id = ?",
            [auth.current_user['id']]
        )
        
        conn.commit()

        # Record transaction to central finance system
        finance_payment_id = record_payment_to_finance(
            student_id=student_id or "EXTERNAL",
            amount=total,
            payment_method=payment_method,
            transaction_source='Shop',
            transaction_ref=transaction_id,
            notes=f'Shop purchase: {len(cart_items)} item(s)',
            created_by=auth.current_user['username'] if auth and auth.current_user else None
        )

        # Display confirmation
        print("\nOrder placed successfully!")
        print(f"Transaction ID: {transaction_id}")
        print(f"Total Amount: £{total:.2f}")
        print(f"Date: {transaction_date}")
        print(f"Payment Method: {payment_method}")
        if finance_payment_id:
            print(f"Finance System Payment ID: {finance_payment_id}")
        print("\nThank you for your purchase!")

        conn.close()
        input("\nPress Enter to continue...")
        
    except sqlite3.Error as e:
        print(f"Database error during checkout: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
    except Exception as e:
        print(f"Error during checkout: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

@log_read(module="shop", description="Viewing purchase history")
def view_purchase_history():
    """View the user's purchase history"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view purchase history.")
        return
    
    if not auth.check_permission('view_own_purchase_history'):
        print("You don't have permission to view purchase history.")
        return
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get transactions for the current user
        cursor.execute(
            '''
            SELECT * FROM shop_transactions
            WHERE user_id = ?
            ORDER BY transaction_date DESC
            ''',
            [auth.current_user['id']]
        )
        
        transactions = cursor.fetchall()
        
        if not transactions:
            print("\nYou haven't made any purchases yet.")
            conn.close()
            return
        
        # Display transactions
        print("\nYour Purchase History:")
        print(f"{'Transaction ID':<20} {'Date':<20} {'Total':<12} {'Payment Method':<20} {'Status'}")
        print("-" * 85)
        
        for transaction in transactions:
            total_formatted = f"£{transaction['total_amount']:.2f}"
            date_formatted = transaction['transaction_date']
            print(f"{transaction['transaction_id']:<20} {date_formatted:<20} {total_formatted:<12} {transaction['payment_method']:<20} {transaction['status']}")
        
        # Option to view transaction details
        while True:
            transaction_id = input("\nEnter transaction ID to view details (or 'back' to return): ").strip()
            
            if transaction_id.lower() == 'back':
                break
            
            # Check if transaction belongs to user
            cursor.execute(
                '''
                SELECT * FROM shop_transactions
                WHERE transaction_id = ? AND user_id = ?
                ''',
                [transaction_id, auth.current_user['id']]
            )
            
            transaction = cursor.fetchone()
            
            if not transaction:
                print("Transaction not found or not authorized to view.")
                continue
            
            # Get transaction items
            cursor.execute(
                '''
                SELECT i.*, p.name 
                FROM shop_transaction_items i
                JOIN shop_products p ON i.product_id = p.product_id
                WHERE i.transaction_id = ?
                ''',
                [transaction_id]
            )
            
            items = cursor.fetchall()
            
            # Display transaction details
            print(f"\nTransaction Details - {transaction_id}")
            print(f"Date: {transaction['transaction_date']}")
            print(f"Status: {transaction['status']}")
            print(f"Payment Method: {transaction['payment_method']}")
            
            print("\nItems:")
            print(f"{'Product':<30} {'Price':<10} {'Quantity':<10} {'Subtotal':<12}")
            print("-" * 70)
            
            for item in items:
                price_formatted = f"£{item['price_per_item']:.2f}"
                subtotal_formatted = f"£{item['subtotal']:.2f}"
                print(f"{item['name'][:28]:<30} {price_formatted:<10} {item['quantity']:<10} {subtotal_formatted:<12}")
            
            print("-" * 70)
            print(f"Total: £{transaction['total_amount']:.2f}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error viewing purchase history: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error viewing purchase history: {e}")
        if 'conn' in locals():
            conn.close()

@log_read(module="shop", description="Viewing all transactions")
def view_all_transactions():
    """View all shop transactions (admin function)"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view transactions.")
        return
    
    if not auth.check_permission('view_all_transactions'):
        print("You don't have permission to view all transactions.")
        return
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get filter options
        print("\nFilter options:")
        print("1. All transactions")
        print("2. By date range")
        print("3. By payment method")
        print("4. By student ID")
        print("5. By minimum amount")
        
        filter_choice = input("Enter your choice (1-5): ").strip()
        
        query_params = []
        base_query = '''
        SELECT t.*, u.username 
        FROM shop_transactions t
        LEFT JOIN users u ON t.user_id = u.id
        '''
        
        if filter_choice == '1':
            # All transactions
            query = base_query + ' ORDER BY t.transaction_date DESC'
        elif filter_choice == '2':
            # By date range
            start_date = input("Enter start date (YYYY-MM-DD): ").strip()
            end_date = input("Enter end date (YYYY-MM-DD): ").strip()
            
            try:
                # Validate dates
                start = datetime.strptime(start_date, '%Y-%m-%d')
                end = datetime.strptime(end_date, '%Y-%m-%d')
                
                # Add time to make it a full day range
                start_date = start.strftime('%Y-%m-%d 00:00:00')
                end_date = end.strftime('%Y-%m-%d 23:59:59')
                
                query = base_query + ' WHERE t.transaction_date BETWEEN ? AND ? ORDER BY t.transaction_date DESC'
                query_params = [start_date, end_date]
            except ValueError:
                print("Invalid date format. Using all transactions.")
                query = base_query + ' ORDER BY t.transaction_date DESC'
            
        elif filter_choice == '3':
            # By payment method
            print("\nPayment Methods:")
            print("1. Credit/Debit Card")
            print("2. Student Account")
            print("3. PayPal")
            
            method_choice = input("Select payment method (1-3): ").strip()
            
            if method_choice == '1':
                payment_method = "Credit/Debit Card"
            elif method_choice == '2':
                payment_method = "Student Account"
            elif method_choice == '3':
                payment_method = "PayPal"
            else:
                print("Invalid choice. Using all transactions.")
                query = base_query + ' ORDER BY t.transaction_date DESC'
                payment_method = None
            
            if payment_method:
                query = base_query + ' WHERE t.payment_method = ? ORDER BY t.transaction_date DESC'
                query_params = [payment_method]
            
        elif filter_choice == '4':
            # By student ID
            student_id = input("Enter student ID: ").strip()
            
            if student_id:
                query = base_query + ' WHERE t.student_id = ? ORDER BY t.transaction_date DESC'
                query_params = [student_id]
            else:
                print("Invalid student ID. Using all transactions.")
                query = base_query + ' ORDER BY t.transaction_date DESC'
            
        elif filter_choice == '5':
            # By minimum amount
            try:
                min_amount = float(input("Enter minimum amount: ").strip())
                
                query = base_query + ' WHERE t.total_amount >= ? ORDER BY t.total_amount DESC'
                query_params = [min_amount]
            except ValueError:
                print("Invalid amount. Using all transactions.")
                query = base_query + ' ORDER BY t.transaction_date DESC'
            
        else:
            print("Invalid choice. Using all transactions.")
            query = base_query + ' ORDER BY t.transaction_date DESC'
        
        # Execute the query
        cursor.execute(query, query_params)
        transactions = cursor.fetchall()
        
        if not transactions:
            print("\nNo transactions found matching your criteria.")
            conn.close()
            return
        
        # Display transactions
        print("\nTransaction List:")
        print(f"{'ID':<12} {'User':<15} {'Student ID':<12} {'Date':<20} {'Amount':<10} {'Payment Method':<20} {'Status'}")
        print("-" * 100)
        
        for transaction in transactions:
            amount_formatted = f"£{transaction['total_amount']:.2f}"
            date_formatted = transaction['transaction_date']
            username = transaction['username'] or 'Unknown'
            student_id = transaction['student_id'] or 'N/A'
            
            print(f"{transaction['transaction_id']:<12} {username[:13]:<15} {student_id:<12} {date_formatted:<20} {amount_formatted:<10} {transaction['payment_method']:<20} {transaction['status']}")
        
        print(f"\nTotal Transactions: {len(transactions)}")
        
        # Sum of all amounts
        total_value = sum(t['total_amount'] for t in transactions)
        print(f"Total Value: £{total_value:.2f}")
        
        # Option to view transaction details
        while True:
            transaction_id = input("\nEnter transaction ID to view details (or 'back' to return): ").strip()
            
            if transaction_id.lower() == 'back':
                break
            
            # Check if transaction exists
            cursor.execute(
                '''
                SELECT t.*, u.username, u.email
                FROM shop_transactions t
                LEFT JOIN users u ON t.user_id = u.id
                WHERE t.transaction_id = ?
                ''',
                [transaction_id]
            )
            
            transaction = cursor.fetchone()
            
            if not transaction:
                print("Transaction not found.")
                continue
            
            # Get transaction items
            cursor.execute(
                '''
                SELECT i.*, p.name 
                FROM shop_transaction_items i
                JOIN shop_products p ON i.product_id = p.product_id
                WHERE i.transaction_id = ?
                ''',
                [transaction_id]
            )
            
            items = cursor.fetchall()
            
            # Display transaction details
            print(f"\nTransaction Details - {transaction_id}")
            print(f"User: {transaction['username']} (ID: {transaction['user_id']})")
            print(f"Email: {transaction['email']}")
            if transaction['student_id']:
                print(f"Student ID: {transaction['student_id']}")
            print(f"Date: {transaction['transaction_date']}")
            print(f"Status: {transaction['status']}")
            print(f"Payment Method: {transaction['payment_method']}")
            
            if transaction['notes']:
                print(f"Notes: {transaction['notes']}")
            
            print("\nItems:")
            print(f"{'Product':<30} {'Price':<10} {'Quantity':<10} {'Subtotal':<12}")
            print("-" * 70)
            
            for item in items:
                price_formatted = f"£{item['price_per_item']:.2f}"
                subtotal_formatted = f"£{item['subtotal']:.2f}"
                print(f"{item['name'][:28]:<30} {price_formatted:<10} {item['quantity']:<10} {subtotal_formatted:<12}")
            
            print("-" * 70)
            print(f"Total: £{transaction['total_amount']:.2f}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error viewing transactions: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error viewing transactions: {e}")
        if 'conn' in locals():
            conn.close()

# Product Management Functions
@log_menu_navigation(description="Displaying product management menu")
def display_product_management_menu():
    """Display the menu for product management"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage products.")
        return
    
    if not auth.check_permission('manage_products'):
        print("You don't have permission to manage products.")
        return
    
    while True:
        print("\nProduct Management Menu:")
        print("1. Add New Product")
        print("2. Edit Product")
        print("3. Deactivate/Activate Product")
        print("4. View All Products")
        print("5. Return to Shop Menu")
        
        choice = input("Enter your choice (1-5): ").strip()
        
        if choice == '1':
            add_new_product()
        elif choice == '2':
            edit_product()
        elif choice == '3':
            toggle_product_status()
        elif choice == '4':
            view_all_products()
        elif choice == '5':
            return
        else:
            print("Invalid choice. Please try again.")

@log_create(module="shop", description="Adding new product")
def add_new_product():
    """Add a new product to the shop"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to add products.")
        return
    
    if not auth.check_permission('manage_products'):
        print("You don't have permission to add products.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nAdd New Product:")
        
        # Generate product ID
        cursor.execute("SELECT MAX(SUBSTR(product_id, 2)) FROM shop_products WHERE product_id LIKE 'P%'")
        result = cursor.fetchone()
        
        try:
            if result[0]:
                next_id = int(result[0]) + 1
            else:
                next_id = 1
            product_id = f"P{next_id:03d}"
        except (ValueError, TypeError):
            product_id = f"P{int(time.time())}"
        
        print(f"Generated Product ID: {product_id}")
        
        # Get product details
        name = None
        while not name:
            name = input("Product Name: ").strip()
            if not name:
                print("Product name cannot be empty.")
        
        description = input("Description: ").strip()
        
        # Get price with validation
        price = None
        while price is None:
            try:
                price_input = input("Price (£): ").strip()
                price = float(price_input)
                if price < 0:
                    print("Price cannot be negative.")
                    price = None
            except ValueError:
                print("Invalid price. Please enter a valid number.")
        
        # Get category
        cursor.execute("SELECT DISTINCT category FROM shop_products ORDER BY category")
        categories = cursor.fetchall()
        
        print("\nExisting Categories:")
        if categories:
            for i, category in enumerate(categories):
                print(f"{i+1}. {category[0]}")
            print(f"{len(categories)+1}. Other (create new)")
            
            try:
                category_choice = int(input(f"Select category (1-{len(categories)+1}): "))
                
                if 1 <= category_choice <= len(categories):
                    category = categories[category_choice-1][0]
                else:
                    category = input("Enter new category name: ").strip()
            except ValueError:
                category = input("Enter category name: ").strip()
        else:
            category = input("Enter category name: ").strip()
        
        # Get tax rate (with default)
        tax_rate = 0.2  # Default 20%
        try:
            tax_input = input("Tax Rate (default 20%): ").strip()
            if tax_input:
                tax_rate = float(tax_input) / 100
        except ValueError:
            print("Invalid tax rate. Using default 20%.")
        
        # Get initial inventory
        initial_stock = None
        while initial_stock is None:
            try:
                stock_input = input("Initial Stock Quantity: ").strip()
                initial_stock = int(stock_input)
                if initial_stock < 0:
                    print("Stock cannot be negative.")
                    initial_stock = None
            except ValueError:
                print("Invalid quantity. Please enter a whole number.")
        
        # Get restock threshold
        restock_threshold = 5  # Default
        try:
            threshold_input = input("Restock Threshold (default 5): ").strip()
            if threshold_input:
                restock_threshold = int(threshold_input)
                if restock_threshold < 0:
                    print("Threshold cannot be negative. Using default 5.")
                    restock_threshold = 5
        except ValueError:
            print("Invalid threshold. Using default 5.")
        
        # Current datetime for timestamps
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Insert product
        cursor.execute(
            '''
            INSERT INTO shop_products
            (product_id, name, description, price, category, created_at, updated_at, tax_rate, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            [product_id, name, description, price, category, now, now, tax_rate, 1]
        )
        
        # Insert inventory
        cursor.execute(
            '''
            INSERT INTO shop_inventory
            (product_id, quantity, last_restock_date, restock_threshold)
            VALUES (?, ?, ?, ?)
            ''',
            [product_id, initial_stock, now, restock_threshold]
        )
        
        conn.commit()
        
        print(f"\nProduct {product_id} added successfully!")
        print(f"Name: {name}")
        print(f"Price: £{price:.2f}")
        print(f"Category: {category}")
        print(f"Initial Stock: {initial_stock}")
        
        conn.close()
        input("\nPress Enter to continue...")
        
    except sqlite3.Error as e:
        print(f"Database error adding product: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
    except Exception as e:
        print(f"Error adding product: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

@log_update(module="shop", description="Editing product")
def edit_product():
    """Edit an existing product"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to edit products.")
        return
    
    if not auth.check_permission('manage_products'):
        print("You don't have permission to edit products.")
        return
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get product list
        cursor.execute(
            '''
            SELECT p.*, i.quantity
            FROM shop_products p
            JOIN shop_inventory i ON p.product_id = i.product_id
            ORDER BY p.name
            '''
        )
        
        products = cursor.fetchall()
        
        if not products:
            print("No products found in the database.")
            conn.close()
            return
        
        # Display product list
        print("\nProduct List:")
        print(f"{'ID':<8} {'Name':<30} {'Price':<10} {'Stock':<8} {'Active'}")
        print("-" * 70)
        
        for product in products:
            price_formatted = f"£{product['price']:.2f}"
            active_status = "Yes" if product['is_active'] else "No"
            print(f"{product['product_id']:<8} {product['name'][:28]:<30} {price_formatted:<10} {product['quantity']:<8} {active_status}")
        
        # Get product to edit
        product_id = input("\nEnter product ID to edit: ").strip().upper()
        
        cursor.execute(
            '''
            SELECT p.*, i.quantity, i.restock_threshold
            FROM shop_products p
            JOIN shop_inventory i ON p.product_id = i.product_id
            WHERE p.product_id = ?
            ''',
            [product_id]
        )
        
        product = cursor.fetchone()
        
        if not product:
            print(f"Product {product_id} not found.")
            conn.close()
            return
        
        # Display current product details
        print(f"\nEditing Product: {product['product_id']} - {product['name']}")
        print("Current details:")
        print(f"Name: {product['name']}")
        print(f"Description: {product['description']}")
        print(f"Price: £{product['price']:.2f}")
        print(f"Category: {product['category']}")
        print(f"Tax Rate: {product['tax_rate']*100:.1f}%")
        print(f"Active: {'Yes' if product['is_active'] else 'No'}")
        print(f"Stock: {product['quantity']}")
        print(f"Restock Threshold: {product['restock_threshold']}")
        
        # Get updated details
        print("\nEnter new details (leave blank to keep current value):")
        
        name = input(f"Name [{product['name']}]: ").strip()
        if not name:
            name = product['name']
        
        description = input(f"Description [{product['description']}]: ").strip()
        if not description:
            description = product['description']
        
        price = None
        while price is None:
            try:
                price_input = input(f"Price (£) [{product['price']:.2f}]: ").strip()
                if not price_input:
                    price = product['price']
                else:
                    price = float(price_input)
                    if price < 0:
                        print("Price cannot be negative.")
                        price = None
            except ValueError:
                print("Invalid price. Please enter a valid number.")
        
        category = input(f"Category [{product['category']}]: ").strip()
        if not category:
            category = product['category']
        
        tax_rate = None
        while tax_rate is None:
            try:
                tax_input = input(f"Tax Rate % [{product['tax_rate']*100:.1f}]: ").strip()
                if not tax_input:
                    tax_rate = product['tax_rate']
                else:
                    tax_rate = float(tax_input) / 100
                    if tax_rate < 0:
                        print("Tax rate cannot be negative.")
                        tax_rate = None
            except ValueError:
                print("Invalid tax rate. Please enter a valid number.")
        
        # Update product
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute(
            '''
            UPDATE shop_products
            SET name = ?, description = ?, price = ?, category = ?, 
                tax_rate = ?, updated_at = ?
            WHERE product_id = ?
            ''',
            [name, description, price, category, tax_rate, now, product_id]
        )
        
        conn.commit()
        
        print(f"\nProduct {product_id} updated successfully!")
        
        conn.close()
        input("\nPress Enter to continue...")
        
    except sqlite3.Error as e:
        print(f"Database error editing product: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
    except Exception as e:
        print(f"Error editing product: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

@log_update(module="shop", description="Toggling product status")
def toggle_product_status():
    """Activate or deactivate a product"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to change product status.")
        return
    
    if not auth.check_permission('manage_products'):
        print("You don't have permission to change product status.")
        return
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get product list
        cursor.execute(
            '''
            SELECT p.*, i.quantity
            FROM shop_products p
            JOIN shop_inventory i ON p.product_id = i.product_id
            ORDER BY p.is_active DESC, p.name
            '''
        )
        
        products = cursor.fetchall()
        
        if not products:
            print("No products found in the database.")
            conn.close()
            return
        
        # Display product list
        print("\nProduct List:")
        print(f"{'ID':<8} {'Name':<30} {'Price':<10} {'Stock':<8} {'Active'}")
        print("-" * 70)
        
        for product in products:
            price_formatted = f"£{product['price']:.2f}"
            active_status = "Yes" if product['is_active'] else "No"
            print(f"{product['product_id']:<8} {product['name'][:28]:<30} {price_formatted:<10} {product['quantity']:<8} {active_status}")
        
        # Get product to toggle
        product_id = input("\nEnter product ID to toggle status: ").strip().upper()
        
        cursor.execute(
            '''
            SELECT * FROM shop_products
            WHERE product_id = ?
            ''',
            [product_id]
        )
        
        product = cursor.fetchone()
        
        if not product:
            print(f"Product {product_id} not found.")
            conn.close()
            return
        
        # Toggle status
        new_status = 0 if product['is_active'] else 1
        status_text = "activated" if new_status else "deactivated"
        
        confirm = input(f"Are you sure you want to {status_text.lower()} {product['name']}? (y/n): ").strip().lower()
        
        if confirm != 'y':
            print("Operation cancelled.")
            conn.close()
            return
        
        cursor.execute(
            '''
            UPDATE shop_products
            SET is_active = ?, updated_at = ?
            WHERE product_id = ?
            ''',
            [new_status, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), product_id]
        )
        
        conn.commit()
        
        print(f"\nProduct {product_id} - {product['name']} has been {status_text}.")
        
        conn.close()
        input("\nPress Enter to continue...")
        
    except sqlite3.Error as e:
        print(f"Database error toggling product status: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
    except Exception as e:
        print(f"Error toggling product status: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

@log_read(module="shop", description="Viewing all products")
def view_all_products():
    """View all products in the shop database"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view all products.")
        return
    
    if not auth.check_permission('manage_products') and not auth.check_permission('view_products'):
        print("You don't have permission to view products.")
        return
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all products with inventory
        cursor.execute(
            '''
            SELECT p.*, i.quantity, i.restock_threshold, i.last_restock_date
            FROM shop_products p
            JOIN shop_inventory i ON p.product_id = i.product_id
            ORDER BY p.category, p.name
            '''
        )
        
        products = cursor.fetchall()
        
        if not products:
            print("No products found in the database.")
            conn.close()
            return
        
        # Display products by category
        current_category = None
        
        print("\nProduct Inventory:")
        for product in products:
            # Print category header if changed
            if product['category'] != current_category:
                current_category = product['category']
                print(f"\n--- {current_category} ---")
                print(f"{'ID':<8} {'Name':<30} {'Price':<10} {'Stock':<8} {'Threshold':<10} {'Active'}")
                print("-" * 75)
            
            price_formatted = f"£{product['price']:.2f}"
            active_status = "Yes" if product['is_active'] else "No"
            
            # Highlight low stock with asterisk
            stock_display = f"{product['quantity']}"
            if product['quantity'] <= product['restock_threshold']:
                stock_display += "*"
            
            print(f"{product['product_id']:<8} {product['name'][:28]:<30} {price_formatted:<10} {stock_display:<8} {product['restock_threshold']:<10} {active_status}")
        
        # Show legend for low stock
        print("\n* indicates stock below or at restock threshold")
        
        # Count statistics
        total_products = len(products)
        active_products = sum(1 for p in products if p['is_active'])
        low_stock = sum(1 for p in products if p['quantity'] <= p['restock_threshold'])
        
        print(f"\nTotal Products: {total_products}")
        print(f"Active Products: {active_products}")
        print(f"Products with Low Stock: {low_stock}")
        
        conn.close()
        input("\nPress Enter to continue...")
        
    except sqlite3.Error as e:
        print(f"Database error viewing products: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error viewing products: {e}")
        if 'conn' in locals():
            conn.close()

# Inventory Management Functions
@log_menu_navigation(description="Displaying inventory management menu")
def display_inventory_management_menu():
    """Display the menu for inventory management"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage inventory.")
        return
    
    if not auth.check_permission('manage_inventory'):
        print("You don't have permission to manage inventory.")
        return
    
    while True:
        print("\nInventory Management Menu:")
        print("1. Update Stock Levels")
        print("2. Restock Products")
        print("3. View Low Stock Products")
        print("4. Adjust Restock Thresholds")
        print("5. Return to Shop Menu")
        
        choice = input("Enter your choice (1-5): ").strip()
        
        if choice == '1':
            update_stock_levels()
        elif choice == '2':
            restock_products()
        elif choice == '3':
            view_low_stock_products()
        elif choice == '4':
            adjust_restock_thresholds()
        elif choice == '5':
            return
        else:
            print("Invalid choice. Please try again.")

@log_update(module="shop", description="Updating stock levels")
def update_stock_levels():
    """Update stock levels for products"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to update stock levels.")
        return
    
    if not auth.check_permission('manage_inventory'):
        print("You don't have permission to update stock levels.")
        return
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get product list
        cursor.execute(
            '''
            SELECT p.product_id, p.name, p.category, i.quantity
            FROM shop_products p
            JOIN shop_inventory i ON p.product_id = i.product_id
            WHERE p.is_active = 1
            ORDER BY p.category, p.name
            '''
        )
        
        products = cursor.fetchall()
        
        if not products:
            print("No active products found in the database.")
            conn.close()
            return
        
        # Display product list
        print("\nCurrent Stock Levels:")
        print(f"{'ID':<8} {'Name':<30} {'Category':<15} {'Current Stock'}")
        print("-" * 70)
        
        for product in products:
            print(f"{product['product_id']:<8} {product['name'][:28]:<30} {product['category'][:13]:<15} {product['quantity']}")
        
        # Get product to update
        product_id = input("\nEnter product ID to update stock (or 'back' to return): ").strip().upper()
        
        if product_id.lower() == 'back':
            conn.close()
            return
        
        cursor.execute(
            '''
            SELECT p.product_id, p.name, i.quantity
            FROM shop_products p
            JOIN shop_inventory i ON p.product_id = i.product_id
            WHERE p.product_id = ?
            ''',
            [product_id]
        )
        
        product = cursor.fetchone()
        
        if not product:
            print(f"Product {product_id} not found.")
            conn.close()
            return
        
        # Display current stock
        print(f"\nUpdating stock for: {product['name']}")
        print(f"Current stock: {product['quantity']}")
        
        # Get new stock level
        while True:
            try:
                print("\nOptions:")
                print("1. Set exact stock level")
                print("2. Add to current stock")
                print("3. Remove from current stock")
                
                update_type = input("Choose option (1-3): ").strip()
                
                if update_type == '1':
                    # Set exact amount
                    new_quantity = int(input("Enter new stock level: ").strip())
                    if new_quantity < 0:
                        print("Stock cannot be negative.")
                        continue
                    
                    change = new_quantity - product['quantity']
                    action = "Set"
                    
                elif update_type == '2':
                    # Add to stock
                    add_quantity = int(input("Enter amount to add: ").strip())
                    if add_quantity < 0:
                        print("Amount to add cannot be negative.")
                        continue
                    
                    new_quantity = product['quantity'] + add_quantity
                    change = add_quantity
                    action = "Added"
                    
                elif update_type == '3':
                    # Remove from stock
                    remove_quantity = int(input("Enter amount to remove: ").strip())
                    if remove_quantity < 0:
                        print("Amount to remove cannot be negative.")
                        continue
                    
                    if remove_quantity > product['quantity']:
                        print(f"Cannot remove more than current stock ({product['quantity']}).")
                        continue
                    
                    new_quantity = product['quantity'] - remove_quantity
                    change = -remove_quantity
                    action = "Removed"
                    
                else:
                    print("Invalid choice. Please select 1, 2, or 3.")
                    continue
                
                # Confirm update
                sign = "+" if change >= 0 else ""
                print(f"\nUpdate Summary:")
                print(f"Product: {product['name']} ({product_id})")
                print(f"Current Stock: {product['quantity']}")
                print(f"New Stock: {new_quantity} ({sign}{change})")
                
                confirm = input("Confirm update? (y/n): ").strip().lower()
                
                if confirm == 'y':
                    # Update stock
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute(
                        '''
                        UPDATE shop_inventory
                        SET quantity = ?, last_restock_date = ?
                        WHERE product_id = ?
                        ''',
                        [new_quantity, now, product_id]
                    )
                    
                    conn.commit()
                    print(f"\n{action} stock successfully! New level: {new_quantity}")
                    break
                else:
                    print("Update cancelled.")
                    break
                
            except ValueError:
                print("Invalid input. Please enter a whole number.")
        
        conn.close()
        input("\nPress Enter to continue...")
        
    except sqlite3.Error as e:
        print(f"Database error updating stock: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
    except Exception as e:
        print(f"Error updating stock: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

@log_update(module="shop", description="Restocking products")
def restock_products():
    """Restock products that are below threshold"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to restock products.")
        return
    
    if not auth.check_permission('manage_inventory'):
        print("You don't have permission to restock products.")
        return
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get products below restock threshold
        cursor.execute(
            '''
            SELECT p.product_id, p.name, p.category, i.quantity, i.restock_threshold
            FROM shop_products p
            JOIN shop_inventory i ON p.product_id = i.product_id
            WHERE p.is_active = 1 AND i.quantity <= i.restock_threshold
            ORDER BY (i.quantity * 1.0 / i.restock_threshold), p.category, p.name
            '''
        )
        
        products = cursor.fetchall()
        
        if not products:
            print("No products need restocking at this time.")
            conn.close()
            return
        
        # Display products needing restock
        print("\nProducts Needing Restock:")
        print(f"{'ID':<8} {'Name':<30} {'Category':<15} {'Current Stock':<15} {'Threshold'}")
        print("-" * 80)
        
        for product in products:
            print(f"{product['product_id']:<8} {product['name'][:28]:<30} {product['category'][:13]:<15} {product['quantity']:<15} {product['restock_threshold']}")
        
        print("\nRestock Options:")
        print("1. Restock all products to threshold + 50%")
        print("2. Restock specific product")
        print("3. Cancel")
        
        choice = input("Choose option (1-3): ").strip()
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if choice == '1':
            # Restock all products
            confirm = input("Are you sure you want to restock all listed products? (y/n): ").strip().lower()
            
            if confirm != 'y':
                print("Restock cancelled.")
                conn.close()
                return
            
            # Restock each product to threshold + 50%
            for product in products:
                new_quantity = int(product['restock_threshold'] * 1.5)
                if new_quantity <= product['quantity']:
                    new_quantity = product['restock_threshold'] * 2
                
                cursor.execute(
                    '''
                    UPDATE shop_inventory
                    SET quantity = ?, last_restock_date = ?
                    WHERE product_id = ?
                    ''',
                    [new_quantity, now, product['product_id']]
                )
            
            conn.commit()
            print(f"\nRestocked {len(products)} products successfully!")
            
        elif choice == '2':
            # Restock specific product
            product_id = input("Enter product ID to restock: ").strip().upper()
            
            # Check if product is in the list
            product_to_restock = None
            for product in products:
                if product['product_id'] == product_id:
                    product_to_restock = product
                    break
            
            if not product_to_restock:
                print(f"Product {product_id} is not in the restock list.")
                conn.close()
                return
            
            # Get restock amount
            try:
                current = product_to_restock['quantity']
                threshold = product_to_restock['restock_threshold']
                suggested = threshold * 2 - current
                
                print(f"\nProduct: {product_to_restock['name']}")
                print(f"Current Stock: {current}")
                print(f"Threshold: {threshold}")
                print(f"Suggested Restock Amount: {suggested}")
                
                amount_input = input(f"Enter amount to add [default: {suggested}]: ").strip()
                
                if amount_input:
                    amount = int(amount_input)
                    if amount < 0:
                        print("Amount cannot be negative.")
                        conn.close()
                        return
                else:
                    amount = suggested
                
                new_quantity = current + amount
                
                # Update inventory
                cursor.execute(
                    '''
                    UPDATE shop_inventory
                    SET quantity = ?, last_restock_date = ?
                    WHERE product_id = ?
                    ''',
                    [new_quantity, now, product_id]
                )
                
                conn.commit()
                print(f"\nRestocked {product_id} successfully!")
                print(f"Previous stock: {current}")
                print(f"Added: {amount}")
                print(f"New stock: {new_quantity}")
                
            except ValueError:
                print("Invalid input. Please enter a whole number.")
                conn.close()
                return
                
        elif choice == '3':
            print("Restock cancelled.")
            conn.close()
            return
        
        else:
            print("Invalid choice.")
            conn.close()
            return
        
        conn.close()
        input("\nPress Enter to continue...")
        
    except sqlite3.Error as e:
        print(f"Database error restocking products: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
    except Exception as e:
        print(f"Error restocking products: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

@log_read(module="shop", description="Viewing low stock")
def view_low_stock_products():
    """View products with low stock levels"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view low stock products.")
        return
    
    if not auth.check_permission('manage_inventory'):
        print("You don't have permission to view inventory details.")
        return
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get products below threshold
        cursor.execute(
            '''
            SELECT p.product_id, p.name, p.category, p.price, i.quantity, i.restock_threshold,
                   i.last_restock_date, (i.quantity * 100.0 / i.restock_threshold) as stock_percent
            FROM shop_products p
            JOIN shop_inventory i ON p.product_id = i.product_id
            WHERE p.is_active = 1 AND i.quantity <= i.restock_threshold
            ORDER BY stock_percent, p.category, p.name
            '''
        )
        
        low_stock = cursor.fetchall()
        
        if not low_stock:
            print("No products are below their restock threshold.")
            
            # Check for products getting close (within 20% above threshold)
            cursor.execute(
                '''
                SELECT p.product_id, p.name, p.category, i.quantity, i.restock_threshold,
                       (i.quantity * 100.0 / i.restock_threshold) as stock_percent
                FROM shop_products p
                JOIN shop_inventory i ON p.product_id = i.product_id
                WHERE p.is_active = 1 
                  AND i.quantity > i.restock_threshold 
                  AND i.quantity <= (i.restock_threshold * 1.2)
                ORDER BY stock_percent, p.category, p.name
                '''
            )
            
            warning_stock = cursor.fetchall()
            
            if warning_stock:
                print("\nProducts approaching restock threshold:")
                print(f"{'ID':<8} {'Name':<30} {'Category':<15} {'Stock':<8} {'Threshold':<10} {'Percent'}")
                print("-" * 85)
                
                for product in warning_stock:
                    percent = int(product['stock_percent'])
                    print(f"{product['product_id']:<8} {product['name'][:28]:<30} {product['category'][:13]:<15} {product['quantity']:<8} {product['restock_threshold']:<10} {percent}%")
            
            conn.close()
            input("\nPress Enter to continue...")
            return
        
        # Display low stock products
        print("\nLow Stock Products:")
        print(f"{'ID':<8} {'Name':<30} {'Category':<15} {'Price':<10} {'Stock':<8} {'Threshold':<10} {'Percent':<8} {'Last Restock'}")
        print("-" * 110)
        
        for product in low_stock:
            price_formatted = f"£{product['price']:.2f}"
            percent = int(product['stock_percent'])
            last_restock = product['last_restock_date']
            
            print(f"{product['product_id']:<8} {product['name'][:28]:<30} {product['category'][:13]:<15} "
                  f"{price_formatted:<10} {product['quantity']:<8} {product['restock_threshold']:<10} "
                  f"{percent}%{'':<8} {last_restock}")
        
        # Print summary
        total_value = sum(p['price'] * p['quantity'] for p in low_stock)
        print(f"\nTotal Low Stock Products: {len(low_stock)}")
        print(f"Total Value of Low Stock: £{total_value:.2f}")
        
        # Option to restock
        restock_option = input("\nWould you like to restock these products now? (y/n): ").strip().lower()
        
        if restock_option == 'y':
            conn.close()
            restock_products()
        else:
            conn.close()
            input("\nPress Enter to continue...")
        
    except sqlite3.Error as e:
        print(f"Database error viewing low stock: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error viewing low stock: {e}")
        if 'conn' in locals():
            conn.close()

@log_update(module="shop", description="Adjusting restock thresholds")
def adjust_restock_thresholds():
    """Adjust restock thresholds for products"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to adjust restock thresholds.")
        return
    
    if not auth.check_permission('manage_inventory'):
        print("You don't have permission to adjust inventory settings.")
        return
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get product list with inventory details
        cursor.execute(
            '''
            SELECT p.product_id, p.name, p.category, i.quantity, i.restock_threshold
            FROM shop_products p
            JOIN shop_inventory i ON p.product_id = i.product_id
            WHERE p.is_active = 1
            ORDER BY p.category, p.name
            '''
        )
        
        products = cursor.fetchall()
        
        if not products:
            print("No active products found.")
            conn.close()
            return
        
        # Display products with thresholds
        print("\nCurrent Restock Thresholds:")
        print(f"{'ID':<8} {'Name':<30} {'Category':<15} {'Current Stock':<15} {'Threshold'}")
        print("-" * 80)
        
        for product in products:
            print(f"{product['product_id']:<8} {product['name'][:28]:<30} {product['category'][:13]:<15} {product['quantity']:<15} {product['restock_threshold']}")
        
        print("\nAdjustment Options:")
        print("1. Adjust threshold for specific product")
        print("2. Adjust thresholds by category")
        print("3. Adjust all thresholds")
        print("4. Return to Inventory Menu")
        
        choice = input("Choose option (1-4): ").strip()
        
        if choice == '1':
            # Adjust specific product
            product_id = input("Enter product ID: ").strip().upper()
            
            cursor.execute(
                '''
                SELECT p.product_id, p.name, i.quantity, i.restock_threshold
                FROM shop_products p
                JOIN shop_inventory i ON p.product_id = i.product_id
                WHERE p.product_id = ?
                ''',
                [product_id]
            )
            
            product = cursor.fetchone()
            
            if not product:
                print(f"Product {product_id} not found.")
                conn.close()
                return
            
            print(f"\nProduct: {product['name']} ({product_id})")
            print(f"Current Stock: {product['quantity']}")
            print(f"Current Threshold: {product['restock_threshold']}")
            
            try:
                new_threshold = int(input("Enter new threshold: ").strip())
                
                if new_threshold < 0:
                    print("Threshold cannot be negative.")
                    conn.close()
                    return
                
                # Update threshold
                cursor.execute(
                    '''
                    UPDATE shop_inventory
                    SET restock_threshold = ?
                    WHERE product_id = ?
                    ''',
                    [new_threshold, product_id]
                )
                
                conn.commit()
                print(f"Threshold updated successfully for {product_id}!")
                
            except ValueError:
                print("Invalid input. Please enter a whole number.")
                conn.close()
                return
            
        elif choice == '2':
            # Adjust by category
            cursor.execute("SELECT DISTINCT category FROM shop_products WHERE is_active = 1 ORDER BY category")
            categories = cursor.fetchall()
            
            print("\nAvailable Categories:")
            for i, category in enumerate(categories):
                print(f"{i+1}. {category['category']}")
            
            try:
                cat_choice = int(input("Select category number: ").strip())
                
                if cat_choice < 1 or cat_choice > len(categories):
                    print("Invalid category selection.")
                    conn.close()
                    return
                
                selected_category = categories[cat_choice-1]['category']
                
                # Get current thresholds for this category
                cursor.execute(
                    '''
                    SELECT AVG(i.restock_threshold) as avg_threshold
                    FROM shop_products p
                    JOIN shop_inventory i ON p.product_id = i.product_id
                    WHERE p.category = ? AND p.is_active = 1
                    ''',
                    [selected_category]
                )
                
                avg_threshold = cursor.fetchone()['avg_threshold']
                
                print(f"\nCategory: {selected_category}")
                print(f"Average Current Threshold: {avg_threshold:.1f}")
                
                new_threshold = int(input("Enter new threshold for all products in this category: ").strip())
                
                if new_threshold < 0:
                    print("Threshold cannot be negative.")
                    conn.close()
                    return
                
                # Update thresholds for this category
                cursor.execute(
                    '''
                    UPDATE shop_inventory
                    SET restock_threshold = ?
                    WHERE product_id IN (
                        SELECT p.product_id FROM shop_products p
                        WHERE p.category = ? AND p.is_active = 1
                    )
                    ''',
                    [new_threshold, selected_category]
                )
                
                affected = cursor.rowcount
                conn.commit()
                print(f"Updated thresholds for {affected} products in {selected_category} category!")
                
            except ValueError:
                print("Invalid input. Please enter a number.")
                conn.close()
                return
            
        elif choice == '3':
            # Adjust all thresholds
            try:
                # Get current average
                cursor.execute(
                    '''
                    SELECT AVG(i.restock_threshold) as avg_threshold
                    FROM shop_inventory i
                    JOIN shop_products p ON i.product_id = p.product_id
                    WHERE p.is_active = 1
                    '''
                )
                
                avg_threshold = cursor.fetchone()['avg_threshold']
                print(f"\nCurrent Average Threshold: {avg_threshold:.1f}")
                
                new_threshold = int(input("Enter new threshold for all active products: ").strip())
                
                if new_threshold < 0:
                    print("Threshold cannot be negative.")
                    conn.close()
                    return
                
                # Update all thresholds
                cursor.execute(
                    '''
                    UPDATE shop_inventory
                    SET restock_threshold = ?
                    WHERE product_id IN (
                        SELECT p.product_id FROM shop_products p
                        WHERE p.is_active = 1
                    )
                    ''',
                    [new_threshold]
                )
                
                affected = cursor.rowcount
                conn.commit()
                print(f"Updated thresholds for {affected} products to {new_threshold}!")
                
            except ValueError:
                print("Invalid input. Please enter a number.")
                conn.close()
                return
                
        elif choice == '4':
            print("Returning to Inventory Menu...")
            conn.close()
            return
            
        else:
            print("Invalid choice.")
            conn.close()
            return
        
        conn.close()
        input("\nPress Enter to continue...")
        
    except sqlite3.Error as e:
        print(f"Database error adjusting thresholds: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
    except Exception as e:
        print(f"Error adjusting thresholds: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

# Discount Management Functions
@log_menu_navigation(description="Displaying discount management menu")
def display_discount_management_menu():
    """Display the menu for discount management"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage discounts.")
        return
    
    if not auth.check_permission('manage_discounts'):
        print("You don't have permission to manage discounts.")
        return
    
    while True:
        print("\nDiscount Management Menu:")
        print("1. Create New Discount")
        print("2. Edit Discount")
        print("3. Activate/Deactivate Discount")
        print("4. View All Discounts")
        print("5. Return to Shop Menu")
        
        choice = input("Enter your choice (1-5): ").strip()
        
        if choice == '1':
            create_discount()
        elif choice == '2':
            edit_discount()
        elif choice == '3':
            toggle_discount_status()
        elif choice == '4':
            view_all_discounts()
        elif choice == '5':
            return
        else:
            print("Invalid choice. Please try again.")

@log_create(module="shop", description="Creating new discount")
def create_discount():
    """Create a new discount in the shop system"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to create discounts.")
        return
    
    if not auth.check_permission('manage_discounts'):
        print("You don't have permission to create discounts.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nCreate New Discount:")
        
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
        
        print(f"Generated Discount ID: {discount_id}")
        
        # Get discount details
        name = None
        while not name:
            name = input("Discount Name: ").strip()
            if not name:
                print("Discount name cannot be empty.")
        
        description = input("Description: ").strip()
        
        # Get discount type
        print("\nDiscount Types:")
        print("1. Percentage (%) off")
        print("2. Fixed Amount (£) off")
        
        discount_type = None
        while not discount_type:
            type_choice = input("Select discount type (1-2): ").strip()
            if type_choice == '1':
                discount_type = 'percentage'
            elif type_choice == '2':
                discount_type = 'fixed'
            else:
                print("Invalid choice. Please select 1 or 2.")
        
        # Get discount value
        discount_value = None
        while discount_value is None:
            try:
                value_input = input("Discount Value: ").strip()
                discount_value = float(value_input)
                
                if discount_value <= 0:
                    print("Discount value must be greater than 0.")
                    discount_value = None
                    continue
                
                if discount_type == 'percentage' and discount_value > 100:
                    print("Percentage discount cannot exceed 100%.")
                    discount_value = None
            except ValueError:
                print("Invalid value. Please enter a number.")
        
        # Get date range (optional)
        start_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"\nStart Date [default: current time ({start_date})]: ")
        custom_start = input("Enter custom start date (YYYY-MM-DD) or press Enter for default: ").strip()
        if custom_start:
            try:
                # Validate date format
                datetime.strptime(custom_start, '%Y-%m-%d')
                start_date = f"{custom_start} 00:00:00"
            except ValueError:
                print(f"Invalid date format. Using default ({start_date}).")
        
        end_date = None
        has_end_date = input("Set an end date? (y/n): ").strip().lower()
        if has_end_date == 'y':
            while True:
                end_date_input = input("End Date (YYYY-MM-DD): ").strip()
                try:
                    # Validate date format
                    end_date_obj = datetime.strptime(end_date_input, '%Y-%m-%d')
                    start_date_obj = datetime.strptime(start_date.split()[0], '%Y-%m-%d')
                    
                    if end_date_obj <= start_date_obj:
                        print("End date must be after start date.")
                        continue
                    
                    end_date = f"{end_date_input} 23:59:59"
                    break
                except ValueError:
                    print("Invalid date format. Please use YYYY-MM-DD.")
        
        # Get applicable products
        print("\nApplicable Products:")
        print("1. All products")
        print("2. Specific category")
        print("3. Custom product list")
        
        applicable_products = 'all'
        applicable_choice = input("Select option (1-3): ").strip()
        
        if applicable_choice == '2':
            # Get categories
            cursor.execute("SELECT DISTINCT category FROM shop_products ORDER BY category")
            categories = cursor.fetchall()
            
            if not categories:
                print("No categories found. Using 'all' as default.")
            else:
                print("\nAvailable Categories:")
                for i, category in enumerate(categories):
                    print(f"{i+1}. {category[0]}")
                
                try:
                    cat_choice = int(input("Select category number: ").strip())
                    if cat_choice < 1 or cat_choice > len(categories):
                        print("Invalid selection. Using 'all' as default.")
                    else:
                        applicable_products = categories[cat_choice-1][0]
                except ValueError:
                    print("Invalid input. Using 'all' as default.")
        
        elif applicable_choice == '3':
            # Custom product list
            product_list = []
            
            cursor.execute("SELECT product_id, name FROM shop_products WHERE is_active = 1 ORDER BY name")
            products = cursor.fetchall()
            
            if not products:
                print("No active products found. Using 'all' as default.")
            else:
                print("\nSelect products (enter product IDs, one per line, blank line to finish):")
                print("\nAvailable Products:")
                for i, product in enumerate(products):
                    print(f"{product[0]}: {product[1]}")
                
                while True:
                    product_id = input("Enter Product ID (or blank to finish): ").strip().upper()
                    if not product_id:
                        break
                    
                    # Verify product exists
                    cursor.execute("SELECT 1 FROM shop_products WHERE product_id = ? AND is_active = 1", [product_id])
                    if cursor.fetchone():
                        if product_id not in product_list:
                            product_list.append(product_id)
                            print(f"Added: {product_id}")
                        else:
                            print(f"Product {product_id} already in list.")
                    else:
                        print(f"Product {product_id} not found or not active.")
                
                if product_list:
                    applicable_products = ','.join(product_list)
                else:
                    print("No products selected. Using 'all' as default.")
        
        # Get minimum purchase amount
        min_purchase = 0.0
        min_input = input("\nMinimum Purchase Amount (£) [default: 0]: ").strip()
        if min_input:
            try:
                min_purchase = float(min_input)
                if min_purchase < 0:
                    print("Minimum purchase cannot be negative. Using 0.")
                    min_purchase = 0.0
            except ValueError:
                print("Invalid amount. Using 0.")
        
        # Current datetime for created_at
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Insert discount
        cursor.execute(
            '''
            INSERT INTO shop_discounts
            (discount_id, name, description, discount_type, discount_value, 
             start_date, end_date, is_active, applicable_products, min_purchase_amount, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            [discount_id, name, description, discount_type, discount_value, 
             start_date, end_date, 1, applicable_products, min_purchase, now]
        )
        
        conn.commit()
        
        print(f"\nDiscount {discount_id} created successfully!")
        print(f"Name: {name}")
        print(f"Type: {discount_type.capitalize()}")
        print(f"Value: {'£' if discount_type == 'fixed' else ''}{discount_value}{'%' if discount_type == 'percentage' else ''}")
        print(f"Start Date: {start_date}")
        if end_date:
            print(f"End Date: {end_date}")
        print(f"Applicable Products: {applicable_products}")
        if min_purchase > 0:
            print(f"Minimum Purchase: £{min_purchase:.2f}")
        
        conn.close()
        input("\nPress Enter to continue...")
        
    except sqlite3.Error as e:
        print(f"Database error creating discount: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
    except Exception as e:
        print(f"Error creating discount: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

@log_update(module="shop", description="Editing discount")
def edit_discount():
    """Edit an existing discount"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to edit discounts.")
        return
    
    if not auth.check_permission('manage_discounts'):
        print("You don't have permission to edit discounts.")
        return
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get discount list
        cursor.execute(
            '''
            SELECT * FROM shop_discounts
            ORDER BY is_active DESC, end_date, name
            '''
        )
        
        discounts = cursor.fetchall()
        
        if not discounts:
            print("No discounts found in the database.")
            conn.close()
            return
        
        # Display discount list
        print("\nDiscount List:")
        print(f"{'ID':<8} {'Name':<25} {'Type':<12} {'Value':<10} {'Start Date':<20} {'End Date':<20} {'Active'}")
        print("-" * 100)
        
        for discount in discounts:
            value_display = f"{'£' if discount['discount_type'] == 'fixed' else ''}{discount['discount_value']}{'%' if discount['discount_type'] == 'percentage' else ''}"
            end_date = discount['end_date'] if discount['end_date'] else 'Never'
            active_status = "Yes" if discount['is_active'] else "No"
            
            print(f"{discount['discount_id']:<8} {discount['name'][:23]:<25} {discount['discount_type']:<12} {value_display:<10} {discount['start_date']:<20} {end_date:<20} {active_status}")
        
        # Get discount to edit
        discount_id = input("\nEnter discount ID to edit: ").strip().upper()
        
        cursor.execute(
            '''
            SELECT * FROM shop_discounts
            WHERE discount_id = ?
            ''',
            [discount_id]
        )
        
        discount = cursor.fetchone()
        
        if not discount:
            print(f"Discount {discount_id} not found.")
            conn.close()
            return
        
        # Display current discount details
        print(f"\nEditing Discount: {discount['discount_id']} - {discount['name']}")
        print("Current details:")
        print(f"Name: {discount['name']}")
        print(f"Description: {discount['description']}")
        print(f"Type: {discount['discount_type']}")
        value_display = f"{'£' if discount['discount_type'] == 'fixed' else ''}{discount['discount_value']}{'%' if discount['discount_type'] == 'percentage' else ''}"
        print(f"Value: {value_display}")
        print(f"Start Date: {discount['start_date']}")
        print(f"End Date: {discount['end_date'] if discount['end_date'] else 'Never'}")
        print(f"Applicable Products: {discount['applicable_products']}")
        print(f"Minimum Purchase: £{discount['min_purchase_amount']:.2f}")
        print(f"Active: {'Yes' if discount['is_active'] else 'No'}")
        
        # Get updated details
        print("\nEnter new details (leave blank to keep current value):")
        
        name = input(f"Name [{discount['name']}]: ").strip()
        if not name:
            name = discount['name']
        
        description = input(f"Description [{discount['description']}]: ").strip()
        if not description:
            description = discount['description']
        
        # Type and value need special handling to maintain compatibility
        discount_type = discount['discount_type']
        discount_value = discount['discount_value']
        
        update_type = input(f"Update discount type/value? (currently {discount_type}, {value_display}) (y/n): ").strip().lower()
        if update_type == 'y':
            print("\nDiscount Types:")
            print("1. Percentage (%) off")
            print("2. Fixed Amount (£) off")
            
            type_choice = input(f"Select discount type [current: {1 if discount_type == 'percentage' else 2}]: ").strip()
            if type_choice == '1':
                discount_type = 'percentage'
            elif type_choice == '2':
                discount_type = 'fixed'
            
            value_input = input(f"Discount Value [current: {discount_value}]: ").strip()
            if value_input:
                try:
                    discount_value = float(value_input)
                    if discount_value <= 0:
                        print("Discount value must be greater than 0. Keeping current value.")
                        discount_value = discount['discount_value']
                    elif discount_type == 'percentage' and discount_value > 100:
                        print("Percentage discount cannot exceed 100%. Setting to 100.")
                        discount_value = 100.0
                except ValueError:
                    print("Invalid value. Keeping current value.")
                    discount_value = discount['discount_value']
        
        # Date range
        update_dates = input("Update date range? (y/n): ").strip().lower()
        start_date = discount['start_date']
        end_date = discount['end_date']
        
        if update_dates == 'y':
            start_input = input(f"Start Date [{start_date}] (YYYY-MM-DD): ").strip()
            if start_input:
                try:
                    # Validate date format
                    datetime.strptime(start_input, '%Y-%m-%d')
                    start_date = f"{start_input} 00:00:00"
                except ValueError:
                    print(f"Invalid date format. Keeping current value.")
            
            has_end_date = input(f"Set an end date? (currently {'Yes' if end_date else 'No'}) (y/n): ").strip().lower()
            if has_end_date == 'y':
                end_input = input("End Date (YYYY-MM-DD): ").strip()
                try:
                    # Validate date format
                    end_date_obj = datetime.strptime(end_input, '%Y-%m-%d')
                    start_date_obj = datetime.strptime(start_date.split()[0], '%Y-%m-%d')
                    
                    if end_date_obj <= start_date_obj:
                        print("End date must be after start date. Keeping current value.")
                    else:
                        end_date = f"{end_input} 23:59:59"
                except ValueError:
                    print("Invalid date format. Keeping current value.")
            else:
                end_date = None
        
        # Applicable products
        applicable_products = discount['applicable_products']
        update_applicable = input("Update applicable products? (y/n): ").strip().lower()
        
        if update_applicable == 'y':
            print("\nApplicable Products:")
            print("1. All products")
            print("2. Specific category")
            print("3. Custom product list")
            
            applicable_choice = input("Select option (1-3): ").strip()
            
            if applicable_choice == '1':
                applicable_products = 'all'
            elif applicable_choice == '2':
                # Get categories
                cursor.execute("SELECT DISTINCT category FROM shop_products ORDER BY category")
                categories = cursor.fetchall()
                
                if not categories:
                    print("No categories found. Using 'all' as default.")
                    applicable_products = 'all'
                else:
                    print("\nAvailable Categories:")
                    for i, category in enumerate(categories):
                        print(f"{i+1}. {category[0]}")
                    
                    try:
                        cat_choice = int(input("Select category number: ").strip())
                        if cat_choice < 1 or cat_choice > len(categories):
                            print("Invalid selection. Keeping current value.")
                        else:
                            applicable_products = categories[cat_choice-1][0]
                    except ValueError:
                        print("Invalid input. Keeping current value.")
            
            elif applicable_choice == '3':
                # Custom product list
                product_list = []
                
                cursor.execute("SELECT product_id, name FROM shop_products WHERE is_active = 1 ORDER BY name")
                products = cursor.fetchall()
                
                if not products:
                    print("No active products found. Using 'all' as default.")
                    applicable_products = 'all'
                else:
                    print("\nSelect products (enter product IDs, one per line, blank line to finish):")
                    print("\nAvailable Products:")
                    for product in products:
                        print(f"{product[0]}: {product[1]}")
                    
                    while True:
                        product_id = input("Enter Product ID (or blank to finish): ").strip().upper()
                        if not product_id:
                            break
                        
                        # Verify product exists
                        cursor.execute("SELECT 1 FROM shop_products WHERE product_id = ? AND is_active = 1", [product_id])
                        if cursor.fetchone():
                            if product_id not in product_list:
                                product_list.append(product_id)
                                print(f"Added: {product_id}")
                            else:
                                print(f"Product {product_id} already in list.")
                        else:
                            print(f"Product {product_id} not found or not active.")
                    
                    if product_list:
                        applicable_products = ','.join(product_list)
                    else:
                        print("No products selected. Keeping current value.")
        
        # Minimum purchase
        min_purchase = discount['min_purchase_amount']
        min_input = input(f"Minimum Purchase Amount (£) [current: {min_purchase:.2f}]: ").strip()
        if min_input:
            try:
                min_purchase = float(min_input)
                if min_purchase < 0:
                    print("Minimum purchase cannot be negative. Using 0.")
                    min_purchase = 0.0
            except ValueError:
                print("Invalid amount. Keeping current value.")
        
        # Update discount
        cursor.execute(
            '''
            UPDATE shop_discounts
            SET name = ?, description = ?, discount_type = ?, discount_value = ?,
                start_date = ?, end_date = ?, applicable_products = ?, min_purchase_amount = ?
            WHERE discount_id = ?
            ''',
            [name, description, discount_type, discount_value, start_date, end_date,
             applicable_products, min_purchase, discount_id]
        )
        
        conn.commit()
        
        print(f"\nDiscount {discount_id} updated successfully!")
        
        conn.close()
        input("\nPress Enter to continue...")
        
    except sqlite3.Error as e:
        print(f"Database error editing discount: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
    except Exception as e:
        print(f"Error editing discount: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

@log_update(module="shop", description="Toggling discount status")
def toggle_discount_status():
    """Activate or deactivate a discount"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to change discount status.")
        return
    
    if not auth.check_permission('manage_discounts'):
        print("You don't have permission to change discount status.")
        return
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get discount list
        cursor.execute(
            '''
            SELECT * FROM shop_discounts
            ORDER BY is_active DESC, name
            '''
        )
        
        discounts = cursor.fetchall()
        
        if not discounts:
            print("No discounts found in the database.")
            conn.close()
            return
        
        # Display discount list
        print("\nDiscount List:")
        print(f"{'ID':<8} {'Name':<25} {'Type':<12} {'Value':<10} {'Start Date':<20} {'End Date':<20} {'Active'}")
        print("-" * 100)
        
        for discount in discounts:
            value_display = f"{'£' if discount['discount_type'] == 'fixed' else ''}{discount['discount_value']}{'%' if discount['discount_type'] == 'percentage' else ''}"
            end_date = discount['end_date'] if discount['end_date'] else 'Never'
            active_status = "Yes" if discount['is_active'] else "No"
            
            print(f"{discount['discount_id']:<8} {discount['name'][:23]:<25} {discount['discount_type']:<12} {value_display:<10} {discount['start_date']:<20} {end_date:<20} {active_status}")
        
        # Get discount to toggle
        discount_id = input("\nEnter discount ID to toggle status: ").strip().upper()
        
        cursor.execute(
            '''
            SELECT * FROM shop_discounts
            WHERE discount_id = ?
            ''',
            [discount_id]
        )
        
        discount = cursor.fetchone()
        
        if not discount:
            print(f"Discount {discount_id} not found.")
            conn.close()
            return
        
        # Toggle status
        new_status = 0 if discount['is_active'] else 1
        status_text = "activated" if new_status else "deactivated"
        
        confirm = input(f"Are you sure you want to {status_text.lower()} '{discount['name']}'? (y/n): ").strip().lower()
        
        if confirm != 'y':
            print("Operation cancelled.")
            conn.close()
            return
        
        cursor.execute(
            '''
            UPDATE shop_discounts
            SET is_active = ?
            WHERE discount_id = ?
            ''',
            [new_status, discount_id]
        )
        
        conn.commit()
        
        print(f"\nDiscount {discount_id} - '{discount['name']}' has been {status_text}.")
        
        conn.close()
        input("\nPress Enter to continue...")
        
    except sqlite3.Error as e:
        print(f"Database error toggling discount status: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
    except Exception as e:
        print(f"Error toggling discount status: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

@log_read(module="shop", description="Viewing all discounts")
def view_all_discounts():
    """View all discounts in the system"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view discounts.")
        return
    
    if not auth.check_permission('manage_discounts'):
        print("You don't have permission to view discounts.")
        return
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all discounts
        cursor.execute(
            '''
            SELECT * FROM shop_discounts
            ORDER BY is_active DESC, end_date, start_date
            '''
        )
        
        discounts = cursor.fetchall()
        
        if not discounts:
            print("No discounts found in the database.")
            conn.close()
            return
        
        # Check for active vs inactive, current vs expired
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        active_current = []
        active_future = []
        active_expired = []
        inactive = []
        
        for discount in discounts:
            if discount['is_active']:
                if discount['end_date'] and discount['end_date'] < now:
                    active_expired.append(discount)
                elif discount['start_date'] > now:
                    active_future.append(discount)
                else:
                    active_current.append(discount)
            else:
                inactive.append(discount)
        
        # Display discounts by category
        def print_discount_header():
            print(f"{'ID':<8} {'Name':<25} {'Type':<12} {'Value':<10} {'Start Date':<20} {'End Date':<20} {'Min Purchase':<15}")
            print("-" * 110)
        
        def print_discount(discount):
            value_display = f"{'£' if discount['discount_type'] == 'fixed' else ''}{discount['discount_value']}{'%' if discount['discount_type'] == 'percentage' else ''}"
            end_date = discount['end_date'] if discount['end_date'] else 'Never'
            min_purchase = f"£{discount['min_purchase_amount']:.2f}" if discount['min_purchase_amount'] > 0 else 'None'
            
            print(f"{discount['discount_id']:<8} {discount['name'][:23]:<25} {discount['discount_type']:<12} {value_display:<10} {discount['start_date']:<20} {end_date:<20} {min_purchase:<15}")
        
        # Active and current
        if active_current:
            print("\n=== Active & Current Discounts ===")
            print_discount_header()
            for discount in active_current:
                print_discount(discount)
        
        # Active but future
        if active_future:
            print("\n=== Active & Future Discounts ===")
            print_discount_header()
            for discount in active_future:
                print_discount(discount)
        
        # Active but expired
        if active_expired:
            print("\n=== Active but Expired Discounts ===")
            print_discount_header()
            for discount in active_expired:
                print_discount(discount)
        
        # Inactive
        if inactive:
            print("\n=== Inactive Discounts ===")
            print_discount_header()
            for discount in inactive:
                print_discount(discount)
        
        # Display summary
        print(f"\nTotal Discounts: {len(discounts)}")
        print(f"Active & Current: {len(active_current)}")
        print(f"Active & Future: {len(active_future)}")
        print(f"Active but Expired: {len(active_expired)}")
        print(f"Inactive: {len(inactive)}")
        
        # View discount details option
        discount_id = input("\nEnter discount ID to view details (or 'back' to return): ").strip().upper()
        
        if discount_id.lower() == 'back':
            conn.close()
            return
        
        cursor.execute(
            '''
            SELECT * FROM shop_discounts
            WHERE discount_id = ?
            ''',
            [discount_id]
        )
        
        discount = cursor.fetchone()
        
        if not discount:
            print(f"Discount {discount_id} not found.")
            conn.close()
            return
        
        # Display full discount details
        print(f"\nDiscount Details - {discount_id}")
        print(f"Name: {discount['name']}")
        print(f"Description: {discount['description']}")
        print(f"Type: {discount['discount_type']}")
        value_display = f"{'£' if discount['discount_type'] == 'fixed' else ''}{discount['discount_value']}{'%' if discount['discount_type'] == 'percentage' else ''}"
        print(f"Value: {value_display}")
        print(f"Start Date: {discount['start_date']}")
        print(f"End Date: {discount['end_date'] if discount['end_date'] else 'Never'}")
        print(f"Status: {'Active' if discount['is_active'] else 'Inactive'}")
        
        if discount['applicable_products'] == 'all':
            print("Applies to: All products")
        else:
            if ',' in discount['applicable_products']:
                product_ids = discount['applicable_products'].split(',')
                print(f"Applies to: {len(product_ids)} specific products")
                
                # Get product details
                placeholders = ','.join(['?'] * len(product_ids))
                cursor.execute(
                    f"SELECT product_id, name FROM shop_products WHERE product_id IN ({placeholders})",
                    product_ids
                )
                products = cursor.fetchall()
                
                if products:
                    print("\nApplicable Products:")
                    for product in products:
                        print(f"- {product['product_id']}: {product['name']}")
            else:
                # Assume it's a category
                print(f"Applies to Category: {discount['applicable_products']}")
                
                # Count products in this category
                cursor.execute(
                    "SELECT COUNT(*) FROM shop_products WHERE category = ? AND is_active = 1",
                    [discount['applicable_products']]
                )
                count = cursor.fetchone()[0]
                print(f"({count} active products in this category)")
        
        print(f"Minimum Purchase: £{discount['min_purchase_amount']:.2f}")
        print(f"Created At: {discount['created_at']}")
        
        conn.close()
        input("\nPress Enter to continue...")
        
    except sqlite3.Error as e:
        print(f"Database error viewing discounts: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error viewing discounts: {e}")
        if 'conn' in locals():
            conn.close()

# Sales Reports Functions
@log_menu_navigation(description="Displaying sales reports menu")
def display_sales_reports_menu():
    """Display the menu for sales reports"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view sales reports.")
        return
    
    if not auth.check_permission('generate_sales_reports'):
        print("You don't have permission to generate sales reports.")
        return
    
    while True:
        print("\nSales Reports Menu:")
        print("1. Daily Sales Report")
        print("2. Weekly Sales Report")
        print("3. Monthly Sales Report")
        print("4. Product Sales Report")
        print("5. Category Sales Report")
        print("6. Export Sales Data")
        print("7. Return to Shop Menu")
        
        choice = input("Enter your choice (1-7): ").strip()
        
        if choice == '1':
            generate_daily_sales_report()
        elif choice == '2':
            generate_weekly_sales_report()
        elif choice == '3':
            generate_monthly_sales_report()
        elif choice == '4':
            generate_product_sales_report()
        elif choice == '5':
            generate_category_sales_report()
        elif choice == '6':
            export_sales_data()
        elif choice == '7':
            return
        else:
            print("Invalid choice. Please try again.")

@log_read(module="shop", description="Generating daily sales report")
def generate_daily_sales_report():
    """Generate a daily sales report"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to generate reports.")
        return
    
    if not auth.check_permission('generate_sales_reports'):
        print("You don't have permission to generate sales reports.")
        return
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get date for report
        print("\nDaily Sales Report")
        print("------------------")
        
        default_date = datetime.now().strftime('%Y-%m-%d')
        date_input = input(f"Enter date (YYYY-MM-DD) [default: {default_date}]: ").strip()
        
        if not date_input:
            date_input = default_date
        
        try:
            # Validate date
            report_date = datetime.strptime(date_input, '%Y-%m-%d')
            date_str = report_date.strftime('%Y-%m-%d')
            
            # Get sales for this date
            cursor.execute(
                '''
                SELECT t.*, u.username
                FROM shop_transactions t
                LEFT JOIN users u ON t.user_id = u.id
                WHERE t.transaction_date LIKE ?
                ORDER BY t.transaction_date
                ''',
                [f"{date_str}%"]
            )
            
            transactions = cursor.fetchall()
            
            if not transactions:
                print(f"No sales found for {date_str}.")
                conn.close()
                return
            
            # Calculate totals
            total_sales = sum(t['total_amount'] for t in transactions)
            transaction_count = len(transactions)
            avg_transaction = total_sales / transaction_count
            
            # Get payment method breakdown
            payment_methods = {}
            for t in transactions:
                method = t['payment_method']
                if method not in payment_methods:
                    payment_methods[method] = {'count': 0, 'amount': 0}
                
                payment_methods[method]['count'] += 1
                payment_methods[method]['amount'] += t['total_amount']
            
            # Get hourly breakdown
            hourly_sales = {}
            for t in transactions:
                hour = t['transaction_date'].split()[1].split(':')[0]
                if hour not in hourly_sales:
                    hourly_sales[hour] = {'count': 0, 'amount': 0}
                
                hourly_sales[hour]['count'] += 1
                hourly_sales[hour]['amount'] += t['total_amount']
            
            # Display report
            print(f"\nSales Report for {date_str}")
            print("=" * 50)
            
            print(f"Total Sales: £{total_sales:.2f}")
            print(f"Number of Transactions: {transaction_count}")
            print(f"Average Transaction Value: £{avg_transaction:.2f}")
            
            print("\nPayment Method Breakdown:")
            print(f"{'Method':<20} {'Transactions':<15} {'Amount':<15} {'Percent'}")
            print("-" * 65)
            
            for method, data in payment_methods.items():
                percent = (data['amount'] / total_sales) * 100
                print(f"{method:<20} {data['count']:<15} £{data['amount']:<15.2f} {percent:.1f}%")
            
            print("\nHourly Breakdown:")
            print(f"{'Hour':<10} {'Transactions':<15} {'Amount':<15} {'Percent'}")
            print("-" * 55)
            
            # Sort by hour
            for hour in sorted(hourly_sales.keys()):
                data = hourly_sales[hour]
                percent = (data['amount'] / total_sales) * 100
                print(f"{hour}:00{'':<7} {data['count']:<15} £{data['amount']:<15.2f} {percent:.1f}%")
            
            # Get product details for the day
            print("\nTop Products Sold:")
            cursor.execute(
                '''
                SELECT ti.product_id, p.name, SUM(ti.quantity) as total_qty, 
                       SUM(ti.subtotal) as total_amount
                FROM shop_transaction_items ti
                JOIN shop_transactions t ON ti.transaction_id = t.transaction_id
                JOIN shop_products p ON ti.product_id = p.product_id
                WHERE t.transaction_date LIKE ?
                GROUP BY ti.product_id
                ORDER BY total_amount DESC
                LIMIT 10
                ''',
                [f"{date_str}%"]
            )
            
            top_products = cursor.fetchall()
            
            if top_products:
                print(f"{'Product ID':<12} {'Name':<30} {'Quantity':<10} {'Total':<12} {'% of Sales'}")
                print("-" * 75)
                
                for product in top_products:
                    percent = (product['total_amount'] / total_sales) * 100
                    print(f"{product['product_id']:<12} {product['name'][:28]:<30} {product['total_qty']:<10} £{product['total_amount']:<12.2f} {percent:.1f}%")
            
            conn.close()
            input("\nPress Enter to continue...")
            
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
            conn.close()
            return
        
    except sqlite3.Error as e:
        print(f"Database error generating report: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error generating report: {e}")
        if 'conn' in locals():
            conn.close()

@log_read(module="shop", description="Generating weekly sales report")
def generate_weekly_sales_report():
    """Generate a weekly sales report"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to generate reports.")
        return
    
    if not auth.check_permission('generate_sales_reports'):
        print("You don't have permission to generate sales reports.")
        return
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get week for report
        print("\nWeekly Sales Report")
        print("------------------")
        
        # Calculate current week's start and end dates
        today = datetime.now()
        # Monday as start of week (0 = Monday in weekday())
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        default_start = start_of_week.strftime('%Y-%m-%d')
        default_end = end_of_week.strftime('%Y-%m-%d')
        
        print(f"Default week: {default_start} to {default_end}")
        
        custom_week = input("Use custom date range? (y/n): ").strip().lower()
        
        if custom_week == 'y':
            start_input = input("Enter start date (YYYY-MM-DD): ").strip()
            end_input = input("Enter end date (YYYY-MM-DD): ").strip()
            
            try:
                start_date = datetime.strptime(start_input, '%Y-%m-%d')
                end_date = datetime.strptime(end_input, '%Y-%m-%d')
                
                if end_date < start_date:
                    print("End date must be after start date. Using default week.")
                    start_date = start_of_week
                    end_date = end_of_week
            except ValueError:
                print("Invalid date format. Using default week.")
                start_date = start_of_week
                end_date = end_of_week
        else:
            start_date = start_of_week
            end_date = end_of_week
        
        # Format for database queries
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        # Get sales for this week
        cursor.execute(
            '''
            SELECT t.*
            FROM shop_transactions t
            WHERE t.transaction_date BETWEEN ? AND ?
            ORDER BY t.transaction_date
            ''',
            [f"{start_str} 00:00:00", f"{end_str} 23:59:59"]
        )
        
        transactions = cursor.fetchall()
        
        if not transactions:
            print(f"No sales found for the period {start_str} to {end_str}.")
            conn.close()
            return
        
        # Calculate totals
        total_sales = sum(t['total_amount'] for t in transactions)
        transaction_count = len(transactions)
        avg_transaction = total_sales / transaction_count
        
        # Get daily breakdown
        daily_sales = {}
        for t in transactions:
            day = t['transaction_date'].split()[0]  # YYYY-MM-DD
            if day not in daily_sales:
                daily_sales[day] = {'count': 0, 'amount': 0}
            
            daily_sales[day]['count'] += 1
            daily_sales[day]['amount'] += t['total_amount']
        
        # Display report
        print(f"\nWeekly Sales Report: {start_str} to {end_str}")
        print("=" * 50)
        
        print(f"Total Sales: £{total_sales:.2f}")
        print(f"Number of Transactions: {transaction_count}")
        print(f"Average Transaction Value: £{avg_transaction:.2f}")
        print(f"Average Daily Sales: £{total_sales / len(daily_sales):.2f}")
        
        print("\nDaily Breakdown:")
        print(f"{'Date':<12} {'Day':<10} {'Transactions':<15} {'Amount':<15} {'% of Total'}")
        print("-" * 65)
        
        # Sort by date
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            day_name = current_date.strftime('%A')
            
            if date_str in daily_sales:
                data = daily_sales[date_str]
                percent = (data['amount'] / total_sales) * 100
                print(f"{date_str:<12} {day_name:<10} {data['count']:<15} £{data['amount']:<15.2f} {percent:.1f}%")
            else:
                print(f"{date_str:<12} {day_name:<10} {'0':<15} £{'0.00':<15} {'0.0'}%")
            
            current_date += timedelta(days=1)
        
        # Get top categories
        cursor.execute(
            '''
            SELECT p.category, SUM(ti.quantity) as total_qty, 
                   SUM(ti.subtotal) as total_amount,
                   COUNT(DISTINCT ti.transaction_id) as transaction_count
            FROM shop_transaction_items ti
            JOIN shop_transactions t ON ti.transaction_id = t.transaction_id
            JOIN shop_products p ON ti.product_id = p.product_id
            WHERE t.transaction_date BETWEEN ? AND ?
            GROUP BY p.category
            ORDER BY total_amount DESC
            ''',
            [f"{start_str} 00:00:00", f"{end_str} 23:59:59"]
        )
        
        categories = cursor.fetchall()
        
        if categories:
            print("\nSales by Category:")
            print(f"{'Category':<20} {'Transactions':<15} {'Items Sold':<12} {'Total':<12} {'% of Sales'}")
            print("-" * 70)
            
            for category in categories:
                percent = (category['total_amount'] / total_sales) * 100
                print(f"{category['category']:<20} {category['transaction_count']:<15} {category['total_qty']:<12} £{category['total_amount']:<12.2f} {percent:.1f}%")
        
        # Get top products
        cursor.execute(
            '''
            SELECT ti.product_id, p.name, p.category, SUM(ti.quantity) as total_qty, 
                   SUM(ti.subtotal) as total_amount
            FROM shop_transaction_items ti
            JOIN shop_transactions t ON ti.transaction_id = t.transaction_id
            JOIN shop_products p ON ti.product_id = p.product_id
            WHERE t.transaction_date BETWEEN ? AND ?
            GROUP BY ti.product_id
            ORDER BY total_amount DESC
            LIMIT 10
            ''',
            [f"{start_str} 00:00:00", f"{end_str} 23:59:59"]
        )
        
        top_products = cursor.fetchall()
        
        if top_products:
            print("\nTop 10 Products:")
            print(f"{'Product ID':<12} {'Name':<25} {'Category':<15} {'Quantity':<10} {'Total':<12} {'% of Sales'}")
            print("-" * 90)
            
            for product in top_products:
                percent = (product['total_amount'] / total_sales) * 100
                print(f"{product['product_id']:<12} {product['name'][:23]:<25} {product['category'][:13]:<15} {product['total_qty']:<10} £{product['total_amount']:<12.2f} {percent:.1f}%")
        
        conn.close()
        input("\nPress Enter to continue...")
        
    except sqlite3.Error as e:
        print(f"Database error generating report: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error generating report: {e}")
        if 'conn' in locals():
            conn.close()

@log_read(module="shop", description="Generating monthly sales report")
def generate_monthly_sales_report():
    """Generate a monthly sales report"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to generate reports.")
        return
    
    if not auth.check_permission('generate_sales_reports'):
        print("You don't have permission to generate sales reports.")
        return
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get month for report
        print("\nMonthly Sales Report")
        print("-------------------")
        
        today = datetime.now()
        default_year = today.year
        default_month = today.month
        
        year_input = input(f"Enter year [default: {default_year}]: ").strip()
        month_input = input(f"Enter month (1-12) [default: {default_month}]: ").strip()
        
        if not year_input:
            year = default_year
        else:
            try:
                year = int(year_input)
                if year < 2000 or year > 2100:
                    print(f"Invalid year. Using default ({default_year}).")
                    year = default_year
            except ValueError:
                print(f"Invalid year. Using default ({default_year}).")
                year = default_year
        
        if not month_input:
            month = default_month
        else:
            try:
                month = int(month_input)
                if month < 1 or month > 12:
                    print(f"Invalid month. Using default ({default_month}).")
                    month = default_month
            except ValueError:
                print(f"Invalid month. Using default ({default_month}).")
                month = default_month
        
        # Get the first and last day of the month
        first_day = datetime(year, month, 1)
        
        # Last day calculation (go to next month, then subtract one day)
        if month == 12:
            last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = datetime(year, month + 1, 1) - timedelta(days=1)
        
        month_name = first_day.strftime('%B')
        first_day_str = first_day.strftime('%Y-%m-%d')
        last_day_str = last_day.strftime('%Y-%m-%d')
        
        # Get sales for this month
        cursor.execute(
            '''
            SELECT t.*
            FROM shop_transactions t
            WHERE t.transaction_date BETWEEN ? AND ?
            ORDER BY t.transaction_date
            ''',
            [f"{first_day_str} 00:00:00", f"{last_day_str} 23:59:59"]
        )
        
        transactions = cursor.fetchall()
        
        if not transactions:
            print(f"No sales found for {month_name} {year}.")
            conn.close()
            return
        
        # Calculate totals
        total_sales = sum(t['total_amount'] for t in transactions)
        transaction_count = len(transactions)
        avg_transaction = total_sales / transaction_count
        
        # Get daily breakdown
        daily_sales = {}
        for t in transactions:
            day = t['transaction_date'].split()[0]  # YYYY-MM-DD
            if day not in daily_sales:
                daily_sales[day] = {'count': 0, 'amount': 0}
            
            daily_sales[day]['count'] += 1
            daily_sales[day]['amount'] += t['total_amount']
        
        # Group by week
        weeks = {}
        current_day = first_day
        week_num = 1
        
        while current_day <= last_day:
            week_key = f"Week {week_num}"
            week_start = current_day
            
            # Days until Sunday (or end of month)
            days_in_week = min((6 - current_day.weekday()) % 7 + 1, (last_day - current_day).days + 1)
            week_end = current_day + timedelta(days=days_in_week - 1)
            
            weeks[week_key] = {
                'start': week_start.strftime('%Y-%m-%d'),
                'end': week_end.strftime('%Y-%m-%d'),
                'amount': 0,
                'count': 0
            }
            
            # Move to next week
            current_day = week_end + timedelta(days=1)
            week_num += 1
        
        # Assign sales to weeks
        for day, data in daily_sales.items():
            for week_key, week_data in weeks.items():
                if week_data['start'] <= day <= week_data['end']:
                    weeks[week_key]['amount'] += data['amount']
                    weeks[week_key]['count'] += data['count']
                    break
        
        # Display report
        print(f"\nMonthly Sales Report: {month_name} {year}")
        print("=" * 50)
        
        print(f"Period: {first_day_str} to {last_day_str}")
        print(f"Total Sales: £{total_sales:.2f}")
        print(f"Number of Transactions: {transaction_count}")
        print(f"Average Transaction Value: £{avg_transaction:.2f}")
        
        # Weekly breakdown
        print("\nWeekly Breakdown:")
        print(f"{'Week':<10} {'Period':<25} {'Transactions':<15} {'Amount':<15} {'% of Total'}")
        print("-" * 80)
        
        for week_key, data in weeks.items():
            period = f"{data['start']} to {data['end']}"
            percent = (data['amount'] / total_sales) * 100 if total_sales > 0 else 0
            print(f"{week_key:<10} {period:<25} {data['count']:<15} £{data['amount']:<15.2f} {percent:.1f}%")
        
        # Payment method breakdown
        cursor.execute(
            '''
            SELECT payment_method, COUNT(*) as count, SUM(total_amount) as amount
            FROM shop_transactions
            WHERE transaction_date BETWEEN ? AND ?
            GROUP BY payment_method
            ORDER BY amount DESC
            ''',
            [f"{first_day_str} 00:00:00", f"{last_day_str} 23:59:59"]
        )
        
        payment_methods = cursor.fetchall()
        
        if payment_methods:
            print("\nPayment Method Breakdown:")
            print(f"{'Method':<20} {'Transactions':<15} {'Amount':<15} {'% of Total'}")
            print("-" * 70)
            
            for method in payment_methods:
                percent = (method['amount'] / total_sales) * 100
                print(f"{method['payment_method']:<20} {method['count']:<15} £{method['amount']:<15.2f} {percent:.1f}%")
        
        # Category breakdown
        cursor.execute(
            '''
            SELECT p.category, COUNT(DISTINCT t.transaction_id) as transaction_count,
                   SUM(ti.quantity) as quantity, SUM(ti.subtotal) as amount
            FROM shop_transaction_items ti
            JOIN shop_transactions t ON ti.transaction_id = t.transaction_id
            JOIN shop_products p ON ti.product_id = p.product_id
            WHERE t.transaction_date BETWEEN ? AND ?
            GROUP BY p.category
            ORDER BY amount DESC
            ''',
            [f"{first_day_str} 00:00:00", f"{last_day_str} 23:59:59"]
        )
        
        categories = cursor.fetchall()
        
        if categories:
            print("\nSales by Category:")
            print(f"{'Category':<20} {'Transactions':<15} {'Items Sold':<12} {'Amount':<15} {'% of Total'}")
            print("-" * 75)
            
            for category in categories:
                percent = (category['amount'] / total_sales) * 100
                print(f"{category['category']:<20} {category['transaction_count']:<15} {category['quantity']:<12} £{category['amount']:<15.2f} {percent:.1f}%")
        
        # Top products
        cursor.execute(
            '''
            SELECT p.product_id, p.name, SUM(ti.quantity) as quantity, SUM(ti.subtotal) as amount
            FROM shop_transaction_items ti
            JOIN shop_transactions t ON ti.transaction_id = t.transaction_id
            JOIN shop_products p ON ti.product_id = p.product_id
            WHERE t.transaction_date BETWEEN ? AND ?
            GROUP BY p.product_id
            ORDER BY amount DESC
            LIMIT 10
            ''',
            [f"{first_day_str} 00:00:00", f"{last_day_str} 23:59:59"]
        )
        
        top_products = cursor.fetchall()
        
        if top_products:
            print("\nTop 10 Products:")
            print(f"{'Product ID':<12} {'Name':<30} {'Quantity':<10} {'Amount':<15} {'% of Total'}")
            print("-" * 80)
            
            for product in top_products:
                percent = (product['amount'] / total_sales) * 100
                print(f"{product['product_id']:<12} {product['name'][:28]:<30} {product['quantity']:<10} £{product['amount']:<15.2f} {percent:.1f}%")
        
        conn.close()
        input("\nPress Enter to continue...")
        
    except sqlite3.Error as e:
        print(f"Database error generating report: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error generating report: {e}")
        if 'conn' in locals():
            conn.close()

@log_read(module="shop", description="Generating product sales report")
def generate_product_sales_report():
    """Generate a sales report for a specific product"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to generate reports.")
        return
    
    if not auth.check_permission('generate_sales_reports'):
        print("You don't have permission to generate sales reports.")
        return
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("\nProduct Sales Report")
        print("-------------------")
        
        # Get product ID
        product_id = input("Enter product ID (or leave blank to see all products): ").strip().upper()
        
        if product_id:
            # Check if product exists
            cursor.execute(
                "SELECT * FROM shop_products WHERE product_id = ?",
                [product_id]
            )
            product = cursor.fetchone()
            
            if not product:
                print(f"Product {product_id} not found.")
                conn.close()
                return
            
            # Get date range
            print("\nSelect date range:")
            print("1. Last 7 days")
            print("2. Last 30 days")
            print("3. Last 90 days")
            print("4. Year to date")
            print("5. All time")
            print("6. Custom range")
            
            range_choice = input("Select option (1-6): ").strip()
            
            today = datetime.now()
            
            if range_choice == '1':
                start_date = (today - timedelta(days=7)).strftime('%Y-%m-%d')
                end_date = today.strftime('%Y-%m-%d')
            elif range_choice == '2':
                start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
                end_date = today.strftime('%Y-%m-%d')
            elif range_choice == '3':
                start_date = (today - timedelta(days=90)).strftime('%Y-%m-%d')
                end_date = today.strftime('%Y-%m-%d')
            elif range_choice == '4':
                start_date = f"{today.year}-01-01"
                end_date = today.strftime('%Y-%m-%d')
            elif range_choice == '5':
                start_date = "2000-01-01"  # Far past
                end_date = today.strftime('%Y-%m-%d')
            elif range_choice == '6':
                start_input = input("Enter start date (YYYY-MM-DD): ").strip()
                end_input = input("Enter end date (YYYY-MM-DD): ").strip()
                
                try:
                    # Validate dates
                    start_date = datetime.strptime(start_input, '%Y-%m-%d').strftime('%Y-%m-%d')
                    end_date = datetime.strptime(end_input, '%Y-%m-%d').strftime('%Y-%m-%d')
                except ValueError:
                    print("Invalid date format. Using last 30 days.")
                    start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
                    end_date = today.strftime('%Y-%m-%d')
            else:
                print("Invalid choice. Using last 30 days.")
                start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
                end_date = today.strftime('%Y-%m-%d')
            
            # Get sales for this product
            cursor.execute(
                '''
                SELECT ti.transaction_id, t.transaction_date, t.payment_method,
                       ti.quantity, ti.price_per_item, ti.subtotal
                FROM shop_transaction_items ti
                JOIN shop_transactions t ON ti.transaction_id = t.transaction_id
                WHERE ti.product_id = ? AND 
                      t.transaction_date BETWEEN ? AND ?
                ORDER BY t.transaction_date DESC
                ''',
                [product_id, f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
            )
            
            sales = cursor.fetchall()
            
            if not sales:
                print(f"No sales found for product {product_id} in the selected period.")
                conn.close()
                return
            
            # Display product details
            print(f"\nProduct: {product['name']} ({product_id})")
            print(f"Category: {product['category']}")
            print(f"Current Price: £{product['price']:.2f}")
            print(f"Status: {'Active' if product['is_active'] else 'Inactive'}")
            
            # Calculate sales totals
            total_quantity = sum(s['quantity'] for s in sales)
            total_revenue = sum(s['subtotal'] for s in sales)
            transaction_count = len(set(s['transaction_id'] for s in sales))
            
            print(f"\nPeriod: {start_date} to {end_date}")
            print(f"Total Units Sold: {total_quantity}")
            print(f"Total Revenue: £{total_revenue:.2f}")
            print(f"Number of Transactions: {transaction_count}")
            print(f"Average Price: £{total_revenue / total_quantity:.2f}")
            
            # Monthly breakdown if range is long enough
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d')
                end = datetime.strptime(end_date, '%Y-%m-%d')
                
                # If period is 60+ days, show monthly breakdown
                if (end - start).days >= 60:
                    monthly_sales = {}
                    for sale in sales:
                        month_key = sale['transaction_date'][:7]  # YYYY-MM
                        if month_key not in monthly_sales:
                            monthly_sales[month_key] = {'quantity': 0, 'revenue': 0}
                        
                        monthly_sales[month_key]['quantity'] += sale['quantity']
                        monthly_sales[month_key]['revenue'] += sale['subtotal']
                    
                    print("\nMonthly Breakdown:")
                    print(f"{'Month':<10} {'Units Sold':<12} {'Revenue':<15} {'% of Total'}")
                    print("-" * 55)
                    
                    for month_key in sorted(monthly_sales.keys()):
                        data = monthly_sales[month_key]
                        month_label = datetime.strptime(month_key, '%Y-%m').strftime('%b %Y')
                        percent = (data['revenue'] / total_revenue) * 100
                        
                        print(f"{month_label:<10} {data['quantity']:<12} £{data['revenue']:<15.2f} {percent:.1f}%")
                
                # If period is less than 60 days, show weekly breakdown
                elif (end - start).days >= 14:
                    weekly_sales = {}
                    for sale in sales:
                        sale_date = datetime.strptime(sale['transaction_date'].split()[0], '%Y-%m-%d')
                        week_num = sale_date.isocalendar()[1]  # ISO week number
                        week_key = f"{sale_date.year}-W{week_num:02d}"
                        
                        if week_key not in weekly_sales:
                            weekly_sales[week_key] = {'quantity': 0, 'revenue': 0}
                        
                        weekly_sales[week_key]['quantity'] += sale['quantity']
                        weekly_sales[week_key]['revenue'] += sale['subtotal']
                    
                    print("\nWeekly Breakdown:")
                    print(f"{'Week':<10} {'Units Sold':<12} {'Revenue':<15} {'% of Total'}")
                    print("-" * 55)
                    
                    for week_key in sorted(weekly_sales.keys()):
                        data = weekly_sales[week_key]
                        percent = (data['revenue'] / total_revenue) * 100
                        
                        print(f"{week_key:<10} {data['quantity']:<12} £{data['revenue']:<15.2f} {percent:.1f}%")
            except Exception as e:
                # Skip breakdown on error
                print(f"Note: Couldn't generate time breakdown: {e}")
            
            # Recent transactions
            print("\nRecent Transactions:")
            print(f"{'Date':<20} {'Transaction ID':<20} {'Quantity':<10} {'Price':<10} {'Subtotal'}")
            print("-" * 75)
            
            for i, sale in enumerate(sales):
                if i >= 10:  # Show only 10 most recent
                    break
                    
                price_formatted = f"£{sale['price_per_item']:.2f}"
                subtotal_formatted = f"£{sale['subtotal']:.2f}"
                date_formatted = sale['transaction_date']
                
                print(f"{date_formatted:<20} {sale['transaction_id']:<20} {sale['quantity']:<10} {price_formatted:<10} {subtotal_formatted}")
            
            # Get inventory information
            cursor.execute(
                "SELECT * FROM shop_inventory WHERE product_id = ?",
                [product_id]
            )
            
            inventory = cursor.fetchone()
            
            if inventory:
                print(f"\nCurrent Stock: {inventory['quantity']}")
                print(f"Restock Threshold: {inventory['restock_threshold']}")
                print(f"Last Restock: {inventory['last_restock_date']}")
                
                # Calculate turnover
                if inventory['quantity'] > 0:
                    # Calculate average daily sales
                    try:
                        days = (end - start).days
                        if days > 0:
                            daily_sales = total_quantity / days
                            estimated_days = inventory['quantity'] / daily_sales if daily_sales > 0 else float('inf')
                            
                            print(f"Average Daily Sales: {daily_sales:.1f} units")
                            print(f"Estimated Days Until Restock Needed: {estimated_days:.1f}")
                    except Exception:
                        pass
            
        else:
            # Show all products sales summary
            print("\nAll Products Sales Summary")
            
            # Get time period
            print("Select time period:")
            print("1. Last 30 days")
            print("2. Last 90 days")
            print("3. Year to date")
            print("4. All time")
            
            period_choice = input("Select option (1-4): ").strip()
            
            today = datetime.now()
            
            if period_choice == '1':
                start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
                period_name = "Last 30 Days"
            elif period_choice == '2':
                start_date = (today - timedelta(days=90)).strftime('%Y-%m-%d')
                period_name = "Last 90 Days"
            elif period_choice == '3':
                start_date = f"{today.year}-01-01"
                period_name = "Year to Date"
            elif period_choice == '4':
                start_date = "2000-01-01"  # Far past
                period_name = "All Time"
            else:
                print("Invalid choice. Using last 30 days.")
                start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
                period_name = "Last 30 Days"
            
            end_date = today.strftime('%Y-%m-%d')
            
            # Get sales data
            cursor.execute(
                '''
                SELECT p.product_id, p.name, p.category, p.price,
                       SUM(ti.quantity) as total_quantity,
                       SUM(ti.subtotal) as total_revenue,
                       COUNT(DISTINCT ti.transaction_id) as transaction_count,
                       AVG(ti.price_per_item) as avg_price
                FROM shop_transaction_items ti
                JOIN shop_products p ON ti.product_id = p.product_id
                JOIN shop_transactions t ON ti.transaction_id = t.transaction_id
                WHERE t.transaction_date BETWEEN ? AND ?
                GROUP BY p.product_id
                ORDER BY total_revenue DESC
                ''',
                [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
            )
            
            product_sales = cursor.fetchall()
            
            if not product_sales:
                print(f"No sales found for the period {start_date} to {end_date}.")
                conn.close()
                return
            
            # Calculate total sales
            total_revenue = sum(p['total_revenue'] for p in product_sales)
            total_quantity = sum(p['total_quantity'] for p in product_sales)
            
            print(f"\nSales Summary for {period_name}: {start_date} to {end_date}")
            print(f"Total Revenue: £{total_revenue:.2f}")
            print(f"Total Units Sold: {total_quantity}")
            print(f"Number of Products Sold: {len(product_sales)}")
            
            # Display product sales
            print("\nProduct Sales Ranking:")
            print(f"{'Rank':<5} {'Product ID':<12} {'Name':<30} {'Category':<15} {'Units Sold':<12} {'Revenue':<15} {'% of Total'}")
            print("-" * 100)
            
            for i, product in enumerate(product_sales):
                percent = (product['total_revenue'] / total_revenue) * 100
                print(f"{i+1:<5} {product['product_id']:<12} {product['name'][:28]:<30} {product['category'][:13]:<15} {product['total_quantity']:<12} £{product['total_revenue']:<15.2f} {percent:.1f}%")
                
                if i >= 19:  # Show only top 20
                    remaining = len(product_sales) - 20
                    if remaining > 0:
                        remaining_revenue = sum(p['total_revenue'] for p in product_sales[20:])
                        remaining_percent = (remaining_revenue / total_revenue) * 100
                        print(f"... and {remaining} more products (£{remaining_revenue:.2f}, {remaining_percent:.1f}% of total)")
                    break
            
            # Get category breakdown
            cursor.execute(
                '''
                SELECT p.category, 
                       SUM(ti.quantity) as total_quantity,
                       SUM(ti.subtotal) as total_revenue,
                       COUNT(DISTINCT p.product_id) as product_count
                FROM shop_transaction_items ti
                JOIN shop_products p ON ti.product_id = p.product_id
                JOIN shop_transactions t ON ti.transaction_id = t.transaction_id
                WHERE t.transaction_date BETWEEN ? AND ?
                GROUP BY p.category
                ORDER BY total_revenue DESC
                ''',
                [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
            )
            
            category_sales = cursor.fetchall()
            
            if category_sales:
                print("\nSales by Category:")
                print(f"{'Category':<20} {'Products':<10} {'Units Sold':<12} {'Revenue':<15} {'% of Total'}")
                print("-" * 70)
                
                for category in category_sales:
                    percent = (category['total_revenue'] / total_revenue) * 100
                    print(f"{category['category']:<20} {category['product_count']:<10} {category['total_quantity']:<12} £{category['total_revenue']:<15.2f} {percent:.1f}%")
        
        conn.close()
        input("\nPress Enter to continue...")
        
    except sqlite3.Error as e:
        print(f"Database error generating report: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error generating report: {e}")
        if 'conn' in locals():
            conn.close()

@log_read(module="shop", description="Generating category sales report")
def generate_category_sales_report():
    """Generate a sales report for a specific category"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to generate reports.")
        return
    
    if not auth.check_permission('generate_sales_reports'):
        print("You don't have permission to generate sales reports.")
        return
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("\nCategory Sales Report")
        print("--------------------")
        
        # Get available categories
        cursor.execute(
            "SELECT DISTINCT category FROM shop_products ORDER BY category"
        )
        
        categories = cursor.fetchall()
        
        if not categories:
            print("No categories found in the database.")
            conn.close()
            return
        
        print("Available Categories:")
        for i, category in enumerate(categories):
            print(f"{i+1}. {category['category']}")
        
        # Get category selection
        try:
            category_choice = int(input("Select category number: ").strip())
            
            if category_choice < 1 or category_choice > len(categories):
                print("Invalid selection.")
                conn.close()
                return
            
            selected_category = categories[category_choice-1]['category']
        except ValueError:
            print("Invalid input. Please enter a number.")
            conn.close()
            return
        
        # Get time period
        print("\nSelect time period:")
        print("1. Last 30 days")
        print("2. Last 90 days")
        print("3. Year to date")
        print("4. All time")
        print("5. Custom range")
        
        period_choice = input("Select option (1-5): ").strip()
        
        today = datetime.now()
        
        if period_choice == '1':
            start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
            period_name = "Last 30 Days"
        elif period_choice == '2':
            start_date = (today - timedelta(days=90)).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
            period_name = "Last 90 Days"
        elif period_choice == '3':
            start_date = f"{today.year}-01-01"
            end_date = today.strftime('%Y-%m-%d')
            period_name = "Year to Date"
        elif period_choice == '4':
            start_date = "2000-01-01"  # Far past
            end_date = today.strftime('%Y-%m-%d')
            period_name = "All Time"
        elif period_choice == '5':
            start_input = input("Enter start date (YYYY-MM-DD): ").strip()
            end_input = input("Enter end date (YYYY-MM-DD): ").strip()
            
            try:
                # Validate dates
                start_date = datetime.strptime(start_input, '%Y-%m-%d').strftime('%Y-%m-%d')
                end_date = datetime.strptime(end_input, '%Y-%m-%d').strftime('%Y-%m-%d')
                period_name = f"Custom: {start_date} to {end_date}"
            except ValueError:
                print("Invalid date format. Using last 30 days.")
                start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
                end_date = today.strftime('%Y-%m-%d')
                period_name = "Last 30 Days"
        else:
            print("Invalid choice. Using last 30 days.")
            start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
            period_name = "Last 30 Days"
        
        # Get products in this category
        cursor.execute(
            '''
            SELECT product_id, name, price, is_active
            FROM shop_products
            WHERE category = ?
            ORDER BY name
            ''',
            [selected_category]
        )
        
        products = cursor.fetchall()
        
        if not products:
            print(f"No products found in category '{selected_category}'.")
            conn.close()
            return
        
        # Get sales data
        cursor.execute(
            '''
            SELECT p.product_id, p.name, p.price,
                   SUM(ti.quantity) as total_quantity,
                   SUM(ti.subtotal) as total_revenue,
                   COUNT(DISTINCT ti.transaction_id) as transaction_count
            FROM shop_transaction_items ti
            JOIN shop_products p ON ti.product_id = p.product_id
            JOIN shop_transactions t ON ti.transaction_id = t.transaction_id
            WHERE p.category = ? AND t.transaction_date BETWEEN ? AND ?
            GROUP BY p.product_id
            ORDER BY total_revenue DESC
            ''',
            [selected_category, f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
        )
        
        sales_data = cursor.fetchall()
        
        # Display category overview
        print(f"\nCategory: {selected_category}")
        print(f"Period: {period_name}")
        print(f"Total Products in Category: {len(products)}")
        print(f"Products with Sales: {len(sales_data)}")
        
        # Display sales summary
        if not sales_data:
            print(f"No sales found for category '{selected_category}' in this period.")
            
            print("\nProducts in Category (No Sales):")
            print(f"{'Product ID':<12} {'Name':<40} {'Price':<10} {'Status'}")
            print("-" * 80)
            
            for product in products:
                price_formatted = f"£{product['price']:.2f}"
                status = "Active" if product['is_active'] else "Inactive"
                print(f"{product['product_id']:<12} {product['name'][:38]:<40} {price_formatted:<10} {status}")
            
            conn.close()
            input("\nPress Enter to continue...")
            return
        
        # Calculate totals
        total_revenue = sum(s['total_revenue'] for s in sales_data)
        total_quantity = sum(s['total_quantity'] for s in sales_data)
        transaction_count = sum(s['transaction_count'] for s in sales_data)
        
        print(f"Total Revenue: £{total_revenue:.2f}")
        print(f"Total Units Sold: {total_quantity}")
        print(f"Transaction Count: {transaction_count}")
        
        # Display product sales ranking
        print("\nProduct Sales Ranking:")
        print(f"{'Rank':<5} {'Product ID':<12} {'Name':<30} {'Units Sold':<12} {'Revenue':<15} {'% of Category'}")
        print("-" * 90)
        
        for i, product in enumerate(sales_data):
            percent = (product['total_revenue'] / total_revenue) * 100 if total_revenue > 0 else 0
            print(f"{i+1:<5} {product['product_id']:<12} {product['name'][:28]:<30} {product['total_quantity']:<12} £{product['total_revenue']:<15.2f} {percent:.1f}%")
        
        # Products with no sales
        sold_product_ids = {s['product_id'] for s in sales_data}
        unsold_products = [p for p in products if p['product_id'] not in sold_product_ids]
        
        if unsold_products:
            print(f"\nProducts with No Sales in this Period ({len(unsold_products)}):")
            print(f"{'Product ID':<12} {'Name':<40} {'Price':<10} {'Status'}")
            print("-" * 80)
            
            for product in unsold_products:
                price_formatted = f"£{product['price']:.2f}"
                status = "Active" if product['is_active'] else "Inactive"
                print(f"{product['product_id']:<12} {product['name'][:38]:<40} {price_formatted:<10} {status}")
        
        # Time-based analysis
        try:
            # Monthly trend if period is long enough
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            days_diff = (end - start).days
            
            if days_diff >= 60:  # If at least 60 days, show monthly trend
                cursor.execute(
                    '''
                    SELECT strftime('%Y-%m', t.transaction_date) as month,
                           SUM(ti.quantity) as quantity,
                           SUM(ti.subtotal) as revenue
                    FROM shop_transaction_items ti
                    JOIN shop_transactions t ON ti.transaction_id = t.transaction_id
                    JOIN shop_products p ON ti.product_id = p.product_id
                    WHERE p.category = ? AND t.transaction_date BETWEEN ? AND ?
                    GROUP BY month
                    ORDER BY month
                    ''',
                    [selected_category, f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
                )
                
                monthly_data = cursor.fetchall()
                
                if monthly_data:
                    print("\nMonthly Sales Trend:")
                    print(f"{'Month':<10} {'Units Sold':<12} {'Revenue':<15} {'Month/Month %'}")
                    print("-" * 60)
                    
                    prev_revenue = None
                    for i, month_data in enumerate(monthly_data):
                        month_label = datetime.strptime(month_data['month'], '%Y-%m').strftime('%b %Y')
                        
                        # Calculate month-over-month percentage
                        if i > 0 and prev_revenue:
                            mom_pct = ((month_data['revenue'] - prev_revenue) / prev_revenue) * 100 if prev_revenue > 0 else float('inf')
                            mom_display = f"{mom_pct:+.1f}%"
                        else:
                            mom_display = "N/A"
                        
                        print(f"{month_label:<10} {month_data['quantity']:<12} £{month_data['revenue']:<15.2f} {mom_display}")
                        prev_revenue = month_data['revenue']
        except Exception as e:
            # Skip time analysis on error
            print(f"Note: Could not generate time trend analysis: {e}")
        
        conn.close()
        input("\nPress Enter to continue...")
        
    except sqlite3.Error as e:
        print(f"Database error generating report: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error generating report: {e}")
        if 'conn' in locals():
            conn.close()

@log_export(module="shop", description="Exporting sales data")
def export_sales_data():
    """Export sales data to CSV or Excel"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to export sales data.")
        return
    
    if not auth.check_permission('generate_sales_reports'):
        print("You don't have permission to export sales data.")
        return
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("\nExport Sales Data")
        print("----------------")
        
        # Get date range
        print("Select date range:")
        print("1. Last 7 days")
        print("2. Last 30 days")
        print("3. Last 90 days")
        print("4. Year to date")
        print("5. Custom range")
        
        range_choice = input("Select option (1-5): ").strip()
        
        today = datetime.now()
        
        if range_choice == '1':
            start_date = (today - timedelta(days=7)).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
            period_name = "7days"
        elif range_choice == '2':
            start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
            period_name = "30days"
        elif range_choice == '3':
            start_date = (today - timedelta(days=90)).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
            period_name = "90days"
        elif range_choice == '4':
            start_date = f"{today.year}-01-01"
            end_date = today.strftime('%Y-%m-%d')
            period_name = f"{today.year}_ytd"
        elif range_choice == '5':
            start_input = input("Enter start date (YYYY-MM-DD): ").strip()
            end_input = input("Enter end date (YYYY-MM-DD): ").strip()
            
            try:
                # Validate dates
                start_date = datetime.strptime(start_input, '%Y-%m-%d').strftime('%Y-%m-%d')
                end_date = datetime.strptime(end_input, '%Y-%m-%d').strftime('%Y-%m-%d')
                period_name = f"{start_date}_to_{end_date}"
            except ValueError:
                print("Invalid date format. Using last 30 days.")
                start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
                end_date = today.strftime('%Y-%m-%d')
                period_name = "30days"
        else:
            print("Invalid choice. Using last 30 days.")
            start_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
            end_date = today.strftime('%Y-%m-%d')
            period_name = "30days"
        
        # Get export format
        print("\nExport Format:")
        print("1. CSV")
        print("2. Excel")
        
        format_choice = input("Select format (1-2): ").strip()
        
        if format_choice == '1':
            export_format = 'csv'
        elif format_choice == '2':
            export_format = 'excel'
        else:
            print("Invalid choice. Using CSV format.")
            export_format = 'csv'
        
        # Get data type
        print("\nData to Export:")
        print("1. Transactions")
        print("2. Product Sales")
        print("3. Category Sales")
        print("4. Daily Sales")
        print("5. All Data")
        
        data_choice = input("Select data type (1-5): ").strip()
        
        if data_choice not in ['1', '2', '3', '4', '5']:
            print("Invalid choice. Exporting transactions.")
            data_choice = '1'
        
        # Define file path
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_base = f"shop_export_{period_name}_{timestamp}"
        
        if export_format == 'csv':
            file_extension = '.csv'
        else:
            file_extension = '.xlsx'
        
        # Get file path from user
        default_path = os.path.join(os.getcwd(), file_base + file_extension)
        file_path = input(f"Enter file path [default: {default_path}]: ").strip()
        
        if not file_path:
            file_path = default_path
        
        # Make sure directory exists
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory)
            except OSError as e:
                print(f"Error creating directory: {e}")
                conn.close()
                return
        
        # Initialize data containers
        all_dataframes = {}
        
        # Export data based on type
        if data_choice in ['1', '5']:  # Transactions
            cursor.execute(
                '''
                SELECT t.transaction_id, t.transaction_date, u.username, t.student_id,
                       t.total_amount, t.payment_method, t.status
                FROM shop_transactions t
                LEFT JOIN users u ON t.user_id = u.id
                WHERE t.transaction_date BETWEEN ? AND ?
                ORDER BY t.transaction_date
                ''',
                [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
            )
            
            transactions = cursor.fetchall()
            
            if transactions:
                # Convert to DataFrame
                transaction_data = []
                for t in transactions:
                    transaction_data.append({
                        'transaction_id': t['transaction_id'],
                        'date': t['transaction_date'],
                        'username': t['username'],
                        'student_id': t['student_id'],
                        'amount': t['total_amount'],
                        'payment_method': t['payment_method'],
                        'status': t['status']
                    })
                
                all_dataframes['Transactions'] = pd.DataFrame(transaction_data)
                print(f"✓ Prepared {len(transactions)} transaction records")
            else:
                print("No transactions found for the selected period.")
        
        if data_choice in ['2', '5']:  # Product Sales
            cursor.execute(
                '''
                SELECT p.product_id, p.name, p.category, 
                       SUM(ti.quantity) as total_quantity,
                       SUM(ti.subtotal) as total_revenue,
                       COUNT(DISTINCT ti.transaction_id) as transaction_count
                FROM shop_transaction_items ti
                JOIN shop_products p ON ti.product_id = p.product_id
                JOIN shop_transactions t ON ti.transaction_id = t.transaction_id
                WHERE t.transaction_date BETWEEN ? AND ?
                GROUP BY p.product_id
                ORDER BY total_revenue DESC
                ''',
                [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
            )
            
            product_sales = cursor.fetchall()
            
            if product_sales:
                # Convert to DataFrame
                product_data = []
                for p in product_sales:
                    product_data.append({
                        'product_id': p['product_id'],
                        'name': p['name'],
                        'category': p['category'],
                        'quantity_sold': p['total_quantity'],
                        'revenue': p['total_revenue'],
                        'transaction_count': p['transaction_count'],
                        'average_price': p['total_revenue'] / p['total_quantity'] if p['total_quantity'] > 0 else 0
                    })
                
                all_dataframes['Product_Sales'] = pd.DataFrame(product_data)
                print(f"✓ Prepared {len(product_sales)} product sales records")
            else:
                print("No product sales found for the selected period.")
        
        if data_choice in ['3', '5']:  # Category Sales
            cursor.execute(
                '''
                SELECT p.category, 
                       COUNT(DISTINCT p.product_id) as product_count,
                       SUM(ti.quantity) as total_quantity,
                       SUM(ti.subtotal) as total_revenue,
                       COUNT(DISTINCT ti.transaction_id) as transaction_count
                FROM shop_transaction_items ti
                JOIN shop_products p ON ti.product_id = p.product_id
                JOIN shop_transactions t ON ti.transaction_id = t.transaction_id
                WHERE t.transaction_date BETWEEN ? AND ?
                GROUP BY p.category
                ORDER BY total_revenue DESC
                ''',
                [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
            )
            
            category_sales = cursor.fetchall()
            
            if category_sales:
                # Convert to DataFrame
                category_data = []
                for c in category_sales:
                    category_data.append({
                        'category': c['category'],
                        'product_count': c['product_count'],
                        'quantity_sold': c['total_quantity'],
                        'revenue': c['total_revenue'],
                        'transaction_count': c['transaction_count'],
                        'average_per_product': c['total_revenue'] / c['product_count'] if c['product_count'] > 0 else 0
                    })
                
                all_dataframes['Category_Sales'] = pd.DataFrame(category_data)
                print(f"✓ Prepared {len(category_sales)} category sales records")
            else:
                print("No category sales found for the selected period.")
        
        if data_choice in ['4', '5']:  # Daily Sales
            cursor.execute(
                '''
                SELECT date(t.transaction_date) as sale_date,
                       COUNT(DISTINCT t.transaction_id) as transaction_count,
                       SUM(t.total_amount) as total_revenue,
                       COUNT(DISTINCT ti.product_id) as products_sold,
                       SUM(ti.quantity) as quantity_sold
                FROM shop_transactions t
                JOIN shop_transaction_items ti ON t.transaction_id = ti.transaction_id
                WHERE t.transaction_date BETWEEN ? AND ?
                GROUP BY sale_date
                ORDER BY sale_date
                ''',
                [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
            )
            
            daily_sales = cursor.fetchall()
            
            if daily_sales:
                # Convert to DataFrame
                daily_data = []
                for d in daily_sales:
                    daily_data.append({
                        'date': d['sale_date'],
                        'transaction_count': d['transaction_count'],
                        'revenue': d['total_revenue'],
                        'unique_products': d['products_sold'],
                        'quantity_sold': d['quantity_sold'],
                        'average_transaction': d['total_revenue'] / d['transaction_count'] if d['transaction_count'] > 0 else 0
                    })
                
                all_dataframes['Daily_Sales'] = pd.DataFrame(daily_data)
                print(f"✓ Prepared {len(daily_sales)} daily sales records")
            else:
                print("No daily sales found for the selected period.")
        
        # Check if we have any data to export
        if not all_dataframes:
            print("No data found to export for the selected criteria.")
            conn.close()
            return
        
        # Export the data
        if export_format == 'csv':
            # For CSV, export each sheet as a separate file if multiple sheets
            if len(all_dataframes) == 1:
                # Single sheet - use the specified filename
                sheet_name, df = list(all_dataframes.items())[0]
                df.to_csv(file_path, index=False)
                print(f"✅ {sheet_name} exported to {file_path}")
            else:
                # Multiple sheets - create separate files
                base_path = file_path.replace('.csv', '')
                for sheet_name, df in all_dataframes.items():
                    csv_path = f"{base_path}_{sheet_name}.csv"
                    df.to_csv(csv_path, index=False)
                    print(f"✅ {sheet_name} exported to {csv_path}")
        
        else:  # Excel format
            # Remove existing file if it exists to avoid conflicts
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # Create Excel file with multiple sheets
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # Add summary sheet if multiple data types
                if data_choice == '5' and len(all_dataframes) > 1:
                    # Create summary
                    summary_data = {
                        'Metric': [
                            'Report Generated',
                            'Period Start',
                            'Period End',
                            'Data Types Exported',
                            'Total Sheets'
                        ],
                        'Value': [
                            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            start_date,
                            end_date,
                            ', '.join(all_dataframes.keys()),
                            len(all_dataframes)
                        ]
                    }
                    
                    # Add data counts for each sheet
                    for sheet_name, df in all_dataframes.items():
                        summary_data['Metric'].append(f"{sheet_name} Records")
                        summary_data['Value'].append(len(df))
                    
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name='Summary', index=False)
                
                # Export all data sheets
                for sheet_name, df in all_dataframes.items():
                    # Ensure sheet name is valid for Excel (max 31 chars, no special chars)
                    safe_sheet_name = sheet_name.replace(' ', '_')[:31]
                    df.to_excel(writer, sheet_name=safe_sheet_name, index=False)
                    
                    # Auto-adjust column widths
                    worksheet = writer.sheets[safe_sheet_name]
                    for column in worksheet.columns:
                        max_length = 0
                        column_letter = column[0].column_letter
                        for cell in column:
                            try:
                                if len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except:
                                pass
                        adjusted_width = min(max_length + 2, 50)  # Cap at 50 chars
                        worksheet.column_dimensions[column_letter].width = adjusted_width
            
            print(f"✅ Excel file with {len(all_dataframes)} sheet(s) exported to {file_path}")
        
        conn.close()
        
        # Show export summary
        total_records = sum(len(df) for df in all_dataframes.values())
        print(f"\nExport Summary:")
        print(f"- Total records exported: {total_records:,}")
        print(f"- Period: {start_date} to {end_date}")
        print(f"- Format: {export_format.upper()}")
        print(f"- File location: {file_path}")
        
        input("\nExport complete. Press Enter to continue...")
        
    except sqlite3.Error as e:
        print(f"Database error exporting data: {e}")
        if 'conn' in locals():
            conn.close()
    except Exception as e:
        print(f"Error exporting data: {e}")
        if 'conn' in locals():
            conn.close()

# Main entry point - add to main.py
def display_main_menu_extended():
    """Extended display_menu function for the main module to include shop"""
    global auth
    
    # Initialize all databases first
    if not init_all_databases():
        print("Failed to initialize databases. Exiting.")
        return
    
    # Initialize authentication system if not already done
    if auth is None:
        from university_system.infrastructure.auth.user_authentication import UserAuth
        auth = UserAuth()
        init_auth_for_modules()  # Initialize auth for other modules

    # Setup permissions for various modules
    setup_shop_permissions(auth)
    
    print("\nWelcome to the Student Record Management System!")
    
    # Main application loop
    while True:
        # Check if user is logged in
        if not auth or not auth.current_user:
            # User is not logged in, show authentication menu first
            print("\nPlease log in to access the system.")
            from university_system.infrastructure.auth.user_authentication import display_auth_menu
            auth = display_auth_menu()
            if auth is None:
                # Create a new auth object if none was returned
                from university_system.infrastructure.auth.user_authentication import UserAuth
                auth = UserAuth()
            init_auth_for_modules()  # Reinitialize auth for other modules
            # Loop back to check if login was successful
            continue
        
        # User is now logged in, show main menu
        print(f"\nLogged in as: {auth.current_user['username']} ({auth.current_user['role']})")
        
        print("\nMain Menu:")
        print("==========")
        
        # Options based on permissions
        option_num = 1
        option_map = {}
        
        # ... (all existing menu options from the original function) ...
        
        # Show university shop option
        print(f"{option_num}. university shop")
        option_map[str(option_num)] = "university_shop"
        option_num += 1
        
        # ... (continue with other menu options) ...
            
        # Add logout option
        print(f"{option_num}. logout")
        option_map[str(option_num)] = "logout"
        option_num += 1
            
        # Add exit option
        print(f"{option_num}. exit")
        max_option = option_num
        
        choice = input("\nEnter your choice: ")
        
        if choice in option_map:
            option = option_map[choice]
            
            if option == "university_shop":
                display_shop_menu()
            # ... (handle other menu options) ...
            elif option == "logout":
                auth.logout()
                # Continue to loop back to login menu
        elif choice == str(max_option):
            # Exit
            if auth and auth.current_user:
                auth.logout()
            print("Thank you for using the Student Record Management System. Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")

# Integration function to add to main.py
def add_shop_system_to_main_menu(main_display_menu):
    """
    Adds the university shop system to the main menu options.
    This function should be called from main.py.
    
    Args:
        main_display_menu: The original display_menu function from main.py
    """
    # Initialize shop database
    init_shop_db()
    
    def extended_display_menu():
        """Extended version of display_menu that includes shop system"""
        global auth
        
        # Initialize all databases first
        if not init_all_databases():
            print("Failed to initialize databases. Exiting.")
            return
        
        # Initialize authentication system if not already done
        if auth is None:
            from university_system.infrastructure.auth.user_authentication import UserAuth
            auth = UserAuth()
            init_auth_for_modules()  # Initialize auth for other modules

        # Setup permissions for various modules including shop
        setup_shop_permissions(auth)
        
        print("\nWelcome to the Student Record Management System!")
        
        # Main application loop
        while True:
            # Check if user is logged in
            if not auth or not auth.current_user:
                # User is not logged in, show authentication menu first
                print("\nPlease log in to access the system.")
                from university_system.infrastructure.auth.user_authentication import display_auth_menu
                auth = display_auth_menu()
                if auth is None:
                    # Create a new auth object if none was returned
                    from university_system.infrastructure.auth.user_authentication import UserAuth
                    auth = UserAuth()
                init_auth_for_modules()  # Reinitialize auth for other modules
                # Loop back to check if login was successful
                continue
            
            # User is now logged in, show main menu
            print(f"\nLogged in as: {auth.current_user['username']} ({auth.current_user['role']})")
            
            print("\nMain Menu:")
            print("==========")
            
            # Options based on permissions
            option_num = 1
            option_map = {}
            
            # Show standard options
            # ... (all existing menu options from original function) ...
            
            # Show university shop option - available to all authenticated users
            print(f"{option_num}. University Shop")
            option_map[str(option_num)] = "university_shop"
            option_num += 1
            
            # ... (continue with other menu options) ...
                
            # Add logout option
            print(f"{option_num}. Logout")
            option_map[str(option_num)] = "logout"
            option_num += 1
                
            # Add exit option
            print(f"{option_num}. Exit")
            max_option = option_num
            
            choice = input("\nEnter your choice: ")
            
            if choice in option_map:
                option = option_map[choice]
                
                if option == "university_shop":
                    display_shop_menu()
                # ... (handle other menu options) ...
                elif option == "logout":
                    auth.logout()
                    # Continue to loop back to login menu
            elif choice == str(max_option):
                # Exit
                if auth and auth.current_user:
                    auth.logout()
                print("Thank you for using the Student Record Management System. Goodbye!")
                break
            else:
                print("Invalid choice. Please try again.")
    
    # Return the extended menu function
    return extended_display_menu

def generate_pdf_receipt(transaction_id):
    """Generate a PDF receipt for a transaction"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to generate receipts.")
        return False
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get transaction details
        cursor.execute(
            '''
            SELECT t.*, u.username, u.email
            FROM shop_transactions t
            LEFT JOIN users u ON t.user_id = u.id
            WHERE t.transaction_id = ?
            ''',
            [transaction_id]
        )
        
        transaction = cursor.fetchone()
        
        if not transaction:
            print(f"Transaction {transaction_id} not found.")
            conn.close()
            return False
        
        # Get transaction items
        cursor.execute(
            '''
            SELECT ti.*, p.name, p.category
            FROM shop_transaction_items ti
            JOIN shop_products p ON ti.product_id = p.product_id
            WHERE ti.transaction_id = ?
            ''',
            [transaction_id]
        )
        
        items = cursor.fetchall()
        
        if not items:
            print(f"No items found for transaction {transaction_id}.")
            conn.close()
            return False
        
        # Create PDF receipt
        filename = f"receipt_{transaction_id}.pdf"
        doc = SimpleDocTemplate(filename, pagesize=letter)
        story = []
        styles = getSampleStyleSheet()
        
        # Header
        story.append(Paragraph("University Shop Receipt", styles['Title']))
        story.append(Paragraph("<br/><br/>", styles['Normal']))
        
        # Transaction details
        story.append(Paragraph(f"<b>Transaction ID:</b> {transaction['transaction_id']}", styles['Normal']))
        story.append(Paragraph(f"<b>Date:</b> {transaction['transaction_date']}", styles['Normal']))
        story.append(Paragraph(f"<b>Customer:</b> {transaction['username']}", styles['Normal']))
        if transaction['student_id']:
            story.append(Paragraph(f"<b>Student ID:</b> {transaction['student_id']}", styles['Normal']))
        story.append(Paragraph(f"<b>Payment Method:</b> {transaction['payment_method']}", styles['Normal']))
        story.append(Paragraph("<br/>", styles['Normal']))
        
        # Items table
        table_data = [['Item', 'Quantity', 'Price', 'Subtotal']]
        
        for item in items:
            table_data.append([
                item['name'],
                str(item['quantity']),
                f"£{item['price_per_item']:.2f}",
                f"£{item['subtotal']:.2f}"
            ])
        
        # Add total row
        table_data.append(['', '', 'Total:', f"£{transaction['total_amount']:.2f}"])
        
        # Create table
        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey)
        ]))
        
        story.append(table)
        story.append(Paragraph("<br/><br/>", styles['Normal']))
        story.append(Paragraph("Thank you for your purchase!", styles['Normal']))
        
        # Build PDF
        doc.build(story)
        
        print(f"Receipt generated: {filename}")
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error generating receipt: {e}")
        if 'conn' in locals():
            conn.close()
        return False

def get_low_stock_alert():
    """Get alert message for low stock products"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            '''
            SELECT COUNT(*) as low_stock_count
            FROM shop_products p
            JOIN shop_inventory i ON p.product_id = i.product_id
            WHERE p.is_active = 1 AND i.quantity <= i.restock_threshold
            '''
        )
        
        result = cursor.fetchone()
        low_stock_count = result[0] if result else 0
        
        conn.close()
        
        if low_stock_count > 0:
            return f"⚠️  Warning: {low_stock_count} product(s) are low on stock!"
        
        return None
        
    except Exception:
        return None

def calculate_discount_for_transaction(cart_items, user_id=None):
    """Calculate applicable discounts for a transaction"""
    global auth
    
    if not cart_items:
        return 0, None
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get current active discounts
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            '''
            SELECT * FROM shop_discounts
            WHERE is_active = 1 
            AND (start_date IS NULL OR start_date <= ?)
            AND (end_date IS NULL OR end_date >= ?)
            ORDER BY discount_value DESC
            ''',
            [now, now]
        )
        
        discounts = cursor.fetchall()
        
        if not discounts:
            conn.close()
            return 0, None
        
        # Calculate subtotal
        subtotal = sum(item['price'] * item['quantity'] for item in cart_items)
        
        best_discount = None
        best_discount_amount = 0
        
        for discount in discounts:
            # Check minimum purchase amount
            if discount['min_purchase_amount'] > subtotal:
                continue
            
            # Check applicable products
            applicable = False
            
            if discount['applicable_products'] == 'all':
                applicable = True
            else:
                # Check if any cart items match the discount criteria
                if ',' in discount['applicable_products']:
                    # Specific product list
                    applicable_products = discount['applicable_products'].split(',')
                    applicable = any(item['product_id'] in applicable_products for item in cart_items)
                else:
                    # Category
                    applicable = any(item.get('category') == discount['applicable_products'] for item in cart_items)
            
            if not applicable:
                continue
            
            # Calculate discount amount
            if discount['discount_type'] == 'percentage':
                discount_amount = subtotal * (discount['discount_value'] / 100)
            else:  # fixed
                discount_amount = discount['discount_value']
            
            # Don't let discount exceed subtotal
            discount_amount = min(discount_amount, subtotal)
            
            if discount_amount > best_discount_amount:
                best_discount_amount = discount_amount
                best_discount = discount
        
        conn.close()
        return best_discount_amount, best_discount
        
    except Exception as e:
        print(f"Error calculating discount: {e}")
        if 'conn' in locals():
            conn.close()
        return 0, None

def validate_inventory_before_checkout(cart_items):
    """Validate that all cart items are still available in sufficient quantity"""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        validation_errors = []
        
        for item in cart_items:
            cursor.execute(
                '''
                SELECT i.quantity, p.name, p.is_active
                FROM shop_inventory i
                JOIN shop_products p ON i.product_id = p.product_id
                WHERE p.product_id = ?
                ''',
                [item['product_id']]
            )
            
            result = cursor.fetchone()
            
            if not result:
                validation_errors.append(f"Product {item['product_id']} not found")
                continue
            
            if not result['is_active']:
                validation_errors.append(f"{result['name']} is no longer available")
                continue
            
            if result['quantity'] < item['quantity']:
                validation_errors.append(
                    f"{result['name']}: Only {result['quantity']} available, "
                    f"but {item['quantity']} requested"
                )
        
        conn.close()
        return validation_errors
        
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return [f"Validation error: {e}"]

def get_popular_products(limit=10, days=30):
    """Get most popular products based on recent sales"""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        cursor.execute(
            '''
            SELECT p.product_id, p.name, p.category, p.price,
                   SUM(ti.quantity) as total_sold,
                   COUNT(DISTINCT ti.transaction_id) as transaction_count
            FROM shop_transaction_items ti
            JOIN shop_transactions t ON ti.transaction_id = t.transaction_id
            JOIN shop_products p ON ti.product_id = p.product_id
            WHERE t.transaction_date >= ? AND p.is_active = 1
            GROUP BY p.product_id
            ORDER BY total_sold DESC, transaction_count DESC
            LIMIT ?
            ''',
            [start_date.strftime('%Y-%m-%d %H:%M:%S'), limit]
        )
        
        popular_products = cursor.fetchall()
        conn.close()
        
        return popular_products
        
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return []

def search_products(search_term, category=None, min_price=None, max_price=None):
    """Advanced product search function"""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Build query
        query = '''
        SELECT p.*, i.quantity
        FROM shop_products p
        JOIN shop_inventory i ON p.product_id = i.product_id
        WHERE p.is_active = 1
        '''
        params = []
        
        if search_term:
            query += ' AND (p.name LIKE ? OR p.description LIKE ?)'
            params.extend([f'%{search_term}%', f'%{search_term}%'])
        
        if category:
            query += ' AND p.category = ?'
            params.append(category)
        
        if min_price is not None:
            query += ' AND p.price >= ?'
            params.append(min_price)
        
        if max_price is not None:
            query += ' AND p.price <= ?'
            params.append(max_price)
        
        query += ' ORDER BY p.name'
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        conn.close()
        return results
        
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return []

def backup_shop_database():
    """Create a backup of the shop database"""
    try:
        import shutil

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"shop_backup_{timestamp}.db"

        db_path = str(DEFAULT_DB_PATH)
        shutil.copy2(db_path, backup_filename)
        
        print(f"Database backup created: {backup_filename}")
        return backup_filename
        
    except Exception as e:
        print(f"Error creating backup: {e}")
        return None

def get_sales_statistics(days=30):
    """Get comprehensive sales statistics"""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Get basic stats
        cursor.execute(
            '''
            SELECT 
                COUNT(DISTINCT transaction_id) as transaction_count,
                SUM(total_amount) as total_revenue,
                AVG(total_amount) as avg_transaction,
                MIN(total_amount) as min_transaction,
                MAX(total_amount) as max_transaction
            FROM shop_transactions
            WHERE transaction_date >= ?
            ''',
            [start_date.strftime('%Y-%m-%d %H:%M:%S')]
        )
        
        basic_stats = cursor.fetchone()
        
        # Get payment method breakdown
        cursor.execute(
            '''
            SELECT payment_method, COUNT(*) as count, SUM(total_amount) as amount
            FROM shop_transactions
            WHERE transaction_date >= ?
            GROUP BY payment_method
            ORDER BY amount DESC
            ''',
            [start_date.strftime('%Y-%m-%d %H:%M:%S')]
        )
        
        payment_stats = cursor.fetchall()
        
        # Get top categories
        cursor.execute(
            '''
            SELECT p.category, SUM(ti.subtotal) as revenue, SUM(ti.quantity) as quantity
            FROM shop_transaction_items ti
            JOIN shop_transactions t ON ti.transaction_id = t.transaction_id
            JOIN shop_products p ON ti.product_id = p.product_id
            WHERE t.transaction_date >= ?
            GROUP BY p.category
            ORDER BY revenue DESC
            LIMIT 5
            ''',
            [start_date.strftime('%Y-%m-%d %H:%M:%S')]
        )
        
        category_stats = cursor.fetchall()
        
        conn.close()
        
        return {
            'period_days': days,
            'basic': basic_stats,
            'payment_methods': payment_stats,
            'top_categories': category_stats
        }
        
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return None

def display_dashboard():
    """Display a dashboard with key shop metrics"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view the dashboard.")
        return
    
    if not auth.check_permission('generate_sales_reports'):
        print("You don't have permission to view the dashboard.")
        return
    
    try:
        print("\n" + "="*60)
        print("UNIVERSITY SHOP DASHBOARD")
        print("="*60)
        
        # Get low stock alert
        alert = get_low_stock_alert()
        if alert:
            print(f"\n{alert}")
        
        # Get sales statistics
        stats = get_sales_statistics(30)
        
        if stats and stats['basic']:
            basic = stats['basic']
            print(f"\nSALES SUMMARY (Last 30 Days)")
            print("-" * 40)
            print(f"Total Transactions: {basic['transaction_count'] or 0}")
            print(f"Total Revenue: £{basic['total_revenue'] or 0:.2f}")
            print(f"Average Transaction: £{basic['avg_transaction'] or 0:.2f}")
            
            if stats['payment_methods']:
                print(f"\nPAYMENT METHODS")
                print("-" * 20)
                for method in stats['payment_methods']:
                    print(f"{method['payment_method']}: {method['count']} transactions (£{method['amount']:.2f})")
            
            if stats['top_categories']:
                print(f"\nTOP CATEGORIES")
                print("-" * 20)
                for cat in stats['top_categories']:
                    print(f"{cat['category']}: £{cat['revenue']:.2f} ({cat['quantity']} items)")
        
        # Get popular products
        popular = get_popular_products(5, 30)
        if popular:
            print(f"\nPOPULAR PRODUCTS (Last 30 Days)")
            print("-" * 40)
            for i, product in enumerate(popular, 1):
                print(f"{i}. {product['name']} - {product['total_sold']} sold")
        
        print("\n" + "="*60)
        input("\nPress Enter to continue...")
        
    except Exception as e:
        print(f"Error displaying dashboard: {e}")

def cleanup_expired_discounts():
    """Clean up expired discounts from the database"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Deactivate expired discounts
        cursor.execute(
            '''
            UPDATE shop_discounts 
            SET is_active = 0 
            WHERE end_date IS NOT NULL AND end_date < ? AND is_active = 1
            ''',
            [now]
        )
        
        expired_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        if expired_count > 0:
            print(f"Deactivated {expired_count} expired discount(s).")
        
        return expired_count
        
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        print(f"Error cleaning up expired discounts: {e}")
        return 0

def validate_product_data(product_data):
    """Validate product data before insertion/update"""
    errors = []
    
    # Required fields
    if not product_data.get('name', '').strip():
        errors.append("Product name is required")
    
    if not product_data.get('price'):
        errors.append("Product price is required")
    else:
        try:
            price = float(product_data['price'])
            if price < 0:
                errors.append("Product price cannot be negative")
        except (ValueError, TypeError):
            errors.append("Product price must be a valid number")
    
    if not product_data.get('category', '').strip():
        errors.append("Product category is required")
    
    # Optional validations
    if 'tax_rate' in product_data:
        try:
            tax_rate = float(product_data['tax_rate'])
            if tax_rate < 0 or tax_rate > 1:
                errors.append("Tax rate must be between 0 and 1 (0-100%)")
        except (ValueError, TypeError):
            errors.append("Tax rate must be a valid number")
    
    return errors

def format_currency(amount):
    """Format amount as currency"""
    try:
        return f"£{float(amount):.2f}"
    except (ValueError, TypeError):
        return "£0.00"

def calculate_tax(amount, tax_rate=0.2):
    """Calculate tax amount"""
    try:
        return float(amount) * float(tax_rate)
    except (ValueError, TypeError):
        return 0.0

def get_system_settings():
    """Get system-wide shop settings"""
    default_settings = {
        'currency_symbol': '£',
        'default_tax_rate': 0.2,
        'low_stock_threshold': 10,
        'max_cart_items': 50,
        'receipt_footer': 'Thank you for shopping with us!',
        'shop_name': 'University Shop',
        'shop_address': 'University Campus',
        'shop_phone': '555-SHOP',
        'shop_email': 'shop@university.edu'
    }
    
    # In a real system, these might be stored in a settings table
    return default_settings

def log_shop_activity(activity_type, description, user_id=None, details=None):
    """Log shop activities for audit trail"""
    global auth
    
    try:
        if not user_id and auth and auth.current_user:
            user_id = auth.current_user['id']
        
        # This would typically log to a separate audit table
        # For now, we'll just use the simple activity logger
        from university_system.modules.shared.utils.simple_activity_logger import log_dynamic_activity
        
        log_dynamic_activity(
            module="shop",
            activity_type=activity_type,
            description=description,
            user_id=user_id,
            additional_data=details
        )
        
    except Exception as e:
        # Don't let logging errors break the main functionality
        print(f"Warning: Could not log activity: {e}")

def get_transaction_summary(transaction_id):
    """Get a detailed summary of a transaction"""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get transaction
        cursor.execute(
            '''
            SELECT t.*, u.username, u.email
            FROM shop_transactions t
            LEFT JOIN users u ON t.user_id = u.id
            WHERE t.transaction_id = ?
            ''',
            [transaction_id]
        )
        
        transaction = cursor.fetchone()
        
        if not transaction:
            conn.close()
            return None
        
        # Get items
        cursor.execute(
            '''
            SELECT ti.*, p.name, p.category
            FROM shop_transaction_items ti
            JOIN shop_products p ON ti.product_id = p.product_id
            WHERE ti.transaction_id = ?
            ORDER BY p.name
            ''',
            [transaction_id]
        )
        
        items = cursor.fetchall()
        
        conn.close()
        
        return {
            'transaction': dict(transaction),
            'items': [dict(item) for item in items],
            'item_count': len(items),
            'total_quantity': sum(item['quantity'] for item in items)
        }
        
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        print(f"Error getting transaction summary: {e}")
        return None

def send_low_stock_notification():
    """Send notification for low stock items (placeholder for email/SMS)"""
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get low stock items
        cursor.execute(
            '''
            SELECT p.product_id, p.name, p.category, i.quantity, i.restock_threshold
            FROM shop_products p
            JOIN shop_inventory i ON p.product_id = i.product_id
            WHERE p.is_active = 1 AND i.quantity <= i.restock_threshold
            ORDER BY (i.quantity * 1.0 / i.restock_threshold)
            '''
        )
        
        low_stock_items = cursor.fetchall()
        conn.close()
        
        if not low_stock_items:
            return
        
        # In a real system, this would send email/SMS notifications
        print(f"\n📧 Low Stock Notification would be sent for {len(low_stock_items)} items:")
        for item in low_stock_items:
            print(f"  - {item['name']} ({item['product_id']}): {item['quantity']} remaining")
        
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        print(f"Error sending low stock notification: {e}")

def get_inventory_valuation():
    """Calculate total inventory value"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            '''
            SELECT SUM(p.price * i.quantity) as total_value,
                   COUNT(p.product_id) as product_count,
                   SUM(i.quantity) as total_quantity
            FROM shop_products p
            JOIN shop_inventory i ON p.product_id = i.product_id
            WHERE p.is_active = 1
            '''
        )
        
        result = cursor.fetchone()
        conn.close()
        
        return {
            'total_value': result[0] or 0,
            'product_count': result[1] or 0,
            'total_quantity': result[2] or 0
        }
        
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return {'total_value': 0, 'product_count': 0, 'total_quantity': 0}

# Additional helper function for the main menu integration
def setup_shop_system():
    """Complete setup function for the shop system"""
    print("Setting up University Shop System...")
    
    # Initialize databases
    if not init_all_databases():
        print("❌ Failed to initialize databases")
        return False
    
    # Initialize authentication
    global auth
    if not auth:
        from university_system.infrastructure.auth.user_authentication import UserAuth
        auth = UserAuth()
    
    # Setup permissions
    if not setup_shop_permissions(auth):
        print("❌ Failed to setup shop permissions")
        return False
    
    # Create sample users if needed
    create_sample_users()
    
    # Clean up expired discounts
    cleanup_expired_discounts()
    
    print("✅ Shop system setup complete!")
    return True

def quick_add_product():
    """Quick product addition with minimal input"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to add products.")
        return False
    
    if not auth.check_permission('manage_products'):
        print("You don't have permission to add products.")
        return False
    
    try:
        print("\n🚀 Quick Add Product")
        print("-" * 20)
        
        # Get basic info
        name = input("Product name: ").strip()
        if not name:
            print("Product name is required.")
            return False
        
        try:
            price = float(input("Price (£): ").strip())
            if price < 0:
                print("Price cannot be negative.")
                return False
        except ValueError:
            print("Invalid price.")
            return False
        
        category = input("Category: ").strip() or "General"
        
        try:
            stock = int(input("Initial stock: ").strip() or "10")
            if stock < 0:
                print("Stock cannot be negative.")
                return False
        except ValueError:
            print("Invalid stock quantity.")
            return False
        
        # Generate product ID
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT MAX(SUBSTR(product_id, 2)) FROM shop_products WHERE product_id LIKE 'P%'")
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
        cursor.execute(
            '''
            INSERT INTO shop_products
            (product_id, name, description, price, category, created_at, updated_at, tax_rate, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            [product_id, name, f"Quick-added product: {name}", price, category, now, now, 0.2, 1]
        )
        
        # Insert inventory
        cursor.execute(
            '''
            INSERT INTO shop_inventory
            (product_id, quantity, last_restock_date, restock_threshold)
            VALUES (?, ?, ?, ?)
            ''',
            [product_id, stock, now, max(5, stock // 4)]
        )
        
        conn.commit()
        conn.close()
        
        print(f"✅ Product {product_id} '{name}' added successfully!")
        return True
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        print(f"❌ Error adding product: {e}")
        return False

def bulk_update_prices():
    """Bulk update prices by category or percentage"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to update prices.")
        return
    
    if not auth.check_permission('manage_products'):
        print("You don't have permission to update prices.")
        return
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("\n💰 Bulk Price Update")
        print("-" * 20)
        
        print("Update options:")
        print("1. Update all prices by percentage")
        print("2. Update prices by category")
        print("3. Set fixed price for category")
        
        choice = input("Select option (1-3): ").strip()
        
        if choice == '1':
            # Update all prices by percentage
            try:
                percentage = float(input("Enter percentage change (+/-): ").strip())
                
                cursor.execute(
                    '''
                    UPDATE shop_products 
                    SET price = price * (1 + ? / 100), updated_at = ?
                    WHERE is_active = 1
                    ''',
                    [percentage, datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
                )
                
                affected = cursor.rowcount
                conn.commit()
                
                print(f"✅ Updated prices for {affected} products by {percentage:+.1f}%")
                
            except ValueError:
                print("❌ Invalid percentage value.")
                
        elif choice == '2':
            # Update by category
            cursor.execute("SELECT DISTINCT category FROM shop_products WHERE is_active = 1 ORDER BY category")
            categories = cursor.fetchall()
            
            if not categories:
                print("No categories found.")
                conn.close()
                return
            
            print("\nAvailable categories:")
            for i, cat in enumerate(categories):
                print(f"{i+1}. {cat['category']}")
            
            try:
                cat_choice = int(input("Select category: ").strip())
                if cat_choice < 1 or cat_choice > len(categories):
                    print("Invalid category selection.")
                    conn.close()
                    return
                
                selected_category = categories[cat_choice-1]['category']
                percentage = float(input("Enter percentage change (+/-): ").strip())
                
                cursor.execute(
                    '''
                    UPDATE shop_products 
                    SET price = price * (1 + ? / 100), updated_at = ?
                    WHERE category = ? AND is_active = 1
                    ''',
                    [percentage, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), selected_category]
                )
                
                affected = cursor.rowcount
                conn.commit()
                
                print(f"✅ Updated prices for {affected} products in '{selected_category}' by {percentage:+.1f}%")
                
            except (ValueError, IndexError):
                print("❌ Invalid input.")
        
        elif choice == '3':
            # Set fixed price for category
            cursor.execute("SELECT DISTINCT category FROM shop_products WHERE is_active = 1 ORDER BY category")
            categories = cursor.fetchall()
            
            if not categories:
                print("No categories found.")
                conn.close()
                return
            
            print("\nAvailable categories:")
            for i, cat in enumerate(categories):
                print(f"{i+1}. {cat['category']}")
            
            try:
                cat_choice = int(input("Select category: ").strip())
                if cat_choice < 1 or cat_choice > len(categories):
                    print("Invalid category selection.")
                    conn.close()
                    return
                
                selected_category = categories[cat_choice-1]['category']
                new_price = float(input("Enter new price (£): ").strip())
                
                if new_price < 0:
                    print("❌ Price cannot be negative.")
                    conn.close()
                    return
                
                cursor.execute(
                    '''
                    UPDATE shop_products 
                    SET price = ?, updated_at = ?
                    WHERE category = ? AND is_active = 1
                    ''',
                    [new_price, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), selected_category]
                )
                
                affected = cursor.rowcount
                conn.commit()
                
                print(f"✅ Set price to £{new_price:.2f} for {affected} products in '{selected_category}'")
                
            except (ValueError, IndexError):
                print("❌ Invalid input.")
        
        else:
            print("❌ Invalid choice.")
        
        conn.close()
        input("\nPress Enter to continue...")
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        print(f"❌ Error updating prices: {e}")

def generate_barcode(product_id):
    """Generate a barcode using python-barcode library or fallback to text representation."""
    try:
        # Try to use python-barcode library for actual barcode generation
        from barcode import Code128
        from barcode.writer import ImageWriter
        import io
        import base64

        # Generate Code128 barcode
        barcode_class = Code128(str(product_id), writer=ImageWriter())
        buffer = io.BytesIO()
        barcode_class.write(buffer)

        # Return base64 encoded image data
        buffer.seek(0)
        barcode_data = base64.b64encode(buffer.getvalue()).decode()
        return {
            'type': 'image',
            'format': 'png',
            'data': barcode_data,
            'text': str(product_id)
        }

    except ImportError:
        # Fallback to text representation if barcode library not available
        barcode_chars = {
            '0': '||  | ||',
            '1': '| |  |||',
            '2': '| || | |',
            '3': '||||   |',
            '4': '|   ||||',
            '5': '||   |||',
            '6': '| |||  |',
            '7': '| | |||',
            '8': '|||  | |',
            '9': '|||  |||',
            'P': '|||| | |',
            'A': '| ||||||',
            'B': '|||| |||',
            'C': '| | ||||',
            'D': '||||| ||',
            'E': '|| |||||',
            'F': '|||||| |'
        }

        barcode = "| "  # Start
        for char in str(product_id):
            if char.upper() in barcode_chars:
                barcode += barcode_chars[char.upper()] + " "
            else:
                barcode += "| | | | "  # Default pattern
        barcode += "|"  # End

        return {
            'type': 'text',
            'data': barcode,
            'text': str(product_id)
        }

def print_product_labels(product_ids=None):
    """Print product labels with barcodes"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to print labels.")
        return
    
    if not auth.check_permission('manage_products'):
        print("You don't have permission to print labels.")
        return
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if product_ids:
            # Print specific products
            placeholders = ','.join(['?'] * len(product_ids))
            cursor.execute(
                f'''
                SELECT p.*, i.quantity
                FROM shop_products p
                JOIN shop_inventory i ON p.product_id = i.product_id
                WHERE p.product_id IN ({placeholders})
                ORDER BY p.name
                ''',
                product_ids
            )
        else:
            # Print all active products
            cursor.execute(
                '''
                SELECT p.*, i.quantity
                FROM shop_products p
                JOIN shop_inventory i ON p.product_id = i.product_id
                WHERE p.is_active = 1
                ORDER BY p.name
                '''
            )
        
        products = cursor.fetchall()
        
        if not products:
            print("No products found for label printing.")
            conn.close()
            return
        
        print(f"\n📄 Product Labels ({len(products)} products)")
        print("=" * 80)
        
        for product in products:
            print(f"\n┌{'─' * 60}┐")
            print(f"│ {product['name'][:56]:<56} │")
            print(f"│ ID: {product['product_id']:<8} Price: £{product['price']:<8.2f} Stock: {product['quantity']:<8} │")
            print(f"│ Category: {product['category']:<46} │")
            print(f"│ {generate_barcode(product['product_id']):<56} │")
            print(f"└{'─' * 60}┘")
        
        conn.close()
        
        # In a real system, this would send to a label printer
        print(f"\n✅ {len(products)} labels ready for printing!")
        input("\nPress Enter to continue...")
        
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        print(f"❌ Error printing labels: {e}")

def get_customer_analytics():
    """Get customer purchase analytics"""
    global auth
    
    if not auth or not auth.current_user:
        return None
    
    if not auth.check_permission('generate_sales_reports'):
        return None
    
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get customer stats
        cursor.execute(
            '''
            SELECT 
                COUNT(DISTINCT user_id) as total_customers,
                AVG(total_amount) as avg_order_value,
                COUNT(*) as total_orders,
                SUM(total_amount) as total_revenue
            FROM shop_transactions
            WHERE transaction_date >= date('now', '-30 days')
            '''
        )
        
        overview = cursor.fetchone()
        
        # Get top customers
        cursor.execute(
            '''
            SELECT u.username, u.student_id,
                   COUNT(t.transaction_id) as order_count,
                   SUM(t.total_amount) as total_spent,
                   AVG(t.total_amount) as avg_order
            FROM shop_transactions t
            JOIN users u ON t.user_id = u.id
            WHERE t.transaction_date >= date('now', '-30 days')
            GROUP BY u.id
            ORDER BY total_spent DESC
            LIMIT 10
            '''
        )
        
        top_customers = cursor.fetchall()
        
        # Get payment method preferences
        cursor.execute(
            '''
            SELECT payment_method, 
                   COUNT(*) as usage_count,
                   ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM shop_transactions WHERE transaction_date >= date('now', '-30 days')), 1) as percentage
            FROM shop_transactions
            WHERE transaction_date >= date('now', '-30 days')
            GROUP BY payment_method
            ORDER BY usage_count DESC
            '''
        )
        
        payment_methods = cursor.fetchall()
        
        conn.close()
        
        return {
            'overview': dict(overview) if overview else {},
            'top_customers': [dict(customer) for customer in top_customers],
            'payment_methods': [dict(method) for method in payment_methods]
        }
        
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return None

def display_customer_analytics():
    """Display customer analytics dashboard"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view analytics.")
        return
    
    if not auth.check_permission('generate_sales_reports'):
        print("You don't have permission to view analytics.")
        return
    
    analytics = get_customer_analytics()
    
    if not analytics:
        print("❌ Could not retrieve customer analytics.")
        return
    
    print("\n" + "="*60)
    print("CUSTOMER ANALYTICS (Last 30 Days)")
    print("="*60)
    
    overview = analytics['overview']
    if overview:
        print(f"\nOVERVIEW")
        print("-" * 20)
        print(f"Total Customers: {overview.get('total_customers', 0)}")
        print(f"Total Orders: {overview.get('total_orders', 0)}")
        print(f"Total Revenue: £{overview.get('total_revenue', 0):.2f}")
        print(f"Average Order Value: £{overview.get('avg_order_value', 0):.2f}")
    
    if analytics['top_customers']:
        print(f"\nTOP CUSTOMERS")
        print("-" * 50)
        print(f"{'Rank':<5} {'Username':<15} {'Student ID':<12} {'Orders':<8} {'Total Spent':<15} {'Avg Order'}")
        print("-" * 70)
        
        for i, customer in enumerate(analytics['top_customers'], 1):
            student_id = customer['student_id'] or 'N/A'
            print(f"{i:<5} {customer['username']:<15} {student_id:<12} {customer['order_count']:<8} £{customer['total_spent']:<14.2f} £{customer['avg_order']:.2f}")
    
    if analytics['payment_methods']:
        print(f"\nPAYMENT METHOD PREFERENCES")
        print("-" * 35)
        print(f"{'Method':<20} {'Usage':<8} {'Percentage'}")
        print("-" * 35)
        
        for method in analytics['payment_methods']:
            print(f"{method['payment_method']:<20} {method['usage_count']:<8} {method['percentage']}%")
    
    input("\nPress Enter to continue...")

# Integration test function
def test_shop_system():
    """Test basic shop system functionality"""
    print("\n🧪 Testing Shop System...")
    
    try:
        # Test database connection
        conn = get_connection()
        cursor = conn.cursor()
        
        # Test tables exist
        tables = ['shop_products', 'shop_inventory', 'shop_transactions', 'shop_transaction_items', 'shop_discounts', 'shop_cart']
        
        for table in tables:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if not cursor.fetchone():
                print(f"❌ Table {table} not found")
                conn.close()
                return False
        
        # Test sample data
        cursor.execute("SELECT COUNT(*) FROM shop_products")
        product_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM shop_inventory")
        inventory_count = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"✅ Database structure: OK")
        print(f"✅ Products: {product_count}")
        print(f"✅ Inventory records: {inventory_count}")
        
        # Test utility functions
        settings = get_system_settings()
        if settings and 'currency_symbol' in settings:
            print(f"✅ System settings: OK")
        
        valuation = get_inventory_valuation()
        if valuation:
            print(f"✅ Inventory valuation: £{valuation['total_value']:.2f}")
        
        print("✅ Shop system test completed successfully!")
        return True
        
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        print(f"❌ Shop system test failed: {e}")
        return False

# Final integration function for main.py
def integrate_shop_with_main():
    """
    Main integration function to be called from main.py
    This sets up everything needed for the shop system
    """
    print("🏪 Initializing University Shop System...")
    
    # Setup the complete system
    if not setup_shop_system():
        print("❌ Failed to setup shop system")
        return False
    
    # Test the system
    if not test_shop_system():
        print("❌ Shop system tests failed")
        return False
    
    print("✅ University Shop System ready!")
    return True


# Main execution block for running as module or script
if __name__ == "__main__":
    print("=" * 60)
    print("UNIVERSITY SHOP MANAGEMENT SYSTEM - CLI MODE")
    print("=" * 60)
    print()

    # Initialize shop database
    if init_shop_db():
        # Launch the shop menu
        try:
            display_shop_menu()
        except KeyboardInterrupt:
            print("\n\nExiting shop system...")
        except Exception as e:
            print(f"\n❌ Error running shop system: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("❌ Failed to initialize shop database")
        print("Please check your database configuration and try again.")
