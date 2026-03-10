"""
Takeaway System Service
Campus food ordering and delivery management
"""

from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple
import uuid

from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from education_system.university_system.modules.shared.utils.simple_activity_logger import (
    log_dynamic_activity as log_activity,
    log_menu_navigation,
)

# Import i18n for internationalization
from education_system.university_system.modules.shared.utils.i18n import (
    get_text,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)

try:
    from education_system.university_system.infrastructure.auth import get_current_user, set_auth_instance
    from education_system.university_system.infrastructure.shared_context import get_auth
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None
    get_auth = lambda: None

try:
    from education_system.university_system.modules.shared.utils.finance_integration import record_payment_to_finance
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


def init_takeaway_db() -> bool:
    """Initialize the takeaway database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Create takeaway restaurants table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS takeaway_restaurants (
            restaurant_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            cuisine_type TEXT,
            description TEXT,
            delivery_fee REAL DEFAULT 2.00,
            min_order_amount REAL DEFAULT 10.00,
            estimated_delivery_time INTEGER DEFAULT 30,
            is_open BOOLEAN DEFAULT 1,
            opening_hours TEXT,
            rating REAL DEFAULT 0.0,
            total_orders INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        ''')

        # Create takeaway menu items table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS takeaway_menu_items (
            item_id TEXT PRIMARY KEY,
            restaurant_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            price REAL NOT NULL,
            is_available BOOLEAN DEFAULT 1,
            is_vegetarian BOOLEAN DEFAULT 0,
            is_vegan BOOLEAN DEFAULT 0,
            is_gluten_free BOOLEAN DEFAULT 0,
            calories INTEGER,
            allergens TEXT,
            image_url TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (restaurant_id) REFERENCES takeaway_restaurants (restaurant_id)
        )
        ''')

        # Create takeaway orders table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS takeaway_orders (
            order_id TEXT PRIMARY KEY,
            user_id INTEGER,
            student_id TEXT,
            restaurant_id TEXT NOT NULL,
            order_date TEXT NOT NULL,
            delivery_address TEXT,
            delivery_type TEXT DEFAULT 'delivery',
            subtotal REAL NOT NULL,
            delivery_fee REAL DEFAULT 0.0,
            total_amount REAL NOT NULL,
            payment_method TEXT,
            payment_status TEXT DEFAULT 'pending',
            order_status TEXT DEFAULT 'pending',
            estimated_delivery TEXT,
            actual_delivery TEXT,
            notes TEXT,
            rating INTEGER,
            review TEXT,
            FOREIGN KEY (restaurant_id) REFERENCES takeaway_restaurants (restaurant_id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')

        # Create takeaway order items table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS takeaway_order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            item_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            special_instructions TEXT,
            subtotal REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES takeaway_orders (order_id),
            FOREIGN KEY (item_id) REFERENCES takeaway_menu_items (item_id)
        )
        ''')

        # Create takeaway cart table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS takeaway_cart (
            cart_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            restaurant_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            special_instructions TEXT,
            added_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (restaurant_id) REFERENCES takeaway_restaurants (restaurant_id),
            FOREIGN KEY (item_id) REFERENCES takeaway_menu_items (item_id),
            UNIQUE(user_id, item_id)
        )
        ''')

        # Create delivery addresses table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS takeaway_addresses (
            address_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            label TEXT DEFAULT 'Home',
            building TEXT,
            room_number TEXT,
            address_line TEXT NOT NULL,
            phone TEXT,
            is_default BOOLEAN DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')

        # Insert sample restaurants if none exist
        cursor.execute("SELECT COUNT(*) FROM takeaway_restaurants")
        if cursor.fetchone()[0] == 0:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            restaurants = [
                ('R001', 'Campus Pizza', 'Italian', 'Authentic Italian pizzas and pasta', 2.50, 12.00, 25, 1, '11:00-22:00', 4.5, 0, now, now),
                ('R002', 'Dragon Palace', 'Chinese', 'Traditional Chinese cuisine', 2.00, 10.00, 30, 1, '11:30-21:30', 4.3, 0, now, now),
                ('R003', 'Burger Barn', 'American', 'Gourmet burgers and fries', 1.50, 8.00, 20, 1, '10:00-23:00', 4.6, 0, now, now),
                ('R004', 'Curry House', 'Indian', 'Authentic Indian curries', 2.50, 12.00, 35, 1, '12:00-22:00', 4.4, 0, now, now),
                ('R005', 'Sushi Express', 'Japanese', 'Fresh sushi and Japanese dishes', 3.00, 15.00, 25, 1, '11:00-21:00', 4.7, 0, now, now),
                ('R006', 'Campus Kebab', 'Mediterranean', 'Kebabs, wraps and falafel', 1.50, 8.00, 15, 1, '10:00-02:00', 4.2, 0, now, now),
            ]
            cursor.executemany(
                '''INSERT INTO takeaway_restaurants VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                restaurants
            )

            # Insert sample menu items
            menu_items = [
                # Campus Pizza
                ('M001', 'R001', 'Margherita Pizza', 'Classic tomato and mozzarella', 'Pizza', 9.99, 1, 1, 0, 0, 800, 'Gluten, Dairy', None, now),
                ('M002', 'R001', 'Pepperoni Pizza', 'Pepperoni with mozzarella', 'Pizza', 11.99, 1, 0, 0, 0, 950, 'Gluten, Dairy', None, now),
                ('M003', 'R001', 'Vegetarian Pizza', 'Mixed vegetables and cheese', 'Pizza', 10.99, 1, 1, 0, 0, 750, 'Gluten, Dairy', None, now),
                ('M004', 'R001', 'Garlic Bread', 'Toasted garlic bread', 'Sides', 3.99, 1, 1, 0, 0, 300, 'Gluten, Dairy', None, now),
                ('M005', 'R001', 'Spaghetti Carbonara', 'Creamy pasta with bacon', 'Pasta', 10.99, 1, 0, 0, 0, 850, 'Gluten, Dairy, Eggs', None, now),
                # Dragon Palace
                ('M006', 'R002', 'Sweet & Sour Chicken', 'Crispy chicken in sweet sour sauce', 'Mains', 9.99, 1, 0, 0, 0, 650, 'Soy', None, now),
                ('M007', 'R002', 'Vegetable Chow Mein', 'Stir-fried noodles with vegetables', 'Noodles', 8.99, 1, 1, 1, 0, 500, 'Gluten, Soy', None, now),
                ('M008', 'R002', 'Chicken Fried Rice', 'Egg fried rice with chicken', 'Rice', 8.49, 1, 0, 0, 0, 600, 'Eggs, Soy', None, now),
                ('M009', 'R002', 'Spring Rolls (4)', 'Crispy vegetable spring rolls', 'Starters', 4.99, 1, 1, 1, 0, 300, 'Gluten', None, now),
                # Burger Barn
                ('M010', 'R003', 'Classic Burger', 'Beef patty with lettuce and tomato', 'Burgers', 7.99, 1, 0, 0, 0, 700, 'Gluten, Dairy', None, now),
                ('M011', 'R003', 'Cheese Burger', 'Classic with cheddar cheese', 'Burgers', 8.99, 1, 0, 0, 0, 800, 'Gluten, Dairy', None, now),
                ('M012', 'R003', 'Veggie Burger', 'Plant-based patty', 'Burgers', 8.49, 1, 1, 1, 0, 550, 'Gluten', None, now),
                ('M013', 'R003', 'Fries', 'Crispy golden fries', 'Sides', 3.49, 1, 1, 1, 1, 350, None, None, now),
                ('M014', 'R003', 'Onion Rings', 'Beer-battered onion rings', 'Sides', 3.99, 1, 1, 0, 0, 400, 'Gluten', None, now),
                # Curry House
                ('M015', 'R004', 'Chicken Tikka Masala', 'Creamy tomato-based curry', 'Curry', 11.99, 1, 0, 0, 1, 700, 'Dairy', None, now),
                ('M016', 'R004', 'Vegetable Korma', 'Mild creamy vegetable curry', 'Curry', 9.99, 1, 1, 0, 1, 550, 'Dairy, Nuts', None, now),
                ('M017', 'R004', 'Lamb Biryani', 'Spiced rice with lamb', 'Rice', 12.99, 1, 0, 0, 1, 800, None, None, now),
                ('M018', 'R004', 'Naan Bread', 'Traditional flatbread', 'Sides', 2.49, 1, 1, 0, 0, 250, 'Gluten, Dairy', None, now),
                ('M019', 'R004', 'Onion Bhaji (4)', 'Crispy onion fritters', 'Starters', 4.49, 1, 1, 1, 0, 280, 'Gluten', None, now),
                # Sushi Express
                ('M020', 'R005', 'Salmon Nigiri (4)', 'Fresh salmon on rice', 'Sushi', 8.99, 1, 0, 0, 1, 300, 'Fish', None, now),
                ('M021', 'R005', 'California Roll (8)', 'Crab, avocado, cucumber', 'Rolls', 9.99, 1, 0, 0, 1, 350, 'Shellfish', None, now),
                ('M022', 'R005', 'Vegetable Roll (8)', 'Avocado, cucumber, carrot', 'Rolls', 7.99, 1, 1, 1, 1, 250, None, None, now),
                ('M023', 'R005', 'Miso Soup', 'Traditional miso soup', 'Soup', 3.49, 1, 1, 0, 1, 80, 'Soy, Fish', None, now),
                # Campus Kebab
                ('M024', 'R006', 'Chicken Kebab Wrap', 'Grilled chicken in flatbread', 'Wraps', 6.99, 1, 0, 0, 0, 550, 'Gluten', None, now),
                ('M025', 'R006', 'Lamb Doner', 'Sliced lamb in pitta', 'Kebabs', 7.99, 1, 0, 0, 0, 600, 'Gluten', None, now),
                ('M026', 'R006', 'Falafel Wrap', 'Chickpea falafel with salad', 'Wraps', 5.99, 1, 1, 1, 0, 450, 'Gluten', None, now),
                ('M027', 'R006', 'Halloumi Box', 'Grilled halloumi with chips', 'Boxes', 7.49, 1, 1, 0, 1, 650, 'Dairy', None, now),
            ]
            cursor.executemany(
                '''INSERT INTO takeaway_menu_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                menu_items
            )

        conn.commit()
        conn.close()
        print("Takeaway database initialized successfully!")
        return True

    except sqlite3.Error as e:
        print(f"Error initializing takeaway database: {e}")
        if 'conn' in locals():
            conn.close()
        return False


def setup_takeaway_permissions(auth_instance=None):
    """Setup permissions for the takeaway module"""
    global auth

    if auth_instance:
        auth = auth_instance

    if not auth:
        print("Authentication system not initialized.")
        return False

    try:
        conn = get_connection()
        cursor = conn.cursor()

        takeaway_permissions = [
            ('view_takeaway_restaurants', 'View available takeaway restaurants'),
            ('order_takeaway', 'Place takeaway orders'),
            ('view_own_takeaway_orders', 'View own takeaway order history'),
            ('rate_takeaway_orders', 'Rate and review takeaway orders'),
            ('manage_takeaway_restaurants', 'Add, update, or delete restaurants'),
            ('manage_takeaway_menu', 'Manage restaurant menu items'),
            ('view_all_takeaway_orders', 'View all takeaway orders'),
            ('update_takeaway_order_status', 'Update order delivery status'),
            ('generate_takeaway_reports', 'Generate takeaway sales reports'),
        ]

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        perm_names = [p[0] for p in takeaway_permissions]
        placeholders = ','.join('?' * len(perm_names))
        cursor.execute(
            f'SELECT permission_name FROM permissions WHERE permission_name IN ({placeholders})',
            perm_names
        )
        existing_perms = {row[0] for row in cursor.fetchall()}

        new_perms = [
            (perm_name, perm_desc, timestamp)
            for perm_name, perm_desc in takeaway_permissions
            if perm_name not in existing_perms
        ]
        if new_perms:
            cursor.executemany(
                'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                new_perms
            )

        conn.commit()

        role_permissions = {
            'student': ['view_takeaway_restaurants', 'order_takeaway', 'view_own_takeaway_orders', 'rate_takeaway_orders'],
            'staff': ['view_takeaway_restaurants', 'order_takeaway', 'view_own_takeaway_orders', 'rate_takeaway_orders',
                     'view_all_takeaway_orders'],
            'admin': ['view_takeaway_restaurants', 'order_takeaway', 'view_own_takeaway_orders', 'rate_takeaway_orders',
                     'manage_takeaway_restaurants', 'manage_takeaway_menu', 'view_all_takeaway_orders',
                     'update_takeaway_order_status', 'generate_takeaway_reports'],
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

        print("Takeaway permissions setup successfully!")
        return True

    except Exception as e:
        if 'conn' in locals():
            conn.close()
        print(f"Error setting up takeaway permissions: {e}")
        return False


def get_restaurants() -> List[Dict]:
    """Get all available restaurants"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM takeaway_restaurants
            WHERE is_open = 1
            ORDER BY rating DESC
        ''')
        restaurants = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return restaurants
    except sqlite3.Error as e:
        print(f"Error fetching restaurants: {e}")
        return []


def get_menu_items(restaurant_id: str) -> List[Dict]:
    """Get menu items for a restaurant"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM takeaway_menu_items
            WHERE restaurant_id = ? AND is_available = 1
            ORDER BY category, name
        ''', (restaurant_id,))
        items = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return items
    except sqlite3.Error as e:
        print(f"Error fetching menu items: {e}")
        return []


