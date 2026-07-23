"""
Grocery Shop Service
Campus convenience store and grocery management
"""

from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple
import uuid

from education_system.post_18.university_system.core.paths import DEFAULT_DB_PATH
from education_system.post_18.university_system.modules.shared.utils.simple_activity_logger import (
    log_dynamic_activity as log_activity,
    log_menu_navigation,
)

# Import i18n for internationalization
from education_system.post_18.university_system.core.i18n import (
    get_text,
    get_current_language,
)
from education_system.post_18.university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)

try:
    from education_system.post_18.university_system.infrastructure.auth import get_current_user, set_auth_instance
    from education_system.post_18.university_system.infrastructure.shared_context import get_auth
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None
    get_auth = lambda: None

try:
    from education_system.post_18.university_system.modules.shared.utils.finance_integration import record_payment_to_finance
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False
    record_payment_to_finance = None

auth = None


def set_auth(auth_instance: Any) -> None:
    """Set the authentication instance"""
    global auth
    auth = auth_instance
    if HAS_AUTH:
        set_auth_instance(auth_instance)


def init_grocery_db() -> bool:
    """Initialize the grocery shop database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Create grocery categories table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS grocery_categories (
            category_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            display_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT NOT NULL
        )
        ''')

        # Products table (unified) for grocery products
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL DEFAULT 'grocery',
            source_product_id TEXT,
            category_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            brand TEXT,
            unit TEXT DEFAULT 'each',
            price REAL NOT NULL,
            cost_price REAL,
            stock_quantity INTEGER DEFAULT 0,
            min_stock_level INTEGER DEFAULT 5,
            barcode TEXT,
            is_available BOOLEAN DEFAULT 1,
            is_perishable BOOLEAN DEFAULT 0,
            expiry_date TEXT,
            discount_percentage REAL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (category_id) REFERENCES grocery_categories (category_id)
        )
        ''')

        # NOTE: grocery transactions now use the unified 'transactions' table
        # with source_type = 'grocery'

        # Create grocery transaction items table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS grocery_transaction_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            discount REAL DEFAULT 0,
            subtotal REAL NOT NULL,
            FOREIGN KEY (transaction_id) REFERENCES transactions (source_transaction_id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
        ''')

        # Grocery cart uses unified cart table with source_type='grocery'

        # Create grocery stock movements table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS grocery_stock_movements (
            movement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            movement_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            previous_stock INTEGER,
            new_stock INTEGER,
            reference TEXT,
            notes TEXT,
            created_by INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
        ''')

        # Create grocery suppliers table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS grocery_suppliers (
            supplier_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            contact_person TEXT,
            email TEXT,
            phone TEXT,
            address TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT NOT NULL
        )
        ''')

        # Insert sample categories if none exist
        cursor.execute("SELECT COUNT(*) FROM grocery_categories")
        if cursor.fetchone()[0] == 0:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            categories = [
                ('CAT01', 'Fresh Food', 'Fresh fruits, vegetables, and bakery items', 1, 1, now),
                ('CAT02', 'Dairy & Eggs', 'Milk, cheese, yogurt, and eggs', 2, 1, now),
                ('CAT03', 'Drinks & Beverages', 'Soft drinks, juices, water, and energy drinks', 3, 1, now),
                ('CAT04', 'Snacks & Confectionery', 'Chips, chocolates, sweets, and biscuits', 4, 1, now),
                ('CAT05', 'Frozen Food', 'Frozen meals, ice cream, and frozen vegetables', 5, 1, now),
                ('CAT06', 'Household', 'Cleaning supplies and household essentials', 6, 1, now),
                ('CAT07', 'Personal Care', 'Toiletries and personal hygiene products', 7, 1, now),
                ('CAT08', 'Stationery', 'Pens, notebooks, and study supplies', 8, 1, now),
                ('CAT09', 'Ready Meals', 'Sandwiches, salads, and quick meals', 9, 1, now),
                ('CAT10', 'International Foods', 'International cuisine and specialty items', 10, 1, now),
            ]
            cursor.executemany(
                '''INSERT INTO grocery_categories VALUES (?, ?, ?, ?, ?, ?)''',
                categories
            )

            # Insert sample products
            products = [
                # Fresh Food
                ('GR001', 'CAT01', 'Banana (bunch)', 'Fresh bananas', None, 'bunch', 1.29, 0.80, 50, 10, None, 1, 1, None, 0, now, now),
                ('GR002', 'CAT01', 'Apple (each)', 'Fresh red apple', None, 'each', 0.49, 0.30, 100, 20, None, 1, 1, None, 0, now, now),
                ('GR003', 'CAT01', 'Fresh Bread Loaf', 'White sliced bread', 'Campus Bakery', 'loaf', 1.49, 0.90, 30, 10, None, 1, 1, None, 0, now, now),
                ('GR004', 'CAT01', 'Croissant', 'Butter croissant', 'Campus Bakery', 'each', 1.29, 0.70, 40, 10, None, 1, 1, None, 0, now, now),
                # Dairy & Eggs
                ('GR005', 'CAT02', 'Whole Milk 1L', 'Fresh whole milk', 'Dairy Fresh', 'litre', 1.49, 1.00, 50, 15, None, 1, 1, None, 0, now, now),
                ('GR006', 'CAT02', 'Semi-Skimmed Milk 1L', 'Fresh semi-skimmed milk', 'Dairy Fresh', 'litre', 1.39, 0.95, 50, 15, None, 1, 1, None, 0, now, now),
                ('GR007', 'CAT02', 'Cheddar Cheese 200g', 'Mature cheddar cheese', 'Dairy Fresh', '200g', 2.99, 2.00, 30, 10, None, 1, 1, None, 0, now, now),
                ('GR008', 'CAT02', 'Free Range Eggs (6)', 'Box of 6 free range eggs', 'Farm Fresh', '6 pack', 2.49, 1.50, 40, 10, None, 1, 1, None, 0, now, now),
                ('GR009', 'CAT02', 'Greek Yogurt 500g', 'Natural Greek yogurt', 'Dairy Fresh', '500g', 2.29, 1.50, 35, 10, None, 1, 1, None, 0, now, now),
                # Drinks
                ('GR010', 'CAT03', 'Coca-Cola 500ml', 'Classic cola', 'Coca-Cola', '500ml', 1.79, 1.20, 100, 20, None, 1, 0, None, 0, now, now),
                ('GR011', 'CAT03', 'Pepsi 500ml', 'Classic cola', 'Pepsi', '500ml', 1.79, 1.20, 100, 20, None, 1, 0, None, 0, now, now),
                ('GR012', 'CAT03', 'Orange Juice 1L', 'Fresh orange juice', 'Tropicana', 'litre', 2.99, 2.00, 40, 10, None, 1, 1, None, 0, now, now),
                ('GR013', 'CAT03', 'Still Water 500ml', 'Mineral water', 'Evian', '500ml', 0.99, 0.50, 150, 30, None, 1, 0, None, 0, now, now),
                ('GR014', 'CAT03', 'Energy Drink 250ml', 'Energy boost drink', 'Red Bull', '250ml', 1.99, 1.30, 80, 20, None, 1, 0, None, 0, now, now),
                ('GR015', 'CAT03', 'Coffee (ground) 200g', 'Ground coffee', 'Nescafe', '200g', 4.49, 3.00, 25, 8, None, 1, 0, None, 0, now, now),
                # Snacks
                ('GR016', 'CAT04', 'Walkers Crisps', 'Ready salted crisps', 'Walkers', 'pack', 1.19, 0.70, 100, 25, None, 1, 0, None, 0, now, now),
                ('GR017', 'CAT04', 'Dairy Milk Bar', 'Milk chocolate bar', 'Cadbury', 'bar', 1.49, 0.90, 80, 20, None, 1, 0, None, 0, now, now),
                ('GR018', 'CAT04', 'Mars Bar', 'Chocolate caramel bar', 'Mars', 'bar', 0.89, 0.55, 100, 25, None, 1, 0, None, 0, now, now),
                ('GR019', 'CAT04', 'Haribo Gummies', 'Gummy sweets', 'Haribo', 'bag', 1.29, 0.75, 60, 15, None, 1, 0, None, 0, now, now),
                ('GR020', 'CAT04', 'McVities Digestives', 'Wheat biscuits', 'McVities', 'pack', 1.89, 1.20, 40, 10, None, 1, 0, None, 0, now, now),
                # Frozen
                ('GR021', 'CAT05', 'Frozen Pizza', 'Pepperoni pizza', 'Dr. Oetker', 'each', 3.49, 2.20, 30, 8, None, 1, 0, None, 0, now, now),
                ('GR022', 'CAT05', 'Ice Cream 500ml', 'Vanilla ice cream', 'Ben & Jerrys', '500ml', 4.99, 3.20, 25, 8, None, 1, 0, None, 0, now, now),
                ('GR023', 'CAT05', 'Frozen Chips 1kg', 'Oven chips', 'McCain', 'kg', 2.49, 1.50, 35, 10, None, 1, 0, None, 0, now, now),
                # Household
                ('GR024', 'CAT06', 'Kitchen Roll', '2 pack kitchen roll', 'Plenty', '2 pack', 2.49, 1.50, 40, 10, None, 1, 0, None, 0, now, now),
                ('GR025', 'CAT06', 'Toilet Roll (4)', '4 pack toilet roll', 'Andrex', '4 pack', 2.99, 1.80, 50, 15, None, 1, 0, None, 0, now, now),
                ('GR026', 'CAT06', 'Washing Up Liquid', 'Dish soap', 'Fairy', 'bottle', 1.79, 1.10, 30, 8, None, 1, 0, None, 0, now, now),
                ('GR027', 'CAT06', 'Laundry Pods (15)', 'Washing capsules', 'Persil', '15 pack', 4.99, 3.20, 25, 8, None, 1, 0, None, 0, now, now),
                # Personal Care
                ('GR028', 'CAT07', 'Shower Gel 250ml', 'Shower gel', 'Lynx', '250ml', 2.99, 1.80, 40, 10, None, 1, 0, None, 0, now, now),
                ('GR029', 'CAT07', 'Shampoo 400ml', 'Hair shampoo', 'Head & Shoulders', '400ml', 3.99, 2.50, 35, 10, None, 1, 0, None, 0, now, now),
                ('GR030', 'CAT07', 'Toothpaste', 'Mint toothpaste', 'Colgate', 'tube', 1.99, 1.20, 50, 15, None, 1, 0, None, 0, now, now),
                ('GR031', 'CAT07', 'Deodorant', 'Roll-on deodorant', 'Sure', 'each', 2.49, 1.50, 40, 10, None, 1, 0, None, 0, now, now),
                # Stationery
                ('GR032', 'CAT08', 'Biro Pens (10)', 'Blue ballpoint pens', 'BIC', '10 pack', 2.49, 1.50, 60, 15, None, 1, 0, None, 0, now, now),
                ('GR033', 'CAT08', 'A4 Notebook', 'Lined notebook', 'Pukka', 'each', 2.99, 1.80, 50, 15, None, 1, 0, None, 0, now, now),
                ('GR034', 'CAT08', 'Highlighters (4)', 'Assorted highlighters', 'Stabilo', '4 pack', 3.49, 2.20, 40, 10, None, 1, 0, None, 0, now, now),
                ('GR035', 'CAT08', 'Post-it Notes', 'Sticky notes', 'Post-it', 'pack', 2.29, 1.40, 45, 12, None, 1, 0, None, 0, now, now),
                # Ready Meals
                ('GR036', 'CAT09', 'BLT Sandwich', 'Bacon, lettuce, tomato sandwich', 'Campus Kitchen', 'each', 3.49, 2.00, 20, 5, None, 1, 1, None, 0, now, now),
                ('GR037', 'CAT09', 'Chicken Wrap', 'Grilled chicken wrap', 'Campus Kitchen', 'each', 3.99, 2.30, 15, 5, None, 1, 1, None, 0, now, now),
                ('GR038', 'CAT09', 'Caesar Salad', 'Chicken Caesar salad', 'Campus Kitchen', 'each', 4.49, 2.80, 12, 4, None, 1, 1, None, 0, now, now),
                ('GR039', 'CAT09', 'Pasta Pot', 'Ready-to-eat pasta', 'Pot Noodle', 'each', 1.99, 1.20, 40, 10, None, 1, 0, None, 0, now, now),
                # International
                ('GR040', 'CAT10', 'Instant Noodles', 'Asian instant noodles', 'Nissin', 'pack', 0.99, 0.55, 80, 20, None, 1, 0, None, 0, now, now),
                ('GR041', 'CAT10', 'Sriracha Sauce', 'Hot chili sauce', 'Huy Fong', 'bottle', 3.99, 2.50, 25, 8, None, 1, 0, None, 0, now, now),
                ('GR042', 'CAT10', 'Tortilla Wraps (8)', 'Mexican tortillas', 'Old El Paso', '8 pack', 2.29, 1.40, 35, 10, None, 1, 0, None, 0, now, now),
            ]
            cursor.executemany(
                '''INSERT INTO products (source_type, source_product_id, category_id, name, description, brand, unit, price, cost_price, stock_quantity, min_stock_level, barcode, is_available, is_perishable, expiry_date, discount_percentage, created_at, updated_at) VALUES ('grocery', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                products
            )

        conn.commit()
        conn.close()
        print("Grocery shop database initialized successfully!")
        return True

    except sqlite3.Error as e:
        print(f"Error initializing grocery database: {e}")
        if 'conn' in locals():
            conn.close()
        return False


def setup_grocery_permissions(auth_instance=None):
    """Setup permissions for the grocery module"""
    global auth

    if auth_instance:
        auth = auth_instance

    if not auth:
        print("Authentication system not initialized.")
        return False

    try:
        conn = get_connection()
        cursor = conn.cursor()

        grocery_permissions = [
            ('view_grocery_products', 'View available grocery products'),
            ('purchase_grocery', 'Purchase grocery items'),
            ('view_own_grocery_history', 'View own purchase history'),
            ('manage_grocery_products', 'Add, update, or delete products'),
            ('manage_grocery_inventory', 'Manage product inventory levels'),
            ('view_all_grocery_transactions', 'View all grocery transactions'),
            ('manage_grocery_categories', 'Manage product categories'),
            ('generate_grocery_reports', 'Generate grocery sales reports'),
            ('manage_grocery_suppliers', 'Manage suppliers'),
            ('process_grocery_refunds', 'Process refunds'),
        ]

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        perm_names = [p[0] for p in grocery_permissions]
        placeholders = ','.join('?' * len(perm_names))
        cursor.execute(
            f'SELECT permission_name FROM permissions WHERE permission_name IN ({placeholders})',
            perm_names
        )
        existing_perms = {row[0] for row in cursor.fetchall()}

        new_perms = [
            (perm_name, perm_desc, timestamp)
            for perm_name, perm_desc in grocery_permissions
            if perm_name not in existing_perms
        ]
        if new_perms:
            cursor.executemany(
                'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                new_perms
            )

        conn.commit()

        role_permissions = {
            'student': ['view_grocery_products', 'purchase_grocery', 'view_own_grocery_history'],
            'staff': ['view_grocery_products', 'purchase_grocery', 'view_own_grocery_history',
                     'view_all_grocery_transactions'],
            'admin': ['view_grocery_products', 'purchase_grocery', 'view_own_grocery_history',
                     'manage_grocery_products', 'manage_grocery_inventory', 'view_all_grocery_transactions',
                     'manage_grocery_categories', 'generate_grocery_reports', 'manage_grocery_suppliers',
                     'process_grocery_refunds'],
        }

        role_names = list(role_permissions.keys())
        placeholders = ','.join('?' * len(role_names))
        cursor.execute(
            f'SELECT id, role_name FROM roles WHERE role_name IN ({placeholders})',
            role_names
        )
        role_id_map = {row['role_name']: row['id'] for row in cursor.fetchall()}

        perm_placeholders = ','.join('?' * len(perm_names))
        cursor.execute(
            f'SELECT id, permission_name FROM permissions WHERE permission_name IN ({perm_placeholders})',
            perm_names
        )
        perm_id_map = {row['permission_name']: row['id'] for row in cursor.fetchall()}

        cursor.execute('SELECT role_id, permission_id FROM role_permissions')
        existing_role_perms = {(row['role_id'], row['permission_id']) for row in cursor.fetchall()}

        new_role_perms = []
        for role_name, permissions in role_permissions.items():
            role_id = role_id_map.get(role_name)
            if role_id:
                for perm_name in permissions:
                    perm_id = perm_id_map.get(perm_name)
                    if perm_id and (role_id, perm_id) not in existing_role_perms:
                        new_role_perms.append((role_id, perm_id))

        if new_role_perms:
            cursor.executemany(
                'INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                new_role_perms
            )

        conn.commit()
        conn.close()

        print("Grocery permissions setup successfully!")
        return True

    except Exception as e:
        if 'conn' in locals():
            conn.close()
        print(f"Error setting up grocery permissions: {e}")
        return False


def get_categories() -> List[Dict]:
    """Get all product categories"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM grocery_categories
            WHERE is_active = 1
            ORDER BY display_order
        ''')
        categories = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return categories
    except sqlite3.Error as e:
        print(f"Error fetching categories: {e}")
        return []


def get_products(category_id: str = None, search: str = None) -> List[Dict]:
    """Get products, optionally filtered by category or search term"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = '''
            SELECT p.*, c.name as category_name
            FROM products p
            JOIN grocery_categories c ON p.category_id = c.category_id
            WHERE p.source_type = 'grocery' AND p.is_available = 1
        '''
        params = []

        if category_id:
            query += ' AND p.category_id = ?'
            params.append(category_id)

        if search:
            query += ' AND (p.name LIKE ? OR p.brand LIKE ? OR p.description LIKE ?)'
            search_term = f'%{search}%'
            params.extend([search_term, search_term, search_term])

        query += ' ORDER BY c.display_order, p.name'

        cursor.execute(query, params)
        products = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return products
    except sqlite3.Error as e:
        print(f"Error fetching products: {e}")
        return []


def add_to_cart(user_id: int, product_id: str, quantity: int = 1) -> bool:
    """Add product to cart"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check stock availability
        cursor.execute("SELECT stock_quantity, name FROM products WHERE source_type = 'grocery' AND source_product_id = ?", (product_id,))
        result = cursor.fetchone()
        if not result:
            print("Product not found.")
            conn.close()
            return False

        if result[0] < quantity:
            print(f"Insufficient stock. Only {result[0]} available.")
            conn.close()
            return False

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Check if item already in cart
        cursor.execute(
            "SELECT cart_id, quantity FROM cart WHERE source_type = 'grocery' AND user_id = ? AND product_id = ?",
            (user_id, product_id),
        )
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                "UPDATE cart SET quantity = quantity + ? WHERE cart_id = ?",
                (quantity, existing[0]),
            )
        else:
            cursor.execute('''
                INSERT INTO cart (source_type, user_id, product_id, quantity, added_at)
                VALUES ('grocery', ?, ?, ?, ?)
            ''', (user_id, product_id, quantity, now))

        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        print(f"Error adding to cart: {e}")
        return False


def update_cart_quantity(user_id: int, product_id: str, quantity: int) -> bool:
    """Update cart item quantity"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        if quantity <= 0:
            cursor.execute("DELETE FROM cart WHERE source_type = 'grocery' AND user_id = ? AND product_id = ?",
                          (user_id, product_id))
        else:
            cursor.execute('''
                UPDATE cart SET quantity = ?
                WHERE source_type = 'grocery' AND user_id = ? AND product_id = ?
            ''', (quantity, user_id, product_id))

        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        print(f"Error updating cart: {e}")
        return False


def view_cart(user_id: int) -> Tuple[List[Dict], float]:
    """View cart contents and subtotal"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT c.*, p.name, p.price, p.brand, p.discount_percentage, p.stock_quantity
            FROM cart c
            JOIN products p ON c.product_id = p.source_product_id AND p.source_type = 'grocery'
            WHERE c.source_type = 'grocery' AND c.user_id = ?
        ''', (user_id,))

        items = [dict(row) for row in cursor.fetchall()]
        conn.close()

        subtotal = 0
        for item in items:
            price = item['price']
            if item['discount_percentage'] > 0:
                price = price * (1 - item['discount_percentage'] / 100)
            subtotal += price * item['quantity']

        return items, subtotal
    except sqlite3.Error as e:
        print(f"Error viewing cart: {e}")
        return [], 0.0


