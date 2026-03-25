"""
Butcher Shop CLI for University Management System

Provides comprehensive butcher shop services including products, orders,
inventory management, and reporting with finance and email integration.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
import re

# Import centralized database and authentication
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.infrastructure.shared_context import get_auth

# Import butcher core services
try:
    from education_system.university_system.modules.domain.butcher.services.butcher_core import (
        init_butcher_db, MEAT_PRODUCTS, PRODUCT_CATEGORIES
    )
    BUTCHER_CORE_AVAILABLE = True
except ImportError:
    BUTCHER_CORE_AVAILABLE = False
    MEAT_PRODUCTS = {}
    PRODUCT_CATEGORIES = ['Beef', 'Pork', 'Chicken', 'Lamb', 'Seafood', 'Deli']

    def init_butcher_db():
        """Fallback database initialization"""
        try:
            with transaction() as conn:
                # Products now use unified 'products' table with source_type='butcher'

                # Orders now use unified 'orders' table with source_type='butcher'

                # Order items now use unified 'order_items' table with source_type='butcher'

                # Inventory adjustments table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS butcher_inventory_adjustments (
                        adjustment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_id INTEGER NOT NULL,
                        quantity_change REAL NOT NULL,
                        reason TEXT NOT NULL,
                        adjusted_by TEXT NOT NULL,
                        adjustment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        notes TEXT,
                        FOREIGN KEY (product_id) REFERENCES products(product_id)
                    )
                ''')

                # Stock alerts table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS butcher_stock_alerts (
                        alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_id INTEGER NOT NULL,
                        alert_type TEXT NOT NULL,
                        alert_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        resolved BOOLEAN DEFAULT 0,
                        resolved_date TIMESTAMP,
                        FOREIGN KEY (product_id) REFERENCES products(product_id)
                    )
                ''')

                # Expiry tracking table
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS butcher_product_expiry (
                        expiry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_id INTEGER NOT NULL,
                        batch_number TEXT,
                        quantity_kg REAL NOT NULL,
                        expiry_date DATE NOT NULL,
                        received_date DATE DEFAULT CURRENT_DATE,
                        status TEXT DEFAULT 'active',
                        FOREIGN KEY (product_id) REFERENCES products(product_id)
                    )
                ''')

                # Initialize sample products if table is empty
                cursor = conn.execute("SELECT COUNT(*) FROM products WHERE source_type = 'butcher'")
                if cursor.fetchone()[0] == 0:
                    sample_products = [
                        ('Ribeye Steak', 'Beef', 24.99, 15.0, 'Premium ribeye steak', 'Prime Meats Ltd'),
                        ('Sirloin Steak', 'Beef', 19.99, 20.0, 'Quality sirloin steak', 'Prime Meats Ltd'),
                        ('Beef Mince', 'Beef', 8.99, 30.0, 'Lean beef mince', 'Prime Meats Ltd'),
                        ('Pork Chops', 'Pork', 12.99, 18.0, 'Thick cut pork chops', 'Farm Fresh Pork'),
                        ('Pork Sausages', 'Pork', 7.99, 25.0, 'Traditional pork sausages', 'Farm Fresh Pork'),
                        ('Chicken Breast', 'Chicken', 10.99, 22.0, 'Free-range chicken breast', 'Valley Poultry'),
                        ('Whole Chicken', 'Chicken', 6.99, 15.0, 'Free-range whole chicken', 'Valley Poultry'),
                        ('Lamb Chops', 'Lamb', 18.99, 12.0, 'Premium lamb chops', 'Highland Lamb'),
                        ('Leg of Lamb', 'Lamb', 16.99, 10.0, 'Whole leg of lamb', 'Highland Lamb'),
                        ('Salmon Fillet', 'Seafood', 22.99, 8.0, 'Fresh Atlantic salmon', 'Ocean Fresh'),
                        ('Cod Fillet', 'Seafood', 16.99, 10.0, 'Fresh cod fillet', 'Ocean Fresh'),
                        ('Bacon Rashers', 'Deli', 9.99, 20.0, 'Smoked bacon rashers', 'Deli Masters'),
                        ('Ham Slices', 'Deli', 11.99, 15.0, 'Honey roast ham', 'Deli Masters'),
                    ]

                    for product in sample_products:
                        conn.execute('''
                            INSERT INTO products
                            (source_type, product_name, category, price_per_kg, stock_kg, description, supplier)
                            VALUES ('butcher', ?, ?, ?, ?, ?, ?)
                        ''', product)

                    logger.info("Initialized butcher shop with sample products")

            return True
        except Exception as e:
            logging.error(f"Database initialization error: {e}")
            return False

# Import email service
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

# Import finance integration
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        record_payment_to_finance,
        process_student_finance_account_payment
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False

logger = logging.getLogger(__name__)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def print_header(text: str):
    """Print a formatted header"""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)


def print_subheader(text: str):
    """Print a formatted subheader"""
    print("\n" + "-" * 80)
    print(f"  {text}")
    print("-" * 80)


def get_current_user():
    """Get the currently logged-in user"""
    try:
        auth = get_auth()
        if auth and hasattr(auth, 'current_user') and auth.current_user:
            return auth.current_user
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
    return None


def is_admin() -> bool:
    """Check if current user is admin"""
    user = get_current_user()
    return user and user.get('role') in ['admin', 'staff']


def validate_positive_number(value: str, field_name: str = "Value") -> Optional[float]:
    """Validate and convert a positive number"""
    try:
        num = float(value)
        if num <= 0:
            print(f"❌ {field_name} must be greater than 0")
            return None
        return num
    except ValueError:
        print(f"❌ Invalid {field_name}. Please enter a valid number.")
        return None


def format_currency(amount: float) -> str:
    """Format amount as currency"""
    return f"GBP {amount:.2f}"


def format_date(date_str: str) -> str:
    """Format date string for display"""
    try:
        if not date_str:
            return "N/A"
        dt = datetime.fromisoformat(date_str)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return date_str


def get_stock_status_icon(stock: float) -> str:
    """Get status icon based on stock level"""
    if stock > 10:
        return "🟢"  # Good stock
    elif stock > 5:
        return "🟡"  # Low stock
    elif stock > 0:
        return "🟠"  # Very low stock
    else:
        return "🔴"  # Out of stock


# ============================================================================
# PRODUCT CATALOG FUNCTIONS
# ============================================================================

def browse_products_by_category():
    """Browse products filtered by category"""
    try:
        print_subheader("Browse Products by Category")

        # Display categories
        print("\n📦 Product Categories:")
        for idx, category in enumerate(PRODUCT_CATEGORIES, 1):
            print(f"{idx}. {category}")
        print("0. View All Categories")

        choice = input("\nSelect category (0 for all): ").strip()

        category_filter = None
        if choice.isdigit() and 1 <= int(choice) <= len(PRODUCT_CATEGORIES):
            category_filter = PRODUCT_CATEGORIES[int(choice) - 1]

        with get_connection() as conn:
            if category_filter:
                cursor = conn.execute('''
                    SELECT product_id, product_name, category, price_per_kg,
                           stock_kg, description, status
                    FROM products
                    WHERE source_type = 'butcher' AND category = ? AND status = 'available'
                    ORDER BY product_name
                ''', (category_filter,))
            else:
                cursor = conn.execute('''
                    SELECT product_id, product_name, category, price_per_kg,
                           stock_kg, description, status
                    FROM products
                    WHERE source_type = 'butcher' AND status = 'available'
                    ORDER BY category, product_name
                ''')

            products = cursor.fetchall()

            if not products:
                print("\n❌ No products found in this category")
            else:
                print(f"\n🥩 PRODUCTS{f' - {category_filter}' if category_filter else ''}:")
                print("-" * 80)

                current_category = None
                for product in products:
                    try:
                        prod_id, name, category, price, stock, desc, status = product

                        if not category_filter and category != current_category:
                            print(f"\n📦 {category}:")
                            current_category = category

                        stock_icon = get_stock_status_icon(float(stock))
                        print(f"  {stock_icon} ID {prod_id}: {name}")
                        print(f"      Price: {format_currency(float(price))}/kg | Stock: {float(stock):.2f}kg")
                        if desc:
                            print(f"      {desc}")
                    except Exception as e:
                        logger.error(f"Error displaying product: {e}")
                        continue

    except Exception as e:
        logger.error(f"Error browsing products: {e}")
        print(f"❌ Error browsing products: {e}")

    input("\nPress Enter to continue...")


def view_product_details():
    """View detailed information about a specific product"""
    try:
        print_subheader("Product Details")

        product_id = input("\nEnter Product ID: ").strip()

        if not product_id.isdigit():
            print("❌ Invalid Product ID")
            input("\nPress Enter to continue...")
            return

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT source_product_id as product_id, product_name, category, price_per_kg,
                       stock_kg, description, status, reorder_point, supplier,
                       created_at, updated_at
                FROM products
                WHERE source_product_id = ? AND source_type = 'butcher'
            ''', (product_id,))

            product = cursor.fetchone()

            if not product:
                print(f"❌ Product with ID {product_id} not found")
            else:
                (prod_id, name, category, price, stock, desc, status,
                 reorder_point, supplier, created, updated) = product

                stock_icon = get_stock_status_icon(float(stock))

                print(f"\n{stock_icon} PRODUCT DETAILS:")
                print("-" * 80)
                print(f"ID: {prod_id}")
                print(f"Name: {name}")
                print(f"Category: {category}")
                print(f"Price: {format_currency(float(price))}/kg")
                print(f"Stock: {float(stock):.2f}kg")
                print(f"Status: {status.upper()}")
                print(f"Reorder Point: {float(reorder_point):.2f}kg")
                if supplier:
                    print(f"Supplier: {supplier}")
                if desc:
                    print(f"Description: {desc}")
                print(f"Created: {format_date(created)}")
                print(f"Updated: {format_date(updated)}")

                # Check for expiry information
                expiry_cursor = conn.execute('''
                    SELECT batch_number, quantity_kg, expiry_date, received_date
                    FROM butcher_product_expiry
                    WHERE product_id = ? AND status = 'active'
                    ORDER BY expiry_date
                ''', (product_id,))

                expiry_batches = expiry_cursor.fetchall()
                if expiry_batches:
                    print("\n📅 Expiry Information:")
                    for batch in expiry_batches:
                        batch_num, qty, exp_date, recv_date = batch
                        print(f"  Batch {batch_num}: {float(qty):.2f}kg - Expires: {exp_date}")

                # Stock alert check
                if float(stock) <= float(reorder_point):
                    print(f"\n⚠️  LOW STOCK ALERT: Current stock ({float(stock):.2f}kg) is at or below reorder point ({float(reorder_point):.2f}kg)")

    except Exception as e:
        logger.error(f"Error viewing product details: {e}")
        print(f"❌ Error viewing product details: {e}")

    input("\nPress Enter to continue...")


def search_products():
    """Search products by name"""
    try:
        print_subheader("Search Products")

        search_term = input("\nEnter product name to search: ").strip()

        if not search_term:
            print("❌ Search term cannot be empty")
            input("\nPress Enter to continue...")
            return

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT product_id, product_name, category, price_per_kg,
                       stock_kg, description, status
                FROM products
                WHERE source_type = 'butcher' AND (product_name LIKE ? OR description LIKE ?)
                ORDER BY
                    CASE WHEN product_name LIKE ? THEN 1 ELSE 2 END,
                    product_name
            ''', (f'%{search_term}%', f'%{search_term}%', f'{search_term}%'))

            products = cursor.fetchall()

            if not products:
                print(f"\n❌ No products found matching '{search_term}'")
            else:
                print(f"\n🔍 SEARCH RESULTS ({len(products)} found):")
                print("-" * 80)

                for product in products:
                    try:
                        prod_id, name, category, price, stock, desc, status = product

                        stock_icon = get_stock_status_icon(float(stock))
                        status_text = "✅ Available" if status == 'available' else "❌ Unavailable"

                        print(f"\n  {stock_icon} ID {prod_id}: {name} ({category})")
                        print(f"      Price: {format_currency(float(price))}/kg | Stock: {float(stock):.2f}kg")
                        print(f"      Status: {status_text}")
                        if desc:
                            print(f"      {desc}")
                    except Exception as e:
                        logger.error(f"Error displaying search result: {e}")
                        continue

    except Exception as e:
        logger.error(f"Error searching products: {e}")
        print(f"❌ Error searching products: {e}")

    input("\nPress Enter to continue...")


def add_product():
    """Add a new product (admin only)"""
    if not is_admin():
        print("❌ You don't have permission to add products")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("Add New Product")

        # Get product details
        name = input("\nProduct Name: ").strip()
        if not name:
            print("❌ Product name cannot be empty")
            input("\nPress Enter to continue...")
            return

        # Category selection
        print("\nSelect Category:")
        for idx, category in enumerate(PRODUCT_CATEGORIES, 1):
            print(f"{idx}. {category}")

        cat_choice = input("Enter category number: ").strip()
        if not cat_choice.isdigit() or not (1 <= int(cat_choice) <= len(PRODUCT_CATEGORIES)):
            print("❌ Invalid category selection")
            input("\nPress Enter to continue...")
            return

        category = PRODUCT_CATEGORIES[int(cat_choice) - 1]

        # Price
        price_str = input("Price per kg (GBP): ").strip()
        price = validate_positive_number(price_str, "Price")
        if price is None:
            input("\nPress Enter to continue...")
            return

        # Initial stock
        stock_str = input("Initial stock (kg): ").strip()
        stock = validate_positive_number(stock_str, "Stock")
        if stock is None:
            input("\nPress Enter to continue...")
            return

        # Optional fields
        description = input("Description (optional): ").strip()
        supplier = input("Supplier (optional): ").strip()

        reorder_str = input("Reorder point in kg (default 5.0): ").strip()
        reorder_point = 5.0
        if reorder_str:
            reorder_point = validate_positive_number(reorder_str, "Reorder point")
            if reorder_point is None:
                reorder_point = 5.0

        # Confirm
        print("\n📋 PRODUCT SUMMARY:")
        print("-" * 80)
        print(f"Name: {name}")
        print(f"Category: {category}")
        print(f"Price: {format_currency(price)}/kg")
        print(f"Initial Stock: {stock:.2f}kg")
        print(f"Reorder Point: {reorder_point:.2f}kg")
        if description:
            print(f"Description: {description}")
        if supplier:
            print(f"Supplier: {supplier}")

        confirm = input("\nAdd this product? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Product addition cancelled")
            input("\nPress Enter to continue...")
            return

        # Add product
        with transaction() as conn:
            conn.execute('''
                INSERT INTO products
                (source_type, product_name, category, price_per_kg, stock_kg, description,
                 supplier, reorder_point, status, created_at, updated_at)
                VALUES ('butcher', ?, ?, ?, ?, ?, ?, ?, 'available', ?, ?)
            ''', (name, category, price, stock, description, supplier,
                  reorder_point, datetime.now().isoformat(), datetime.now().isoformat()))

            product_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]

        print(f"\n✅ Product added successfully! (ID: {product_id})")
        logger.info(f"Admin added new butcher product: {name} (ID: {product_id})")

    except Exception as e:
        logger.error(f"Error adding product: {e}")
        print(f"❌ Error adding product: {e}")

    input("\nPress Enter to continue...")


def update_product():
    """Update an existing product (admin only)"""
    if not is_admin():
        print("❌ You don't have permission to update products")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("Update Product")

        product_id = input("\nEnter Product ID to update: ").strip()

        if not product_id.isdigit():
            print("❌ Invalid Product ID")
            input("\nPress Enter to continue...")
            return

        # Get current product details
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT product_name, category, price_per_kg, description,
                       supplier, reorder_point, status
                FROM products
                WHERE source_product_id = ? AND source_type = 'butcher'
            ''', (product_id,))

            product = cursor.fetchone()

            if not product:
                print(f"❌ Product with ID {product_id} not found")
                input("\nPress Enter to continue...")
                return

            name, category, price, desc, supplier, reorder_point, status = product

            print(f"\nCurrent Product Details:")
            print(f"Name: {name}")
            print(f"Category: {category}")
            print(f"Price: {format_currency(float(price))}/kg")
            print(f"Status: {status}")
            if desc:
                print(f"Description: {desc}")
            if supplier:
                print(f"Supplier: {supplier}")
            print(f"Reorder Point: {float(reorder_point):.2f}kg")

            print("\n(Press Enter to keep current value)")

            # Update fields
            new_name = input(f"\nNew name [{name}]: ").strip() or name

            # Category
            print("\nSelect new category:")
            for idx, cat in enumerate(PRODUCT_CATEGORIES, 1):
                mark = "✓" if cat == category else " "
                print(f"{idx}. [{mark}] {cat}")

            cat_choice = input(f"Enter category number [current: {category}]: ").strip()
            if cat_choice.isdigit() and 1 <= int(cat_choice) <= len(PRODUCT_CATEGORIES):
                new_category = PRODUCT_CATEGORIES[int(cat_choice) - 1]
            else:
                new_category = category

            # Price
            price_str = input(f"New price per kg [{format_currency(float(price))}]: ").strip()
            new_price = validate_positive_number(price_str, "Price") if price_str else float(price)
            if new_price is None:
                new_price = float(price)

            # Description
            new_desc = input(f"New description [{desc or 'None'}]: ").strip()
            if not new_desc:
                new_desc = desc

            # Supplier
            new_supplier = input(f"New supplier [{supplier or 'None'}]: ").strip()
            if not new_supplier:
                new_supplier = supplier

            # Reorder point
            reorder_str = input(f"New reorder point [{float(reorder_point):.2f}kg]: ").strip()
            new_reorder = validate_positive_number(reorder_str, "Reorder point") if reorder_str else float(reorder_point)
            if new_reorder is None:
                new_reorder = float(reorder_point)

            # Status
            print(f"\nStatus: 1) Available 2) Unavailable [current: {status}]")
            status_choice = input("Select status (1/2): ").strip()
            if status_choice == '1':
                new_status = 'available'
            elif status_choice == '2':
                new_status = 'unavailable'
            else:
                new_status = status

            # Confirm
            print("\n📋 UPDATED PRODUCT SUMMARY:")
            print("-" * 80)
            print(f"Name: {new_name}")
            print(f"Category: {new_category}")
            print(f"Price: {format_currency(new_price)}/kg")
            print(f"Status: {new_status}")
            print(f"Reorder Point: {new_reorder:.2f}kg")
            if new_desc:
                print(f"Description: {new_desc}")
            if new_supplier:
                print(f"Supplier: {new_supplier}")

            confirm = input("\nUpdate this product? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("❌ Product update cancelled")
                input("\nPress Enter to continue...")
                return

            # Update product
            with transaction() as conn:
                conn.execute('''
                    UPDATE products
                    SET product_name = ?, category = ?, price_per_kg = ?,
                        description = ?, supplier = ?, reorder_point = ?,
                        status = ?, updated_at = ?
                    WHERE source_product_id = ? AND source_type = 'butcher'
                ''', (new_name, new_category, new_price, new_desc, new_supplier,
                      new_reorder, new_status, datetime.now().isoformat(), product_id))

            print(f"\n✅ Product updated successfully!")
            logger.info(f"Admin updated butcher product ID {product_id}")

    except Exception as e:
        logger.error(f"Error updating product: {e}")
        print(f"❌ Error updating product: {e}")

    input("\nPress Enter to continue...")


# ============================================================================
# ORDER MANAGEMENT FUNCTIONS
# ============================================================================

def convert_units(quantity: float, from_unit: str) -> Optional[float]:
    """Convert various units to kilograms"""
    try:
        from_unit = from_unit.lower()

        # Already in kg
        if from_unit in ['kg', 'kgs', 'kilogram', 'kilograms']:
            return quantity

        # Grams to kg
        if from_unit in ['g', 'gram', 'grams']:
            return quantity / 1000

        # Pounds to kg
        if from_unit in ['lb', 'lbs', 'pound', 'pounds']:
            return quantity * 0.453592

        # Ounces to kg
        if from_unit in ['oz', 'ounce', 'ounces']:
            return quantity * 0.0283495

        print(f"❌ Unknown unit: {from_unit}")
        print("   Supported units: kg, g, lb, oz")
        return None

    except Exception as e:
        logger.error(f"Error converting units: {e}")
        return None


def place_order():
    """Place a new order"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to place orders")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("Place New Order")

        # Show available products
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT source_product_id as product_id, product_name, category, price_per_kg, stock_kg
                FROM products
                WHERE source_type = 'butcher' AND status = 'available' AND stock_kg > 0
                ORDER BY category, product_name
            ''')
            products = cursor.fetchall()

            if not products:
                print("\n❌ No products available for order")
                input("\nPress Enter to continue...")
                return

            print("\n🥩 AVAILABLE PRODUCTS:")
            print("-" * 80)
            current_category = None
            for product in products:
                prod_id, name, category, price, stock = product
                if category != current_category:
                    print(f"\n📦 {category}:")
                    current_category = category

                stock_icon = get_stock_status_icon(float(stock))
                print(f"  {stock_icon} ID {prod_id}: {name} - {format_currency(float(price))}/kg (Stock: {float(stock):.2f}kg)")

        cart = []
        total = 0.0

        print("\n🛒 BUILD YOUR ORDER:")
        print("(Enter product ID and quantity, or 0 to finish)")

        while True:
            print(f"\n{'─' * 80}")
            print("📦 Current Cart:")
            if not cart:
                print("  (empty)")
            else:
                for idx, item in enumerate(cart, 1):
                    print(f"  {idx}. {item['name']} - {item['quantity']:.2f}kg @ {format_currency(item['price'])}/kg = {format_currency(item['subtotal'])}")
                print(f"\n  💰 Total: {format_currency(total)}")

            choice = input("\nEnter product ID (0 to finish, -1 to cancel): ").strip()

            if choice == "0":
                break
            elif choice == "-1":
                print("❌ Order cancelled")
                input("\nPress Enter to continue...")
                return

            if not choice.isdigit():
                print("❌ Invalid product ID")
                continue

            product_id = choice

            # Get product details
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT product_name, price_per_kg, stock_kg, status
                    FROM products
                    WHERE source_product_id = ? AND source_type = 'butcher'
                ''', (product_id,))
                product = cursor.fetchone()

                if not product:
                    print("❌ Product not found")
                    continue

                name, price, stock, status = product

                if status != 'available':
                    print(f"❌ Product '{name}' is not available")
                    continue

                if float(stock) <= 0:
                    print(f"❌ Product '{name}' is out of stock")
                    continue

                # Get quantity with unit conversion
                print(f"\n📦 {name} - {format_currency(float(price))}/kg")
                print(f"   Available: {float(stock):.2f}kg")

                quantity_input = input("Enter quantity (e.g., '2.5 kg', '500 g', '1 lb'): ").strip()

                # Parse quantity and unit
                parts = quantity_input.split()
                if len(parts) == 1:
                    # No unit specified, assume kg
                    try:
                        quantity = float(parts[0])
                    except ValueError:
                        print("❌ Invalid quantity")
                        continue
                elif len(parts) == 2:
                    # Quantity and unit specified
                    try:
                        qty_value = float(parts[0])
                        qty_unit = parts[1]
                        quantity = convert_units(qty_value, qty_unit)
                        if quantity is None:
                            continue
                    except ValueError:
                        print("❌ Invalid quantity")
                        continue
                else:
                    print("❌ Invalid format. Use: '<number> <unit>' or just '<number>' for kg")
                    continue

                if quantity <= 0:
                    print("❌ Quantity must be greater than 0")
                    continue

                if quantity > float(stock):
                    print(f"❌ Insufficient stock. Available: {float(stock):.2f}kg")
                    continue

                subtotal = quantity * float(price)
                cart.append({
                    'product_id': product_id,
                    'name': name,
                    'quantity': quantity,
                    'price': float(price),
                    'subtotal': subtotal
                })
                total += subtotal
                print(f"✅ Added {quantity:.2f}kg of {name} to cart")

        if not cart:
            print("❌ Cart is empty. Order cancelled")
            input("\nPress Enter to continue...")
            return

        # Order summary and payment
        print_subheader("ORDER SUMMARY")
        for idx, item in enumerate(cart, 1):
            print(f"{idx}. {item['name']} - {item['quantity']:.2f}kg @ {format_currency(item['price'])}/kg = {format_currency(item['subtotal'])}")
        print(f"\n💰 Total: {format_currency(total)}")

        # Payment method
        print("\n💳 Payment Method:")
        print("1. Cash")
        print("2. Card")
        print("3. Student Finance Account")

        payment_choice = input("Select payment method (1-3): ").strip()

        payment_methods = {
            '1': 'cash',
            '2': 'card',
            '3': 'finance_account'
        }

        payment_method = payment_methods.get(payment_choice, 'cash')

        # Pickup date
        pickup_input = input("\nPickup date (YYYY-MM-DD, or press Enter for today): ").strip()
        if pickup_input:
            try:
                pickup_date = datetime.strptime(pickup_input, '%Y-%m-%d').date().isoformat()
            except ValueError:
                print("⚠️  Invalid date format. Using today.")
                pickup_date = datetime.now().date().isoformat()
        else:
            pickup_date = datetime.now().date().isoformat()

        # Order notes
        notes = input("Order notes (optional): ").strip()

        confirm = input("\n✅ Confirm order? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("❌ Order cancelled")
            input("\nPress Enter to continue...")
            return

        # Process payment if using finance account
        if payment_method == 'finance_account' and FINANCE_AVAILABLE:
            try:
                success = process_student_finance_account_payment(
                    user.get('username'),
                    total,
                    'Butcher Shop Purchase'
                )
                if not success:
                    print("❌ Payment failed. Insufficient funds or finance account error.")
                    input("\nPress Enter to continue...")
                    return
            except Exception as e:
                logger.error(f"Finance payment error: {e}")
                print(f"❌ Payment processing error: {e}")
                input("\nPress Enter to continue...")
                return

        # Create order
        order_number = f"BO-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        with transaction() as conn:
            # Insert order
            conn.execute('''
                INSERT INTO orders
                (source_type, order_number, user_id, user_name, user_email, total_amount,
                 payment_method, order_status, order_date, pickup_date, notes)
                VALUES ('butcher', ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
            ''', (order_number, user.get('username'),
                  user.get('full_name', user.get('username')),
                  user.get('email', ''), total, payment_method,
                  datetime.now().isoformat(), pickup_date, notes))

            order_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]

            # Insert order items and update stock
            for item in cart:
                conn.execute('''
                    INSERT INTO order_items
                    (source_type, order_id, product_id, item_name, quantity_kg, unit_price, subtotal)
                    VALUES ('butcher', ?, ?, ?, ?, ?, ?)
                ''', (order_id, item['product_id'], item['name'], item['quantity'],
                      item['price'], item['subtotal']))

                # Update stock
                conn.execute('''
                    UPDATE products
                    SET stock_kg = stock_kg - ?
                    WHERE source_product_id = ? AND source_type = 'butcher'
                ''', (item['quantity'], item['product_id']))

                # Check if stock is now below reorder point
                cursor = conn.execute('''
                    SELECT stock_kg, reorder_point, product_name
                    FROM products
                    WHERE source_product_id = ? AND source_type = 'butcher' AND stock_kg <= reorder_point
                ''', (item['product_id'],))

                low_stock = cursor.fetchone()
                if low_stock:
                    # Create stock alert
                    conn.execute('''
                        INSERT INTO butcher_stock_alerts
                        (product_id, alert_type, alert_date)
                        VALUES (?, 'low_stock', ?)
                    ''', (item['product_id'], datetime.now().isoformat()))

        # Record to finance system
        if FINANCE_AVAILABLE and payment_method != 'finance_account':
            try:
                record_payment_to_finance(
                    user.get('username'),
                    total,
                    payment_method,
                    'Butcher Shop',
                    order_number
                )
            except Exception as e:
                logger.error(f"Error recording payment to finance: {e}")

        print(f"\n✅ Order placed successfully!")
        print(f"📝 Order Number: {order_number}")
        print(f"📅 Pickup Date: {pickup_date}")
        print(f"💰 Total: {format_currency(total)}")
        print(f"💳 Payment: {payment_method.replace('_', ' ').title()}")

        logger.info(f"User {user.get('username')} placed butcher order {order_number} for {format_currency(total)}")

        # Send email confirmation if available
        if EMAIL_AVAILABLE and user.get('email'):
            try:
                send_email(
                    user.get('email'),
                    'Butcher Shop Order Confirmation',
                    f"Your order {order_number} has been confirmed. Total: {format_currency(total)}. Pickup: {pickup_date}."
                )
            except Exception as e:
                logger.error(f"Error sending order confirmation email: {e}")

    except Exception as e:
        logger.error(f"Error placing order: {e}")
        print(f"❌ Error placing order: {e}")

    input("\nPress Enter to continue...")