def add_to_cart(user_id: int, restaurant_id: str, item_id: str, quantity: int = 1, instructions: str = "") -> bool:
    """Add item to cart"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if cart has items from different restaurant
        cursor.execute('SELECT restaurant_id FROM takeaway_cart WHERE user_id = ? LIMIT 1', (user_id,))
        existing = cursor.fetchone()
        if existing and existing[0] != restaurant_id:
            print("Cart contains items from a different restaurant. Please clear cart first.")
            conn.close()
            return False

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Try to update existing item or insert new
        cursor.execute('''
            INSERT INTO takeaway_cart (user_id, restaurant_id, item_id, quantity, special_instructions, added_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, item_id) DO UPDATE SET
                quantity = quantity + excluded.quantity,
                special_instructions = excluded.special_instructions
        ''', (user_id, restaurant_id, item_id, quantity, instructions, now))

        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        print(f"Error adding to cart: {e}")
        return False


def view_cart(user_id: int) -> Tuple[List[Dict], float, str]:
    """View cart contents and total"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT c.*, m.name, m.price, r.name as restaurant_name, r.delivery_fee, r.min_order_amount
            FROM takeaway_cart c
            JOIN takeaway_menu_items m ON c.item_id = m.item_id
            JOIN takeaway_restaurants r ON c.restaurant_id = r.restaurant_id
            WHERE c.user_id = ?
        ''', (user_id,))

        items = [dict(row) for row in cursor.fetchall()]
        conn.close()

        if not items:
            return [], 0.0, ""

        subtotal = sum(item['price'] * item['quantity'] for item in items)
        restaurant_name = items[0]['restaurant_name']
        delivery_fee = items[0]['delivery_fee']
        min_order = items[0]['min_order_amount']

        return items, subtotal, restaurant_name
    except sqlite3.Error as e:
        print(f"Error viewing cart: {e}")
        return [], 0.0, ""


def clear_cart(user_id: int) -> bool:
    """Clear user's cart"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM takeaway_cart WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        print(f"Error clearing cart: {e}")
        return False


def place_order(user_id: int, delivery_address: str, delivery_type: str = 'delivery',
                payment_method: str = 'card', notes: str = "") -> Optional[str]:
    """Place an order from cart"""
    try:
        cart_items, subtotal, restaurant_name = view_cart(user_id)

        if not cart_items:
            print("Cart is empty!")
            return None

        conn = get_connection()
        cursor = conn.cursor()

        restaurant_id = cart_items[0]['restaurant_id']
        delivery_fee = cart_items[0]['delivery_fee'] if delivery_type == 'delivery' else 0
        min_order = cart_items[0]['min_order_amount']

        if subtotal < min_order:
            print(f"Minimum order amount is ${min_order:.2f}")
            conn.close()
            return None

        total = subtotal + delivery_fee
        order_id = f"TO{datetime.now().strftime('%Y%m%d%H%M%S')}{str(uuid.uuid4())[:4].upper()}"
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Get estimated delivery time
        cursor.execute('SELECT estimated_delivery_time FROM takeaway_restaurants WHERE restaurant_id = ?',
                      (restaurant_id,))
        est_time = cursor.fetchone()[0]
        estimated_delivery = (datetime.now() + timedelta(minutes=est_time)).strftime('%Y-%m-%d %H:%M:%S')

        # Get student_id if user is a student
        student_id = None
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (user_id,))
        result = cursor.fetchone()
        if result:
            student_id = result[0]

        # Create order
        cursor.execute('''
            INSERT INTO takeaway_orders
            (order_id, user_id, student_id, restaurant_id, order_date, delivery_address,
             delivery_type, subtotal, delivery_fee, total_amount, payment_method,
             payment_status, order_status, estimated_delivery, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'paid', 'confirmed', ?, ?)
        ''', (order_id, user_id, student_id, restaurant_id, now, delivery_address,
              delivery_type, subtotal, delivery_fee, total, payment_method,
              estimated_delivery, notes))

        # Create order items
        for item in cart_items:
            cursor.execute('''
                INSERT INTO takeaway_order_items
                (order_id, item_id, item_name, quantity, unit_price, special_instructions, subtotal)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (order_id, item['item_id'], item['name'], item['quantity'],
                  item['price'], item['special_instructions'], item['price'] * item['quantity']))

        # Update restaurant order count
        cursor.execute('''
            UPDATE takeaway_restaurants SET total_orders = total_orders + 1 WHERE restaurant_id = ?
        ''', (restaurant_id,))

        # Clear cart
        cursor.execute('DELETE FROM takeaway_cart WHERE user_id = ?', (user_id,))

        conn.commit()
        conn.close()

        log_activity('create', 'takeaway_order', details=f'Order {order_id} placed for ${total:.2f}')

        return order_id

    except sqlite3.Error as e:
        print(f"Error placing order: {e}")
        return None


