#!/usr/bin/env python3
"""
Phone Shop CLI - Mobile Phone & Accessories Shop
Features: Product catalog, shopping cart, order processing, inventory management
"""

from datetime import datetime
from pathlib import Path

try:
    from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
except ImportError:
    DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "db_files" / "student_records.db"

try:
    from education_system.university_system.infrastructure.database.db import get_connection
except ImportError:
    from education_system.university_system.infrastructure.database.db import sqlite3
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))

try:
    from education_system.university_system.infrastructure.shared_context import get_current_user as get_user
except ImportError:
    get_user = None

try:
    from education_system.university_system.infrastructure.email.email_service import send_email_as_system
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    send_email_as_system = None

# Phone categories
PHONE_CATEGORIES = ["Smartphone", "Feature Phone", "Accessories", "Cases", "Chargers", "Headphones", "Screen Protectors"]

# Order statuses
ORDER_STATUSES = ["Pending", "Processing", "Shipped", "Delivered", "Cancelled"]

PHONE_SHOP_SCHEMA = """
CREATE TABLE IF NOT EXISTS phoneshop_products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    brand TEXT,
    category TEXT NOT NULL,
    price REAL NOT NULL,
    stock INTEGER DEFAULT 0,
    description TEXT,
    created_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS phoneshop_orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_number TEXT UNIQUE NOT NULL,
    customer_name TEXT NOT NULL,
    customer_email TEXT,
    customer_phone TEXT,
    student_id TEXT,
    total_amount REAL NOT NULL,
    payment_method TEXT,
    payment_status TEXT DEFAULT 'Pending',
    order_status TEXT DEFAULT 'Pending',
    order_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS phoneshop_order_items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    subtotal REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES phoneshop_orders (order_id),
    FOREIGN KEY (product_id) REFERENCES phoneshop_products (product_id)
);
"""