def view_my_orders():
    """View user's order history"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in to view orders")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("My Orders")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT order_id, order_number, total_amount, order_status,
                       order_date, pickup_date, payment_method, notes
                FROM orders
                WHERE source_type = 'butcher' AND user_id = ?
                ORDER BY order_date DESC
                LIMIT 50
            ''', (user.get('username'),))
            orders = cursor.fetchall()

            if not orders:
                print("\n❌ No orders found")
            else:
                print(f"\n📜 YOUR ORDERS ({len(orders)} total):")

                for order in orders:
                    try:
                        (order_id, order_num, total, status, order_date,
                         pickup_date, payment_method, notes) = order

                        status_icons = {
                            'pending': '⏳',
                            'processing': '🔄',
                            'ready': '✅',
                            'completed': '✔️',
                            'cancelled': '❌'
                        }
                        status_icon = status_icons.get(status, '❓')

                        print(f"\n{'-' * 80}")
                        print(f"{status_icon} Order: {order_num}")
                        print(f"   Status: {status.upper()}")
                        print(f"   Total: {format_currency(float(total))}")
                        print(f"   Payment: {payment_method.replace('_', ' ').title()}")
                        print(f"   Ordered: {format_date(order_date)}")
                        if pickup_date:
                            print(f"   Pickup: {pickup_date}")
                        if notes:
                            print(f"   Notes: {notes}")

                        # Get order items
                        item_cursor = conn.execute('''
                            SELECT item_name as product_name, quantity_kg, unit_price, subtotal
                            FROM order_items
                            WHERE order_id = ? AND source_type = 'butcher'
                        ''', (order_id,))
                        items = item_cursor.fetchall()

                        if items:
                            print("   Items:")
                            for item in items:
                                prod_name, qty, price, subtotal = item
                                print(f"     • {prod_name}: {float(qty):.2f}kg @ {format_currency(float(price))}/kg = {format_currency(float(subtotal))}")

                    except Exception as e:
                        logger.error(f"Error displaying order: {e}")
                        continue

                # Option to view specific order or cancel
                print(f"\n{'-' * 80}")
                print("\nOptions:")
                print("1. View detailed receipt for an order")
                print("2. Cancel a pending order")
                print("0. Return to menu")

                choice = input("\nEnter choice: ").strip()

                if choice == '1':
                    view_order_receipt()
                elif choice == '2':
                    cancel_order()

    except Exception as e:
        logger.error(f"Error viewing orders: {e}")
        print(f"❌ Error viewing orders: {e}")

    input("\nPress Enter to continue...")


def view_order_receipt():
    """View detailed receipt for a specific order"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in")
        input("\nPress Enter to continue...")
        return

    try:
        order_number = input("\nEnter order number: ").strip()

        if not order_number:
            print("❌ Order number cannot be empty")
            return

        with get_connection() as conn:
            # Check if user owns this order or is admin
            if is_admin():
                cursor = conn.execute('''
                    SELECT order_id, order_number, user_name, user_email, total_amount,
                           order_status, order_date, pickup_date, payment_method, notes, completed_date
                    FROM orders
                    WHERE source_type = 'butcher' AND order_number = ?
                ''', (order_number,))
            else:
                cursor = conn.execute('''
                    SELECT order_id, order_number, user_name, user_email, total_amount,
                           order_status, order_date, pickup_date, payment_method, notes, completed_date
                    FROM orders
                    WHERE source_type = 'butcher' AND order_number = ? AND user_id = ?
                ''', (order_number, user.get('username')))

            order = cursor.fetchone()

            if not order:
                print(f"❌ Order {order_number} not found or access denied")
                return

            (order_id, order_num, user_name, user_email, total, status,
             order_date, pickup_date, payment_method, notes, completed_date) = order

            # Print receipt
            print("\n" + "=" * 80)
            print("                    UNIVERSITY BUTCHER SHOP")
            print("                         ORDER RECEIPT")
            print("=" * 80)
            print(f"\nOrder Number: {order_num}")
            print(f"Date: {format_date(order_date)}")
            print(f"Customer: {user_name}")
            if user_email:
                print(f"Email: {user_email}")
            print(f"\nStatus: {status.upper()}")
            if pickup_date:
                print(f"Pickup Date: {pickup_date}")
            if completed_date:
                print(f"Completed: {format_date(completed_date)}")

            print("\n" + "-" * 80)
            print(f"{'Item':<30} {'Qty (kg)':<12} {'Price/kg':<12} {'Subtotal':>10}")
            print("-" * 80)

            # Get items
            item_cursor = conn.execute('''
                SELECT item_name as product_name, quantity_kg, unit_price, subtotal
                FROM order_items
                WHERE order_id = ? AND source_type = 'butcher'
            ''', (order_id,))
            items = item_cursor.fetchall()

            for item in items:
                prod_name, qty, price, subtotal = item
                print(f"{prod_name:<30} {float(qty):<12.2f} {format_currency(float(price)):<12} {format_currency(float(subtotal)):>10}")

            print("-" * 80)
            print(f"{'TOTAL':<54} {format_currency(float(total)):>10}")
            print("-" * 80)
            print(f"\nPayment Method: {payment_method.replace('_', ' ').title()}")

            if notes:
                print(f"\nNotes: {notes}")

            print("\n" + "=" * 80)
            print("                    Thank you for your order!")
            print("=" * 80)

    except Exception as e:
        logger.error(f"Error viewing receipt: {e}")
        print(f"❌ Error viewing receipt: {e}")