def get_order_history(user_id: int) -> List[Dict]:
    """Get user's order history"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT o.*, r.name as restaurant_name
            FROM takeaway_orders o
            JOIN takeaway_restaurants r ON o.restaurant_id = r.restaurant_id
            WHERE o.user_id = ?
            ORDER BY o.order_date DESC
        ''', (user_id,))
        orders = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return orders
    except sqlite3.Error as e:
        print(f"Error fetching order history: {e}")
        return []


def get_order_details(order_id: str) -> Tuple[Optional[Dict], List[Dict]]:
    """Get order details with items"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT o.*, r.name as restaurant_name
            FROM takeaway_orders o
            JOIN takeaway_restaurants r ON o.restaurant_id = r.restaurant_id
            WHERE o.order_id = ?
        ''', (order_id,))
        order = cursor.fetchone()

        if not order:
            conn.close()
            return None, []

        cursor.execute('SELECT * FROM takeaway_order_items WHERE order_id = ?', (order_id,))
        items = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return dict(order), items

    except sqlite3.Error as e:
        print(f"Error fetching order details: {e}")
        return None, []


def rate_order(order_id: str, rating: int, review: str = "") -> bool:
    """Rate a completed order"""
    try:
        if rating < 1 or rating > 5:
            print("Rating must be between 1 and 5")
            return False

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE takeaway_orders
            SET rating = ?, review = ?
            WHERE order_id = ? AND order_status = 'delivered'
        ''', (rating, review, order_id))

        if cursor.rowcount == 0:
            print("Order not found or not yet delivered")
            conn.close()
            return False

        # Update restaurant rating
        cursor.execute('SELECT restaurant_id FROM takeaway_orders WHERE order_id = ?', (order_id,))
        restaurant_id = cursor.fetchone()[0]

        cursor.execute('''
            SELECT AVG(rating) FROM takeaway_orders
            WHERE restaurant_id = ? AND rating IS NOT NULL
        ''', (restaurant_id,))
        avg_rating = cursor.fetchone()[0] or 0

        cursor.execute('UPDATE takeaway_restaurants SET rating = ? WHERE restaurant_id = ?',
                      (round(avg_rating, 1), restaurant_id))

        conn.commit()
        conn.close()
        return True

    except sqlite3.Error as e:
        print(f"Error rating order: {e}")
        return False


