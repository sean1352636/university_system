#!/usr/bin/env python3
"""
Cafe System CLI for University Management System
A command-line interface for campus cafe point-of-sale operations.
Features: Menu management, order processing, inventory tracking, and reporting.

Integrated with the University Management System.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# University system imports
from university_system.infrastructure.database.db import DEFAULT_DB_PATH

# Import auth instance management
try:
    from university_system.infrastructure.auth import get_current_user, set_auth_instance
    from university_system.infrastructure.shared_context import get_auth, set_auth as set_shared_auth
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None
    get_auth = lambda: None
    set_shared_auth = lambda x: None

# Import finance integration for student payments
try:
    from university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False

# Import activity logger for audit trail
try:
    from university_system.modules.shared.utils.simple_activity_logger import (
        log_activity,
        log_create,
        log_read,
        log_update,
        log_delete,
        log_menu_navigation,
    )
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None
    log_create = lambda *args, **kwargs: None
    log_read = lambda *args, **kwargs: None
    log_update = lambda *args, **kwargs: None
    log_delete = lambda *args, **kwargs: None
    log_menu_navigation = lambda *args, **kwargs: None

# Import i18n for internationalization
from university_system.modules.shared.utils.i18n import (
    get_text,
    get_current_language,
)
from university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)

logger = logging.getLogger(__name__)

# Global auth instance
auth = None

# Categories for cafe menu items
CATEGORIES = ["Hot Drinks", "Cold Drinks", "Pastries", "Food"]


def set_auth(auth_instance: Any) -> None:
    """Set the global auth instance for cafe CLI."""
    global auth
    auth = auth_instance
    if HAS_AUTH:
        set_auth_instance(auth_instance)
        try:
            set_shared_auth(auth_instance)
        except Exception as e:
            logger.warning(f"Failed to set auth in shared_context: {e}")


def get_db_connection():
    """Get database connection with proper error handling."""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        return conn
    except (sqlite3.Error, OSError) as e:
        print(f"Database connection error: {e}")
        return None


def init_cafe_db() -> bool:
    """Initialize cafe database tables."""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Cafe menu items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cafe_menu_items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                available INTEGER DEFAULT 1,
                stock_quantity INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Cafe orders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cafe_orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                customer_name TEXT,
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_amount REAL NOT NULL,
                payment_method TEXT,
                status TEXT DEFAULT 'pending',
                notes TEXT
            )
        ''')

        # Cafe order items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cafe_order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                item_id INTEGER,
                item_name TEXT,
                quantity INTEGER,
                unit_price REAL,
                subtotal REAL,
                FOREIGN KEY (order_id) REFERENCES cafe_orders(order_id),
                FOREIGN KEY (item_id) REFERENCES cafe_menu_items(item_id)
            )
        ''')

        # Cafe inventory transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cafe_inventory_transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER,
                quantity_change INTEGER,
                transaction_type TEXT,
                transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (item_id) REFERENCES cafe_menu_items(item_id)
            )
        ''')

        conn.commit()

        # Insert sample menu items if table is empty
        cursor.execute('SELECT COUNT(*) FROM cafe_menu_items')
        if cursor.fetchone()[0] == 0:
            sample_items = [
                ('Espresso', 'Hot Drinks', 'Classic Italian espresso', 2.50, 1, 100),
                ('Cappuccino', 'Hot Drinks', 'Espresso with steamed milk and foam', 3.50, 1, 100),
                ('Latte', 'Hot Drinks', 'Espresso with steamed milk', 3.75, 1, 100),
                ('Americano', 'Hot Drinks', 'Espresso with hot water', 2.75, 1, 100),
                ('Hot Chocolate', 'Hot Drinks', 'Rich hot chocolate', 3.25, 1, 100),
                ('Tea', 'Hot Drinks', 'Selection of teas', 2.25, 1, 100),
                ('Iced Coffee', 'Cold Drinks', 'Chilled coffee over ice', 3.50, 1, 100),
                ('Iced Tea', 'Cold Drinks', 'Refreshing iced tea', 2.75, 1, 100),
                ('Smoothie', 'Cold Drinks', 'Fruit smoothie', 4.50, 1, 50),
                ('Fresh Juice', 'Cold Drinks', 'Freshly squeezed juice', 3.95, 1, 50),
                ('Croissant', 'Pastries', 'Buttery French croissant', 2.50, 1, 30),
                ('Muffin', 'Pastries', 'Blueberry or chocolate chip', 2.75, 1, 40),
                ('Danish', 'Pastries', 'Sweet pastry', 3.00, 1, 30),
                ('Cookie', 'Pastries', 'Freshly baked cookie', 1.50, 1, 60),
                ('Brownie', 'Pastries', 'Chocolate brownie', 2.95, 1, 40),
                ('Sandwich', 'Food', 'Various sandwich options', 5.50, 1, 25),
                ('Panini', 'Food', 'Grilled panini', 6.50, 1, 20),
                ('Salad', 'Food', 'Fresh garden salad', 5.95, 1, 15),
                ('Soup', 'Food', 'Soup of the day', 4.50, 1, 20),
                ('Bagel', 'Food', 'Toasted bagel with spreads', 3.25, 1, 35)
            ]
            cursor.executemany(
                'INSERT INTO cafe_menu_items (name, category, description, price, available, stock_quantity) VALUES (?, ?, ?, ?, ?, ?)',
                sample_items
            )
            conn.commit()

        conn.close()
        logger.info("Cafe database initialized successfully")
        return True

    except sqlite3.Error as e:
        logger.error(f"Error initializing cafe database: {e}")
        print(f"Database error: {e}")
        return False


def setup_cafe_permissions(auth_instance=None) -> None:
    """Setup permissions for the cafe module."""
    if auth_instance is None:
        auth_instance = auth or get_auth()

    if auth_instance is None:
        logger.warning("No auth instance available for setting up cafe permissions")
        return

    # Define cafe permissions
    permissions = [
        'view_cafe_menu',
        'add_cafe_item',
        'edit_cafe_item',
        'delete_cafe_item',
        'process_cafe_order',
        'view_cafe_orders',
        'manage_cafe_inventory',
        'view_cafe_reports',
        'manage_cafe',
    ]

    # Add permissions to roles
    try:
        if hasattr(auth_instance, 'add_permission_to_role'):
            # Admin gets all permissions
            for perm in permissions:
                try:
                    auth_instance.add_permission_to_role('admin', perm)
                except Exception:
                    pass

            # Staff gets most permissions
            staff_perms = [p for p in permissions if 'delete' not in p]
            for perm in staff_perms:
                try:
                    auth_instance.add_permission_to_role('staff', perm)
                except Exception:
                    pass

            # Students can view menu and place orders
            for perm in ['view_cafe_menu', 'process_cafe_order']:
                try:
                    auth_instance.add_permission_to_role('student', perm)
                    auth_instance.add_permission_to_role('instructor', perm)
                except Exception:
                    pass

            logger.info("Cafe permissions setup complete")
    except Exception as e:
        logger.warning(f"Could not setup cafe permissions: {e}")


# ============================================================================
# Database Operations
# ============================================================================

def get_all_menu_items(category: str = None, available_only: bool = False) -> List[Tuple]:
    """Retrieve all menu items with optional filtering."""
    conn = get_db_connection()
    if not conn:
        return []

    cursor = conn.cursor()
    query = "SELECT item_id, name, category, description, price, available, stock_quantity FROM cafe_menu_items"
    params = []

    conditions = []
    if category and category != "All":
        conditions.append("category = ?")
        params.append(category)
    if available_only:
        conditions.append("available = 1")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY category, name"
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    return results


def get_menu_item(item_id: int) -> Optional[Tuple]:
    """Get a single menu item by ID."""
    conn = get_db_connection()
    if not conn:
        return None

    cursor = conn.cursor()
    cursor.execute(
        "SELECT item_id, name, category, description, price, available, stock_quantity FROM cafe_menu_items WHERE item_id = ?",
        (item_id,)
    )
    result = cursor.fetchone()
    conn.close()
    return result


def add_menu_item(name: str, category: str, description: str, price: float, stock: int) -> bool:
    """Add a new menu item."""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO cafe_menu_items (name, category, description, price, available, stock_quantity) VALUES (?, ?, ?, ?, 1, ?)",
            (name, category, description, price, stock)
        )
        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_create('cafe_menu_item', item_name=name, category=category, price=price)

        return True
    except sqlite3.Error as e:
        logger.error(f"Error adding menu item: {e}")
        return False


def update_menu_item(item_id: int, name: str, category: str, price: float, stock: int, available: bool) -> bool:
    """Update an existing menu item."""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        cursor.execute(
            "UPDATE cafe_menu_items SET name = ?, category = ?, price = ?, stock_quantity = ?, available = ? WHERE item_id = ?",
            (name, category, price, stock, 1 if available else 0, item_id)
        )
        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_update('cafe_menu_item', item_id=item_id, changes={'name': name, 'price': price})

        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating menu item: {e}")
        return False


def delete_menu_item(item_id: int) -> bool:
    """Delete a menu item."""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        cursor.execute("SELECT name FROM cafe_menu_items WHERE item_id = ?", (item_id,))
        row = cursor.fetchone()
        item_name = row[0] if row else "Unknown"

        cursor.execute("DELETE FROM cafe_menu_items WHERE item_id = ?", (item_id,))
        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_delete('cafe_menu_item', item_id=item_id, item_name=item_name)

        return True
    except sqlite3.Error as e:
        logger.error(f"Error deleting menu item: {e}")
        return False


def create_order(student_id: str, customer_name: str, items: List[Dict], payment_method: str) -> Optional[int]:
    """Create a new order with items."""
    try:
        conn = get_db_connection()
        if not conn:
            return None

        cursor = conn.cursor()

        # Calculate total
        total = sum(item['subtotal'] for item in items)

        # Insert order
        cursor.execute(
            "INSERT INTO cafe_orders (student_id, customer_name, total_amount, payment_method, status) VALUES (?, ?, ?, ?, 'completed')",
            (student_id or None, customer_name, total, payment_method)
        )
        order_id = cursor.lastrowid

        # Insert order items and update inventory
        for item in items:
            cursor.execute(
                "INSERT INTO cafe_order_items (order_id, item_id, item_name, quantity, unit_price, subtotal) VALUES (?, ?, ?, ?, ?, ?)",
                (order_id, item['item_id'], item['name'], item['quantity'], item['price'], item['subtotal'])
            )

            # Update inventory
            cursor.execute(
                "UPDATE cafe_menu_items SET stock_quantity = stock_quantity - ? WHERE item_id = ?",
                (item['quantity'], item['item_id'])
            )

            # Log inventory transaction
            cursor.execute(
                "INSERT INTO cafe_inventory_transactions (item_id, quantity_change, transaction_type, notes) VALUES (?, ?, 'sale', ?)",
                (item['item_id'], -item['quantity'], f'Order #{order_id}')
            )

        conn.commit()
        conn.close()

        if ACTIVITY_LOGGER_AVAILABLE:
            log_activity('sale', 'cafe_order', order_id=order_id, total=total, payment_method=payment_method)

        return order_id
    except sqlite3.Error as e:
        logger.error(f"Error creating order: {e}")
        return None


def get_orders(filter_type: str = "all") -> List[Tuple]:
    """Get order history with optional date filter."""
    conn = get_db_connection()
    if not conn:
        return []

    cursor = conn.cursor()

    date_filter = ""
    if filter_type == "today":
        date_filter = "WHERE DATE(o.order_date) = DATE('now')"
    elif filter_type == "week":
        date_filter = "WHERE DATE(o.order_date) >= DATE('now', '-7 days')"
    elif filter_type == "month":
        date_filter = "WHERE DATE(o.order_date) >= DATE('now', 'start of month')"

    query = f'''
        SELECT
            o.order_id,
            o.order_date,
            COALESCE(o.customer_name, o.student_id, 'Walk-in'),
            COUNT(oi.id),
            o.total_amount,
            o.payment_method,
            o.status
        FROM cafe_orders o
        LEFT JOIN cafe_order_items oi ON o.order_id = oi.order_id
        {date_filter}
        GROUP BY o.order_id
        ORDER BY o.order_date DESC
    '''

    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()
    return results


def get_order_items(order_id: int) -> List[Tuple]:
    """Get items for a specific order."""
    conn = get_db_connection()
    if not conn:
        return []

    cursor = conn.cursor()
    cursor.execute(
        "SELECT item_name, quantity, unit_price, subtotal FROM cafe_order_items WHERE order_id = ?",
        (order_id,)
    )
    results = cursor.fetchall()
    conn.close()
    return results


def update_stock(item_id: int, quantity_change: int, transaction_type: str, notes: str = "") -> bool:
    """Update stock quantity for an item."""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        cursor.execute(
            "UPDATE cafe_menu_items SET stock_quantity = stock_quantity + ? WHERE item_id = ?",
            (quantity_change, item_id)
        )
        cursor.execute(
            "INSERT INTO cafe_inventory_transactions (item_id, quantity_change, transaction_type, notes) VALUES (?, ?, ?, ?)",
            (item_id, quantity_change, transaction_type, notes)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating stock: {e}")
        return False


def get_inventory_transactions(limit: int = 100) -> List[Tuple]:
    """Get recent inventory transactions."""
    conn = get_db_connection()
    if not conn:
        return []

    cursor = conn.cursor()
    cursor.execute('''
        SELECT t.transaction_id, m.name, t.quantity_change, t.transaction_type, t.transaction_date, t.notes
        FROM cafe_inventory_transactions t
        JOIN cafe_menu_items m ON t.item_id = m.item_id
        ORDER BY t.transaction_date DESC
        LIMIT ?
    ''', (limit,))
    results = cursor.fetchall()
    conn.close()
    return results


def get_sales_summary(period: str = "day") -> Dict:
    """Get sales summary for a period."""
    conn = get_db_connection()
    if not conn:
        return {}

    cursor = conn.cursor()

    if period == "day":
        date_filter = "DATE(order_date) = DATE('now')"
    elif period == "week":
        date_filter = "DATE(order_date) >= DATE('now', '-7 days')"
    elif period == "month":
        date_filter = "DATE(order_date) >= DATE('now', 'start of month')"
    else:
        date_filter = "1=1"

    cursor.execute(f'''
        SELECT COUNT(*), COALESCE(SUM(total_amount), 0)
        FROM cafe_orders
        WHERE {date_filter}
    ''')
    result = cursor.fetchone()
    order_count = result[0] or 0
    total_sales = result[1] or 0.0

    cursor.execute(f'''
        SELECT payment_method, COUNT(*), COALESCE(SUM(total_amount), 0)
        FROM cafe_orders
        WHERE {date_filter}
        GROUP BY payment_method
    ''')
    payment_breakdown = cursor.fetchall()

    conn.close()

    return {
        'order_count': order_count,
        'total_sales': total_sales,
        'payment_breakdown': payment_breakdown
    }


def get_popular_items(limit: int = 20) -> List[Tuple]:
    """Get most popular items by quantity sold."""
    conn = get_db_connection()
    if not conn:
        return []

    cursor = conn.cursor()
    cursor.execute('''
        SELECT item_name, SUM(quantity) as total_qty, SUM(subtotal) as total_sales
        FROM cafe_order_items
        GROUP BY item_name
        ORDER BY total_qty DESC
        LIMIT ?
    ''', (limit,))
    results = cursor.fetchall()
    conn.close()
    return results


def get_low_stock_items(threshold: int = 20) -> List[Tuple]:
    """Get items with low stock."""
    conn = get_db_connection()
    if not conn:
        return []

    cursor = conn.cursor()
    cursor.execute('''
        SELECT name, category, stock_quantity
        FROM cafe_menu_items
        WHERE stock_quantity < ?
        ORDER BY stock_quantity ASC
    ''', (threshold,))
    results = cursor.fetchall()
    conn.close()
    return results


# ============================================================================
# CLI Menu Functions
# ============================================================================

def display_cafe_menu() -> None:
    """Display the main menu for the cafe CLI."""
    global auth

    # Get auth from shared context if not set
    if not auth:
        auth = get_auth()

    if not auth or not auth.current_user:
        print(get_text('cafe.not_logged_in', default='\nYou must be logged in to access the Cafe System.'))
        return

    # Initialize database if needed
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cafe_menu_items'")
            if not cursor.fetchone():
                conn.close()
                print("Cafe database not initialized. Initializing now...")
                if not init_cafe_db():
                    print("Failed to initialize cafe database.")
                    return
            else:
                conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if not init_cafe_db():
            print("Failed to initialize cafe database.")
            return

    if ACTIVITY_LOGGER_AVAILABLE:
        log_menu_navigation('cafe_system_menu')

    while True:
        print("\n" + "=" * 60)
        print(f"              {get_text('cafe.title', default='UNIVERSITY CAFE SYSTEM')}")
        print("=" * 60)

        # Show quick summary
        summary = get_sales_summary("day")
        today_text = get_text('cafe.summary.today', default="Today's Sales")
        orders_text = get_text('cafe.summary.orders', default='orders')
        print(f"\n{today_text}: {summary['order_count']} {orders_text} | £{summary['total_sales']:.2f}")
        print("-" * 60)

        # Build menu based on permissions
        options = []
        option_num = 1

        # Point of Sale (available to all with permission)
        if auth.check_permission('process_cafe_order') or auth.check_permission('manage_cafe'):
            print(f"\n{option_num}. {get_text('cafe.menu.pos', default='New Order (Point of Sale)')}")
            options.append('pos')
            option_num += 1

        # View menu (available to all)
        print(f"{option_num}. {get_text('cafe.menu.view_menu', default='View Menu')}")
        options.append('view_menu')
        option_num += 1

        # Menu management
        if auth.check_permission('add_cafe_item') or auth.check_permission('manage_cafe'):
            print(f"{option_num}. {get_text('cafe.menu.menu_mgmt', default='Menu Management')}")
            options.append('menu_mgmt')
            option_num += 1

        # Order history
        if auth.check_permission('view_cafe_orders') or auth.check_permission('manage_cafe'):
            print(f"{option_num}. {get_text('cafe.menu.orders', default='Order History')}")
            options.append('orders')
            option_num += 1

        # Inventory management
        if auth.check_permission('manage_cafe_inventory') or auth.check_permission('manage_cafe'):
            print(f"{option_num}. {get_text('cafe.menu.inventory', default='Inventory Management')}")
            options.append('inventory')
            option_num += 1

        # Reports
        if auth.check_permission('view_cafe_reports') or auth.check_permission('manage_cafe'):
            print(f"{option_num}. {get_text('cafe.menu.reports', default='Reports')}")
            options.append('reports')
            option_num += 1

        # Language option
        print(f"{option_num}. {get_text('cafe.menu.language', default='Language')}")
        options.append('language')
        option_num += 1

        print(f"{option_num}. {get_text('cafe.menu.return', default='Return to Main Menu')}")

        choice = input(f"\n{get_text('cafe.prompt.choice', default='Enter your choice')}: ").strip()

        try:
            choice_num = int(choice)

            if choice_num > 0 and choice_num <= len(options):
                selected = options[choice_num - 1]

                if selected == 'pos':
                    point_of_sale_cli()
                elif selected == 'view_menu':
                    view_menu_cli()
                elif selected == 'menu_mgmt':
                    menu_management_cli()
                elif selected == 'orders':
                    order_history_cli()
                elif selected == 'inventory':
                    inventory_management_cli()
                elif selected == 'reports':
                    reports_cli()
                elif selected == 'language':
                    display_language_menu_option()

            elif choice_num == len(options) + 1:
                print(get_text('cafe.returning', default='Returning to main menu...'))
                break
            else:
                print(get_text('cafe.invalid_choice', default='Invalid choice. Please try again.'))

        except ValueError:
            if choice.lower() in ['q', 'quit', 'exit', 'back']:
                break
            print(get_text('cafe.invalid_input', default='Invalid input. Please enter a number.'))


def view_menu_cli() -> None:
    """View the cafe menu."""
    print("\n--- Cafe Menu ---")
    print("\nFilter by category:")
    print("1. All Items")
    for i, cat in enumerate(CATEGORIES, 2):
        print(f"{i}. {cat}")

    filter_choice = input("\nSelect category (or press Enter for All): ").strip()

    category = None
    try:
        choice_num = int(filter_choice)
        if 2 <= choice_num <= len(CATEGORIES) + 1:
            category = CATEGORIES[choice_num - 2]
    except ValueError:
        pass

    items = get_all_menu_items(category=category, available_only=True)

    if not items:
        print("\nNo menu items found.")
        input("\nPress Enter to continue...")
        return

    if ACTIVITY_LOGGER_AVAILABLE:
        log_read('cafe_menu', category=category or 'all', count=len(items))

    print(f"\n{'=' * 80}")
    print(f"{'ID':<5} {'Item':<25} {'Category':<12} {'Price':<10} {'Stock':<8}")
    print(f"{'=' * 80}")

    current_category = None
    for item in items:
        item_id, name, cat, desc, price, available, stock = item
        if cat != current_category:
            current_category = cat
            print(f"\n--- {cat} ---")
        print(f"{item_id:<5} {name[:24]:<25} {cat:<12} £{price:<9.2f} {stock:<8}")

    print(f"{'=' * 80}")
    input("\nPress Enter to continue...")


def point_of_sale_cli() -> None:
    """Process a new order via CLI."""
    print("\n" + "=" * 60)
    print("              NEW ORDER")
    print("=" * 60)

    # Get customer info
    student_id = input("Student ID (press Enter to skip): ").strip()
    customer_name = input("Customer Name (press Enter for Walk-in): ").strip() or "Walk-in Customer"

    # Current order items
    order_items = []
    total = 0.0

    while True:
        print("\n--- Order Items ---")
        if order_items:
            print(f"\n{'Item':<25} {'Qty':<5} {'Price':<10} {'Subtotal':<10}")
            print("-" * 55)
            for item in order_items:
                print(f"{item['name'][:24]:<25} {item['quantity']:<5} £{item['price']:<9.2f} £{item['subtotal']:<9.2f}")
            print("-" * 55)
            print(f"{'TOTAL:':<42} £{total:.2f}")
        else:
            print("No items in order.")

        print("\n1. Add Item")
        print("2. Remove Item")
        print("3. Complete Order")
        print("4. Cancel Order")

        action = input("\nSelect action: ").strip()

        if action == '1':
            # Add item
            items = get_all_menu_items(available_only=True)
            if not items:
                print("No items available.")
                continue

            print(f"\n{'ID':<5} {'Item':<25} {'Price':<10} {'Stock':<8}")
            print("-" * 50)
            for item in items:
                item_id, name, cat, desc, price, available, stock = item
                if stock > 0:
                    print(f"{item_id:<5} {name[:24]:<25} £{price:<9.2f} {stock:<8}")

            try:
                item_id = int(input("\nEnter Item ID: "))
                item = get_menu_item(item_id)
                if not item:
                    print("Item not found.")
                    continue

                item_id, name, cat, desc, price, available, stock = item
                if stock <= 0:
                    print(f"'{name}' is out of stock.")
                    continue

                quantity = int(input(f"Quantity (available: {stock}): "))
                if quantity < 1 or quantity > stock:
                    print("Invalid quantity.")
                    continue

                # Check if item already in order
                existing = next((i for i in order_items if i['item_id'] == item_id), None)
                if existing:
                    existing['quantity'] += quantity
                    existing['subtotal'] = existing['quantity'] * existing['price']
                else:
                    order_items.append({
                        'item_id': item_id,
                        'name': name,
                        'price': price,
                        'quantity': quantity,
                        'subtotal': price * quantity
                    })

                total = sum(i['subtotal'] for i in order_items)
                print(f"\nAdded {quantity} x {name}")

            except ValueError:
                print("Invalid input.")

        elif action == '2':
            # Remove item
            if not order_items:
                print("No items to remove.")
                continue

            print("\nSelect item to remove:")
            for i, item in enumerate(order_items, 1):
                print(f"{i}. {item['name']} (x{item['quantity']})")

            try:
                idx = int(input("Enter number: ")) - 1
                if 0 <= idx < len(order_items):
                    removed = order_items.pop(idx)
                    total = sum(i['subtotal'] for i in order_items)
                    print(f"Removed {removed['name']}")
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Invalid input.")

        elif action == '3':
            # Complete order
            if not order_items:
                print("Cannot complete empty order.")
                continue

            print(f"\n--- Payment ---")
            print(f"Total: £{total:.2f}")
            print("\nPayment Method:")
            print("1. Student Account")
            print("2. Cash")
            print("3. Card")

            pay_choice = input("Select payment method: ").strip()

            payment_method = None
            if pay_choice == '1':
                payment_method = 'student_account'
                if not student_id:
                    student_id = input("Enter Student ID for payment: ").strip()
                    if not student_id:
                        print("Student ID required for student account payment.")
                        continue

                if FINANCE_ACCOUNT_AVAILABLE:
                    balance = get_student_finance_account_balance(student_id)
                    if balance < total:
                        print(f"Insufficient balance. Current balance: £{balance:.2f}")
                        continue

                    success, message = process_student_finance_account_payment(
                        student_id, total, "Cafe Purchase", payment_method='debit'
                    )
                    if not success:
                        print(f"Payment failed: {message}")
                        continue
                else:
                    print("Student finance integration not available. Processing as regular payment.")

            elif pay_choice == '2':
                payment_method = 'cash'
            elif pay_choice == '3':
                payment_method = 'card'
            else:
                print("Invalid payment method.")
                continue

            # Create order
            order_id = create_order(student_id, customer_name, order_items, payment_method)
            if order_id:
                print(f"\n{'=' * 40}")
                print(f"ORDER #{order_id} COMPLETE")
                print(f"Total: £{total:.2f}")
                print(f"Payment: {payment_method}")
                print(f"{'=' * 40}")
            else:
                print("Failed to create order.")

            input("\nPress Enter to continue...")
            return

        elif action == '4':
            confirm = input("Cancel order? (y/n): ").strip().lower()
            if confirm == 'y':
                print("Order cancelled.")
                return


def menu_management_cli() -> None:
    """Menu management submenu."""
    while True:
        print("\n--- Menu Management ---")
        print("1. View All Items")
        print("2. Add New Item")
        print("3. Edit Item")
        print("4. Delete Item")
        print("5. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            items = get_all_menu_items()
            print(f"\n{'=' * 90}")
            print(f"{'ID':<5} {'Item':<25} {'Category':<12} {'Price':<10} {'Stock':<8} {'Available':<10}")
            print(f"{'=' * 90}")
            for item in items:
                item_id, name, cat, desc, price, available, stock = item
                avail_str = "Yes" if available else "No"
                print(f"{item_id:<5} {name[:24]:<25} {cat:<12} £{price:<9.2f} {stock:<8} {avail_str:<10}")
            input("\nPress Enter to continue...")

        elif choice == '2':
            # Add new item
            print("\n--- Add New Menu Item ---")
            name = input("Item name: ").strip()
            if not name:
                print("Name is required.")
                continue

            print("\nCategories: " + ", ".join(f"{i+1}. {c}" for i, c in enumerate(CATEGORIES)))
            try:
                cat_choice = int(input("Select category: "))
                category = CATEGORIES[cat_choice - 1] if 1 <= cat_choice <= len(CATEGORIES) else "Food"
            except (ValueError, IndexError):
                category = "Food"

            description = input("Description: ").strip()

            try:
                price = float(input("Price (£): "))
                stock = int(input("Initial stock: "))
            except ValueError:
                print("Invalid price or stock.")
                continue

            if add_menu_item(name, category, description, price, stock):
                print(f"\n Item '{name}' added successfully!")
            else:
                print("\n Failed to add item.")

        elif choice == '3':
            # Edit item
            try:
                item_id = int(input("Enter Item ID to edit: "))
            except ValueError:
                print("Invalid ID.")
                continue

            item = get_menu_item(item_id)
            if not item:
                print("Item not found.")
                continue

            item_id, name, cat, desc, price, available, stock = item
            print(f"\nEditing: {name}")
            print("(Press Enter to keep current value)")

            new_name = input(f"Name [{name}]: ").strip() or name

            print("\nCategories: " + ", ".join(f"{i+1}. {c}" for i, c in enumerate(CATEGORIES)))
            cat_input = input(f"Category [{cat}]: ").strip()
            try:
                new_cat = CATEGORIES[int(cat_input) - 1] if cat_input else cat
            except (ValueError, IndexError):
                new_cat = cat

            price_input = input(f"Price [{price:.2f}]: ").strip()
            new_price = float(price_input) if price_input else price

            stock_input = input(f"Stock [{stock}]: ").strip()
            new_stock = int(stock_input) if stock_input else stock

            avail_input = input(f"Available [{'Y' if available else 'N'}] (Y/N): ").strip().upper()
            new_available = avail_input == 'Y' if avail_input else bool(available)

            if update_menu_item(item_id, new_name, new_cat, new_price, new_stock, new_available):
                print("\n Item updated successfully!")
            else:
                print("\n Failed to update item.")

        elif choice == '4':
            # Delete item
            try:
                item_id = int(input("Enter Item ID to delete: "))
            except ValueError:
                print("Invalid ID.")
                continue

            item = get_menu_item(item_id)
            if not item:
                print("Item not found.")
                continue

            confirm = input(f"Delete '{item[1]}'? (y/n): ").strip().lower()
            if confirm == 'y':
                if delete_menu_item(item_id):
                    print(f"\n Item '{item[1]}' deleted!")
                else:
                    print("\n Failed to delete item.")

        elif choice == '5':
            break


def order_history_cli() -> None:
    """View order history."""
    while True:
        print("\n--- Order History ---")
        print("1. Today's Orders")
        print("2. This Week")
        print("3. This Month")
        print("4. All Orders")
        print("5. View Order Details")
        print("6. Back")

        choice = input("\nEnter choice: ").strip()

        filter_map = {'1': 'today', '2': 'week', '3': 'month', '4': 'all'}

        if choice in filter_map:
            orders = get_orders(filter_map[choice])
            if not orders:
                print("\nNo orders found.")
                continue

            print(f"\n{'=' * 100}")
            print(f"{'Order ID':<10} {'Date':<20} {'Customer':<20} {'Items':<8} {'Total':<12} {'Payment':<15} {'Status':<10}")
            print(f"{'=' * 100}")
            for order in orders:
                order_id, date, customer, items, total, payment, status = order
                print(f"{order_id:<10} {str(date)[:19]:<20} {customer[:19]:<20} {items:<8} £{total:<11.2f} {payment or 'N/A':<15} {status:<10}")
            print(f"\nTotal: {len(orders)} orders")
            input("\nPress Enter to continue...")

        elif choice == '5':
            try:
                order_id = int(input("Enter Order ID: "))
            except ValueError:
                print("Invalid ID.")
                continue

            items = get_order_items(order_id)
            if not items:
                print("Order not found or no items.")
                continue

            print(f"\n--- Order #{order_id} Details ---")
            print(f"{'Item':<30} {'Qty':<8} {'Price':<10} {'Subtotal':<10}")
            print("-" * 60)
            total = 0
            for item in items:
                name, qty, price, subtotal = item
                total += subtotal
                print(f"{name[:29]:<30} {qty:<8} £{price:<9.2f} £{subtotal:<9.2f}")
            print("-" * 60)
            print(f"{'Total:':<50} £{total:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '6':
            break


def inventory_management_cli() -> None:
    """Inventory management submenu."""
    while True:
        print("\n--- Inventory Management ---")
        print("1. View Current Stock")
        print("2. Add Stock")
        print("3. Remove Stock")
        print("4. View Transactions")
        print("5. Low Stock Alert")
        print("6. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            items = get_all_menu_items()
            print(f"\n{'=' * 70}")
            print(f"{'ID':<5} {'Item':<30} {'Category':<15} {'Stock':<10} {'Status':<12}")
            print(f"{'=' * 70}")
            for item in items:
                item_id, name, cat, desc, price, available, stock = item
                if stock == 0:
                    status = "OUT OF STOCK"
                elif stock < 10:
                    status = "LOW"
                elif stock < 20:
                    status = "MODERATE"
                else:
                    status = "GOOD"
                print(f"{item_id:<5} {name[:29]:<30} {cat:<15} {stock:<10} {status:<12}")
            input("\nPress Enter to continue...")

        elif choice == '2':
            try:
                item_id = int(input("Enter Item ID: "))
                item = get_menu_item(item_id)
                if not item:
                    print("Item not found.")
                    continue

                quantity = int(input(f"Quantity to add for '{item[1]}': "))
                if quantity < 1:
                    print("Invalid quantity.")
                    continue

                if update_stock(item_id, quantity, 'restock', 'Manual stock addition'):
                    print(f"\n Added {quantity} units to '{item[1]}'")
                else:
                    print("\n Failed to update stock.")
            except ValueError:
                print("Invalid input.")

        elif choice == '3':
            try:
                item_id = int(input("Enter Item ID: "))
                item = get_menu_item(item_id)
                if not item:
                    print("Item not found.")
                    continue

                current_stock = item[6]
                quantity = int(input(f"Quantity to remove from '{item[1]}' (current: {current_stock}): "))
                if quantity < 1 or quantity > current_stock:
                    print("Invalid quantity.")
                    continue

                if update_stock(item_id, -quantity, 'adjustment', 'Manual stock removal'):
                    print(f"\n Removed {quantity} units from '{item[1]}'")
                else:
                    print("\n Failed to update stock.")
            except ValueError:
                print("Invalid input.")

        elif choice == '4':
            transactions = get_inventory_transactions(50)
            if not transactions:
                print("\nNo transactions found.")
                continue

            print(f"\n{'=' * 90}")
            print(f"{'ID':<6} {'Item':<25} {'Change':<10} {'Type':<12} {'Date':<20} {'Notes':<15}")
            print(f"{'=' * 90}")
            for trans in transactions:
                trans_id, name, change, trans_type, date, notes = trans
                change_str = f"+{change}" if change > 0 else str(change)
                print(f"{trans_id:<6} {name[:24]:<25} {change_str:<10} {trans_type:<12} {str(date)[:19]:<20} {(notes or '')[:14]:<15}")
            input("\nPress Enter to continue...")

        elif choice == '5':
            items = get_low_stock_items(20)
            if not items:
                print("\nAll items have adequate stock.")
            else:
                print(f"\n{'=' * 50}")
                print("LOW STOCK ALERT")
                print(f"{'=' * 50}")
                for name, cat, stock in items:
                    status = "OUT OF STOCK" if stock == 0 else "LOW STOCK"
                    print(f"[{status}] {name} ({cat}): {stock} units")
            input("\nPress Enter to continue...")

        elif choice == '6':
            break


def reports_cli() -> None:
    """View reports."""
    while True:
        print("\n--- Cafe Reports ---")
        print("1. Daily Sales Report")
        print("2. Weekly Sales Report")
        print("3. Monthly Sales Report")
        print("4. Popular Items")
        print("5. Low Stock Alert")
        print("6. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            summary = get_sales_summary("day")
            print(f"\n{'=' * 50}")
            print("DAILY SALES REPORT")
            print(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
            print(f"{'=' * 50}")
            print(f"Total Orders: {summary['order_count']}")
            print(f"Total Sales: £{summary['total_sales']:.2f}")
            print("\nSales by Payment Method:")
            for method, count, amount in summary['payment_breakdown']:
                print(f"  {method}: {count} orders, £{amount:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '2':
            summary = get_sales_summary("week")
            print(f"\n{'=' * 50}")
            print("WEEKLY SALES REPORT")
            print(f"Week ending: {datetime.now().strftime('%Y-%m-%d')}")
            print(f"{'=' * 50}")
            print(f"Total Orders: {summary['order_count']}")
            print(f"Total Sales: £{summary['total_sales']:.2f}")
            if summary['order_count'] > 0:
                print(f"Average per order: £{summary['total_sales']/summary['order_count']:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '3':
            summary = get_sales_summary("month")
            print(f"\n{'=' * 50}")
            print("MONTHLY SALES REPORT")
            print(f"Month: {datetime.now().strftime('%B %Y')}")
            print(f"{'=' * 50}")
            print(f"Total Orders: {summary['order_count']}")
            print(f"Total Sales: £{summary['total_sales']:.2f}")
            input("\nPress Enter to continue...")

        elif choice == '4':
            items = get_popular_items(20)
            print(f"\n{'=' * 60}")
            print("TOP 20 MOST POPULAR ITEMS")
            print(f"{'=' * 60}")
            if items:
                for i, (name, qty, sales) in enumerate(items, 1):
                    print(f"{i:>2}. {name}: {qty} units sold, £{sales:.2f} revenue")
            else:
                print("No sales data available.")
            input("\nPress Enter to continue...")

        elif choice == '5':
            items = get_low_stock_items(20)
            print(f"\n{'=' * 50}")
            print("LOW STOCK ALERT")
            print(f"{'=' * 50}")
            if items:
                for name, cat, stock in items:
                    status = "OUT OF STOCK" if stock == 0 else "LOW STOCK"
                    print(f"[{status}] {name} ({cat}): {stock} units")
            else:
                print("All items have adequate stock levels.")
            input("\nPress Enter to continue...")

        elif choice == '6':
            break


# Export functions for use in cli_main.py
__all__ = [
    'display_cafe_menu',
    'init_cafe_db',
    'setup_cafe_permissions',
    'set_auth',
]
