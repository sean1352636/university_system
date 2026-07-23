#!/usr/bin/env python3
"""
Cafe System CLI for University Management System
A command-line interface for campus cafe point-of-sale operations.
Features: Menu management, order processing, inventory tracking, and reporting.

Integrated with the University Management System.
"""

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# University system imports
from education_system.post_18.university_system.infrastructure.database.db import DEFAULT_DB_PATH

# Import auth instance management
try:
    from education_system.post_18.university_system.infrastructure.auth import get_current_user, set_auth_instance
    from education_system.post_18.university_system.infrastructure.shared_context import get_auth, set_auth as set_shared_auth
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None
    get_auth = lambda: None
    set_shared_auth = lambda x: None

# Import finance integration for student payments
try:
    from education_system.post_18.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False

# Import activity logger for audit trail
try:
    from education_system.post_18.university_system.modules.shared.utils.simple_activity_logger import (
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
from education_system.post_18.university_system.core.i18n import (
    get_text,
    get_current_language,
)
from education_system.post_18.university_system.modules.shared.utils.language_selector import (
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

        # Unified products table (cafe items have source_type='cafe')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL DEFAULT 'cafe',
                source_product_id INTEGER,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                is_alcoholic INTEGER DEFAULT 0,
                is_available INTEGER DEFAULT 1,
                stock_quantity INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Unified orders table (cafe orders have source_type='cafe')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL DEFAULT 'cafe',
                source_order_id INTEGER,
                student_id TEXT,
                customer_name TEXT,
                order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_amount REAL NOT NULL,
                payment_method TEXT,
                age_verified INTEGER DEFAULT 0,
                order_status TEXT DEFAULT 'pending',
                notes TEXT
            )
        ''')

        # Unified order_items table (cafe order items have source_type='cafe')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL DEFAULT 'cafe',
                source_order_id INTEGER,
                product_id INTEGER,
                item_name TEXT,
                quantity INTEGER,
                unit_price REAL,
                subtotal REAL,
                FOREIGN KEY (source_order_id) REFERENCES orders(order_id),
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            )
        ''')

        # NOTE: cafe inventory transactions now use the unified 'transactions' table
        # with source_type = 'cafe_inventory'

        # Suppliers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cafe_suppliers (
                supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                contact_person TEXT,
                email TEXT,
                phone TEXT,
                address TEXT,
                payment_terms TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Supplier-product link table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cafe_supplier_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                cost_per_unit REAL,
                notes TEXT,
                FOREIGN KEY (supplier_id) REFERENCES cafe_suppliers(supplier_id),
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            )
        ''')

        # Reservations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cafe_reservations (
                reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                student_id TEXT,
                reservation_date DATE NOT NULL,
                reservation_time TIME NOT NULL,
                party_size INTEGER NOT NULL,
                status TEXT DEFAULT 'confirmed',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Loyalty points table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cafe_loyalty (
                loyalty_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL UNIQUE,
                customer_name TEXT NOT NULL,
                points INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Loyalty points log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cafe_loyalty_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                points_change INTEGER NOT NULL,
                transaction_type TEXT NOT NULL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES cafe_loyalty(student_id)
            )
        ''')

        # Staff scheduling table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cafe_staff_schedules (
                schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_name TEXT NOT NULL,
                position TEXT NOT NULL DEFAULT 'barista',
                day_of_week TEXT NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()

        # Insert sample menu items if table is empty
        cursor.execute("SELECT COUNT(*) FROM products WHERE source_type = 'cafe'")
        if cursor.fetchone()[0] == 0:
            sample_items = [
                ('cafe', 'Espresso', 'Hot Drinks', 'Classic Italian espresso', 2.50, 1, 100),
                ('cafe', 'Cappuccino', 'Hot Drinks', 'Espresso with steamed milk and foam', 3.50, 1, 100),
                ('cafe', 'Latte', 'Hot Drinks', 'Espresso with steamed milk', 3.75, 1, 100),
                ('cafe', 'Americano', 'Hot Drinks', 'Espresso with hot water', 2.75, 1, 100),
                ('cafe', 'Hot Chocolate', 'Hot Drinks', 'Rich hot chocolate', 3.25, 1, 100),
                ('cafe', 'Tea', 'Hot Drinks', 'Selection of teas', 2.25, 1, 100),
                ('cafe', 'Iced Coffee', 'Cold Drinks', 'Chilled coffee over ice', 3.50, 1, 100),
                ('cafe', 'Iced Tea', 'Cold Drinks', 'Refreshing iced tea', 2.75, 1, 100),
                ('cafe', 'Smoothie', 'Cold Drinks', 'Fruit smoothie', 4.50, 1, 50),
                ('cafe', 'Fresh Juice', 'Cold Drinks', 'Freshly squeezed juice', 3.95, 1, 50),
                ('cafe', 'Croissant', 'Pastries', 'Buttery French croissant', 2.50, 1, 30),
                ('cafe', 'Muffin', 'Pastries', 'Blueberry or chocolate chip', 2.75, 1, 40),
                ('cafe', 'Danish', 'Pastries', 'Sweet pastry', 3.00, 1, 30),
                ('cafe', 'Cookie', 'Pastries', 'Freshly baked cookie', 1.50, 1, 60),
                ('cafe', 'Brownie', 'Pastries', 'Chocolate brownie', 2.95, 1, 40),
                ('cafe', 'Sandwich', 'Food', 'Various sandwich options', 5.50, 1, 25),
                ('cafe', 'Panini', 'Food', 'Grilled panini', 6.50, 1, 20),
                ('cafe', 'Salad', 'Food', 'Fresh garden salad', 5.95, 1, 15),
                ('cafe', 'Soup', 'Food', 'Soup of the day', 4.50, 1, 20),
                ('cafe', 'Bagel', 'Food', 'Toasted bagel with spreads', 3.25, 1, 35)
            ]
            cursor.executemany(
                "INSERT INTO products (source_type, name, category, description, price, is_available, stock_quantity) VALUES (?, ?, ?, ?, ?, ?, ?)",
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
    query = "SELECT product_id, name, category, description, price, is_available, stock_quantity FROM products WHERE source_type = 'cafe'"
    params = []

    conditions = []
    if category and category != "All":
        conditions.append("category = ?")
        params.append(category)
    if available_only:
        conditions.append("is_available = 1")

    if conditions:
        query += " AND " + " AND ".join(conditions)

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
        "SELECT product_id, name, category, description, price, is_available, stock_quantity FROM products WHERE source_type = 'cafe' AND product_id = ?",
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
            "INSERT INTO products (source_type, name, category, description, price, is_available, stock_quantity) VALUES ('cafe', ?, ?, ?, ?, 1, ?)",
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
            "UPDATE products SET name = ?, category = ?, price = ?, stock_quantity = ?, is_available = ? WHERE product_id = ? AND source_type = 'cafe'",
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
        cursor.execute("SELECT name FROM products WHERE source_type = 'cafe' AND product_id = ?", (item_id,))
        row = cursor.fetchone()
        item_name = row[0] if row else "Unknown"

        cursor.execute("DELETE FROM products WHERE product_id = ? AND source_type = 'cafe'", (item_id,))
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
            "INSERT INTO orders (source_type, student_id, customer_name, total_amount, payment_method, order_status) VALUES ('cafe', ?, ?, ?, ?, 'completed')",
            (student_id or None, customer_name, total, payment_method)
        )
        order_id = cursor.lastrowid

        # Insert order items and update inventory
        for item in items:
            cursor.execute(
                "INSERT INTO order_items (source_type, source_order_id, product_id, item_name, quantity, unit_price, subtotal) VALUES ('cafe', ?, ?, ?, ?, ?, ?)",
                (order_id, item['item_id'], item['name'], item['quantity'], item['price'], item['subtotal'])
            )

            # Update inventory
            cursor.execute(
                "UPDATE products SET stock_quantity = stock_quantity - ? WHERE product_id = ? AND source_type = 'cafe'",
                (item['quantity'], item['item_id'])
            )

            # Log inventory transaction
            cursor.execute(
                "INSERT INTO transactions (source_type, reference_id, reference_type, quantity_change, transaction_type, notes) VALUES ('cafe_inventory', ?, 'item', ?, 'sale', ?)",
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

    source_filter = "WHERE o.source_type = 'cafe'"
    if filter_type == "today":
        source_filter = "WHERE o.source_type = 'cafe' AND DATE(o.order_date) = DATE('now')"
    elif filter_type == "week":
        source_filter = "WHERE o.source_type = 'cafe' AND DATE(o.order_date) >= DATE('now', '-7 days')"
    elif filter_type == "month":
        source_filter = "WHERE o.source_type = 'cafe' AND DATE(o.order_date) >= DATE('now', 'start of month')"

    query = f'''
        SELECT
            o.order_id,
            o.order_date,
            COALESCE(o.customer_name, o.student_id, 'Walk-in'),
            COUNT(oi.item_id),
            o.total_amount,
            o.payment_method,
            o.order_status
        FROM orders o
        LEFT JOIN order_items oi ON o.order_id = oi.source_order_id AND oi.source_type = 'cafe'
        {source_filter}
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
        "SELECT item_name, quantity, unit_price, subtotal FROM order_items WHERE source_type = 'cafe' AND source_order_id = ?",
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
            "UPDATE products SET stock_quantity = stock_quantity + ? WHERE product_id = ? AND source_type = 'cafe'",
            (quantity_change, item_id)
        )
        cursor.execute(
            "INSERT INTO transactions (source_type, reference_id, reference_type, quantity_change, transaction_type, notes) VALUES ('cafe_inventory', ?, 'item', ?, ?, ?)",
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
        SELECT t.transaction_id, m.name, t.quantity_change, t.transaction_type, t.created_at, t.notes
        FROM transactions t
        JOIN products m ON t.reference_id = m.product_id AND m.source_type = 'cafe' AND t.reference_type = 'item'
        WHERE t.source_type = 'cafe_inventory'
        ORDER BY t.created_at DESC
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

    _PERIOD_FILTERS = {
        "day": "DATE(order_date) = DATE('now')",
        "week": "DATE(order_date) >= DATE('now', '-7 days')",
        "month": "DATE(order_date) >= DATE('now', 'start of month')",
    }
    date_filter = _PERIOD_FILTERS.get(period, "1=1")

    cursor.execute(f'''
        SELECT COUNT(*), COALESCE(SUM(total_amount), 0)
        FROM orders
        WHERE source_type = 'cafe' AND {date_filter}
    ''')
    result = cursor.fetchone()
    order_count = result[0] or 0
    total_sales = result[1] or 0.0

    cursor.execute(f'''
        SELECT payment_method, COUNT(*), COALESCE(SUM(total_amount), 0)
        FROM orders
        WHERE source_type = 'cafe' AND {date_filter}
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
        FROM order_items
        WHERE source_type = 'cafe'
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
        FROM products
        WHERE source_type = 'cafe' AND stock_quantity < ?
        ORDER BY stock_quantity ASC
    ''', (threshold,))
    results = cursor.fetchall()
    conn.close()
    return results

# ============================================================================
# Supplier Database Operations
# ============================================================================

def add_supplier(name: str, contact_person: str, email: str, phone: str, address: str, payment_terms: str) -> Optional[int]:
    """Add a new supplier. Returns supplier_id or None."""
    try:
        conn = get_db_connection()
        if not conn:
            return None
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO cafe_suppliers (name, contact_person, email, phone, address, payment_terms) VALUES (?, ?, ?, ?, ?, ?)",
            (name, contact_person or None, email or None, phone or None, address or None, payment_terms or None)
        )
        conn.commit()
        supplier_id = cursor.lastrowid
        conn.close()
        if ACTIVITY_LOGGER_AVAILABLE:
            log_create('cafe_supplier', supplier_name=name)
        return supplier_id
    except sqlite3.Error as e:
        logger.error(f"Error adding supplier: {e}")
        return None

def get_all_suppliers() -> List[Tuple]:
    """Get all suppliers."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor()
    cursor.execute("SELECT supplier_id, name, contact_person, email, phone, address, payment_terms FROM cafe_suppliers ORDER BY name")
    results = cursor.fetchall()
    conn.close()
    return results

def get_supplier(supplier_id: int) -> Optional[Tuple]:
    """Get a single supplier by ID."""
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()
    cursor.execute("SELECT supplier_id, name, contact_person, email, phone, address, payment_terms FROM cafe_suppliers WHERE supplier_id = ?", (supplier_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def update_supplier(supplier_id: int, name: str, contact_person: str, email: str, phone: str, address: str, payment_terms: str) -> bool:
    """Update a supplier."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE cafe_suppliers SET name = ?, contact_person = ?, email = ?, phone = ?, address = ?, payment_terms = ? WHERE supplier_id = ?",
            (name, contact_person, email, phone, address, payment_terms, supplier_id)
        )
        conn.commit()
        conn.close()
        if ACTIVITY_LOGGER_AVAILABLE:
            log_update('cafe_supplier', supplier_id=supplier_id)
        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating supplier: {e}")
        return False

def delete_supplier(supplier_id: int) -> bool:
    """Delete a supplier."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cafe_supplier_products WHERE supplier_id = ?", (supplier_id,))
        cursor.execute("DELETE FROM cafe_suppliers WHERE supplier_id = ?", (supplier_id,))
        conn.commit()
        conn.close()
        if ACTIVITY_LOGGER_AVAILABLE:
            log_delete('cafe_supplier', supplier_id=supplier_id)
        return True
    except sqlite3.Error as e:
        logger.error(f"Error deleting supplier: {e}")
        return False

def link_supplier_to_product(supplier_id: int, product_id: int, cost_per_unit: float = None, notes: str = "") -> bool:
    """Link a supplier to a product/inventory item."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO cafe_supplier_products (supplier_id, product_id, cost_per_unit, notes) VALUES (?, ?, ?, ?)",
            (supplier_id, product_id, cost_per_unit, notes)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error linking supplier to product: {e}")
        return False

def get_supplier_products(supplier_id: int) -> List[Tuple]:
    """Get products linked to a supplier."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.product_id, p.name, p.category, sp.cost_per_unit, sp.notes
        FROM cafe_supplier_products sp
        JOIN products p ON sp.product_id = p.product_id AND p.source_type = 'cafe'
        WHERE sp.supplier_id = ?
        ORDER BY p.name
    ''', (supplier_id,))
    results = cursor.fetchall()
    conn.close()
    return results