def cancel_order():
    """Cancel a pending order"""
    user = get_current_user()
    if not user:
        print("❌ You must be logged in")
        input("\nPress Enter to continue...")
        return

    try:
        order_number = input("\nEnter order number to cancel: ").strip()

        if not order_number:
            print("❌ Order number cannot be empty")
            return

        with get_connection() as conn:
            # Check order exists and is pending
            if is_admin():
                cursor = conn.execute('''
                    SELECT order_id, total_amount, order_status, payment_method
                    FROM orders
                    WHERE source_type = 'butcher' AND order_number = ?
                ''', (order_number,))
            else:
                cursor = conn.execute('''
                    SELECT order_id, total_amount, order_status, payment_method
                    FROM orders
                    WHERE source_type = 'butcher' AND order_number = ? AND user_id = ?
                ''', (order_number, user.get('username')))

            order = cursor.fetchone()

            if not order:
                print(f"❌ Order {order_number} not found or access denied")
                return

            order_id, total, status, payment_method = order

            if status != 'pending':
                print(f"❌ Cannot cancel order with status: {status}")
                print("   Only pending orders can be cancelled")
                return

            confirm = input(f"\n⚠️  Cancel order {order_number} ({format_currency(float(total))})? (yes/no): ").strip().lower()

            if confirm != 'yes':
                print("❌ Cancellation aborted")
                return

            # Restore stock
            item_cursor = conn.execute('''
                SELECT product_id, quantity_kg
                FROM order_items
                WHERE order_id = ? AND source_type = 'butcher'
            ''', (order_id,))
            items = item_cursor.fetchall()

            with transaction() as trans_conn:
                for product_id, quantity in items:
                    trans_conn.execute('''
                        UPDATE products
                        SET stock_kg = stock_kg + ?
                        WHERE source_product_id = ? AND source_type = 'butcher'
                    ''', (quantity, product_id))

                # Update order status
                trans_conn.execute('''
                    UPDATE orders
                    SET order_status = 'cancelled'
                    WHERE order_id = ? AND source_type = 'butcher'
                ''', (order_id,))

            # Refund if paid via finance account
            if payment_method == 'finance_account' and FINANCE_AVAILABLE:
                try:
                    record_payment_to_finance(
                        user.get('username'),
                        -float(total),  # Negative for refund
                        'refund',
                        'Butcher Shop',
                        f'Refund for {order_number}'
                    )
                except Exception as e:
                    logger.error(f"Error processing refund: {e}")

            print(f"\n✅ Order {order_number} has been cancelled")
            if payment_method == 'finance_account':
                print(f"   Refund of {format_currency(float(total))} processed to finance account")

            logger.info(f"User {user.get('username')} cancelled order {order_number}")

    except Exception as e:
        logger.error(f"Error cancelling order: {e}")
        print(f"❌ Error cancelling order: {e}")