@log_menu_navigation(description="Displaying takeaway main menu")
def display_takeaway_menu():
    """Display the main menu for the takeaway system"""
    global auth

    if not auth or not auth.current_user:
        print(get_text('takeaway.not_logged_in', default='You must be logged in to access the takeaway system.'))
        return

    # Initialize database if needed
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='takeaway_restaurants'")
        if not cursor.fetchone():
            conn.close()
            print("Takeaway database not initialized. Initializing now...")
            if not init_takeaway_db():
                print("Failed to initialize takeaway database.")
                return
        else:
            conn.close()
    except sqlite3.Error:
        if not init_takeaway_db():
            print("Failed to initialize takeaway database.")
            return

    user_id = auth.current_user.get('id')

    while True:
        print("\n" + "=" * 50)
        print(f"       {get_text('takeaway.title', default='CAMPUS TAKEAWAY ORDERING SYSTEM')}")
        print("=" * 50)

        options = []
        option_num = 1

        if auth.check_permission('view_takeaway_restaurants'):
            print(f"{option_num}. {get_text('takeaway.menu.browse', default='Browse Restaurants')}")
            options.append('browse')
            option_num += 1

        if auth.check_permission('order_takeaway'):
            print(f"{option_num}. {get_text('takeaway.menu.cart', default='View Cart')}")
            options.append('cart')
            option_num += 1

        if auth.check_permission('view_own_takeaway_orders'):
            print(f"{option_num}. {get_text('takeaway.menu.history', default='Order History')}")
            options.append('history')
            option_num += 1

        if auth.check_permission('manage_takeaway_restaurants'):
            print(f"{option_num}. {get_text('takeaway.menu.manage', default='Manage Restaurants')}")
            options.append('manage_restaurants')
            option_num += 1

        if auth.check_permission('view_all_takeaway_orders'):
            print(f"{option_num}. {get_text('takeaway.menu.all_orders', default='View All Orders')}")
            options.append('all_orders')
            option_num += 1

        if auth.check_permission('generate_takeaway_reports'):
            print(f"{option_num}. {get_text('takeaway.menu.reports', default='Generate Reports')}")
            options.append('reports')
            option_num += 1

        # Language option
        print(f"{option_num}. {get_text('takeaway.menu.language', default='Language')}")
        options.append('language')
        option_num += 1

        print(f"{option_num}. {get_text('takeaway.menu.return', default='Return to Main Menu')}")
        options.append('exit')

        choice = input(f"\n{get_text('takeaway.prompt.choice', default='Enter your choice')}: ").strip()

        try:
            choice_idx = int(choice) - 1
            if choice_idx < 0 or choice_idx >= len(options):
                print(get_text('takeaway.invalid_choice', default='Invalid choice. Please try again.'))
                continue

            selected = options[choice_idx]

            if selected == 'browse':
                browse_restaurants(user_id)
            elif selected == 'cart':
                view_and_manage_cart(user_id)
            elif selected == 'history':
                view_order_history(user_id)
            elif selected == 'manage_restaurants':
                manage_restaurants()
            elif selected == 'all_orders':
                view_all_orders()
            elif selected == 'reports':
                generate_reports()
            elif selected == 'language':
                display_language_menu_option()
            elif selected == 'exit':
                print(get_text('takeaway.returning', default='Returning to main menu...'))
                break

        except ValueError:
            print(get_text('takeaway.invalid_input', default='Invalid choice. Please enter a number.'))


