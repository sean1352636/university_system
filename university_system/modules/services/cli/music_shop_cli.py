#!/usr/bin/env python3
"""
Music Shop CLI - Music Store & Instruments Shop
Features: Music catalog, shopping cart, order processing, wishlists
"""

from datetime import datetime
from pathlib import Path

try:
    from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
except ImportError:
    DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "db_files" / "student_records.db"

try:
    from university_system.infrastructure.database.db import get_connection
except ImportError:
    from university_system.infrastructure.database.db import sqlite3
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))

try:
    from university_system.infrastructure.shared_context import get_current_user as get_user
except ImportError:
    get_user = None

try:
    from university_system.infrastructure.email.email_service import send_email_as_system
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    send_email_as_system = None

# Music categories
MUSIC_CATEGORIES = ["Albums", "Singles", "Vinyl", "Instruments", "Accessories", "Sheet Music", "Merchandise"]

# Genres
GENRES = ["Rock", "Pop", "Jazz", "Classical", "Hip Hop", "Electronic", "Country", "R&B", "Metal", "Other"]

# Order statuses
ORDER_STATUSES = ["Pending", "Processing", "Shipped", "Delivered", "Cancelled"]

# Condition types
CONDITION_TYPES = ["New", "Like New", "Very Good", "Good", "Acceptable"]

MUSIC_SHOP_SCHEMA = """
CREATE TABLE IF NOT EXISTS musicshop_products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    artist TEXT,
    category TEXT NOT NULL,
    genre TEXT,
    price REAL NOT NULL,
    stock INTEGER DEFAULT 0,
    condition TEXT DEFAULT 'New',
    description TEXT,
    release_year INTEGER,
    created_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS musicshop_orders (
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

CREATE TABLE IF NOT EXISTS musicshop_order_items (
    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    subtotal REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES musicshop_orders (order_id),
    FOREIGN KEY (product_id) REFERENCES musicshop_products (product_id)
);

CREATE TABLE IF NOT EXISTS musicshop_wishlist (
    wishlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL,
    product_id INTEGER NOT NULL,
    added_date TEXT NOT NULL,
    FOREIGN KEY (product_id) REFERENCES musicshop_products (product_id)
);
"""