# ============================================================================
# Reservation Database Operations
# ============================================================================

def create_reservation(customer_name: str, student_id: str, reservation_date: str, reservation_time: str, party_size: int, notes: str = "") -> Optional[int]:
    """Create a new reservation. Returns reservation_id or None."""
    try:
        conn = get_db_connection()
        if not conn:
            return None
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO cafe_reservations (customer_name, student_id, reservation_date, reservation_time, party_size, status, notes) VALUES (?, ?, ?, ?, ?, 'confirmed', ?)",
            (customer_name, student_id or None, reservation_date, reservation_time, party_size, notes or None)
        )
        conn.commit()
        reservation_id = cursor.lastrowid
        conn.close()
        if ACTIVITY_LOGGER_AVAILABLE:
            log_create('cafe_reservation', customer=customer_name, date=reservation_date)
        return reservation_id
    except sqlite3.Error as e:
        logger.error(f"Error creating reservation: {e}")
        return None

def get_all_reservations(filter_type: str = "all") -> List[Tuple]:
    """Get reservations with optional date filter."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor()

    date_filter = ""
    if filter_type == "today":
        date_filter = "AND reservation_date = DATE('now')"
    elif filter_type == "upcoming":
        date_filter = "AND reservation_date >= DATE('now')"
    elif filter_type == "past":
        date_filter = "AND reservation_date < DATE('now')"

    cursor.execute(f'''
        SELECT reservation_id, customer_name, student_id, reservation_date, reservation_time, party_size, status, notes
        FROM cafe_reservations
        WHERE 1=1 {date_filter}
        ORDER BY reservation_date DESC, reservation_time DESC
    ''')
    results = cursor.fetchall()
    conn.close()
    return results

def get_reservation(reservation_id: int) -> Optional[Tuple]:
    """Get a single reservation by ID."""
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()
    cursor.execute(
        "SELECT reservation_id, customer_name, student_id, reservation_date, reservation_time, party_size, status, notes FROM cafe_reservations WHERE reservation_id = ?",
        (reservation_id,)
    )
    result = cursor.fetchone()
    conn.close()
    return result

def update_reservation_details(reservation_id: int, customer_name: str, reservation_date: str, reservation_time: str, party_size: int, notes: str) -> bool:
    """Update a reservation."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE cafe_reservations SET customer_name = ?, reservation_date = ?, reservation_time = ?, party_size = ?, notes = ? WHERE reservation_id = ?",
            (customer_name, reservation_date, reservation_time, party_size, notes, reservation_id)
        )
        conn.commit()
        conn.close()
        if ACTIVITY_LOGGER_AVAILABLE:
            log_update('cafe_reservation', reservation_id=reservation_id)
        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating reservation: {e}")
        return False