def init_phoneshop_database():
    """Initialize phone shop database tables."""
    try:
        with get_connection() as conn:
            conn.executescript(PHONE_SHOP_SCHEMA)

            # Insert sample products if none exist
            cursor = conn.execute("SELECT COUNT(*) FROM phoneshop_products")
            if cursor.fetchone()[0] == 0:
                sample_products = [
                    ("PHN001", "iPhone 15 Pro", "Apple", "Smartphone", 999.00, 15, "Latest flagship phone"),
                    ("PHN002", "iPhone 15", "Apple", "Smartphone", 799.00, 20, "Standard model"),
                    ("PHN003", "Samsung Galaxy S24 Ultra", "Samsung", "Smartphone", 1199.00, 12, "Premium Android phone"),
                    ("PHN004", "Samsung Galaxy S24", "Samsung", "Smartphone", 899.00, 18, "Standard flagship"),
                    ("PHN005", "Google Pixel 8 Pro", "Google", "Smartphone", 999.00, 10, "Pure Android experience"),
                    ("PHN006", "OnePlus 12", "OnePlus", "Smartphone", 699.00, 14, "High performance value"),
                    ("ACC001", "AirPods Pro 2", "Apple", "Headphones", 249.00, 30, "Premium wireless earbuds"),
                    ("ACC002", "Galaxy Buds Pro", "Samsung", "Headphones", 199.00, 25, "Premium Samsung earbuds"),
                    ("ACC003", "iPhone Silicone Case", "Apple", "Cases", 49.00, 50, "Official protective case"),
                    ("ACC004", "USB-C Cable", "Generic", "Chargers", 19.00, 100, "Fast charging cable"),
                    ("ACC005", "Wireless Charger", "Generic", "Chargers", 39.00, 40, "Qi wireless charging pad"),
                    ("ACC006", "Tempered Glass Screen Protector", "Generic", "Screen Protectors", 12.00, 80, "9H hardness protection"),
                ]
                for product in sample_products:
                    conn.execute("""
                        INSERT INTO phoneshop_products
                        (sku, name, brand, category, price, stock, description, created_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (*product, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            conn.commit()
        return True
    except Exception as e:
        print(f"Error initializing database: {e}")
        return False

def get_current_user():
    """Get the current authenticated user."""
    if get_user:
        user = get_user()
        if user:
            return user
    return {"username": "guest", "role": "guest", "email": "", "id": None, "name": "Guest User"}

def generate_order_number():
    """Generate unique order number."""
    return f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"

# ==================== PRODUCT MANAGEMENT ====================

def get_all_products(category=None, search=None):
    """Get all products, optionally filtered."""
    try:
        with get_connection() as conn:
            if category and category != 'All':
                cursor = conn.execute("""
                    SELECT product_id, sku, name, brand, category, price, stock
                    FROM phoneshop_products WHERE category = ?
                    ORDER BY category, name
                """, (category,))
            elif search:
                cursor = conn.execute("""
                    SELECT product_id, sku, name, brand, category, price, stock
                    FROM phoneshop_products
                    WHERE name LIKE ? OR brand LIKE ?
                    ORDER BY category, name
                """, (f'%{search}%', f'%{search}%'))
            else:
                cursor = conn.execute("""
                    SELECT product_id, sku, name, brand, category, price, stock
                    FROM phoneshop_products
                    ORDER BY category, name
                """)

            products = []
            for row in cursor.fetchall():
                products.append({
                    'product_id': row[0], 'sku': row[1], 'name': row[2],
                    'brand': row[3], 'category': row[4], 'price': row[5], 'stock': row[6]
                })
            return products
    except Exception as e:
        print(f"Error getting products: {e}")
        return []

def get_product_by_id(product_id):
    """Get specific product by ID."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT product_id, sku, name, brand, category, price, stock, description
                FROM phoneshop_products WHERE product_id = ?
            """, (product_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'product_id': row[0], 'sku': row[1], 'name': row[2],
                    'brand': row[3], 'category': row[4], 'price': row[5],
                    'stock': row[6], 'description': row[7]
                }
    except Exception as e:
        print(f"Error getting product: {e}")
    return None

# ==================== ORDER MANAGEMENT ====================

def create_order(order_data, cart_items):
    """Create a new order with items."""
    try:
        with get_connection() as conn:
            # Create order
            conn.execute("""
                INSERT INTO phoneshop_orders
                (order_number, customer_name, customer_email, customer_phone, student_id,
                 total_amount, payment_method, payment_status, order_status, order_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order_data['order_number'], order_data['customer_name'],
                order_data.get('customer_email', ''), order_data.get('customer_phone', ''),
                order_data.get('student_id', ''), order_data['total_amount'],
                order_data['payment_method'], order_data['payment_status'],
                order_data['order_status'], order_data['order_date']
            ))

            cursor = conn.execute("SELECT last_insert_rowid()")
            order_id = cursor.fetchone()[0]

            # Add order items
            for item in cart_items:
                conn.execute("""
                    INSERT INTO phoneshop_order_items
                    (order_id, product_id, quantity, unit_price, subtotal)
                    VALUES (?, ?, ?, ?, ?)
                """, (order_id, item['product_id'], item['quantity'],
                      item['price'], item['quantity'] * item['price']))

                # Update stock
                conn.execute("""
                    UPDATE phoneshop_products
                    SET stock = stock - ?
                    WHERE product_id = ?
                """, (item['quantity'], item['product_id']))

            conn.commit()
        return True
    except Exception as e:
        print(f"Error creating order: {e}")
        return False

def get_all_orders():
    """Get all orders."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT order_id, order_number, customer_name, total_amount,
                       payment_status, order_status, order_date
                FROM phoneshop_orders
                ORDER BY order_date DESC
            """)
            orders = []
            for row in cursor.fetchall():
                orders.append({
                    'order_id': row[0], 'order_number': row[1], 'customer_name': row[2],
                    'total_amount': row[3], 'payment_status': row[4],
                    'order_status': row[5], 'order_date': row[6]
                })
            return orders
    except Exception as e:
        print(f"Error getting orders: {e}")
        return []