def init_musicshop_database():
    """Initialize music shop database tables."""
    try:
        with get_connection() as conn:
            conn.executescript(MUSIC_SHOP_SCHEMA)

            # Insert sample products if none exist
            cursor = conn.execute("SELECT COUNT(*) FROM musicshop_products")
            if cursor.fetchone()[0] == 0:
                sample_products = [
                    ("ALB001", "Abbey Road", "The Beatles", "Albums", "Rock", 24.99, 20, "New", "Classic album", 1969),
                    ("ALB002", "Thriller", "Michael Jackson", "Albums", "Pop", 19.99, 15, "New", "Best-selling album", 1982),
                    ("ALB003", "The Dark Side of the Moon", "Pink Floyd", "Albums", "Rock", 22.99, 18, "New", "Progressive rock masterpiece", 1973),
                    ("VIN001", "Led Zeppelin IV", "Led Zeppelin", "Vinyl", "Rock", 34.99, 10, "New", "Vinyl edition", 1971),
                    ("VIN002", "Kind of Blue", "Miles Davis", "Vinyl", "Jazz", 29.99, 12, "New", "Jazz classic on vinyl", 1959),
                    ("INS001", "Fender Stratocaster", "Fender", "Instruments", "Rock", 899.00, 5, "New", "Electric guitar", 2024),
                    ("INS002", "Yamaha P-125", "Yamaha", "Instruments", "Classical", 649.00, 3, "New", "Digital piano", 2024),
                    ("INS003", "Gibson Les Paul", "Gibson", "Instruments", "Rock", 1299.00, 2, "New", "Classic electric guitar", 2024),
                    ("ACC001", "Guitar Strings Set", "D'Addario", "Accessories", "Rock", 12.99, 50, "New", "Premium strings", 2024),
                    ("ACC002", "Microphone Stand", "K&M", "Accessories", "Pop", 39.99, 25, "New", "Professional stand", 2024),
                    ("ACC003", "Guitar Pick Pack", "Dunlop", "Accessories", "Rock", 4.99, 100, "New", "12-pack assorted picks", 2024),
                    ("SHT001", "Piano Sheet Music - Classical Collection", "Various", "Sheet Music", "Classical", 19.99, 30, "New", "Classical pieces", 2023),
                ]
                for product in sample_products:
                    conn.execute("""
                        INSERT INTO musicshop_products
                        (sku, title, artist, category, genre, price, stock, condition, description, release_year, created_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    return f"MUS-{datetime.now().strftime('%Y%m%d%H%M%S')}"

# ==================== PRODUCT MANAGEMENT ====================

def get_all_products(category=None, genre=None, search=None):
    """Get all products, optionally filtered."""
    try:
        with get_connection() as conn:
            if category and category != 'All':
                cursor = conn.execute("""
                    SELECT product_id, sku, title, artist, category, genre, price, stock, condition
                    FROM musicshop_products WHERE category = ?
                    ORDER BY category, title
                """, (category,))
            elif genre and genre != 'All':
                cursor = conn.execute("""
                    SELECT product_id, sku, title, artist, category, genre, price, stock, condition
                    FROM musicshop_products WHERE genre = ?
                    ORDER BY category, title
                """, (genre,))
            elif search:
                cursor = conn.execute("""
                    SELECT product_id, sku, title, artist, category, genre, price, stock, condition
                    FROM musicshop_products
                    WHERE title LIKE ? OR artist LIKE ?
                    ORDER BY category, title
                """, (f'%{search}%', f'%{search}%'))
            else:
                cursor = conn.execute("""
                    SELECT product_id, sku, title, artist, category, genre, price, stock, condition
                    FROM musicshop_products
                    ORDER BY category, title
                """)

            products = []
            for row in cursor.fetchall():
                products.append({
                    'product_id': row[0], 'sku': row[1], 'title': row[2],
                    'artist': row[3], 'category': row[4], 'genre': row[5],
                    'price': row[6], 'stock': row[7], 'condition': row[8]
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
                SELECT product_id, sku, title, artist, category, genre, price,
                       stock, condition, description, release_year
                FROM musicshop_products WHERE product_id = ?
            """, (product_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'product_id': row[0], 'sku': row[1], 'title': row[2],
                    'artist': row[3], 'category': row[4], 'genre': row[5],
                    'price': row[6], 'stock': row[7], 'condition': row[8],
                    'description': row[9], 'release_year': row[10]
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
                INSERT INTO musicshop_orders
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
                    INSERT INTO musicshop_order_items
                    (order_id, product_id, quantity, unit_price, subtotal)
                    VALUES (?, ?, ?, ?, ?)
                """, (order_id, item['product_id'], item['quantity'],
                      item['price'], item['quantity'] * item['price']))

                # Update stock
                conn.execute("""
                    UPDATE musicshop_products
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
                FROM musicshop_orders
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

# ==================== WISHLIST ====================

def add_to_wishlist(customer_name, product_id):
    """Add product to wishlist."""
    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO musicshop_wishlist (customer_name, product_id, added_date)
                VALUES (?, ?, ?)
            """, (customer_name, product_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error adding to wishlist: {e}")
        return False

def get_wishlist(customer_name):
    """Get customer's wishlist."""
    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                SELECT w.wishlist_id, p.product_id, p.title, p.artist, p.price, p.stock
                FROM musicshop_wishlist w
                JOIN musicshop_products p ON w.product_id = p.product_id
                WHERE w.customer_name = ?
                ORDER BY w.added_date DESC
            """, (customer_name,))
            wishlist = []
            for row in cursor.fetchall():
                wishlist.append({
                    'wishlist_id': row[0], 'product_id': row[1], 'title': row[2],
                    'artist': row[3], 'price': row[4], 'stock': row[5]
                })
            return wishlist
    except Exception as e:
        print(f"Error getting wishlist: {e}")
        return []

# ==================== CLI INTERFACE ====================

def print_header(title):
    """Print formatted header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

# Shopping cart (global for session)
cart = []

def browse_catalog_menu():
    """Browse music catalog."""
    print_header("Music Shop - Catalog")

    print("\n  Browse by:")
    print("    1. Category")
    print("    2. Genre")
    print("    3. Search")

    choice = input("\n  Select option (1-3): ").strip()

    if choice == '1':
        print("\n  Categories:")
        print("    0. All")
        for i, cat in enumerate(MUSIC_CATEGORIES, 1):
            print(f"    {i}. {cat}")

        cat_choice = input(f"\n  Select category (0-{len(MUSIC_CATEGORIES)}): ").strip()
        if cat_choice == '0':
            products = get_all_products()
        elif cat_choice.isdigit() and 1 <= int(cat_choice) <= len(MUSIC_CATEGORIES):
            category = MUSIC_CATEGORIES[int(cat_choice) - 1]
            products = get_all_products(category=category)
        else:
            products = get_all_products()

    elif choice == '2':
        print("\n  Genres:")
        print("    0. All")
        for i, genre in enumerate(GENRES, 1):
            print(f"    {i}. {genre}")

        genre_choice = input(f"\n  Select genre (0-{len(GENRES)}): ").strip()
        if genre_choice == '0':
            products = get_all_products()
        elif genre_choice.isdigit() and 1 <= int(genre_choice) <= len(GENRES):
            genre = GENRES[int(genre_choice) - 1]
            products = get_all_products(genre=genre)
        else:
            products = get_all_products()

    elif choice == '3':
        search = input("  Enter search term: ").strip()
        products = get_all_products(search=search)

    else:
        products = get_all_products()

    if not products:
        print("\n  No products found.")
        return

    print(f"\n  Total products: {len(products)}\n")
    print(f"  {'ID':<5} {'SKU':<10} {'Title':<30} {'Artist':<20} {'Price':<10} {'Stock':<6}")
    print("  " + "-" * 90)

    for product in products[:20]:  # Show first 20
        title = product['title'][:27] + "..." if len(product['title']) > 30 else product['title']
        artist = product['artist'][:17] + "..." if product['artist'] and len(product['artist']) > 20 else (product['artist'] or 'N/A')
        print(f"  {product['product_id']:<5} {product['sku']:<10} {title:<30} {artist:<20} £{product['price']:<9.2f} {product['stock']:<6}")

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
        'title': product['title'],
        'artist': product['artist'],
        'price': product['price'],
        'quantity': quantity
    })

    print(f"\n  ✅ Added {quantity}x {product['title']} to cart!")