def clear_cart(user_id: int) -> bool:
    """Clear user's cart"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cart WHERE source_type = 'grocery' AND user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        print(f"Error clearing cart: {e}")
        return False


def checkout(user_id: int, payment_method: str = 'card') -> Optional[str]:
    """Process checkout"""
    try:
        items, subtotal = view_cart(user_id)

        if not items:
            print("Cart is empty!")
            return None

        conn = get_connection()
        cursor = conn.cursor()

        # Verify stock for all items
        for item in items:
            cursor.execute("SELECT stock_quantity FROM products WHERE source_type = 'grocery' AND source_product_id = ?",
                          (item['product_id'],))
            stock = cursor.fetchone()[0]
            if stock < item['quantity']:
                print(f"Insufficient stock for {item['name']}. Only {stock} available.")
                conn.close()
                return None

        # Calculate totals
        tax_rate = 0.0  # Could be configurable
        tax_amount = subtotal * tax_rate
        total = subtotal + tax_amount

        # Generate transaction ID
        transaction_id = f"GR{datetime.now().strftime('%Y%m%d%H%M%S')}{str(uuid.uuid4())[:4].upper()}"
        receipt_number = f"RCP{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:6].upper()}"
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Get student_id if applicable
        student_id = None
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (user_id,))
        result = cursor.fetchone()
        if result:
            student_id = result[0]

        # Create transaction
        cursor.execute('''
            INSERT INTO transactions
            (source_type, source_transaction_id, customer_id, student_id, created_at, subtotal,
             discount_amount, tax_amount, total_amount, payment_method,
             status, receipt_number)
            VALUES ('grocery', ?, ?, ?, ?, ?, 0, ?, ?, ?, 'completed', ?)
        ''', (transaction_id, user_id, student_id, now, subtotal,
              tax_amount, total, payment_method, receipt_number))

        # Create transaction items and update stock
        for item in items:
            price = item['price']
            discount = 0
            if item['discount_percentage'] > 0:
                discount = price * item['discount_percentage'] / 100
                price = price - discount

            item_subtotal = price * item['quantity']

            cursor.execute('''
                INSERT INTO grocery_transaction_items
                (transaction_id, product_id, product_name, quantity, unit_price, discount, subtotal)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (transaction_id, item['product_id'], item['name'],
                  item['quantity'], item['price'], discount * item['quantity'], item_subtotal))

            # Update stock
            cursor.execute('''
                UPDATE products
                SET stock_quantity = stock_quantity - ?
                WHERE source_type = 'grocery' AND source_product_id = ?
            ''', (item['quantity'], item['product_id']))

            # Record stock movement
            cursor.execute('''
                INSERT INTO grocery_stock_movements
                (product_id, movement_type, quantity, reference, created_at)
                VALUES (?, 'sale', ?, ?, ?)
            ''', (item['product_id'], -item['quantity'], transaction_id, now))

        # Clear cart
        cursor.execute("DELETE FROM cart WHERE source_type = 'grocery' AND user_id = ?", (user_id,))

        conn.commit()
        conn.close()

        log_activity('create', 'grocery_transaction', details=f'Transaction {transaction_id} for £{total:.2f}')

        return transaction_id

    except sqlite3.Error as e:
        print(f"Error during checkout: {e}")
        return None


def get_purchase_history(user_id: int) -> List[Dict]:
    """Get user's purchase history"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT *, created_at as transaction_date FROM transactions
            WHERE source_type = 'grocery' AND customer_id = ?
            ORDER BY created_at DESC
        ''', (user_id,))
        transactions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return transactions
    except sqlite3.Error as e:
        print(f"Error fetching purchase history: {e}")
        return []


def get_transaction_details(transaction_id: str) -> Tuple[Optional[Dict], List[Dict]]:
    """Get transaction details with items"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT *, created_at as transaction_date FROM transactions WHERE source_type = 'grocery' AND source_transaction_id = ?", (transaction_id,))
        transaction = cursor.fetchone()

        if not transaction:
            conn.close()
            return None, []

        cursor.execute('SELECT * FROM grocery_transaction_items WHERE transaction_id = ?', (transaction_id,))
        items = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return dict(transaction), items

    except sqlite3.Error as e:
        print(f"Error fetching transaction details: {e}")
        return None, []


def restock_product(product_id: str, quantity: int, notes: str = "", user_id: int = None) -> bool:
    """Restock a product"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT stock_quantity FROM products WHERE source_type = 'grocery' AND source_product_id = ?", (product_id,))
        result = cursor.fetchone()
        if not result:
            print("Product not found.")
            conn.close()
            return False

        previous_stock = result[0]
        new_stock = previous_stock + quantity
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            UPDATE products
            SET stock_quantity = ?, updated_at = ?
            WHERE source_type = 'grocery' AND source_product_id = ?
        ''', (new_stock, now, product_id))

        cursor.execute('''
            INSERT INTO grocery_stock_movements
            (product_id, movement_type, quantity, previous_stock, new_stock, notes, created_by, created_at)
            VALUES (?, 'restock', ?, ?, ?, ?, ?, ?)
        ''', (product_id, quantity, previous_stock, new_stock, notes, user_id, now))

        conn.commit()
        conn.close()
        return True

    except sqlite3.Error as e:
        print(f"Error restocking product: {e}")
        return False