def browse_restaurants(user_id: int):
    """Browse restaurants and order"""
    restaurants = get_restaurants()

    if not restaurants:
        print("No restaurants available at the moment.")
        return

    while True:
        print("\n" + "-" * 40)
        print("Available Restaurants:")
        print("-" * 40)

        for i, r in enumerate(restaurants, 1):
            status = "OPEN" if r['is_open'] else "CLOSED"
            print(f"{i}. {r['name']} ({r['cuisine_type']})")
            print(f"   Rating: {'*' * int(r['rating'])} ({r['rating']:.1f})")
            print(f"   Delivery: ${r['delivery_fee']:.2f} | Min order: ${r['min_order_amount']:.2f}")
            print(f"   Est. delivery: {r['estimated_delivery_time']} mins | {status}")
            print()

        print(f"{len(restaurants) + 1}. Back to Menu")

        choice = input("Select a restaurant: ").strip()

        try:
            choice_idx = int(choice) - 1
            if choice_idx == len(restaurants):
                break
            if choice_idx < 0 or choice_idx >= len(restaurants):
                print("Invalid choice.")
                continue

            browse_menu(user_id, restaurants[choice_idx])

        except ValueError:
            print("Invalid choice. Please enter a number.")


def browse_menu(user_id: int, restaurant: Dict):
    """Browse restaurant menu and add items to cart"""
    items = get_menu_items(restaurant['restaurant_id'])

    if not items:
        print("No menu items available.")
        return

    # Group by category
    categories = {}
    for item in items:
        cat = item['category'] or 'Other'
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(item)

    while True:
        print(f"\n{'=' * 50}")
        print(f"   {restaurant['name']} - Menu")
        print(f"{'=' * 50}")

        item_list = []
        idx = 1
        for category, cat_items in categories.items():
            print(f"\n  {category}")
            print("  " + "-" * 30)
            for item in cat_items:
                dietary = []
                if item['is_vegetarian']:
                    dietary.append('V')
                if item['is_vegan']:
                    dietary.append('VG')
                if item['is_gluten_free']:
                    dietary.append('GF')
                dietary_str = f" [{', '.join(dietary)}]" if dietary else ""

                print(f"  {idx}. {item['name']} - ${item['price']:.2f}{dietary_str}")
                if item['description']:
                    print(f"      {item['description']}")
                item_list.append(item)
                idx += 1

        print(f"\n  {idx}. View Cart")
        print(f"  {idx + 1}. Back to Restaurants")

        choice = input("\nSelect item to add (or action): ").strip()

        try:
            choice_num = int(choice)
            if choice_num == idx:
                view_and_manage_cart(user_id)
                continue
            if choice_num == idx + 1:
                break
            if choice_num < 1 or choice_num > len(item_list):
                print("Invalid choice.")
                continue

            selected_item = item_list[choice_num - 1]

            qty = input(f"Quantity for {selected_item['name']} (default 1): ").strip()
            quantity = int(qty) if qty else 1

            instructions = input("Special instructions (optional): ").strip()

            if add_to_cart(user_id, restaurant['restaurant_id'], selected_item['item_id'], quantity, instructions):
                print(f"Added {quantity}x {selected_item['name']} to cart!")

        except ValueError:
            print("Invalid input. Please enter a number.")