def cancel_reservation(reservation_id: int) -> bool:
    """Cancel a reservation by setting status to cancelled."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE cafe_reservations SET status = 'cancelled' WHERE reservation_id = ?",
            (reservation_id,)
        )
        conn.commit()
        conn.close()
        if ACTIVITY_LOGGER_AVAILABLE:
            log_update('cafe_reservation', reservation_id=reservation_id, action='cancelled')
        return True
    except sqlite3.Error as e:
        logger.error(f"Error cancelling reservation: {e}")
        return False

# ============================================================================
# Loyalty Points Database Operations
# ============================================================================

def get_or_create_loyalty_account(student_id: str, customer_name: str) -> Optional[Tuple]:
    """Get or create a loyalty account. Returns (loyalty_id, student_id, customer_name, points)."""
    try:
        conn = get_db_connection()
        if not conn:
            return None
        cursor = conn.cursor()
        cursor.execute("SELECT loyalty_id, student_id, customer_name, points FROM cafe_loyalty WHERE student_id = ?", (student_id,))
        result = cursor.fetchone()
        if result:
            conn.close()
            return result
        # Create new account
        cursor.execute(
            "INSERT INTO cafe_loyalty (student_id, customer_name, points) VALUES (?, ?, 0)",
            (student_id, customer_name)
        )
        conn.commit()
        loyalty_id = cursor.lastrowid
        conn.close()
        return (loyalty_id, student_id, customer_name, 0)
    except sqlite3.Error as e:
        logger.error(f"Error with loyalty account: {e}")
        return None

def get_loyalty_account(student_id: str) -> Optional[Tuple]:
    """Get loyalty account by student ID."""
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()
    cursor.execute("SELECT loyalty_id, student_id, customer_name, points FROM cafe_loyalty WHERE student_id = ?", (student_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def get_all_loyalty_accounts() -> List[Tuple]:
    """Get all loyalty accounts."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor()
    cursor.execute("SELECT loyalty_id, student_id, customer_name, points FROM cafe_loyalty ORDER BY points DESC")
    results = cursor.fetchall()
    conn.close()
    return results

