"""
Bar/Pub CLI for University Management System

Provides a complete command-line point-of-sale system for the university bar
with age verification, menu management, order processing, and finance integration.
"""

from university_system.infrastructure.database.db import sqlite3
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Tuple

# Import centralized database and authentication
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.infrastructure.shared_context import get_auth

# Import finance integration
try:
    from university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        record_payment_to_finance
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False

# Import email service
try:
    from university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

# Import activity logger
try:
    from university_system.modules.shared.utils.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None

def get_current_user():
    """Get current authenticated user"""
    auth = get_auth()
    if auth and hasattr(auth, 'current_user') and auth.current_user:
        return auth.current_user
    return None

def init_bar_db():
    """Initialize bar database tables"""
    try:
        with transaction() as conn:
            # Bar menu items table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS bar_menu_items (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT,
                    price REAL NOT NULL,
                    is_alcoholic INTEGER DEFAULT 0,
                    available INTEGER DEFAULT 1,
                    stock_quantity INTEGER DEFAULT 100,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Bar orders table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS bar_orders (
                    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    customer_name TEXT,
                    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_amount REAL NOT NULL,
                    payment_method TEXT,
                    age_verified INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'completed',
                    notes TEXT
                )
            ''')

            # Bar order items table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS bar_order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER,
                    item_id INTEGER,
                    item_name TEXT,
                    quantity INTEGER,
                    unit_price REAL,
                    subtotal REAL,
                    FOREIGN KEY (order_id) REFERENCES bar_orders(order_id),
                    FOREIGN KEY (item_id) REFERENCES bar_menu_items(item_id)
                )
            ''')

            # Bar inventory transactions table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS bar_inventory_transactions (
                    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER,
                    quantity_change INTEGER,
                    transaction_type TEXT,
                    transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT,
                    FOREIGN KEY (item_id) REFERENCES bar_menu_items(item_id)
                )
            ''')

            # Insert sample menu items if table is empty
            cursor = conn.execute('SELECT COUNT(*) FROM bar_menu_items')
            if cursor.fetchone()[0] == 0:
                sample_items = [
                    # Beer
                    ('Lager', 'Beer', 'Refreshing lager beer', 3.50, 1, 1, 100),
                    ('Ale', 'Beer', 'Traditional English ale', 4.00, 1, 1, 80),
                    ('IPA', 'Beer', 'India Pale Ale', 4.50, 1, 1, 60),
                    ('Stout', 'Beer', 'Rich dark stout', 5.00, 1, 1, 50),
                    ('Cider', 'Beer', 'Crisp apple cider', 4.00, 1, 1, 70),
                    # Wine
                    ('House Red', 'Wine', 'House red wine', 4.50, 1, 1, 40),
                    ('House White', 'Wine', 'House white wine', 4.50, 1, 1, 40),
                    ('Prosecco', 'Wine', 'Italian sparkling wine', 6.00, 1, 1, 30),
                    # Spirits
                    ('Vodka', 'Spirits', 'Single shot of vodka', 3.00, 1, 1, 100),
                    ('Gin', 'Spirits', 'Single shot of gin', 3.50, 1, 1, 100),
                    ('Rum', 'Spirits', 'Single shot of rum', 3.00, 1, 1, 100),
                    ('Whisky', 'Spirits', 'Single shot of whisky', 4.00, 1, 1, 80),
                    # Cocktails
                    ('Mojito', 'Cocktails', 'Rum, mint, lime, soda', 7.00, 1, 1, 50),
                    ('Margarita', 'Cocktails', 'Tequila, lime, triple sec', 7.50, 1, 1, 50),
                    ('Long Island', 'Cocktails', 'Mixed spirits and cola', 8.50, 1, 1, 40),
                    # Soft Drinks
                    ('Cola', 'Soft Drinks', 'Classic cola', 1.80, 0, 1, 200),
                    ('Lemonade', 'Soft Drinks', 'Sparkling lemonade', 1.80, 0, 1, 200),
                    ('Orange Juice', 'Soft Drinks', 'Fresh orange juice', 2.50, 0, 1, 100),
                    ('Water', 'Soft Drinks', 'Sparkling water', 1.50, 0, 1, 200),
                    # Snacks
                    ('Crisps', 'Snacks', 'Variety of crisps', 1.50, 0, 1, 100),
                    ('Nuts', 'Snacks', 'Salted peanuts', 2.00, 0, 1, 80),
                    ('Nachos', 'Snacks', 'Nachos with salsa/cheese', 5.00, 0, 1, 50),
                    ('Chips', 'Snacks', 'Portion of chips', 3.50, 0, 1, 60),
                    # Hot Drinks
                    ('Coffee', 'Hot Drinks', 'Fresh brewed coffee', 2.50, 0, 1, 100),
                    ('Tea', 'Hot Drinks', 'Selection of teas', 2.00, 0, 1, 100),
                ]
                conn.executemany('''
                    INSERT INTO bar_menu_items (name, category, description, price, is_alcoholic, available, stock_quantity)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', sample_items)

        print("✅ Bar database initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        return False

def print_header(title: str):
    """Print formatted header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

# Current order (global shopping cart)
current_order = []

def view_menu():
    """View all menu items by category"""
    print_header("BAR MENU")

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT DISTINCT category FROM bar_menu_items
                WHERE available = 1
                ORDER BY category
            ''')
            categories = [row[0] for row in cursor.fetchall()]

            for category in categories:
                print(f"\n━━━ {category} ━━━")
                cursor = conn.execute('''
                    SELECT item_id, name, description, price, stock_quantity, is_alcoholic
                    FROM bar_menu_items
                    WHERE category = ? AND available = 1
                    ORDER BY name
                ''', (category,))

                items = cursor.fetchall()
                for item in items:
                    item_id, name, desc, price, stock, is_alc = item
                    alc_marker = "🍺" if is_alc else "🥤"
                    print(f"  [{item_id}] {alc_marker} {name} - £{price:.2f}")
                    if desc:
                        print(f"      {desc}")
                    print(f"      Stock: {stock}")

    except Exception as e:
        print(f"❌ Error loading menu: {e}")

    input("\nPress Enter to continue...")

def browse_by_category():
    """Browse menu items by category"""
    print_header("BROWSE BY CATEGORY")

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT DISTINCT category FROM bar_menu_items
                WHERE available = 1
                ORDER BY category
            ''')
            categories = [row[0] for row in cursor.fetchall()]

            print("\nAvailable Categories:")
            for i, cat in enumerate(categories, 1):
                print(f"{i}. {cat}")

            choice = input("\nSelect category number (or Enter to cancel): ").strip()
            if not choice:
                return

            try:
                cat_index = int(choice) - 1
                if 0 <= cat_index < len(categories):
                    selected_category = categories[cat_index]

                    print(f"\n━━━ {selected_category} ━━━")
                    cursor = conn.execute('''
                        SELECT item_id, name, description, price, stock_quantity, is_alcoholic
                        FROM bar_menu_items
                        WHERE category = ? AND available = 1
                        ORDER BY name
                    ''', (selected_category,))

                    items = cursor.fetchall()
                    for item in items:
                        item_id, name, desc, price, stock, is_alc = item
                        alc_marker = "🍺" if is_alc else "🥤"
                        print(f"\n[{item_id}] {alc_marker} {name} - £{price:.2f}")
                        if desc:
                            print(f"    {desc}")
                        print(f"    Stock: {stock}")
                else:
                    print("Invalid category selection")
            except ValueError:
                print("Invalid input")

    except Exception as e:
        print(f"❌ Error browsing categories: {e}")

    input("\nPress Enter to continue...")

def add_to_order():
    """Add item to current order"""
    print_header("ADD TO ORDER")

    item_id = input("Enter item ID: ").strip()
    if not item_id:
        return

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT item_id, name, price, stock_quantity, is_alcoholic
                FROM bar_menu_items
                WHERE item_id = ? AND available = 1
            ''', (item_id,))

            item = cursor.fetchone()
            if not item:
                print("❌ Item not found or unavailable")
                input("Press Enter to continue...")
                return

            item_id, name, price, stock, is_alcoholic = item

            if stock <= 0:
                print("❌ Item out of stock")
                input("Press Enter to continue...")
                return

            quantity = input(f"Enter quantity (stock: {stock}): ").strip()
            try:
                quantity = int(quantity)
                if quantity <= 0:
                    print("❌ Quantity must be positive")
                    return
                if quantity > stock:
                    print(f"❌ Only {stock} available")
                    return

                # Add to order
                current_order.append({
                    'item_id': item_id,
                    'name': name,
                    'price': price,
                    'quantity': quantity,
                    'is_alcoholic': is_alcoholic
                })

                print(f"✅ Added {quantity}x {name} to order")
                log_activity('add_to_cart', 'bar', details={'item': name, 'quantity': quantity})

            except ValueError:
                print("❌ Invalid quantity")

    except Exception as e:
        print(f"❌ Error adding to order: {e}")

    input("Press Enter to continue...")

def view_current_order():
    """View current order"""
    print_header("CURRENT ORDER")

    if not current_order:
        print("\n📦 Order is empty")
        input("\nPress Enter to continue...")
        return

    total = 0.0
    has_alcohol = False

    print("\nItem                          Qty    Price    Subtotal")
    print("-" * 60)

    for item in current_order:
        subtotal = item['price'] * item['quantity']
        total += subtotal
        alc_marker = "🍺" if item['is_alcoholic'] else "  "
        print(f"{alc_marker} {item['name']:<25} {item['quantity']:3d}  £{item['price']:6.2f}  £{subtotal:7.2f}")
        if item['is_alcoholic']:
            has_alcohol = True

    print("-" * 60)
    print(f"{'TOTAL':<35}           £{total:7.2f}")

    if has_alcohol:
        print("\n⚠️  Order contains alcoholic items - age verification required")

    input("\nPress Enter to continue...")

def checkout():
    """Process checkout"""
    global current_order

    print_header("CHECKOUT")

    if not current_order:
        print("\n❌ Order is empty")
        input("Press Enter to continue...")
        return

    # Calculate total and check for alcohol
    total = sum(item['price'] * item['quantity'] for item in current_order)
    has_alcohol = any(item['is_alcoholic'] for item in current_order)

    print(f"\nOrder Total: £{total:.2f}")

    # Age verification if order contains alcohol
    age_verified = False
    if has_alcohol:
        print("\n⚠️  This order contains alcoholic items")
        verify = input("Verify customer is 18+ (yes/no): ").strip().lower()
        if verify != 'yes':
            print("❌ Age verification failed - cannot complete order")
            input("Press Enter to continue...")
            return
        age_verified = True

    # Get customer details
    customer_name = input("\nEnter customer name: ").strip()
    if not customer_name:
        customer_name = "Guest"

    # Get student ID (optional)
    student_id = input("Enter student ID (or Enter to skip): ").strip()

    # Payment method
    print("\nPayment Methods:")
    print("1. Cash")
    print("2. Card")
    if student_id and FINANCE_AVAILABLE:
        print("3. Student Account")

    payment_choice = input("\nSelect payment method: ").strip()

    payment_method = None
    if payment_choice == "1":
        payment_method = "Cash"
    elif payment_choice == "2":
        payment_method = "Card"
    elif payment_choice == "3" and student_id and FINANCE_AVAILABLE:
        payment_method = "Student Account"
        # Process student account payment
        try:
            success = process_student_finance_account_payment(
                student_id=student_id,
                amount=total,
                description=f"Bar purchase - {len(current_order)} items"
            )
            if not success:
                print("❌ Student account payment failed")
                input("Press Enter to continue...")
                return
        except Exception as e:
            print(f"❌ Payment error: {e}")
            input("Press Enter to continue...")
            return
    else:
        print("❌ Invalid payment method")
        input("Press Enter to continue...")
        return

    # Process order
    try:
        with transaction() as conn:
            # Create order
            cursor = conn.execute('''
                INSERT INTO bar_orders (student_id, customer_name, total_amount, payment_method, age_verified, status)
                VALUES (?, ?, ?, ?, ?, 'completed')
            ''', (student_id or None, customer_name, total, payment_method, 1 if age_verified else 0))

            order_id = cursor.lastrowid

            # Add order items and update stock
            for item in current_order:
                conn.execute('''
                    INSERT INTO bar_order_items (order_id, item_id, item_name, quantity, unit_price, subtotal)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (order_id, item['item_id'], item['name'], item['quantity'],
                      item['price'], item['price'] * item['quantity']))

                # Update stock
                conn.execute('''
                    UPDATE bar_menu_items
                    SET stock_quantity = stock_quantity - ?
                    WHERE item_id = ?
                ''', (item['quantity'], item['item_id']))

                # Log inventory transaction
                conn.execute('''
                    INSERT INTO bar_inventory_transactions (item_id, quantity_change, transaction_type, notes)
                    VALUES (?, ?, 'sale', ?)
                ''', (item['item_id'], -item['quantity'], f'Order #{order_id}'))

            # Record in finance system
            if FINANCE_AVAILABLE and payment_method != "Student Account":
                record_payment_to_finance(
                    student_id=student_id,
                    amount=total,
                    payment_type="Bar Sales",
                    description=f"Bar Order #{order_id}",
                    payment_method=payment_method
                )

        print(f"\n✅ Order #{order_id} completed successfully!")
        print(f"Payment: {payment_method} - £{total:.2f}")

        log_activity('create', 'bar_order', order_id=order_id, details={
            'total': total, 'items': len(current_order), 'payment': payment_method
        })

        # Clear order
        current_order = []

    except Exception as e:
        print(f"❌ Error processing order: {e}")

    input("\nPress Enter to continue...")

def view_order_history():
    """View order history"""
    print_header("ORDER HISTORY")

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT order_id, customer_name, order_date, total_amount, payment_method, status
                FROM bar_orders
                ORDER BY order_date DESC
                LIMIT 50
            ''')

            orders = cursor.fetchall()

            if not orders:
                print("\n📋 No orders found")
            else:
                print("\nID    Customer              Date/Time            Total     Payment      Status")
                print("-" * 90)
                for order in orders:
                    order_id, customer, date, total, payment, status = order
                    print(f"{order_id:<5} {customer:<20} {date[:19]:<20} £{total:7.2f}  {payment:<12} {status}")

                # Option to view order details
                print("\n")
                order_id = input("Enter order ID to view details (or Enter to return): ").strip()
                if order_id:
                    view_order_details(order_id)

    except Exception as e:
        print(f"❌ Error loading order history: {e}")

    input("\nPress Enter to continue...")

def view_order_details(order_id: str):
    """View detailed order information"""
    try:
        with get_connection() as conn:
            # Get order info
            cursor = conn.execute('''
                SELECT order_id, customer_name, student_id, order_date, total_amount,
                       payment_method, age_verified, status, notes
                FROM bar_orders
                WHERE order_id = ?
            ''', (order_id,))

            order = cursor.fetchone()
            if not order:
                print(f"\n❌ Order #{order_id} not found")
                return

            order_id, customer, student_id, date, total, payment, age_verified, status, notes = order

            print(f"\n━━━ Order #{order_id} Details ━━━")
            print(f"Customer: {customer}")
            if student_id:
                print(f"Student ID: {student_id}")
            print(f"Date/Time: {date}")
            print(f"Payment: {payment}")
            print(f"Status: {status}")
            if age_verified:
                print("Age Verified: ✓")
            if notes:
                print(f"Notes: {notes}")

            # Get order items
            cursor = conn.execute('''
                SELECT item_name, quantity, unit_price, subtotal
                FROM bar_order_items
                WHERE order_id = ?
            ''', (order_id,))

            items = cursor.fetchall()

            print("\nItems:")
            print("  Item                          Qty    Price    Subtotal")
            print("  " + "-" * 58)
            for item in items:
                name, qty, price, subtotal = item
                print(f"  {name:<27} {qty:3d}  £{price:6.2f}  £{subtotal:7.2f}")

            print("  " + "-" * 58)
            print(f"  {'TOTAL':<33}           £{total:7.2f}")

    except Exception as e:
        print(f"❌ Error loading order details: {e}")

def manage_menu_items():
    """Manage menu items (admin)"""
    user = get_current_user()
    if not user or user.get('role') not in ['admin', 'staff']:
        print("\n❌ Admin/staff access required")
        input("Press Enter to continue...")
        return

    while True:
        print_header("MENU MANAGEMENT")
        print("\n1. Add new item")
        print("2. Update item")
        print("3. Toggle availability")
        print("4. Update stock")
        print("5. View all items")
        print("6. Return to main menu")

        choice = input("\nEnter choice: ").strip()

        if choice == "1":
            add_menu_item()
        elif choice == "2":
            update_menu_item()
        elif choice == "3":
            toggle_item_availability()
        elif choice == "4":
            update_stock()
        elif choice == "5":
            view_all_items()
        elif choice == "6":
            break
        else:
            print("Invalid choice")
            input("Press Enter to continue...")

def add_menu_item():
    """Add new menu item"""
    print_header("ADD MENU ITEM")

    name = input("Item name: ").strip()
    if not name:
        return

    print("\nCategories: Beer, Wine, Spirits, Cocktails, Soft Drinks, Snacks, Hot Drinks")
    category = input("Category: ").strip()
    if not category:
        return

    description = input("Description: ").strip()

    try:
        price = float(input("Price (£): ").strip())
        stock = int(input("Stock quantity: ").strip())

        is_alcoholic = input("Is alcoholic? (yes/no): ").strip().lower() == 'yes'

        with transaction() as conn:
            conn.execute('''
                INSERT INTO bar_menu_items (name, category, description, price, is_alcoholic, available, stock_quantity)
                VALUES (?, ?, ?, ?, ?, 1, ?)
            ''', (name, category, description, price, 1 if is_alcoholic else 0, stock))

        print(f"✅ Added {name} to menu")
        log_activity('create', 'bar_menu_item', details={'name': name, 'category': category})

    except ValueError:
        print("❌ Invalid price or stock quantity")
    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")

def update_menu_item():
    """Update existing menu item"""
    print_header("UPDATE MENU ITEM")

    item_id = input("Enter item ID: ").strip()
    if not item_id:
        return

    try:
        with get_connection() as conn:
            cursor = conn.execute('SELECT * FROM bar_menu_items WHERE item_id = ?', (item_id,))
            item = cursor.fetchone()

            if not item:
                print("❌ Item not found")
                input("Press Enter to continue...")
                return

            print(f"\nCurrent: {item[1]} - £{item[4]}")

            name = input(f"New name (or Enter to keep): ").strip() or item[1]
            category = input(f"New category (or Enter to keep): ").strip() or item[2]

            price_input = input(f"New price (or Enter to keep £{item[4]}): ").strip()
            price = float(price_input) if price_input else item[4]

            with transaction() as conn:
                conn.execute('''
                    UPDATE bar_menu_items
                    SET name = ?, category = ?, price = ?
                    WHERE item_id = ?
                ''', (name, category, price, item_id))

            print("✅ Item updated")
            log_activity('update', 'bar_menu_item', item_id=item_id)

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")

def toggle_item_availability():
    """Toggle item availability"""
    print_header("TOGGLE AVAILABILITY")

    item_id = input("Enter item ID: ").strip()
    if not item_id:
        return

    try:
        with transaction() as conn:
            cursor = conn.execute('SELECT name, available FROM bar_menu_items WHERE item_id = ?', (item_id,))
            item = cursor.fetchone()

            if not item:
                print("❌ Item not found")
            else:
                name, available = item
                new_status = 0 if available else 1
                conn.execute('UPDATE bar_menu_items SET available = ? WHERE item_id = ?', (new_status, item_id))
                status_text = "available" if new_status else "unavailable"
                print(f"✅ {name} is now {status_text}")
                log_activity('update', 'bar_menu_item', item_id=item_id, details={'available': new_status})

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")

def update_stock():
    """Update item stock quantity"""
    print_header("UPDATE STOCK")

    item_id = input("Enter item ID: ").strip()
    if not item_id:
        return

    try:
        with get_connection() as conn:
            cursor = conn.execute('SELECT name, stock_quantity FROM bar_menu_items WHERE item_id = ?', (item_id,))
            item = cursor.fetchone()

            if not item:
                print("❌ Item not found")
                input("Press Enter to continue...")
                return

            name, current_stock = item
            print(f"\nCurrent stock for {name}: {current_stock}")

            new_stock = int(input("Enter new stock quantity: ").strip())

            with transaction() as conn:
                conn.execute('UPDATE bar_menu_items SET stock_quantity = ? WHERE item_id = ?', (new_stock, item_id))

                # Log inventory transaction
                change = new_stock - current_stock
                trans_type = "restock" if change > 0 else "adjustment"
                conn.execute('''
                    INSERT INTO bar_inventory_transactions (item_id, quantity_change, transaction_type, notes)
                    VALUES (?, ?, ?, 'Manual stock update')
                ''', (item_id, change, trans_type))

            print(f"✅ Stock updated for {name}: {current_stock} → {new_stock}")
            log_activity('update', 'bar_inventory', item_id=item_id, details={'old': current_stock, 'new': new_stock})

    except ValueError:
        print("❌ Invalid stock quantity")
    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")

def view_all_items():
    """View all menu items including unavailable ones"""
    print_header("ALL MENU ITEMS")

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT item_id, name, category, price, stock_quantity, available, is_alcoholic
                FROM bar_menu_items
                ORDER BY category, name
            ''')

            items = cursor.fetchall()

            print("\nID    Name                      Category        Price   Stock   Avail  Alc")
            print("-" * 85)
            for item in items:
                item_id, name, cat, price, stock, avail, is_alc = item
                avail_mark = "✓" if avail else "✗"
                alc_mark = "✓" if is_alc else "✗"
                print(f"{item_id:<5} {name:<25} {cat:<15} £{price:5.2f}  {stock:5d}    {avail_mark}      {alc_mark}")

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")

def view_sales_report():
    """View sales report"""
    user = get_current_user()
    if not user or user.get('role') not in ['admin', 'staff']:
        print("\n❌ Admin/staff access required")
        input("Press Enter to continue...")
        return

    print_header("SALES REPORT")

    try:
        with get_connection() as conn:
            # Today's sales
            cursor = conn.execute('''
                SELECT COUNT(*), SUM(total_amount)
                FROM bar_orders
                WHERE DATE(order_date) = DATE('now')
            ''')
            today = cursor.fetchone()

            # This week's sales
            cursor = conn.execute('''
                SELECT COUNT(*), SUM(total_amount)
                FROM bar_orders
                WHERE order_date >= DATE('now', '-7 days')
            ''')
            week = cursor.fetchone()

            # All time sales
            cursor = conn.execute('''
                SELECT COUNT(*), SUM(total_amount)
                FROM bar_orders
            ''')
            total = cursor.fetchone()

            print("\n📊 Sales Summary:")
            print(f"\nToday:      {today[0] or 0} orders, £{today[1] or 0:.2f}")
            print(f"This Week:  {week[0] or 0} orders, £{week[1] or 0:.2f}")
            print(f"All Time:   {total[0] or 0} orders, £{total[1] or 0:.2f}")

            # Top selling items
            cursor = conn.execute('''
                SELECT item_name, SUM(quantity) as total_qty, SUM(subtotal) as total_sales
                FROM bar_order_items
                GROUP BY item_name
                ORDER BY total_qty DESC
                LIMIT 10
            ''')

            top_items = cursor.fetchall()

            if top_items:
                print("\n🏆 Top Selling Items:")
                print("\nItem                          Quantity  Sales")
                print("-" * 50)
                for item in top_items:
                    name, qty, sales = item
                    print(f"{name:<27} {qty:8d}  £{sales:7.2f}")

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")

def bar_menu():
    """Main bar menu"""
    # Initialize database
    init_bar_db()

    user = get_current_user()
    is_staff = user and user.get('role') in ['admin', 'staff']

    while True:
        print_header("UNIVERSITY BAR / PUB")

        if user:
            print(f"\nLogged in as: {user.get('username')} ({user.get('role')})")

        print("\n📋 MENU OPTIONS:")
        print("1. View Full Menu")
        print("2. Browse by Category")
        print("3. Add Item to Order")
        print("4. View Current Order")
        print("5. Checkout")
        print("6. View Order History")

        if is_staff:
            print("\n🔧 ADMIN OPTIONS:")
            print("7. Manage Menu Items")
            print("8. View Sales Report")

        print("\n0. Return to Main Menu")

        choice = input("\nEnter choice: ").strip()

        if choice == "1":
            view_menu()
        elif choice == "2":
            browse_by_category()
        elif choice == "3":
            add_to_order()
        elif choice == "4":
            view_current_order()
        elif choice == "5":
            checkout()
        elif choice == "6":
            view_order_history()
        elif choice == "7" and is_staff:
            manage_menu_items()
        elif choice == "8" and is_staff:
            view_sales_report()
        elif choice == "0":
            break
        else:
            print("Invalid choice")
            input("Press Enter to continue...")

if __name__ == "__main__":
    bar_menu()