def view_and_manage_cart(user_id: int):
    """View and manage cart"""
    while True:
        items, subtotal, restaurant_name = view_cart(user_id)

        if not items:
            print("\nYour cart is empty.")
            return

        print(f"\n{'=' * 50}")
        print(f"   Your Cart - {restaurant_name}")
        print(f"{'=' * 50}")

        delivery_fee = items[0]['delivery_fee']
        min_order = items[0]['min_order_amount']

        for i, item in enumerate(items, 1):
            line_total = item['price'] * item['quantity']
            print(f"{i}. {item['name']} x{item['quantity']} - ${line_total:.2f}")
            if item['special_instructions']:
                print(f"   Note: {item['special_instructions']}")

        print("-" * 40)
        print(f"Subtotal: ${subtotal:.2f}")
        print(f"Delivery Fee: ${delivery_fee:.2f}")
        print(f"Total: ${subtotal + delivery_fee:.2f}")

        if subtotal < min_order:
            print(f"\n*** Minimum order: ${min_order:.2f} (add ${min_order - subtotal:.2f} more) ***")

        print("\n1. Checkout")
        print("2. Clear Cart")
        print("3. Back")

        choice = input("Choice: ").strip()

        if choice == '1':
            if subtotal < min_order:
                print(f"Please add at least ${min_order - subtotal:.2f} more to order.")
                continue
            checkout(user_id)
            break
        elif choice == '2':
            confirm = input("Clear cart? (y/n): ").strip().lower()
            if confirm == 'y':
                clear_cart(user_id)
                print("Cart cleared.")
                break
        elif choice == '3':
            break