def add_loyalty_points(student_id: str, points: int, reason: str = "") -> bool:
    """Add loyalty points to an account."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        cursor.execute("UPDATE cafe_loyalty SET points = points + ? WHERE student_id = ?", (points, student_id))
        cursor.execute(
            "INSERT INTO cafe_loyalty_log (student_id, points_change, transaction_type, reason) VALUES (?, ?, 'added', ?)",
            (student_id, points, reason or 'Manual addition')
        )
        conn.commit()
        conn.close()
        if ACTIVITY_LOGGER_AVAILABLE:
            log_activity('loyalty', 'cafe_loyalty_add', student_id=student_id, points=points)
        return True
    except sqlite3.Error as e:
        logger.error(f"Error adding loyalty points: {e}")
        return False

def redeem_loyalty_points(student_id: str, points: int, reason: str = "") -> bool:
    """Redeem loyalty points from an account."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        # Check sufficient points
        cursor.execute("SELECT points FROM cafe_loyalty WHERE student_id = ?", (student_id,))
        row = cursor.fetchone()
        if not row or row[0] < points:
            conn.close()
            return False
        cursor.execute("UPDATE cafe_loyalty SET points = points - ? WHERE student_id = ?", (points, student_id))
        cursor.execute(
            "INSERT INTO cafe_loyalty_log (student_id, points_change, transaction_type, reason) VALUES (?, ?, 'redeemed', ?)",
            (student_id, -points, reason or 'Manual redemption')
        )
        conn.commit()
        conn.close()
        if ACTIVITY_LOGGER_AVAILABLE:
            log_activity('loyalty', 'cafe_loyalty_redeem', student_id=student_id, points=points)
        return True
    except sqlite3.Error as e:
        logger.error(f"Error redeeming loyalty points: {e}")
        return False

def get_loyalty_log(student_id: str, limit: int = 50) -> List[Tuple]:
    """Get loyalty points transaction log for a student."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor()
    cursor.execute(
        "SELECT log_id, points_change, transaction_type, reason, created_at FROM cafe_loyalty_log WHERE student_id = ? ORDER BY created_at DESC LIMIT ?",
        (student_id, limit)
    )
    results = cursor.fetchall()
    conn.close()
    return results

# ============================================================================
# Staff Schedule Database Operations
# ============================================================================

def add_staff_schedule(staff_name: str, position: str, day_of_week: str, start_time: str, end_time: str, notes: str = "") -> bool:
    """Add a staff schedule entry."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO cafe_staff_schedules (staff_name, position, day_of_week, start_time, end_time, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (staff_name, position, day_of_week, start_time, end_time, notes or None)
        )
        conn.commit()
        conn.close()
        if ACTIVITY_LOGGER_AVAILABLE:
            log_create('cafe_staff_schedule', staff_name=staff_name, day=day_of_week)
        return True
    except sqlite3.Error as e:
        logger.error(f"Error adding staff schedule: {e}")
        return False

def get_all_staff_schedules() -> List[Tuple]:
    """Get all staff schedules."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor()
    cursor.execute('''
        SELECT schedule_id, staff_name, position, day_of_week, start_time, end_time, notes
        FROM cafe_staff_schedules
        ORDER BY
            CASE day_of_week
                WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6
                WHEN 'Sunday' THEN 7 ELSE 8
            END,
            start_time
    ''')
    results = cursor.fetchall()
    conn.close()
    return results

def get_staff_schedule_by_name(staff_name: str) -> List[Tuple]:
    """Get schedules for a specific staff member."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor()
    cursor.execute(
        "SELECT schedule_id, staff_name, position, day_of_week, start_time, end_time, notes FROM cafe_staff_schedules WHERE LOWER(staff_name) LIKE ? ORDER BY CASE day_of_week WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6 WHEN 'Sunday' THEN 7 ELSE 8 END",
        (f"%{staff_name.lower()}%",)
    )
    results = cursor.fetchall()
    conn.close()
    return results

def update_staff_schedule_entry(schedule_id: int, day_of_week: str, start_time: str, end_time: str, notes: str) -> bool:
    """Update a staff schedule entry."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE cafe_staff_schedules SET day_of_week = ?, start_time = ?, end_time = ?, notes = ? WHERE schedule_id = ?",
            (day_of_week, start_time, end_time, notes, schedule_id)
        )
        conn.commit()
        conn.close()
        if ACTIVITY_LOGGER_AVAILABLE:
            log_update('cafe_staff_schedule', schedule_id=schedule_id)
        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating staff schedule: {e}")
        return False

def delete_staff_schedule_entry(schedule_id: int) -> bool:
    """Delete a staff schedule entry."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cafe_staff_schedules WHERE schedule_id = ?", (schedule_id,))
        conn.commit()
        conn.close()
        if ACTIVITY_LOGGER_AVAILABLE:
            log_delete('cafe_staff_schedule', schedule_id=schedule_id)
        return True
    except sqlite3.Error as e:
        logger.error(f"Error deleting staff schedule: {e}")
        return False

def get_unique_staff_names() -> List[str]:
    """Get unique staff names from schedules."""
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT staff_name FROM cafe_staff_schedules ORDER BY staff_name")
    results = [row[0] for row in cursor.fetchall()]
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
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products'")
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

        # Supplier management
        if auth.check_permission('manage_cafe_inventory') or auth.check_permission('manage_cafe'):
            print(f"{option_num}. {get_text('cafe.menu.suppliers', default='Supplier Management')}")
            options.append('suppliers')
            option_num += 1

        # Reservations
        if auth.check_permission('process_cafe_order') or auth.check_permission('manage_cafe'):
            print(f"{option_num}. {get_text('cafe.menu.reservations', default='Reservations')}")
            options.append('reservations')
            option_num += 1

        # Loyalty points
        if auth.check_permission('process_cafe_order') or auth.check_permission('manage_cafe'):
            print(f"{option_num}. {get_text('cafe.menu.loyalty', default='Loyalty Points')}")
            options.append('loyalty')
            option_num += 1

        # Staff scheduling
        if auth.check_permission('manage_cafe') or auth.check_permission('manage_cafe_inventory'):
            print(f"{option_num}. {get_text('cafe.menu.scheduling', default='Staff Scheduling')}")
            options.append('scheduling')
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
                elif selected == 'suppliers':
                    supplier_management_cli()
                elif selected == 'reservations':
                    reservations_cli()
                elif selected == 'loyalty':
                    loyalty_points_cli()
                elif selected == 'scheduling':
                    staff_scheduling_cli()
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

            print("\n--- Payment ---")
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