def view_cart_menu():
    """View shopping cart."""
    print_header("Shopping Cart")

    if not cart:
        print("\n  Your cart is empty.")
        return

    print(f"\n  Items in cart: {len(cart)}\n")
    print(f"  {'Title':<35} {'Artist':<20} {'Price':<10} {'Qty':<5} {'Subtotal':<10}")
    print("  " + "-" * 85)

    total = 0
    for item in cart:
        subtotal = item['price'] * item['quantity']
        total += subtotal
        title = item['title'][:32] + "..." if len(item['title']) > 35 else item['title']
        artist = item['artist'][:17] + "..." if item['artist'] and len(item['artist']) > 20 else (item['artist'] or 'N/A')
        print(f"  {title:<35} {artist:<20} £{item['price']:<9.2f} {item['quantity']:<5} £{subtotal:<9.2f}")

    print("  " + "-" * 85)
    print(f"  {'TOTAL':<62} £{total:.2f}")
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
    print_header("Music Shop - All Orders")

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

def wishlist_menu():
    """Manage wishlist."""
    current_user = get_current_user()
    customer_name = current_user.get('name', 'Guest')

    print_header("My Wishlist")

    wishlist = get_wishlist(customer_name)

    if not wishlist:
        print("\n  Your wishlist is empty.")
        add = input("\n  Add an item? (yes/no): ").strip().lower()
        if add == 'yes':
            product_id = input("  Enter Product ID: ").strip()
            if product_id.isdigit() and add_to_wishlist(customer_name, int(product_id)):
                print("  ✅ Added to wishlist!")
        return

    print(f"\n  Total items: {len(wishlist)}\n")
    print(f"  {'Title':<35} {'Artist':<20} {'Price':<10} {'Stock':<6}")
    print("  " + "-" * 75)

    for item in wishlist:
        title = item['title'][:32] + "..." if len(item['title']) > 35 else item['title']
        artist = item['artist'][:17] + "..." if item['artist'] and len(item['artist']) > 20 else (item['artist'] or 'N/A')
        print(f"  {title:<35} {artist:<20} £{item['price']:<9.2f} {item['stock']:<6}")

    print()

def statistics_menu():
    """Show shop statistics."""
    print_header("Music Shop Statistics")

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

    # Products by genre
    by_genre = {}
    for product in products:
        if product['genre']:
            by_genre[product['genre']] = by_genre.get(product['genre'], 0) + 1

    if by_genre:
        print("\n  Products by Genre:")
        for genre, count in sorted(by_genre.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"    {genre}: {count}")

    print()

def music_shop_menu():
    """Main music shop CLI menu."""
    init_musicshop_database()

    while True:
        print_header("Music Shop")
        print("\n  1. Browse Catalog")
        print("  2. Add to Cart")
        print("  3. View Cart")
        print("  4. Checkout")
        print("  5. View All Orders")
        print("  6. My Wishlist")
        print("  7. View Statistics")
        print("  0. Return to Main Menu")

        choice = input("\n  Enter your choice: ").strip()

        if choice == '1':
            browse_catalog_menu()
        elif choice == '2':
            add_to_cart_menu()
        elif choice == '3':
            view_cart_menu()
        elif choice == '4':
            checkout_menu()
        elif choice == '5':
            view_orders_menu()
        elif choice == '6':
            wishlist_menu()
        elif choice == '7':
            statistics_menu()
        elif choice == '0':
            print("\n  Returning to main menu...\n")
            break
        else:
            print("\n  ❌ Invalid choice.")

        if choice != '0':
            input("\n  Press Enter to continue...")

if __name__ == '__main__':
    music_shop_menu()