# ============================================================================
# INVENTORY MANAGEMENT FUNCTIONS
# ============================================================================

def view_inventory():
    """View inventory status (staff only)"""
    if not is_admin():
        print("❌ You don't have permission to view inventory")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("Inventory Status")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT source_product_id as product_id, product_name, category, stock_kg,
                       price_per_kg, reorder_point, status
                FROM products
                WHERE source_type = 'butcher'
                ORDER BY
                    CASE
                        WHEN stock_kg <= reorder_point THEN 1
                        ELSE 2
                    END,
                    category, product_name
            ''')
            products = cursor.fetchall()

            if not products:
                print("\n❌ No products in inventory")
            else:
                # Calculate totals
                total_value = 0.0
                low_stock_count = 0
                out_of_stock_count = 0

                print(f"\n📦 INVENTORY STATUS ({len(products)} products):")
                print("=" * 80)

                current_category = None
                for product in products:
                    try:
                        (prod_id, name, category, stock, price,
                         reorder_point, status) = product

                        stock_val = float(stock)
                        price_val = float(price)
                        reorder_val = float(reorder_point)
                        item_value = stock_val * price_val
                        total_value += item_value

                        if category != current_category:
                            if current_category is not None:
                                print()
                            print(f"\n📦 {category}:")
                            print("-" * 80)
                            current_category = category

                        stock_icon = get_stock_status_icon(stock_val)

                        alert = ""
                        if stock_val == 0:
                            alert = " ⚠️  OUT OF STOCK"
                            out_of_stock_count += 1
                        elif stock_val <= reorder_val:
                            alert = f" ⚠️  LOW STOCK (reorder at {reorder_val:.2f}kg)"
                            low_stock_count += 1

                        status_mark = "✓" if status == 'available' else "✗"

                        print(f"  {stock_icon} [{status_mark}] ID {prod_id}: {name}")
                        print(f"      Stock: {stock_val:.2f}kg | Value: {format_currency(item_value)} | {format_currency(price_val)}/kg{alert}")

                    except Exception as e:
                        logger.error(f"Error displaying inventory item: {e}")
                        continue

                # Summary
                print("\n" + "=" * 80)
                print("📊 INVENTORY SUMMARY:")
                print(f"   Total Products: {len(products)}")
                print(f"   Total Value: {format_currency(total_value)}")
                print(f"   Low Stock Alerts: {low_stock_count}")
                print(f"   Out of Stock: {out_of_stock_count}")
                print("=" * 80)

    except Exception as e:
        logger.error(f"Error viewing inventory: {e}")
        print(f"❌ Error viewing inventory: {e}")

    input("\nPress Enter to continue...")


def adjust_inventory():
    """Adjust inventory levels (admin only)"""
    if not is_admin():
        print("❌ You don't have permission to adjust inventory")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("Adjust Inventory")

        product_id = input("\nEnter Product ID: ").strip()

        if not product_id.isdigit():
            print("❌ Invalid Product ID")
            input("\nPress Enter to continue...")
            return

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT product_name, stock_kg
                FROM products
                WHERE source_product_id = ? AND source_type = 'butcher'
            ''', (product_id,))

            product = cursor.fetchone()

            if not product:
                print(f"❌ Product with ID {product_id} not found")
                input("\nPress Enter to continue...")
                return

            name, current_stock = product

            print(f"\n📦 Product: {name}")
            print(f"   Current Stock: {float(current_stock):.2f}kg")

            # Adjustment type
            print("\n🔧 Adjustment Type:")
            print("1. Add stock (restocking)")
            print("2. Remove stock (wastage/damage)")
            print("3. Set exact stock level")

            adj_type = input("\nSelect type (1-3): ").strip()

            if adj_type not in ['1', '2', '3']:
                print("❌ Invalid adjustment type")
                input("\nPress Enter to continue...")
                return

            if adj_type in ['1', '2']:
                quantity_str = input("Enter quantity (kg): ").strip()
                quantity = validate_positive_number(quantity_str, "Quantity")

                if quantity is None:
                    input("\nPress Enter to continue...")
                    return

                if adj_type == '2':
                    if quantity > float(current_stock):
                        print(f"❌ Cannot remove {quantity:.2f}kg - only {float(current_stock):.2f}kg in stock")
                        input("\nPress Enter to continue...")
                        return
                    quantity = -quantity  # Make negative for removal
                    new_stock = float(current_stock) + quantity
                else:
                    new_stock = float(current_stock) + quantity

            else:  # Set exact level
                new_stock_str = input("Enter new stock level (kg): ").strip()
                new_stock = validate_positive_number(new_stock_str, "Stock level")

                if new_stock is None:
                    new_stock = 0.0

                quantity = new_stock - float(current_stock)

            # Reason
            print("\n📝 Reason for adjustment:")
            print("1. Restocking")
            print("2. Wastage")
            print("3. Damage")
            print("4. Correction")
            print("5. Other")

            reason_choice = input("Select reason (1-5): ").strip()
            reasons = {
                '1': 'Restocking',
                '2': 'Wastage',
                '3': 'Damage',
                '4': 'Stock correction',
                '5': 'Other'
            }
            reason = reasons.get(reason_choice, 'Other')

            if reason == 'Other':
                custom_reason = input("Enter reason: ").strip()
                if custom_reason:
                    reason = custom_reason

            notes = input("Additional notes (optional): ").strip()

            # Confirm
            print("\n📋 ADJUSTMENT SUMMARY:")
            print("-" * 80)
            print(f"Product: {name}")
            print(f"Current Stock: {float(current_stock):.2f}kg")
            print(f"Adjustment: {quantity:+.2f}kg")
            print(f"New Stock: {new_stock:.2f}kg")
            print(f"Reason: {reason}")
            if notes:
                print(f"Notes: {notes}")

            confirm = input("\nApply adjustment? (yes/no): ").strip().lower()

            if confirm != 'yes':
                print("❌ Adjustment cancelled")
                input("\nPress Enter to continue...")
                return

            # Apply adjustment
            user = get_current_user()

            with transaction() as trans_conn:
                # Update stock
                trans_conn.execute('''
                    UPDATE products
                    SET stock_kg = ?, updated_at = ?
                    WHERE source_product_id = ? AND source_type = 'butcher'
                ''', (new_stock, datetime.now().isoformat(), product_id))

                # Log adjustment
                trans_conn.execute('''
                    INSERT INTO butcher_inventory_adjustments
                    (product_id, quantity_change, reason, adjusted_by, notes)
                    VALUES (?, ?, ?, ?, ?)
                ''', (product_id, quantity, reason, user.get('username', 'admin'), notes))

                # Check for low stock alert
                cursor = trans_conn.execute('''
                    SELECT reorder_point FROM products WHERE source_product_id = ? AND source_type = 'butcher'
                ''', (product_id,))
                reorder_point = cursor.fetchone()[0]

                if new_stock <= float(reorder_point):
                    trans_conn.execute('''
                        INSERT INTO butcher_stock_alerts
                        (product_id, alert_type, alert_date)
                        VALUES (?, 'low_stock', ?)
                    ''', (product_id, datetime.now().isoformat()))

            print(f"\n✅ Inventory adjusted successfully!")
            print(f"   New stock level: {new_stock:.2f}kg")

            logger.info(f"Admin {user.get('username')} adjusted inventory for product {product_id}: {quantity:+.2f}kg")

    except Exception as e:
        logger.error(f"Error adjusting inventory: {e}")
        print(f"❌ Error adjusting inventory: {e}")

    input("\nPress Enter to continue...")