# ==================== CLI INTERFACE ====================

def print_header(title):
    """Print formatted header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

# Shopping cart (global for session)
cart = []

def browse_products_menu():
    """Browse products catalog."""
    print_header("Phone Shop - Product Catalog")

    print("\n  Filter by category:")
    print("    0. All")
    for i, cat in enumerate(PHONE_CATEGORIES, 1):
        print(f"    {i}. {cat}")

    choice = input(f"\n  Select category (0-{len(PHONE_CATEGORIES)} or 's' to search): ").strip().lower()

    if choice == 's':
        search = input("  Enter search term: ").strip()
        products = get_all_products(search=search)
    elif choice == '0':
        products = get_all_products()
    elif choice.isdigit() and 1 <= int(choice) <= len(PHONE_CATEGORIES):
        category = PHONE_CATEGORIES[int(choice) - 1]
        products = get_all_products(category)
    else:
        products = get_all_products()

    if not products:
        print("\n  No products found.")
        return

    print(f"\n  Total products: {len(products)}\n")
    print(f"  {'ID':<5} {'SKU':<10} {'Name':<35} {'Brand':<12} {'Price':<10} {'Stock':<6}")
    print("  " + "-" * 90)

    for product in products:
        name = product['name'][:32] + "..." if len(product['name']) > 35 else product['name']
        print(f"  {product['product_id']:<5} {product['sku']:<10} {name:<35} {product['brand']:<12} £{product['price']:<9.2f} {product['stock']:<6}")

    print()

def add_to_cart_menu():
    """Add product to cart."""
    product_id = input("\n  Enter Product ID to add to cart: ").strip()
    if not product_id.isdigit():
        print("  ❌ Invalid Product ID.")
        return

    product = get_product_by_id(int(product_id))
    if not product:
        print("  ❌ Product not found.")
        return

    if product['stock'] <= 0:
        print("  ❌ Product out of stock.")
        return

    quantity = input(f"  Quantity (available: {product['stock']}): ").strip()
    if not quantity.isdigit() or int(quantity) < 1:
        print("  ❌ Invalid quantity.")
        return

    quantity = int(quantity)
    if quantity > product['stock']:
        print(f"  ❌ Only {product['stock']} units available.")
        return

    # Add to cart
    cart.append({
        'product_id': product['product_id'],
        'name': product['name'],
        'price': product['price'],
        'quantity': quantity
    })

    print(f"\n  ✅ Added {quantity}x {product['name']} to cart!")

def view_cart_menu():
    """View shopping cart."""
    print_header("Shopping Cart")

    if not cart:
        print("\n  Your cart is empty.")
        return

    print(f"\n  Items in cart: {len(cart)}\n")
    print(f"  {'Item':<40} {'Price':<10} {'Qty':<5} {'Subtotal':<10}")
    print("  " + "-" * 70)

    total = 0
    for item in cart:
        subtotal = item['price'] * item['quantity']
        total += subtotal
        name = item['name'][:37] + "..." if len(item['name']) > 40 else item['name']
        print(f"  {name:<40} £{item['price']:<9.2f} {item['quantity']:<5} £{subtotal:<9.2f}")

    print("  " + "-" * 70)
    print(f"  {'TOTAL':<57} £{total:.2f}")
    print()

def checkout_menu():
    """Process checkout."""
    global cart

    if not cart:
        print("\n  ❌ Your cart is empty.")
        return

    current_user = get_current_user()
    default_name = current_user.get('name', '')

    print_header("Checkout")

    view_cart_menu()

    customer_name = input(f"  Customer name [{default_name}]: ").strip() or default_name
    if not customer_name:
        print("  ❌ Customer name is required.")
        return

    customer_email = input("  Customer email (optional): ").strip()
    customer_phone = input("  Customer phone (optional): ").strip()
    student_id = input("  Student ID (if applicable): ").strip()

    print("\n  Payment Methods:")
    print("    1. Cash")
    print("    2. Card")
    print("    3. Student Account")

    payment_choice = input("  Select payment method (1-3): ").strip()
    payment_methods = {'1': 'Cash', '2': 'Card', '3': 'Student Account'}
    payment_method = payment_methods.get(payment_choice, 'Card')

    total_amount = sum(item['price'] * item['quantity'] for item in cart)

    confirm = input(f"\n  Confirm order for £{total_amount:.2f}? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("  Order cancelled.")
        return

    order_data = {
        'order_number': generate_order_number(),
        'customer_name': customer_name,
        'customer_email': customer_email,
        'customer_phone': customer_phone,
        'student_id': student_id,
        'total_amount': total_amount,
        'payment_method': payment_method,
        'payment_status': 'Paid',
        'order_status': 'Processing',
        'order_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    if create_order(order_data, cart):
        print(f"\n  ✅ Order placed successfully!")
        print(f"  Order Number: {order_data['order_number']}")
        print(f"  Total: £{total_amount:.2f}")
        cart = []  # Clear cart
    else:
        print("\n  ❌ Failed to process order.")

def view_orders_menu():
    """View all orders."""
    print_header("Phone Shop - All Orders")

    orders = get_all_orders()

    if not orders:
        print("\n  No orders found.")
        return

    print(f"\n  Total orders: {len(orders)}\n")
    print(f"  {'Order #':<20} {'Customer':<25} {'Amount':<10} {'Payment':<10} {'Status':<12}")
    print("  " + "-" * 85)

    for order in orders:
        customer = order['customer_name'][:22] + "..." if len(order['customer_name']) > 25 else order['customer_name']
        print(f"  {order['order_number']:<20} {customer:<25} £{order['total_amount']:<9.2f} {order['payment_status']:<10} {order['order_status']:<12}")

    print()

def statistics_menu():
    """Show shop statistics."""
    print_header("Phone Shop Statistics")

    products = get_all_products()
    orders = get_all_orders()

    if not products and not orders:
        print("\n  No data available.")
        return

    total_stock = sum(p['stock'] for p in products)
    total_revenue = sum(o['total_amount'] for o in orders)

    print(f"\n  Total Products: {len(products)}")
    print(f"  Total Stock Units: {total_stock}")
    print(f"  Total Orders: {len(orders)}")
    print(f"  Total Revenue: £{total_revenue:.2f}")

    # Products by category
    by_category = {}
    for product in products:
        by_category[product['category']] = by_category.get(product['category'], 0) + 1

    print("\n  Products by Category:")
    for category, count in sorted(by_category.items()):
        print(f"    {category}: {count}")

    print()

def phone_shop_menu():
    """Main phone shop CLI menu."""
    init_phoneshop_database()

    while True:
        print_header("Phone Shop")
        print("\n  1. Browse Products")
        print("  2. Add to Cart")
        print("  3. View Cart")
        print("  4. Checkout")
        print("  5. View All Orders")
        print("  6. View Statistics")
        print("  0. Return to Main Menu")

        choice = input("\n  Enter your choice: ").strip()

        if choice == '1':
            browse_products_menu()
        elif choice == '2':
            add_to_cart_menu()
        elif choice == '3':
            view_cart_menu()
        elif choice == '4':
            checkout_menu()
        elif choice == '5':
            view_orders_menu()
        elif choice == '6':
            statistics_menu()
        elif choice == '0':
            print("\n  Returning to main menu...\n")
            break
        else:
            print("\n  ❌ Invalid choice.")

        if choice != '0':
            input("\n  Press Enter to continue...")

if __name__ == '__main__':
    phone_shop_menu()