def supplier_management_cli() -> None:
    """Supplier management submenu."""
    while True:
        print("\n--- Supplier Management ---")
        print("1. View All Suppliers")
        print("2. Add New Supplier")
        print("3. View Supplier Details")
        print("4. Update Supplier")
        print("5. Delete Supplier")
        print("6. Link Supplier to Menu Item")
        print("7. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            suppliers = get_all_suppliers()
            if not suppliers:
                print("\nNo suppliers found.")
                input("\nPress Enter to continue...")
                continue

            print(f"\n{'=' * 90}")
            print(f"{'ID':<5} {'Name':<25} {'Contact':<20} {'Email':<25} {'Phone':<15}")
            print(f"{'=' * 90}")
            for s in suppliers:
                sid, name, contact, email, phone, addr, terms = s
                print(f"{sid:<5} {(name or '')[:24]:<25} {(contact or 'N/A')[:19]:<20} {(email or 'N/A')[:24]:<25} {(phone or 'N/A')[:14]:<15}")
            print(f"\nTotal: {len(suppliers)} suppliers")
            input("\nPress Enter to continue...")

        elif choice == '2':
            print("\n--- Add New Supplier ---")
            name = input("Supplier name: ").strip()
            if not name:
                print("Name is required.")
                continue
            contact_person = input("Contact person (optional): ").strip()
            email = input("Email (optional): ").strip()
            phone = input("Phone (optional): ").strip()
            address = input("Address (optional): ").strip()
            payment_terms = input("Payment terms (e.g. Net 30, COD, optional): ").strip()

            supplier_id = add_supplier(name, contact_person, email, phone, address, payment_terms)
            if supplier_id:
                print(f"\n Supplier '{name}' added with ID: {supplier_id}")
            else:
                print("\n Failed to add supplier.")

        elif choice == '3':
            try:
                supplier_id = int(input("Enter Supplier ID: "))
            except ValueError:
                print("Invalid ID.")
                continue

            supplier = get_supplier(supplier_id)
            if not supplier:
                print("Supplier not found.")
                continue

            sid, name, contact, email, phone, address, terms = supplier
            print(f"\n{'=' * 50}")
            print(f"SUPPLIER DETAILS (ID: {sid})")
            print(f"{'=' * 50}")
            print(f"Name:           {name}")
            print(f"Contact Person: {contact or 'N/A'}")
            print(f"Email:          {email or 'N/A'}")
            print(f"Phone:          {phone or 'N/A'}")
            print(f"Address:        {address or 'N/A'}")
            print(f"Payment Terms:  {terms or 'N/A'}")

            # Show linked products
            products = get_supplier_products(supplier_id)
            if products:
                print("\nLinked Menu Items:")
                print(f"  {'ID':<5} {'Item':<25} {'Category':<15} {'Cost/Unit':<10}")
                print(f"  {'-' * 55}")
                for pid, pname, pcat, cost, pnotes in products:
                    cost_str = f"£{cost:.2f}" if cost else "N/A"
                    print(f"  {pid:<5} {pname[:24]:<25} {pcat:<15} {cost_str:<10}")
            else:
                print("\nNo menu items linked to this supplier.")
            input("\nPress Enter to continue...")

        elif choice == '4':
            try:
                supplier_id = int(input("Enter Supplier ID to update: "))
            except ValueError:
                print("Invalid ID.")
                continue

            supplier = get_supplier(supplier_id)
            if not supplier:
                print("Supplier not found.")
                continue

            sid, name, contact, email, phone, address, terms = supplier
            print(f"\nUpdating: {name}")
            print("(Press Enter to keep current value)")

            new_name = input(f"Name [{name}]: ").strip() or name
            new_contact = input(f"Contact [{contact or ''}]: ").strip() or contact
            new_email = input(f"Email [{email or ''}]: ").strip() or email
            new_phone = input(f"Phone [{phone or ''}]: ").strip() or phone
            new_address = input(f"Address [{address or ''}]: ").strip() or address
            new_terms = input(f"Payment Terms [{terms or ''}]: ").strip() or terms

            if update_supplier(supplier_id, new_name, new_contact, new_email, new_phone, new_address, new_terms):
                print(f"\n Supplier '{new_name}' updated!")
            else:
                print("\n Failed to update supplier.")

        elif choice == '5':
            try:
                supplier_id = int(input("Enter Supplier ID to delete: "))
            except ValueError:
                print("Invalid ID.")
                continue

            supplier = get_supplier(supplier_id)
            if not supplier:
                print("Supplier not found.")
                continue

            confirm = input(f"Delete supplier '{supplier[1]}'? This also removes product links. (y/n): ").strip().lower()
            if confirm == 'y':
                if delete_supplier(supplier_id):
                    print(f"\n Supplier '{supplier[1]}' deleted!")
                else:
                    print("\n Failed to delete supplier.")

        elif choice == '6':
            # Link supplier to menu item
            try:
                supplier_id = int(input("Enter Supplier ID: "))
            except ValueError:
                print("Invalid ID.")
                continue

            supplier = get_supplier(supplier_id)
            if not supplier:
                print("Supplier not found.")
                continue

            items = get_all_menu_items()
            if not items:
                print("No menu items available.")
                continue

            print(f"\n{'ID':<5} {'Item':<25} {'Category':<15}")
            print("-" * 45)
            for item in items:
                item_id, name, cat, desc, price, available, stock = item
                print(f"{item_id:<5} {name[:24]:<25} {cat:<15}")

            try:
                product_id = int(input("\nEnter Item ID to link: "))
            except ValueError:
                print("Invalid ID.")
                continue

            cost_input = input("Cost per unit from this supplier (optional, press Enter to skip): ").strip()
            cost = float(cost_input) if cost_input else None
            notes = input("Notes (optional): ").strip()

            if link_supplier_to_product(supplier_id, product_id, cost, notes):
                print(f"\n Supplier '{supplier[1]}' linked to item #{product_id}!")
            else:
                print("\n Failed to link supplier to item.")

        elif choice == '7':
            break


def reservations_cli() -> None:
    """Reservations management submenu."""
    while True:
        print("\n--- Reservations ---")
        print("1. Create Reservation")
        print("2. View Today's Reservations")
        print("3. View Upcoming Reservations")
        print("4. View All Reservations")
        print("5. View Reservation Details")
        print("6. Update Reservation")
        print("7. Cancel Reservation")
        print("8. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            print("\n--- Create New Reservation ---")
            customer_name = input("Customer name: ").strip()
            if not customer_name:
                print("Customer name is required.")
                continue
            student_id = input("Student ID (optional, press Enter to skip): ").strip()

            res_date = input("Reservation date (YYYY-MM-DD): ").strip()
            try:
                parsed_date = datetime.strptime(res_date, "%Y-%m-%d").date()
                if parsed_date < datetime.now().date():
                    print("Date cannot be in the past.")
                    continue
            except ValueError:
                print("Invalid date format. Use YYYY-MM-DD.")
                continue

            res_time = input("Reservation time (HH:MM, 24-hour): ").strip()
            try:
                datetime.strptime(res_time, "%H:%M")
            except ValueError:
                print("Invalid time format. Use HH:MM.")
                continue

            try:
                party_size = int(input("Party size: "))
                if party_size < 1:
                    print("Party size must be at least 1.")
                    continue
            except ValueError:
                print("Invalid party size.")
                continue

            notes = input("Notes (optional): ").strip()

            reservation_id = create_reservation(customer_name, student_id, res_date, res_time, party_size, notes)
            if reservation_id:
                print(f"\n Reservation #{reservation_id} created!")
                print(f"  {customer_name} | {res_date} at {res_time} | Party of {party_size}")
            else:
                print("\n Failed to create reservation.")

        elif choice in ('2', '3', '4'):
            filter_map = {'2': 'today', '3': 'upcoming', '4': 'all'}
            label_map = {'2': "Today's", '3': 'Upcoming', '4': 'All'}
            reservations = get_all_reservations(filter_map[choice])
            if not reservations:
                print(f"\nNo {label_map[choice].lower()} reservations found.")
                input("\nPress Enter to continue...")
                continue

            print(f"\n{'=' * 100}")
            print(f"{'ID':<6} {'Customer':<20} {'Date':<12} {'Time':<8} {'Party':<7} {'Status':<12} {'Notes':<20}")
            print(f"{'=' * 100}")
            for res in reservations:
                rid, cname, sid, rdate, rtime, psize, status, rnotes = res
                print(f"{rid:<6} {cname[:19]:<20} {rdate:<12} {rtime:<8} {psize:<7} {status:<12} {(rnotes or '')[:19]:<20}")
            print(f"\nTotal: {len(reservations)} reservations")
            input("\nPress Enter to continue...")

        elif choice == '5':
            try:
                reservation_id = int(input("Enter Reservation ID: "))
            except ValueError:
                print("Invalid ID.")
                continue

            res = get_reservation(reservation_id)
            if not res:
                print("Reservation not found.")
                continue

            rid, cname, sid, rdate, rtime, psize, status, rnotes = res
            print(f"\n{'=' * 50}")
            print(f"RESERVATION #{rid}")
            print(f"{'=' * 50}")
            print(f"Customer:   {cname}")
            print(f"Student ID: {sid or 'N/A'}")
            print(f"Date:       {rdate}")
            print(f"Time:       {rtime}")
            print(f"Party Size: {psize}")
            print(f"Status:     {status}")
            print(f"Notes:      {rnotes or 'N/A'}")
            input("\nPress Enter to continue...")

        elif choice == '6':
            try:
                reservation_id = int(input("Enter Reservation ID to update: "))
            except ValueError:
                print("Invalid ID.")
                continue

            res = get_reservation(reservation_id)
            if not res:
                print("Reservation not found.")
                continue

            if res[6] == 'cancelled':
                print("Cannot update a cancelled reservation.")
                continue

            rid, cname, sid, rdate, rtime, psize, status, rnotes = res
            print(f"\nUpdating Reservation #{rid}")
            print("(Press Enter to keep current value)")

            new_name = input(f"Customer [{cname}]: ").strip() or cname

            new_date = input(f"Date [{rdate}] (YYYY-MM-DD): ").strip()
            if new_date:
                try:
                    datetime.strptime(new_date, "%Y-%m-%d")
                except ValueError:
                    print("Invalid date. Keeping current.")
                    new_date = rdate
            else:
                new_date = rdate

            new_time = input(f"Time [{rtime}] (HH:MM): ").strip()
            if new_time:
                try:
                    datetime.strptime(new_time, "%H:%M")
                except ValueError:
                    print("Invalid time. Keeping current.")
                    new_time = rtime
            else:
                new_time = rtime

            size_input = input(f"Party size [{psize}]: ").strip()
            try:
                new_size = int(size_input) if size_input else psize
            except ValueError:
                new_size = psize

            new_notes = input(f"Notes [{rnotes or ''}]: ").strip()
            if not new_notes:
                new_notes = rnotes or ""

            if update_reservation_details(reservation_id, new_name, new_date, new_time, new_size, new_notes):
                print(f"\n Reservation #{reservation_id} updated!")
            else:
                print("\n Failed to update reservation.")

        elif choice == '7':
            try:
                reservation_id = int(input("Enter Reservation ID to cancel: "))
            except ValueError:
                print("Invalid ID.")
                continue

            res = get_reservation(reservation_id)
            if not res:
                print("Reservation not found.")
                continue

            if res[6] == 'cancelled':
                print("Reservation is already cancelled.")
                continue

            confirm = input(f"Cancel reservation #{reservation_id} for '{res[1]}'? (y/n): ").strip().lower()
            if confirm == 'y':
                if cancel_reservation(reservation_id):
                    print(f"\n Reservation #{reservation_id} cancelled.")
                else:
                    print("\n Failed to cancel reservation.")

        elif choice == '8':
            break


def loyalty_points_cli() -> None:
    """Loyalty points management submenu."""
    while True:
        print("\n--- Loyalty Points ---")
        print("1. View All Loyalty Accounts")
        print("2. Look Up Account")
        print("3. Register New Account")
        print("4. Add Points")
        print("5. Redeem Points")
        print("6. View Points History")
        print("7. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            accounts = get_all_loyalty_accounts()
            if not accounts:
                print("\nNo loyalty accounts found.")
                input("\nPress Enter to continue...")
                continue

            print(f"\n{'=' * 65}")
            print(f"{'ID':<6} {'Student ID':<15} {'Name':<25} {'Points':<10}")
            print(f"{'=' * 65}")
            for acc in accounts:
                lid, sid, cname, points = acc
                print(f"{lid:<6} {sid:<15} {cname[:24]:<25} {points:<10}")
            print(f"\nTotal: {len(accounts)} accounts")
            input("\nPress Enter to continue...")

        elif choice == '2':
            student_id = input("Enter Student ID: ").strip()
            if not student_id:
                print("Student ID is required.")
                continue

            account = get_loyalty_account(student_id)
            if not account:
                print(f"No loyalty account found for Student ID: {student_id}")
                create = input("Create a new account? (y/n): ").strip().lower()
                if create == 'y':
                    cname = input("Customer name: ").strip()
                    if cname:
                        account = get_or_create_loyalty_account(student_id, cname)
                        if account:
                            print(f"\n Account created for {cname}!")
                if not account:
                    continue

            lid, sid, cname, points = account
            print(f"\n{'=' * 40}")
            print("LOYALTY ACCOUNT")
            print(f"{'=' * 40}")
            print(f"Student ID: {sid}")
            print(f"Name:       {cname}")
            print(f"Points:     {points}")
            # Show conversion: 100 points = £1 discount
            print(f"Value:      £{points / 100:.2f} (100 pts = £1)")
            input("\nPress Enter to continue...")

        elif choice == '3':
            student_id = input("Student ID: ").strip()
            if not student_id:
                print("Student ID is required.")
                continue
            customer_name = input("Customer name: ").strip()
            if not customer_name:
                print("Customer name is required.")
                continue

            account = get_or_create_loyalty_account(student_id, customer_name)
            if account:
                print(f"\n Loyalty account ready for {customer_name} (Student: {student_id})")
                print(f"  Current points: {account[3]}")
            else:
                print("\n Failed to create loyalty account.")

        elif choice == '4':
            student_id = input("Enter Student ID: ").strip()
            if not student_id:
                print("Student ID is required.")
                continue

            account = get_loyalty_account(student_id)
            if not account:
                print("No loyalty account found for this student.")
                continue

            lid, sid, cname, current_points = account
            print(f"\nCustomer: {cname} | Current Points: {current_points}")

            try:
                points = int(input("Points to add: "))
                if points < 1:
                    print("Points must be greater than zero.")
                    continue
            except ValueError:
                print("Invalid number.")
                continue

            reason = input("Reason (optional): ").strip()

            if add_loyalty_points(student_id, points, reason):
                print(f"\n {points} points added to {cname}'s account!")
                print(f"  New balance: {current_points + points} points")
            else:
                print("\n Failed to add points.")

        elif choice == '5':
            student_id = input("Enter Student ID: ").strip()
            if not student_id:
                print("Student ID is required.")
                continue

            account = get_loyalty_account(student_id)
            if not account:
                print("No loyalty account found for this student.")
                continue

            lid, sid, cname, current_points = account
            print(f"\nCustomer: {cname} | Current Points: {current_points}")
            print(f"Redeemable value: £{current_points / 100:.2f} (100 pts = £1)")

            if current_points < 1:
                print("No points available to redeem.")
                continue

            try:
                points = int(input(f"Points to redeem (max {current_points}): "))
                if points < 1:
                    print("Points must be greater than zero.")
                    continue
                if points > current_points:
                    print(f"Insufficient points. Maximum: {current_points}")
                    continue
            except ValueError:
                print("Invalid number.")
                continue

            reason = input("Reason (optional): ").strip()

            if redeem_loyalty_points(student_id, points, reason):
                print(f"\n {points} points redeemed from {cname}'s account!")
                print(f"  Discount value: £{points / 100:.2f}")
                print(f"  Remaining balance: {current_points - points} points")
            else:
                print("\n Failed to redeem points.")

        elif choice == '6':
            student_id = input("Enter Student ID: ").strip()
            if not student_id:
                print("Student ID is required.")
                continue

            account = get_loyalty_account(student_id)
            if not account:
                print("No loyalty account found for this student.")
                continue

            log = get_loyalty_log(student_id)
            if not log:
                print(f"\nNo transaction history for {account[2]}.")
                input("\nPress Enter to continue...")
                continue

            print(f"\n{'=' * 80}")
            print(f"LOYALTY POINTS HISTORY - {account[2]} (Balance: {account[3]} pts)")
            print(f"{'=' * 80}")
            print(f"{'ID':<6} {'Change':<10} {'Type':<12} {'Reason':<25} {'Date':<20}")
            print("-" * 80)
            for entry in log:
                log_id, change, trans_type, reason, date = entry
                change_str = f"+{change}" if change > 0 else str(change)
                print(f"{log_id:<6} {change_str:<10} {trans_type:<12} {(reason or '')[:24]:<25} {str(date)[:19]:<20}")
            input("\nPress Enter to continue...")

        elif choice == '7':
            break


def staff_scheduling_cli() -> None:
    """Staff scheduling submenu."""
    DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    POSITIONS = ["Barista", "Server", "Kitchen", "Supervisor", "Manager"]
    TEMPLATE_SCHEDULES = [
        ("Monday-Friday: 9AM-5PM", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], "09:00", "17:00"),
        ("Monday-Friday: 8AM-4PM", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], "08:00", "16:00"),
        ("Monday-Friday: 12PM-8PM", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], "12:00", "20:00"),
        ("Weekends Only: 10AM-6PM", ["Saturday", "Sunday"], "10:00", "18:00"),
        ("Monday/Wednesday/Friday: 9AM-5PM", ["Monday", "Wednesday", "Friday"], "09:00", "17:00"),
    ]

    while True:
        print("\n--- Staff Scheduling ---")
        print("1. View All Schedules")
        print("2. View Staff Member Schedule")
        print("3. Add Shift")
        print("4. Add Shift from Template")
        print("5. Update Shift")
        print("6. Delete Shift")
        print("7. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            schedules = get_all_staff_schedules()
            if not schedules:
                print("\nNo schedules found.")
                input("\nPress Enter to continue...")
                continue

            print(f"\n{'=' * 90}")
            print(f"{'ID':<5} {'Staff':<20} {'Position':<12} {'Day':<12} {'Start':<8} {'End':<8} {'Notes':<20}")
            print(f"{'=' * 90}")
            current_day = None
            for sched in schedules:
                sid, sname, pos, day, start, end, notes = sched
                if day != current_day:
                    current_day = day
                    print(f"\n--- {day} ---")
                print(f"{sid:<5} {sname[:19]:<20} {pos:<12} {day:<12} {start:<8} {end:<8} {(notes or '')[:19]:<20}")
            print(f"\nTotal: {len(schedules)} shifts")
            input("\nPress Enter to continue...")

        elif choice == '2':
            staff_name = input("Enter staff name (or part of name): ").strip()
            if not staff_name:
                print("Name is required.")
                continue

            schedules = get_staff_schedule_by_name(staff_name)
            if not schedules:
                print(f"No schedules found for '{staff_name}'.")
                input("\nPress Enter to continue...")
                continue

            staff_display = schedules[0][1]
            print(f"\n{'=' * 60}")
            print(f"SCHEDULE FOR: {staff_display}")
            print(f"{'=' * 60}")
            print(f"{'ID':<5} {'Day':<12} {'Start':<8} {'End':<8} {'Notes':<20}")
            print("-" * 55)
            for sched in schedules:
                sid, sname, pos, day, start, end, notes = sched
                print(f"{sid:<5} {day:<12} {start:<8} {end:<8} {(notes or '')[:19]:<20}")
            input("\nPress Enter to continue...")

        elif choice == '3':
            print("\n--- Add New Shift ---")
            staff_name = input("Staff name: ").strip()
            if not staff_name:
                print("Staff name is required.")
                continue

            print("\nPositions: " + ", ".join(f"{i+1}. {p}" for i, p in enumerate(POSITIONS)))
            try:
                pos_choice = int(input("Select position: "))
                position = POSITIONS[pos_choice - 1] if 1 <= pos_choice <= len(POSITIONS) else "Barista"
            except (ValueError, IndexError):
                position = "Barista"

            print("\nDays: " + ", ".join(f"{i+1}. {d}" for i, d in enumerate(DAYS_OF_WEEK)))
            try:
                day_choice = int(input("Select day: "))
                day = DAYS_OF_WEEK[day_choice - 1] if 1 <= day_choice <= len(DAYS_OF_WEEK) else None
            except (ValueError, IndexError):
                day = None

            if not day:
                print("Invalid day selection.")
                continue

            start_time = input("Start time (HH:MM, 24-hour): ").strip()
            try:
                datetime.strptime(start_time, "%H:%M")
            except ValueError:
                print("Invalid time format.")
                continue

            end_time = input("End time (HH:MM, 24-hour): ").strip()
            try:
                datetime.strptime(end_time, "%H:%M")
            except ValueError:
                print("Invalid time format.")
                continue

            notes = input("Notes (optional): ").strip()

            if add_staff_schedule(staff_name, position, day, start_time, end_time, notes):
                print(f"\n Shift added: {staff_name} - {day} {start_time}-{end_time}")
            else:
                print("\n Failed to add shift.")

        elif choice == '4':
            print("\n--- Add Shift from Template ---")
            staff_name = input("Staff name: ").strip()
            if not staff_name:
                print("Staff name is required.")
                continue

            print("\nPositions: " + ", ".join(f"{i+1}. {p}" for i, p in enumerate(POSITIONS)))
            try:
                pos_choice = int(input("Select position: "))
                position = POSITIONS[pos_choice - 1] if 1 <= pos_choice <= len(POSITIONS) else "Barista"
            except (ValueError, IndexError):
                position = "Barista"

            print("\nTemplate Schedules:")
            for i, (desc, days, start, end) in enumerate(TEMPLATE_SCHEDULES, 1):
                print(f"  {i}. {desc}")

            try:
                tmpl_choice = int(input("Select template: "))
                if 1 <= tmpl_choice <= len(TEMPLATE_SCHEDULES):
                    desc, days, start, end = TEMPLATE_SCHEDULES[tmpl_choice - 1]
                    added = 0
                    for day in days:
                        if add_staff_schedule(staff_name, position, day, start, end):
                            added += 1
                    print(f"\n {added} shifts added for {staff_name} using template '{desc}'")
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Invalid input.")

        elif choice == '5':
            try:
                schedule_id = int(input("Enter Shift ID to update: "))
            except ValueError:
                print("Invalid ID.")
                continue

            # Look up current details
            schedules = get_all_staff_schedules()
            current = None
            for s in schedules:
                if s[0] == schedule_id:
                    current = s
                    break

            if not current:
                print("Shift not found.")
                continue

            sid, sname, pos, day, start, end, notes = current
            print(f"\nUpdating shift for {sname}: {day} {start}-{end}")
            print("(Press Enter to keep current value)")

            print("\nDays: " + ", ".join(f"{i+1}. {d}" for i, d in enumerate(DAYS_OF_WEEK)))
            day_input = input(f"Day [{day}]: ").strip()
            try:
                new_day = DAYS_OF_WEEK[int(day_input) - 1] if day_input else day
            except (ValueError, IndexError):
                new_day = day

            new_start = input(f"Start time [{start}] (HH:MM): ").strip() or start
            new_end = input(f"End time [{end}] (HH:MM): ").strip() or end
            new_notes = input(f"Notes [{notes or ''}]: ").strip()
            if not new_notes:
                new_notes = notes or ""

            if update_staff_schedule_entry(schedule_id, new_day, new_start, new_end, new_notes):
                print(f"\n Shift #{schedule_id} updated!")
            else:
                print("\n Failed to update shift.")

        elif choice == '6':
            try:
                schedule_id = int(input("Enter Shift ID to delete: "))
            except ValueError:
                print("Invalid ID.")
                continue

            confirm = input(f"Delete shift #{schedule_id}? (y/n): ").strip().lower()
            if confirm == 'y':
                if delete_staff_schedule_entry(schedule_id):
                    print(f"\n Shift #{schedule_id} deleted!")
                else:
                    print("\n Failed to delete shift.")

        elif choice == '7':
            break


# Export functions for use in cli_main.py
__all__ = [
    'display_cafe_menu',
    'init_cafe_db',
    'setup_cafe_permissions',
    'set_auth',
]