def view_low_stock_alerts():
    """View products with low stock (admin only)"""
    if not is_admin():
        print("❌ You don't have permission to view alerts")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("Low Stock Alerts")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT p.product_id, p.product_name, p.category,
                       p.stock_kg, p.reorder_point, p.supplier
                FROM products p
                WHERE p.source_type = 'butcher' AND p.stock_kg <= p.reorder_point
                ORDER BY
                    CASE
                        WHEN p.stock_kg = 0 THEN 1
                        ELSE 2
                    END,
                    p.stock_kg ASC
            ''')

            alerts = cursor.fetchall()

            if not alerts:
                print("\n✅ No low stock alerts")
            else:
                print(f"\n⚠️  LOW STOCK ALERTS ({len(alerts)} products):")
                print("=" * 80)

                for alert in alerts:
                    prod_id, name, category, stock, reorder_point, supplier = alert

                    stock_val = float(stock)
                    reorder_val = float(reorder_point)

                    if stock_val == 0:
                        icon = "🔴"
                        urgency = "OUT OF STOCK"
                    elif stock_val <= reorder_val / 2:
                        icon = "🟠"
                        urgency = "CRITICAL"
                    else:
                        icon = "🟡"
                        urgency = "LOW"

                    print(f"\n{icon} [{urgency}] ID {prod_id}: {name}")
                    print(f"   Category: {category}")
                    print(f"   Current Stock: {stock_val:.2f}kg")
                    print(f"   Reorder Point: {reorder_val:.2f}kg")
                    print(f"   Need to order: ~{(reorder_val * 2 - stock_val):.2f}kg")
                    if supplier:
                        print(f"   Supplier: {supplier}")

                print("\n" + "=" * 80)

    except Exception as e:
        logger.error(f"Error viewing low stock alerts: {e}")
        print(f"❌ Error viewing alerts: {e}")

    input("\nPress Enter to continue...")


def manage_expiry_dates():
    """Manage product expiry dates (admin only)"""
    if not is_admin():
        print("❌ You don't have permission to manage expiry dates")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("Expiry Date Management")

        print("\n1. Add expiry batch")
        print("2. View expiring products")
        print("3. Mark batch as sold/disposed")
        print("0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            add_expiry_batch()
        elif choice == '2':
            view_expiring_products()
        elif choice == '3':
            mark_batch_disposed()

    except Exception as e:
        logger.error(f"Error in expiry management: {e}")
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def add_expiry_batch():
    """Add a new batch with expiry date"""
    try:
        product_id = input("\nEnter Product ID: ").strip()

        if not product_id.isdigit():
            print("❌ Invalid Product ID")
            return

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT product_name FROM products WHERE source_product_id = ? AND source_type = 'butcher'
            ''', (product_id,))

            product = cursor.fetchone()
            if not product:
                print(f"❌ Product not found")
                return

            name = product[0]

            print(f"\n📦 Product: {name}")

            batch_number = input("Batch number: ").strip()
            if not batch_number:
                batch_number = f"BATCH-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            quantity_str = input("Quantity (kg): ").strip()
            quantity = validate_positive_number(quantity_str, "Quantity")
            if quantity is None:
                return

            expiry_str = input("Expiry date (YYYY-MM-DD): ").strip()
            try:
                expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date().isoformat()
            except ValueError:
                print("❌ Invalid date format")
                return

            with transaction() as trans_conn:
                trans_conn.execute('''
                    INSERT INTO butcher_product_expiry
                    (product_id, batch_number, quantity_kg, expiry_date)
                    VALUES (?, ?, ?, ?)
                ''', (product_id, batch_number, quantity, expiry_date))

            print(f"\n✅ Expiry batch added: {batch_number}")
            logger.info(f"Added expiry batch {batch_number} for product {product_id}")

    except Exception as e:
        logger.error(f"Error adding expiry batch: {e}")
        print(f"❌ Error: {e}")