def checkout(user_id: int):
    """Checkout process"""
    print("\n" + "=" * 40)
    print("       CHECKOUT")
    print("=" * 40)

    print("\nDelivery Type:")
    print("1. Delivery")
    print("2. Collection")

    delivery_choice = input("Choice (1/2): ").strip()
    delivery_type = 'collection' if delivery_choice == '2' else 'delivery'

    delivery_address = ""
    if delivery_type == 'delivery':
        print("\nEnter delivery address:")
        building = input("Building/Hall name: ").strip()
        room = input("Room number (optional): ").strip()
        delivery_address = f"{building}" + (f", Room {room}" if room else "")

    print("\nPayment Method:")
    print("1. Card")
    print("2. Student Account")
    print("3. Cash on Delivery")

    payment_choice = input("Choice: ").strip()
    payment_methods = {'1': 'card', '2': 'student_account', '3': 'cash'}
    payment_method = payment_methods.get(payment_choice, 'card')

    notes = input("\nOrder notes (optional): ").strip()

    print("\nPlacing order...")
    order_id = place_order(user_id, delivery_address, delivery_type, payment_method, notes)

    if order_id:
        print(f"\n{'*' * 40}")
        print(f"Order placed successfully!")
        print(f"Order ID: {order_id}")
        print(f"{'*' * 40}")

        order, items = get_order_details(order_id)
        if order:
            print(f"\nRestaurant: {order['restaurant_name']}")
            print(f"Type: {order['delivery_type'].title()}")
            if order['delivery_address']:
                print(f"Address: {order['delivery_address']}")
            print(f"Estimated: {order['estimated_delivery']}")
            print(f"Total: ${order['total_amount']:.2f}")
    else:
        print("Failed to place order. Please try again.")


def view_order_history(user_id: int):
    """View order history"""
    orders = get_order_history(user_id)

    if not orders:
        print("\nNo order history found.")
        return

    while True:
        print("\n" + "=" * 50)
        print("       ORDER HISTORY")
        print("=" * 50)

        for i, order in enumerate(orders, 1):
            print(f"\n{i}. Order #{order['order_id']}")
            print(f"   {order['restaurant_name']} - {order['order_date']}")
            print(f"   Total: ${order['total_amount']:.2f} | Status: {order['order_status'].upper()}")
            if order['rating']:
                print(f"   Rating: {'*' * order['rating']}")

        print(f"\n{len(orders) + 1}. Back")

        choice = input("\nSelect order for details (or back): ").strip()

        try:
            idx = int(choice) - 1
            if idx == len(orders):
                break
            if idx < 0 or idx >= len(orders):
                print("Invalid choice.")
                continue

            order = orders[idx]
            order_detail, items = get_order_details(order['order_id'])

            if order_detail:
                print(f"\n{'=' * 50}")
                print(f"Order Details - {order_detail['order_id']}")
                print(f"{'=' * 50}")
                print(f"Restaurant: {order_detail['restaurant_name']}")
                print(f"Date: {order_detail['order_date']}")
                print(f"Status: {order_detail['order_status'].upper()}")
                print(f"Delivery: {order_detail['delivery_type'].title()}")
                if order_detail['delivery_address']:
                    print(f"Address: {order_detail['delivery_address']}")

                print("\nItems:")
                for item in items:
                    print(f"  - {item['item_name']} x{item['quantity']} = ${item['subtotal']:.2f}")

                print(f"\nSubtotal: ${order_detail['subtotal']:.2f}")
                print(f"Delivery Fee: ${order_detail['delivery_fee']:.2f}")
                print(f"Total: ${order_detail['total_amount']:.2f}")

                if order_detail['order_status'] == 'delivered' and not order_detail['rating']:
                    rate = input("\nRate this order? (1-5, or skip): ").strip()
                    if rate.isdigit() and 1 <= int(rate) <= 5:
                        review = input("Add a review (optional): ").strip()
                        if rate_order(order_detail['order_id'], int(rate), review):
                            print("Thank you for your rating!")

                input("\nPress Enter to continue...")

        except ValueError:
            print("Invalid choice.")