def get_low_stock_products(threshold: int = None) -> List[Dict]:
    """Get products that are low on stock"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        if threshold:
            cursor.execute('''
                SELECT p.*, c.name as category_name
                FROM products p
                JOIN grocery_categories c ON p.category_id = c.category_id
                WHERE p.source_type = 'grocery' AND p.stock_quantity <= ?
                ORDER BY p.stock_quantity
            ''', (threshold,))
        else:
            cursor.execute('''
                SELECT p.*, c.name as category_name
                FROM products p
                JOIN grocery_categories c ON p.category_id = c.category_id
                WHERE p.source_type = 'grocery' AND p.stock_quantity <= p.min_stock_level
                ORDER BY p.stock_quantity
            ''')

        products = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return products
    except sqlite3.Error as e:
        print(f"Error fetching low stock products: {e}")
        return []


@log_menu_navigation(description="Displaying grocery shop main menu")
def display_grocery_menu():
    """Display the main menu for the grocery shop"""
    global auth

    if not auth or not auth.current_user:
        print(get_text('grocery.not_logged_in', default='You must be logged in to access the grocery shop.'))
        return

    # Initialize database if needed
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products'")
        if not cursor.fetchone():
            conn.close()
            print("Grocery database not initialized. Initializing now...")
            if not init_grocery_db():
                print("Failed to initialize grocery database.")
                return
        else:
            conn.close()
    except sqlite3.Error:
        if not init_grocery_db():
            print("Failed to initialize grocery database.")
            return

    user_id = auth.current_user.get('id')

    while True:
        print("\n" + "=" * 50)
        print(f"       {get_text('grocery.title', default='CAMPUS GROCERY SHOP')}")
        print("=" * 50)

        options = []
        option_num = 1

        if auth.check_permission('view_grocery_products'):
            print(f"{option_num}. {get_text('grocery.menu.browse', default='Browse Products')}")
            options.append('browse')
            option_num += 1

            print(f"{option_num}. {get_text('grocery.menu.search', default='Search Products')}")
            options.append('search')
            option_num += 1

        if auth.check_permission('purchase_grocery'):
            print(f"{option_num}. {get_text('grocery.menu.cart', default='View Cart')}")
            options.append('cart')
            option_num += 1

        if auth.check_permission('view_own_grocery_history'):
            print(f"{option_num}. {get_text('grocery.menu.history', default='Purchase History')}")
            options.append('history')
            option_num += 1

        if auth.check_permission('manage_grocery_products'):
            print(f"{option_num}. {get_text('grocery.menu.manage_products', default='Manage Products')}")
            options.append('manage_products')
            option_num += 1

        if auth.check_permission('manage_grocery_inventory'):
            print(f"{option_num}. {get_text('grocery.menu.inventory', default='Inventory Management')}")
            options.append('inventory')
            option_num += 1

        if auth.check_permission('view_all_grocery_transactions'):
            print(f"{option_num}. {get_text('grocery.menu.all_transactions', default='View All Transactions')}")
            options.append('all_transactions')
            option_num += 1

        if auth.check_permission('generate_grocery_reports'):
            print(f"{option_num}. {get_text('grocery.menu.reports', default='Generate Reports')}")
            options.append('reports')
            option_num += 1

        # Language option
        print(f"{option_num}. {get_text('grocery.menu.language', default='Language')}")
        options.append('language')
        option_num += 1

        print(f"{option_num}. {get_text('grocery.menu.return', default='Return to Main Menu')}")
        options.append('exit')

        choice = input(f"\n{get_text('grocery.prompt.choice', default='Enter your choice')}: ").strip()

        try:
            choice_idx = int(choice) - 1
            if choice_idx < 0 or choice_idx >= len(options):
                print(get_text('grocery.invalid_choice', default='Invalid choice. Please try again.'))
                continue

            selected = options[choice_idx]

            if selected == 'browse':
                browse_products(user_id)
            elif selected == 'search':
                search_products(user_id)
            elif selected == 'cart':
                view_and_manage_cart(user_id)
            elif selected == 'history':
                view_purchase_history(user_id)
            elif selected == 'manage_products':
                manage_products()
            elif selected == 'inventory':
                manage_inventory()
            elif selected == 'all_transactions':
                view_all_transactions()
            elif selected == 'reports':
                generate_reports()
            elif selected == 'language':
                display_language_menu_option()
            elif selected == 'exit':
                print(get_text('grocery.returning', default='Returning to main menu...'))
                break

        except ValueError:
            print(get_text('grocery.invalid_input', default='Invalid choice. Please enter a number.'))


def browse_products(user_id: int):
    """Browse products by category"""
    categories = get_categories()

    if not categories:
        print("No categories available.")
        return

    while True:
        print("\n" + "-" * 40)
        print("Product Categories:")
        print("-" * 40)

        for i, cat in enumerate(categories, 1):
            print(f"{i}. {cat['name']}")
            if cat['description']:
                print(f"   {cat['description']}")

        print(f"{len(categories) + 1}. View All Products")
        print(f"{len(categories) + 2}. Back to Menu")

        choice = input("\nSelect a category: ").strip()

        try:
            choice_idx = int(choice) - 1

            if choice_idx == len(categories):
                # View all products
                browse_category_products(user_id, None)
            elif choice_idx == len(categories) + 1:
                break
            elif choice_idx < 0 or choice_idx >= len(categories):
                print("Invalid choice.")
                continue
            else:
                browse_category_products(user_id, categories[choice_idx])

        except ValueError:
            print("Invalid choice. Please enter a number.")


def browse_category_products(user_id: int, category: Optional[Dict]):
    """Browse products in a category"""
    category_id = category['category_id'] if category else None
    products = get_products(category_id)

    if not products:
        print("No products available in this category.")
        return

    page_size = 10
    current_page = 0
    total_pages = (len(products) + page_size - 1) // page_size

    while True:
        start = current_page * page_size
        end = min(start + page_size, len(products))
        page_products = products[start:end]

        cat_name = category['name'] if category else "All Products"
        print(f"\n{'=' * 50}")
        print(f"   {cat_name} (Page {current_page + 1}/{total_pages})")
        print(f"{'=' * 50}")

        for i, product in enumerate(page_products, start + 1):
            price_str = f"£{product['price']:.2f}"
            if product['discount_percentage'] > 0:
                discounted = product['price'] * (1 - product['discount_percentage'] / 100)
                price_str = f"£{discounted:.2f} (was £{product['price']:.2f})"

            stock_status = "In Stock" if product['stock_quantity'] > 0 else "Out of Stock"
            if 0 < product['stock_quantity'] <= 5:
                stock_status = f"Low Stock ({product['stock_quantity']})"

            print(f"\n{i}. {product['name']}")
            if product['brand']:
                print(f"   Brand: {product['brand']}")
            print(f"   Price: {price_str}")
            print(f"   Status: {stock_status}")

        print(f"\n{'=' * 50}")
        print("Options: [N]ext, [P]revious, [number] to add, [B]ack")

        choice = input("Choice: ").strip().lower()

        if choice == 'n' and current_page < total_pages - 1:
            current_page += 1
        elif choice == 'p' and current_page > 0:
            current_page -= 1
        elif choice == 'b':
            break
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(products):
                product = products[idx]
                if product['stock_quantity'] <= 0:
                    print("Sorry, this product is out of stock.")
                    continue

                qty = input(f"Quantity for {product['name']} (max {product['stock_quantity']}): ").strip()
                quantity = int(qty) if qty and qty.isdigit() else 1

                if quantity > product['stock_quantity']:
                    print(f"Only {product['stock_quantity']} available.")
                    quantity = product['stock_quantity']

                if add_to_cart(user_id, product['product_id'], quantity):
                    print(f"Added {quantity}x {product['name']} to cart!")
            else:
                print("Invalid product number.")


def search_products(user_id: int):
    """Search for products"""
    search_term = input("\nEnter search term: ").strip()

    if not search_term:
        print("Please enter a search term.")
        return

    products = get_products(search=search_term)

    if not products:
        print(f"No products found matching '{search_term}'")
        return

    print(f"\n{'=' * 50}")
    print(f"   Search Results for '{search_term}'")
    print(f"{'=' * 50}")

    for i, product in enumerate(products, 1):
        price_str = f"£{product['price']:.2f}"
        if product['discount_percentage'] > 0:
            discounted = product['price'] * (1 - product['discount_percentage'] / 100)
            price_str = f"£{discounted:.2f} (was £{product['price']:.2f})"

        print(f"\n{i}. {product['name']} ({product['category_name']})")
        if product['brand']:
            print(f"   Brand: {product['brand']}")
        print(f"   Price: {price_str}")
        print(f"   Stock: {product['stock_quantity']}")

    print("\nEnter product number to add to cart (or 0 to go back):")
    choice = input("Choice: ").strip()

    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(products):
            product = products[idx]
            if product['stock_quantity'] <= 0:
                print("Sorry, this product is out of stock.")
                return

            qty = input(f"Quantity (max {product['stock_quantity']}): ").strip()
            quantity = int(qty) if qty and qty.isdigit() else 1

            if add_to_cart(user_id, product['product_id'], quantity):
                print(f"Added {quantity}x {product['name']} to cart!")


def view_and_manage_cart(user_id: int):
    """View and manage cart"""
    while True:
        items, subtotal = view_cart(user_id)

        if not items:
            print("\nYour cart is empty.")
            return

        print(f"\n{'=' * 50}")
        print("   Your Shopping Cart")
        print(f"{'=' * 50}")

        for i, item in enumerate(items, 1):
            price = item['price']
            if item['discount_percentage'] > 0:
                price = price * (1 - item['discount_percentage'] / 100)
            line_total = price * item['quantity']

            print(f"\n{i}. {item['name']}")
            if item['brand']:
                print(f"   Brand: {item['brand']}")
            print(f"   Qty: {item['quantity']} x £{price:.2f} = £{line_total:.2f}")
            if item['discount_percentage'] > 0:
                print(f"   ({item['discount_percentage']}% discount applied)")

        print("-" * 40)
        print(f"Subtotal: £{subtotal:.2f}")

        print("\n1. Checkout")
        print("2. Update Quantities")
        print("3. Remove Item")
        print("4. Clear Cart")
        print("5. Continue Shopping")
        print("6. Back")

        choice = input("Choice: ").strip()

        if choice == '1':
            process_checkout(user_id)
            break
        elif choice == '2':
            item_num = input("Item number to update: ").strip()
            if item_num.isdigit():
                idx = int(item_num) - 1
                if 0 <= idx < len(items):
                    new_qty = input("New quantity (0 to remove): ").strip()
                    if new_qty.isdigit():
                        update_cart_quantity(user_id, items[idx]['product_id'], int(new_qty))
        elif choice == '3':
            item_num = input("Item number to remove: ").strip()
            if item_num.isdigit():
                idx = int(item_num) - 1
                if 0 <= idx < len(items):
                    update_cart_quantity(user_id, items[idx]['product_id'], 0)
                    print(f"Removed {items[idx]['name']} from cart.")
        elif choice == '4':
            confirm = input("Clear entire cart? (y/n): ").strip().lower()
            if confirm == 'y':
                clear_cart(user_id)
                print("Cart cleared.")
                break
        elif choice == '5':
            browse_products(user_id)
        elif choice == '6':
            break


def process_checkout(user_id: int):
    """Process checkout"""
    items, subtotal = view_cart(user_id)

    if not items:
        print("Cart is empty!")
        return

    print("\n" + "=" * 40)
    print("       CHECKOUT")
    print("=" * 40)

    print(f"\nTotal: £{subtotal:.2f}")

    print("\nPayment Method:")
    print("1. Card")
    print("2. Student Account")
    print("3. Cash")

    payment_choice = input("Choice: ").strip()
    payment_methods = {'1': 'card', '2': 'student_account', '3': 'cash'}
    payment_method = payment_methods.get(payment_choice, 'card')

    print("\nProcessing payment...")
    transaction_id = checkout(user_id, payment_method)

    if transaction_id:
        transaction, items = get_transaction_details(transaction_id)

        print(f"\n{'*' * 40}")
        print("   PURCHASE COMPLETE")
        print(f"{'*' * 40}")
        print(f"\nReceipt: {transaction['receipt_number']}")
        print(f"Date: {transaction['transaction_date']}")
        print("-" * 40)

        for item in items:
            print(f"{item['product_name']} x{item['quantity']}")
            print(f"   £{item['subtotal']:.2f}")

        print("-" * 40)
        print(f"Total: £{transaction['total_amount']:.2f}")
        print(f"Payment: {transaction['payment_method'].title()}")
        print("\nThank you for shopping with us!")
    else:
        print("Checkout failed. Please try again.")


def view_purchase_history(user_id: int):
    """View purchase history"""
    transactions = get_purchase_history(user_id)

    if not transactions:
        print("\nNo purchase history found.")
        return

    while True:
        print("\n" + "=" * 50)
        print("       PURCHASE HISTORY")
        print("=" * 50)

        for i, t in enumerate(transactions, 1):
            print(f"\n{i}. {t['receipt_number']}")
            print(f"   Date: {t['transaction_date']}")
            print(f"   Total: £{t['total_amount']:.2f}")

        print(f"\n{len(transactions) + 1}. Back")

        choice = input("\nSelect transaction for details: ").strip()

        try:
            idx = int(choice) - 1
            if idx == len(transactions):
                break
            if idx < 0 or idx >= len(transactions):
                print("Invalid choice.")
                continue

            transaction, items = get_transaction_details(transactions[idx]['transaction_id'])

            if transaction:
                print(f"\n{'=' * 50}")
                print(f"Receipt: {transaction['receipt_number']}")
                print(f"{'=' * 50}")
                print(f"Date: {transaction['transaction_date']}")
                print(f"Payment: {transaction['payment_method'].title()}")

                print("\nItems:")
                for item in items:
                    print(f"  - {item['product_name']} x{item['quantity']} = £{item['subtotal']:.2f}")

                print(f"\nTotal: £{transaction['total_amount']:.2f}")

                input("\nPress Enter to continue...")

        except ValueError:
            print("Invalid choice.")


def manage_products():
    """Admin function to manage products"""
    print("\nProduct Management")
    print("1. Add New Product")
    print("2. Edit Product")
    print("3. Toggle Product Availability")
    print("4. Update Prices")
    print("5. Back")

    choice = input("Choice: ").strip()
    # Implementation details here


def manage_inventory():
    """Admin function to manage inventory"""
    while True:
        print("\n" + "=" * 40)
        print("INVENTORY MANAGEMENT")
        print("=" * 40)
        print("1. View Low Stock Items")
        print("2. Restock Product")
        print("3. Stock Report")
        print("4. Back")

        choice = input("Choice: ").strip()

        if choice == '1':
            products = get_low_stock_products()
            if not products:
                print("\nNo low stock items.")
            else:
                print("\nLow Stock Items:")
                print("-" * 40)
                for p in products:
                    print(f"{p['product_id']}: {p['name']}")
                    print(f"   Stock: {p['stock_quantity']} (min: {p['min_stock_level']})")

        elif choice == '2':
            product_id = input("Product ID: ").strip()
            quantity = input("Quantity to add: ").strip()
            if quantity.isdigit():
                if restock_product(product_id, int(quantity)):
                    print("Product restocked successfully!")

        elif choice == '3':
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT p.source_product_id as product_id, p.name, p.stock_quantity, p.min_stock_level,
                           c.name as category
                    FROM products p
                    JOIN grocery_categories c ON p.category_id = c.category_id
                    WHERE p.source_type = 'grocery'
                    ORDER BY p.stock_quantity
                ''')
                products = cursor.fetchall()
                conn.close()

                print("\nStock Report:")
                print("-" * 60)
                print(f"{'ID':<8} {'Product':<25} {'Stock':<8} {'Min':<8} {'Status'}")
                print("-" * 60)
                for p in products:
                    status = "OK" if p[2] > p[3] else "LOW" if p[2] > 0 else "OUT"
                    print(f"{p[0]:<8} {p[1][:25]:<25} {p[2]:<8} {p[3]:<8} {status}")

            except sqlite3.Error as e:
                print(f"Error: {e}")

        elif choice == '4':
            break

        input("\nPress Enter to continue...")


def view_all_transactions():
    """Admin function to view all transactions"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT *, created_at as transaction_date, status as payment_status FROM transactions
            WHERE source_type = 'grocery'
            ORDER BY created_at DESC
            LIMIT 50
        ''')
        transactions = [dict(row) for row in cursor.fetchall()]
        conn.close()

        if not transactions:
            print("\nNo transactions found.")
            return

        print(f"\n{'=' * 70}")
        print("ALL TRANSACTIONS (Most Recent 50)")
        print(f"{'=' * 70}")

        for t in transactions:
            print(f"\n{t['receipt_number']} | {t['transaction_date']}")
            print(f"   Total: £{t['total_amount']:.2f} | Payment: {t['payment_method']}")
            print(f"   Status: {t['payment_status']}")

        input("\nPress Enter to continue...")

    except sqlite3.Error as e:
        print(f"Error: {e}")


def generate_reports():
    """Generate grocery reports"""
    print("\n" + "=" * 40)
    print("GROCERY SHOP REPORTS")
    print("=" * 40)
    print("1. Daily Sales Summary")
    print("2. Category Sales")
    print("3. Best Selling Products")
    print("4. Revenue Report")
    print("5. Back")

    choice = input("Choice: ").strip()

    try:
        conn = get_connection()
        cursor = conn.cursor()

        if choice == '1':
            cursor.execute('''
                SELECT DATE(created_at) as date,
                       COUNT(*) as transactions,
                       SUM(total_amount) as revenue
                FROM transactions
                WHERE source_type = 'grocery' AND status = 'completed'
                GROUP BY DATE(created_at)
                ORDER BY date DESC
                LIMIT 30
            ''')
            results = cursor.fetchall()
            print("\nDaily Sales (Last 30 days):")
            print("-" * 50)
            for row in results:
                print(f"{row[0]}: {row[1]} transactions, £{row[2]:.2f} revenue")

        elif choice == '2':
            cursor.execute('''
                SELECT c.name as category,
                       COUNT(ti.id) as items_sold,
                       SUM(ti.subtotal) as revenue
                FROM grocery_transaction_items ti
                JOIN products p ON ti.product_id = p.source_product_id AND p.source_type = 'grocery'
                JOIN grocery_categories c ON p.category_id = c.category_id
                GROUP BY c.category_id
                ORDER BY revenue DESC
            ''')
            results = cursor.fetchall()
            print("\nSales by Category:")
            print("-" * 50)
            for row in results:
                print(f"{row[0]}: {row[1]} items, £{row[2]:.2f}")

        elif choice == '3':
            cursor.execute('''
                SELECT product_name,
                       SUM(quantity) as total_qty,
                       SUM(subtotal) as revenue
                FROM grocery_transaction_items
                GROUP BY product_id
                ORDER BY total_qty DESC
                LIMIT 20
            ''')
            results = cursor.fetchall()
            print("\nTop 20 Best Sellers:")
            print("-" * 50)
            for i, row in enumerate(results, 1):
                print(f"{i}. {row[0]}: {row[1]} sold, £{row[2]:.2f}")

        elif choice == '4':
            cursor.execute('''
                SELECT
                    COUNT(*) as total_transactions,
                    SUM(subtotal) as gross_revenue,
                    SUM(discount_amount) as total_discounts,
                    SUM(total_amount) as net_revenue
                FROM transactions
                WHERE source_type = 'grocery' AND status = 'completed'
            ''')
            result = cursor.fetchone()
            print("\nRevenue Summary:")
            print("-" * 50)
            print(f"Total Transactions: {result[0]}")
            print(f"Gross Revenue: £{result[1]:.2f}")
            print(f"Total Discounts: £{result[2]:.2f}")
            print(f"Net Revenue: £{result[3]:.2f}")

        conn.close()
        input("\nPress Enter to continue...")

    except sqlite3.Error as e:
        print(f"Error generating report: {e}")