def view_expiring_products():
    """View products expiring soon"""
    try:
        days = input("\nShow products expiring within (days, default 7): ").strip()
        try:
            days = int(days) if days else 7
        except ValueError:
            days = 7

        cutoff_date = (datetime.now() + timedelta(days=days)).date().isoformat()

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT e.batch_number, p.product_name, p.category,
                       e.quantity_kg, e.expiry_date, e.received_date
                FROM butcher_product_expiry e
                JOIN products p ON e.product_id = p.source_product_id AND p.source_type = 'butcher'
                WHERE e.status = 'active' AND e.expiry_date <= ?
                ORDER BY e.expiry_date
            ''', (cutoff_date,))

            batches = cursor.fetchall()

            if not batches:
                print(f"\n✅ No products expiring within {days} days")
            else:
                print(f"\n⚠️  PRODUCTS EXPIRING WITHIN {days} DAYS:")
                print("=" * 80)

                for batch in batches:
                    batch_num, name, category, qty, exp_date, recv_date = batch

                    days_until = (datetime.fromisoformat(exp_date).date() - datetime.now().date()).days

                    if days_until < 0:
                        urgency = "🔴 EXPIRED"
                    elif days_until <= 2:
                        urgency = "🟠 URGENT"
                    else:
                        urgency = "🟡 WARNING"

                    print(f"\n{urgency}")
                    print(f"   Product: {name} ({category})")
                    print(f"   Batch: {batch_num}")
                    print(f"   Quantity: {float(qty):.2f}kg")
                    print(f"   Expires: {exp_date} ({days_until} days)")
                    print(f"   Received: {recv_date}")

                print("\n" + "=" * 80)

    except Exception as e:
        logger.error(f"Error viewing expiring products: {e}")
        print(f"❌ Error: {e}")


def mark_batch_disposed():
    """Mark a batch as sold or disposed"""
    try:
        batch_number = input("\nEnter batch number: ").strip()

        if not batch_number:
            print("❌ Batch number cannot be empty")
            return

        with transaction() as conn:
            conn.execute('''
                UPDATE butcher_product_expiry
                SET status = 'disposed'
                WHERE batch_number = ?
            ''', (batch_number,))

            if conn.total_changes > 0:
                print(f"\n✅ Batch {batch_number} marked as disposed")
                logger.info(f"Batch {batch_number} marked as disposed")
            else:
                print(f"❌ Batch {batch_number} not found")

    except Exception as e:
        logger.error(f"Error marking batch disposed: {e}")
        print(f"❌ Error: {e}")


# ============================================================================
# REPORTS & ANALYTICS FUNCTIONS
# ============================================================================

def sales_reports():
    """Generate sales reports (admin only)"""
    if not is_admin():
        print("❌ You don't have permission to view reports")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("Sales Reports")

        print("\n📊 Report Period:")
        print("1. Today")
        print("2. This Week")
        print("3. This Month")
        print("4. Custom Date Range")

        choice = input("\nSelect period (1-4): ").strip()

        now = datetime.now()

        if choice == '1':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now
            period_name = "Today"
        elif choice == '2':
            start_date = now - timedelta(days=now.weekday())
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now
            period_name = "This Week"
        elif choice == '3':
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = now
            period_name = "This Month"
        elif choice == '4':
            start_str = input("Start date (YYYY-MM-DD): ").strip()
            end_str = input("End date (YYYY-MM-DD): ").strip()

            try:
                start_date = datetime.strptime(start_str, '%Y-%m-%d')
                end_date = datetime.strptime(end_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                period_name = f"{start_str} to {end_str}"
            except ValueError:
                print("❌ Invalid date format")
                input("\nPress Enter to continue...")
                return
        else:
            print("❌ Invalid choice")
            input("\nPress Enter to continue...")
            return

        with get_connection() as conn:
            # Total sales
            cursor = conn.execute('''
                SELECT COUNT(*), SUM(total_amount), AVG(total_amount)
                FROM orders
                WHERE source_type = 'butcher' AND order_date >= ? AND order_date <= ?
                AND order_status != 'cancelled'
            ''', (start_date.isoformat(), end_date.isoformat()))

            stats = cursor.fetchone()
            total_orders, total_revenue, avg_order = stats if stats else (0, 0, 0)

            # Sales by category
            category_cursor = conn.execute('''
                SELECT p.category, SUM(oi.subtotal), SUM(oi.quantity_kg)
                FROM order_items oi
                JOIN products p ON oi.product_id = p.source_product_id AND p.source_type = 'butcher'
                JOIN orders o ON oi.order_id = o.order_id AND o.source_type = 'butcher'
                WHERE oi.source_type = 'butcher' AND o.order_date >= ? AND o.order_date <= ?
                AND o.order_status != 'cancelled'
                GROUP BY p.category
                ORDER BY SUM(oi.subtotal) DESC
            ''', (start_date.isoformat(), end_date.isoformat()))

            category_sales = category_cursor.fetchall()

            # Top products
            product_cursor = conn.execute('''
                SELECT oi.item_name as product_name, SUM(oi.quantity_kg), SUM(oi.subtotal), COUNT(*)
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.order_id AND o.source_type = 'butcher'
                WHERE oi.source_type = 'butcher' AND o.order_date >= ? AND o.order_date <= ?
                AND o.order_status != 'cancelled'
                GROUP BY oi.item_name
                ORDER BY SUM(oi.subtotal) DESC
                LIMIT 10
            ''', (start_date.isoformat(), end_date.isoformat()))

            top_products = product_cursor.fetchall()

            # Display report
            print("\n" + "=" * 80)
            print(f"           SALES REPORT - {period_name}")
            print("=" * 80)

            print("\n📊 OVERVIEW:")
            print(f"   Total Orders: {total_orders or 0}")
            print(f"   Total Revenue: {format_currency(float(total_revenue or 0))}")
            print(f"   Average Order: {format_currency(float(avg_order or 0))}")

            if category_sales:
                print("\n📦 SALES BY CATEGORY:")
                print("-" * 80)
                for category, revenue, quantity in category_sales:
                    print(f"   {category}: {format_currency(float(revenue))} ({float(quantity):.2f}kg)")

            if top_products:
                print("\n🏆 TOP PRODUCTS:")
                print("-" * 80)
                for idx, (name, quantity, revenue, count) in enumerate(top_products, 1):
                    print(f"   {idx}. {name}")
                    print(f"      Revenue: {format_currency(float(revenue))} | Sold: {float(quantity):.2f}kg | Orders: {count}")

            print("\n" + "=" * 80)

    except Exception as e:
        logger.error(f"Error generating sales report: {e}")
        print(f"❌ Error generating report: {e}")

    input("\nPress Enter to continue...")


def inventory_valuation_report():
    """Generate inventory valuation report (admin only)"""
    if not is_admin():
        print("❌ You don't have permission to view reports")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("Inventory Valuation Report")

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT category,
                       COUNT(*) as product_count,
                       SUM(stock_kg) as total_stock,
                       SUM(stock_kg * price_per_kg) as total_value
                FROM products
                WHERE source_type = 'butcher'
                GROUP BY category
                ORDER BY total_value DESC
            ''')

            categories = cursor.fetchall()

            # Overall totals
            total_cursor = conn.execute('''
                SELECT COUNT(*), SUM(stock_kg), SUM(stock_kg * price_per_kg)
                FROM products
                WHERE source_type = 'butcher'
            ''')

            total_products, total_stock, total_value = total_cursor.fetchone()

            print("\n" + "=" * 80)
            print("              INVENTORY VALUATION REPORT")
            print("=" * 80)
            print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            print("\n📦 BY CATEGORY:")
            print("-" * 80)
            print(f"{'Category':<20} {'Products':<12} {'Stock (kg)':<15} {'Value':>15}")
            print("-" * 80)

            for category, count, stock, value in categories:
                print(f"{category:<20} {count:<12} {float(stock):<15.2f} {format_currency(float(value)):>15}")

            print("-" * 80)
            print(f"{'TOTAL':<20} {total_products:<12} {float(total_stock):<15.2f} {format_currency(float(total_value)):>15}")
            print("=" * 80)

            # Low stock warning
            low_stock_cursor = conn.execute('''
                SELECT COUNT(*) FROM products
                WHERE source_type = 'butcher' AND stock_kg <= reorder_point
            ''')
            low_stock_count = low_stock_cursor.fetchone()[0]

            if low_stock_count > 0:
                print(f"\n⚠️  {low_stock_count} product(s) at or below reorder point")

    except Exception as e:
        logger.error(f"Error generating valuation report: {e}")
        print(f"❌ Error generating report: {e}")

    input("\nPress Enter to continue...")