def manage_restaurants():
    """Admin function to manage restaurants"""
    print("\nRestaurant Management")
    print("1. Add Restaurant")
    print("2. Edit Restaurant")
    print("3. Toggle Restaurant Status")
    print("4. Back")

    choice = input("Choice: ").strip()
    # Implementation would go here


def view_all_orders():
    """Admin function to view all orders"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT o.*, r.name as restaurant_name
            FROM takeaway_orders o
            JOIN takeaway_restaurants r ON o.restaurant_id = r.restaurant_id
            ORDER BY o.order_date DESC
            LIMIT 50
        ''')
        orders = [dict(row) for row in cursor.fetchall()]
        conn.close()

        if not orders:
            print("\nNo orders found.")
            return

        print(f"\n{'=' * 70}")
        print("ALL ORDERS (Most Recent 50)")
        print(f"{'=' * 70}")

        for order in orders:
            print(f"\n{order['order_id']} | {order['restaurant_name']}")
            print(f"   Date: {order['order_date']} | Total: ${order['total_amount']:.2f}")
            print(f"   Status: {order['order_status']} | Payment: {order['payment_status']}")

        input("\nPress Enter to continue...")

    except sqlite3.Error as e:
        print(f"Error: {e}")


def generate_reports():
    """Generate takeaway reports"""
    print("\n" + "=" * 40)
    print("TAKEAWAY REPORTS")
    print("=" * 40)
    print("1. Daily Sales Summary")
    print("2. Restaurant Performance")
    print("3. Popular Items")
    print("4. Back")

    choice = input("Choice: ").strip()

    try:
        conn = get_connection()
        cursor = conn.cursor()

        if choice == '1':
            cursor.execute('''
                SELECT DATE(order_date) as date, COUNT(*) as orders, SUM(total_amount) as revenue
                FROM takeaway_orders
                WHERE payment_status = 'paid'
                GROUP BY DATE(order_date)
                ORDER BY date DESC
                LIMIT 30
            ''')
            results = cursor.fetchall()
            print("\nDaily Sales (Last 30 days):")
            print("-" * 40)
            for row in results:
                print(f"{row[0]}: {row[1]} orders, ${row[2]:.2f} revenue")

        elif choice == '2':
            cursor.execute('''
                SELECT r.name, r.rating, COUNT(o.order_id) as orders,
                       COALESCE(SUM(o.total_amount), 0) as revenue
                FROM takeaway_restaurants r
                LEFT JOIN takeaway_orders o ON r.restaurant_id = o.restaurant_id
                GROUP BY r.restaurant_id
                ORDER BY revenue DESC
            ''')
            results = cursor.fetchall()
            print("\nRestaurant Performance:")
            print("-" * 40)
            for row in results:
                print(f"{row[0]}: Rating {row[1]:.1f}, {row[2]} orders, ${row[3]:.2f}")

        elif choice == '3':
            cursor.execute('''
                SELECT item_name, SUM(quantity) as total_qty, SUM(subtotal) as revenue
                FROM takeaway_order_items
                GROUP BY item_id
                ORDER BY total_qty DESC
                LIMIT 20
            ''')
            results = cursor.fetchall()
            print("\nTop 20 Popular Items:")
            print("-" * 40)
            for i, row in enumerate(results, 1):
                print(f"{i}. {row[0]}: {row[1]} sold, ${row[2]:.2f}")

        conn.close()
        input("\nPress Enter to continue...")

    except sqlite3.Error as e:
        print(f"Error generating report: {e}")