def popular_products_analysis():
    """Analyze popular products (admin only)"""
    if not is_admin():
        print("❌ You don't have permission to view analytics")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("Popular Products Analysis")

        days = input("\nAnalyze last (days, default 30): ").strip()
        try:
            days = int(days) if days else 30
        except ValueError:
            days = 30

        start_date = (datetime.now() - timedelta(days=days)).isoformat()

        with get_connection() as conn:
            # Most ordered products
            cursor = conn.execute('''
                SELECT oi.item_name as product_name,
                       COUNT(DISTINCT o.order_id) as order_count,
                       SUM(oi.quantity_kg) as total_quantity,
                       SUM(oi.subtotal) as total_revenue,
                       AVG(oi.quantity_kg) as avg_quantity_per_order
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.order_id AND o.source_type = 'butcher'
                WHERE oi.source_type = 'butcher' AND o.order_date >= ? AND o.order_status != 'cancelled'
                GROUP BY oi.item_name
                ORDER BY order_count DESC
                LIMIT 15
            ''', (start_date,))

            products = cursor.fetchall()

            print(f"\n🏆 MOST POPULAR PRODUCTS (Last {days} days):")
            print("=" * 80)

            if not products:
                print("No orders in this period")
            else:
                print(f"\n{'Rank':<6} {'Product':<25} {'Orders':<10} {'Qty (kg)':<12} {'Revenue':>15}")
                print("-" * 80)

                for idx, (name, orders, quantity, revenue, avg_qty) in enumerate(products, 1):
                    print(f"{idx:<6} {name:<25} {orders:<10} {float(quantity):<12.2f} {format_currency(float(revenue)):>15}")

                print("=" * 80)

                # Additional insights
                total_orders = sum(p[1] for p in products)
                total_revenue = sum(p[3] for p in products)

                print(f"\n📊 INSIGHTS:")
                print(f"   Top 15 products account for:")
                print(f"   • {total_orders} orders")
                print(f"   • {format_currency(float(total_revenue))} revenue")

    except Exception as e:
        logger.error(f"Error analyzing popular products: {e}")
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def customer_purchase_history():
    """View customer purchase history (admin only)"""
    if not is_admin():
        print("❌ You don't have permission to view customer data")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("Customer Purchase History")

        customer_id = input("\nEnter customer username: ").strip()

        if not customer_id:
            print("❌ Customer username cannot be empty")
            input("\nPress Enter to continue...")
            return

        with get_connection() as conn:
            # Customer summary
            summary_cursor = conn.execute('''
                SELECT COUNT(*), SUM(total_amount), AVG(total_amount),
                       MIN(order_date), MAX(order_date)
                FROM orders
                WHERE source_type = 'butcher' AND user_id = ? AND order_status != 'cancelled'
            ''', (customer_id,))

            summary = summary_cursor.fetchone()

            if not summary or summary[0] == 0:
                print(f"\n❌ No orders found for customer: {customer_id}")
                input("\nPress Enter to continue...")
                return

            total_orders, total_spent, avg_order, first_order, last_order = summary

            # Favorite products
            fav_cursor = conn.execute('''
                SELECT oi.item_name as product_name, COUNT(*), SUM(oi.quantity_kg), SUM(oi.subtotal)
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.order_id AND o.source_type = 'butcher'
                WHERE oi.source_type = 'butcher' AND o.user_id = ? AND o.order_status != 'cancelled'
                GROUP BY oi.item_name
                ORDER BY COUNT(*) DESC
                LIMIT 5
            ''', (customer_id,))

            favorites = fav_cursor.fetchall()

            # Recent orders
            recent_cursor = conn.execute('''
                SELECT order_number, total_amount, order_status, order_date
                FROM orders
                WHERE source_type = 'butcher' AND user_id = ?
                ORDER BY order_date DESC
                LIMIT 10
            ''', (customer_id,))

            recent_orders = recent_cursor.fetchall()

            # Display report
            print("\n" + "=" * 80)
            print(f"        CUSTOMER PURCHASE HISTORY - {customer_id}")
            print("=" * 80)

            print("\n📊 SUMMARY:")
            print(f"   Total Orders: {total_orders}")
            print(f"   Total Spent: {format_currency(float(total_spent))}")
            print(f"   Average Order: {format_currency(float(avg_order))}")
            print(f"   First Order: {format_date(first_order)}")
            print(f"   Last Order: {format_date(last_order)}")

            if favorites:
                print("\n🏆 FAVORITE PRODUCTS:")
                print("-" * 80)
                for idx, (name, count, quantity, spent) in enumerate(favorites, 1):
                    print(f"   {idx}. {name}")
                    print(f"      Ordered {count} times | {float(quantity):.2f}kg total | {format_currency(float(spent))}")

            if recent_orders:
                print("\n📜 RECENT ORDERS:")
                print("-" * 80)
                for order_num, amount, status, order_date in recent_orders:
                    status_icons = {
                        'pending': '⏳',
                        'processing': '🔄',
                        'ready': '✅',
                        'completed': '✔️',
                        'cancelled': '❌'
                    }
                    icon = status_icons.get(status, '❓')
                    print(f"   {icon} {order_num} - {format_currency(float(amount))} - {status} - {format_date(order_date)}")

            print("\n" + "=" * 80)

    except Exception as e:
        logger.error(f"Error viewing customer history: {e}")
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


# ============================================================================
# ADMIN FUNCTIONS
# ============================================================================

def view_all_orders():
    """View all customer orders (admin only)"""
    if not is_admin():
        print("❌ You don't have permission to view all orders")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("All Orders")

        print("\n🔍 Filter by:")
        print("1. All orders")
        print("2. Pending orders")
        print("3. Processing orders")
        print("4. Ready for pickup")
        print("5. Completed orders")
        print("6. Cancelled orders")

        filter_choice = input("\nSelect filter (1-6): ").strip()

        status_filters = {
            '1': None,
            '2': 'pending',
            '3': 'processing',
            '4': 'ready',
            '5': 'completed',
            '6': 'cancelled'
        }

        status_filter = status_filters.get(filter_choice)

        with get_connection() as conn:
            if status_filter:
                cursor = conn.execute('''
                    SELECT order_id, order_number, user_name, total_amount,
                           order_status, order_date, pickup_date
                    FROM orders
                    WHERE source_type = 'butcher' AND order_status = ?
                    ORDER BY order_date DESC
                    LIMIT 50
                ''', (status_filter,))
            else:
                cursor = conn.execute('''
                    SELECT order_id, order_number, user_name, total_amount,
                           order_status, order_date, pickup_date
                    FROM orders
                    WHERE source_type = 'butcher'
                    ORDER BY order_date DESC
                    LIMIT 50
                ''')

            orders = cursor.fetchall()

            if not orders:
                print("\n❌ No orders found")
            else:
                print(f"\n📋 ORDERS ({len(orders)} shown):")
                print("=" * 80)

                for order in orders:
                    order_id, order_num, user_name, amount, status, order_date, pickup_date = order

                    status_icons = {
                        'pending': '⏳',
                        'processing': '🔄',
                        'ready': '✅',
                        'completed': '✔️',
                        'cancelled': '❌'
                    }
                    icon = status_icons.get(status, '❓')

                    print(f"\n{icon} {order_num}")
                    print(f"   Customer: {user_name}")
                    print(f"   Amount: {format_currency(float(amount))}")
                    print(f"   Status: {status.upper()}")
                    print(f"   Ordered: {format_date(order_date)}")
                    if pickup_date:
                        print(f"   Pickup: {pickup_date}")

                print("\n" + "=" * 80)

    except Exception as e:
        logger.error(f"Error viewing all orders: {e}")
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def update_order_status():
    """Update order status (admin only)"""
    if not is_admin():
        print("❌ You don't have permission to update orders")
        input("\nPress Enter to continue...")
        return

    try:
        print_subheader("Update Order Status")

        order_number = input("\nEnter order number: ").strip()

        if not order_number:
            print("❌ Order number cannot be empty")
            input("\nPress Enter to continue...")
            return

        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT order_id, user_name, total_amount, order_status, order_date
                FROM orders
                WHERE source_type = 'butcher' AND order_number = ?
            ''', (order_number,))

            order = cursor.fetchone()

            if not order:
                print(f"❌ Order {order_number} not found")
                input("\nPress Enter to continue...")
                return

            order_id, user_name, amount, current_status, order_date = order

            print(f"\n📋 Order: {order_number}")
            print(f"   Customer: {user_name}")
            print(f"   Amount: {format_currency(float(amount))}")
            print(f"   Current Status: {current_status.upper()}")
            print(f"   Ordered: {format_date(order_date)}")

            print("\n📊 New Status:")
            print("1. Pending")
            print("2. Processing")
            print("3. Ready for Pickup")
            print("4. Completed")
            print("5. Cancelled")

            status_choice = input("\nSelect new status (1-5): ").strip()

            status_map = {
                '1': 'pending',
                '2': 'processing',
                '3': 'ready',
                '4': 'completed',
                '5': 'cancelled'
            }

            new_status = status_map.get(status_choice)

            if not new_status:
                print("❌ Invalid status choice")
                input("\nPress Enter to continue...")
                return

            if new_status == current_status:
                print("❌ Status is already set to this value")
                input("\nPress Enter to continue...")
                return

            notes = input("Notes (optional): ").strip()

            confirm = input(f"\nUpdate status from '{current_status}' to '{new_status}'? (yes/no): ").strip().lower()

            if confirm != 'yes':
                print("❌ Update cancelled")
                input("\nPress Enter to continue...")
                return

            # Update status
            with transaction() as trans_conn:
                if new_status == 'completed':
                    trans_conn.execute('''
                        UPDATE orders
                        SET order_status = ?, completed_date = ?, notes = ?
                        WHERE order_id = ? AND source_type = 'butcher'
                    ''', (new_status, datetime.now().isoformat(), notes, order_id))
                else:
                    trans_conn.execute('''
                        UPDATE orders
                        SET order_status = ?, notes = ?
                        WHERE order_id = ? AND source_type = 'butcher'
                    ''', (new_status, notes, order_id))

            print(f"\n✅ Order {order_number} status updated to {new_status.upper()}")

            logger.info(f"Admin updated order {order_number} status to {new_status}")

            # Send email notification if available
            if EMAIL_AVAILABLE:
                try:
                    email_cursor = conn.execute('''
                        SELECT user_email FROM orders WHERE order_id = ? AND source_type = 'butcher'
                    ''', (order_id,))

                    email_result = email_cursor.fetchone()
                    if email_result and email_result[0]:
                        send_email(
                            email_result[0],
                            f'Butcher Shop Order Update - {order_number}',
                            f'Your order {order_number} status has been updated to: {new_status.upper()}'
                        )
                except Exception as e:
                    logger.error(f"Error sending status update email: {e}")

    except Exception as e:
        logger.error(f"Error updating order status: {e}")
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


# ============================================================================
# MAIN MENU
# ============================================================================

def butcher_menu():
    """Main butcher shop menu"""
    try:
        # Initialize database
        init_butcher_db()
    except Exception as e:
        logger.error(f"Failed to initialize butcher database: {e}")
        print(f"❌ Failed to initialize butcher system: {e}")
        input("\nPress Enter to continue...")
        return

    user = get_current_user()
    if not user:
        print("❌ You must be logged in to access the Butcher Shop")
        input("\nPress Enter to continue...")
        return

    is_staff = user.get('role') in ['admin', 'staff']

    while True:
        try:
            print_header("UNIVERSITY BUTCHER SHOP")

            if user:
                print(f"\nLogged in as: {user.get('username')} ({user.get('role')})")

            print("\n🥩 PRODUCTS:")
            print("1. Browse Products by Category")
            print("2. View Product Details")
            print("3. Search Products")

            print("\n🛒 ORDERS:")
            print("4. Place Order")
            print("5. View My Orders")
            print("6. View Order Receipt")
            print("7. Cancel Order")

            if is_staff:
                print("\n📦 INVENTORY (Staff):")
                print("8. View Inventory Status")
                print("9. Adjust Inventory")
                print("10. Low Stock Alerts")
                print("11. Manage Expiry Dates")

                print("\n📊 REPORTS (Staff):")
                print("12. Sales Reports")
                print("13. Inventory Valuation")
                print("14. Popular Products Analysis")
                print("15. Customer Purchase History")

                print("\n🔧 ADMIN:")
                print("16. Add Product")
                print("17. Update Product")
                print("18. View All Orders")
                print("19. Update Order Status")

            print("\n0. Return to Main Menu")

            choice = input("\nEnter choice: ").strip()

            if choice == "1":
                browse_products_by_category()
            elif choice == "2":
                view_product_details()
            elif choice == "3":
                search_products()
            elif choice == "4":
                place_order()
            elif choice == "5":
                view_my_orders()
            elif choice == "6":
                view_order_receipt()
            elif choice == "7":
                cancel_order()
            elif choice == "8" and is_staff:
                view_inventory()
            elif choice == "9" and is_staff:
                adjust_inventory()
            elif choice == "10" and is_staff:
                view_low_stock_alerts()
            elif choice == "11" and is_staff:
                manage_expiry_dates()
            elif choice == "12" and is_staff:
                sales_reports()
            elif choice == "13" and is_staff:
                inventory_valuation_report()
            elif choice == "14" and is_staff:
                popular_products_analysis()
            elif choice == "15" and is_staff:
                customer_purchase_history()
            elif choice == "16" and is_staff:
                add_product()
            elif choice == "17" and is_staff:
                update_product()
            elif choice == "18" and is_staff:
                view_all_orders()
            elif choice == "19" and is_staff:
                update_order_status()
            elif choice == "0":
                break
            else:
                print("❌ Invalid choice")
                input("Press Enter to continue...")

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in butcher menu: {e}")
            print(f"❌ An error occurred: {e}")
            input("Press Enter to continue...")


def launch_butcher_cli(auth=None):
    """Launch butcher shop CLI (called from main menu)"""
    butcher_menu()


if __name__ == "__main__":
    butcher_menu()
