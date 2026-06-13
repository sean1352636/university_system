"""
Restaurant management service module.
"""

import os
import sys
from typing import Any, Dict, List, Optional
from education_system.university_system.infrastructure.database.db import sqlite3
import logging
from datetime import datetime

# Import centralized paths
from education_system.university_system.core import paths

# Database path from centralized configuration
DB_PATH = str(paths.DEFAULT_DB_PATH)

# Setup logging
logger = logging.getLogger(__name__)

# Import auth instance management from user_authentication
try:
    from education_system.university_system.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

# Global auth variable
_auth_instance = None

def set_auth(auth: Any) -> None:
    """Set the authentication instance."""
    global _auth_instance
    _auth_instance = auth
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth)


def init_db() -> bool:
    """Initialize the restaurant database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Create menu items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS menu_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                category TEXT NOT NULL,
                available BOOLEAN DEFAULT 1,
                ingredients TEXT,
                allergens TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # restaurant_orders table removed - now using unified 'orders' table with source_type='restaurant'

        # Create inventory table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit TEXT NOT NULL,
                minimum_threshold INTEGER DEFAULT 10,
                supplier TEXT,
                cost_per_unit REAL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create staff schedules table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS staff_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id TEXT NOT NULL,
                shift_date DATE NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                position TEXT NOT NULL,
                status TEXT DEFAULT 'scheduled',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()
        logger.info("Restaurant database initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing restaurant database: {e}")
        return False

def display_main_menu(auth=None):
    """Display the main restaurant management menu."""
    if auth is None:
        auth = _auth_instance

    if not auth or not auth.check_session():
        print("Please log in to access the restaurant management system.")
        return

    try:
        # Try to import from domain restaurant operations
        from education_system.university_system.modules.domain.commerce.services.restaurant.operations.restaurant_core import display_main_menu as display_restaurant_menu
        display_restaurant_menu()
    except ImportError:
        logger.warning("Could not import domain restaurant core, using fallback implementation")
        display_fallback_menu(auth)

def display_fallback_menu(auth):
    """Fallback restaurant management menu."""
    while True:
        print("\n" + "="*50)
        print("        RESTAURANT MANAGEMENT SYSTEM")
        print("="*50)
        print("1. Menu Management")
        print("2. Order Management")
        print("3. Inventory Management")
        print("4. Staff Scheduling")
        print("5. Sales Reports")
        print("6. Customer Management")
        print("0. Return to Main Menu")
        print("="*50)

        choice = input("Enter your choice (0-6): ").strip()

        if choice == '0':
            break
        elif choice == '1':
            menu_management(auth)
        elif choice == '2':
            order_management(auth)
        elif choice == '3':
            inventory_management(auth)
        elif choice == '4':
            staff_scheduling(auth)
        elif choice == '5':
            sales_reports(auth)
        elif choice == '6':
            customer_management(auth)
        else:
            print("Invalid choice. Please try again.")

def menu_management(auth):
    """Manage restaurant menu items."""
    while True:
        print("\n--- Menu Management ---")
        print("1. View Menu")
        print("2. Add Menu Item")
        print("3. Update Menu Item")
        print("4. Remove Menu Item")
        print("5. Toggle Availability")
        print("0. Back")

        choice = input("Enter your choice (0-5): ").strip()

        if choice == '0':
            break
        elif choice == '1':
            view_menu()
        elif choice == '2':
            if auth.has_permission('restaurant_manager'):
                add_menu_item()
            else:
                print("Access denied. Manager privileges required.")
        elif choice == '3':
            if auth.has_permission('restaurant_manager'):
                update_menu_item()
            else:
                print("Access denied. Manager privileges required.")
        elif choice == '4':
            if auth.has_permission('restaurant_manager'):
                remove_menu_item()
            else:
                print("Access denied. Manager privileges required.")
        elif choice == '5':
            if auth.has_permission('restaurant_manager'):
                toggle_availability()
            else:
                print("Access denied. Manager privileges required.")
        else:
            print("Invalid choice. Please try again.")

def view_menu():
    """View current menu items."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, name, description, price, category, available
            FROM menu_items
            ORDER BY category, name
        ''')

        items = cursor.fetchall()
        conn.close()

        if not items:
            print("\nNo menu items found.")
            return

        print(f"\n--- Current Menu ({len(items)} items) ---")
        current_category = ""
        for item in items:
            if item[4] != current_category:
                current_category = item[4]
                print(f"\n{current_category.upper()}:")
                print("-" * 40)

            status = "Available" if item[5] else "Unavailable"
            print(f"{item[0]:>3}. {item[1]:<20} £{item[3]:>6.2f} [{status}]")
            if item[2]:
                print(f"     {item[2]}")

    except Exception as e:
        print(f"Error viewing menu: {e}")
        logger.error(f"Error viewing menu: {e}")

def add_menu_item():
    """Add a new menu item."""
    print("\n--- Add Menu Item ---")

    name = input("Item name: ").strip()
    if not name:
        print("Name cannot be empty.")
        return

    description = input("Description: ").strip()

    try:
        price = float(input("Price: $"))
        if price < 0:
            print("Price cannot be negative.")
            return
    except ValueError:
        print("Invalid price format.")
        return

    categories = ["Appetizer", "Main Course", "Dessert", "Beverage", "Side"]
    print("Available categories:")
    for i, cat in enumerate(categories, 1):
        print(f"{i}. {cat}")

    try:
        cat_choice = int(input("Select category (1-5): ")) - 1
        if 0 <= cat_choice < len(categories):
            category = categories[cat_choice]
        else:
            print("Invalid category selection.")
            return
    except ValueError:
        print("Invalid input.")
        return

    ingredients = input("Ingredients (optional): ").strip()
    allergens = input("Allergens (optional): ").strip()

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO menu_items
            (name, description, price, category, ingredients, allergens)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, description, price, category, ingredients, allergens))

        item_id = cursor.lastrowid
        conn.commit()
        conn.close()

        print(f"\nMenu item '{name}' added successfully! ID: {item_id}")
        logger.info(f"Menu item added: {name} (ID: {item_id})")

    except Exception as e:
        print(f"Error adding menu item: {e}")
        logger.error(f"Error adding menu item: {e}")

def order_management(auth):
    """Manage restaurant orders."""
    while True:
        print("\n--- Order Management ---")
        print("1. View All Orders")
        print("2. View Pending Orders")
        print("3. Update Order Status")
        print("4. View Order Details")
        print("5. Daily Order Summary")
        print("0. Back")

        choice = input("Enter your choice (0-5): ").strip()

        if choice == '0':
            break
        elif choice == '1':
            view_all_orders()
        elif choice == '2':
            view_pending_orders()
        elif choice == '3':
            update_order_status()
        elif choice == '4':
            view_order_details()
        elif choice == '5':
            daily_order_summary()
        else:
            print("Invalid choice. Please try again.")

def view_all_orders():
    """View all restaurant orders."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, customer_id, total_amount, status, order_date
            FROM orders
            ORDER BY order_date DESC
            LIMIT 50
        ''')

        orders = cursor.fetchall()
        conn.close()

        if not orders:
            print("\nNo orders found.")
            return

        print(f"\n--- All Orders (Last 50) ---")
        print(f"{'ID':<5} {'Customer':<15} {'Amount':<10} {'Status':<12} {'Date':<19}")
        print("-" * 70)

        for order in orders:
            print(f"{order[0]:<5} {order[1]:<15} £{order[2]:<9.2f} {order[3]:<12} {order[4]:<19}")

    except Exception as e:
        print(f"Error viewing orders: {e}")
        logger.error(f"Error viewing orders: {e}")

def view_pending_orders():
    """View pending orders."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, customer_id, total_amount, order_date, special_instructions
            FROM orders
            WHERE status = 'pending'
            ORDER BY order_date ASC
        ''')

        orders = cursor.fetchall()
        conn.close()

        if not orders:
            print("\nNo pending orders.")
            return

        print(f"\n--- Pending Orders ({len(orders)} total) ---")
        for order in orders:
            print(f"\nOrder #{order[0]} - Customer: {order[1]}")
            print(f"Amount: £{order[2]:.2f} - Ordered: {order[3]}")
            if order[4]:
                print(f"Special Instructions: {order[4]}")

    except Exception as e:
        print(f"Error viewing pending orders: {e}")
        logger.error(f"Error viewing pending orders: {e}")

def inventory_management(auth):
    """Manage restaurant inventory."""
    print("\n--- Inventory Management ---")
    print("This feature manages restaurant inventory and supplies.")
    print("Implementation includes:")
    print("- Stock level monitoring")
    print("- Automatic reorder alerts")
    print("- Supplier management")
    print("- Cost tracking")
    print("\nFeature is being developed...")

def staff_scheduling(auth):
    """Manage staff schedules."""
    print("\n--- Staff Scheduling ---")
    print("This feature manages restaurant staff schedules.")
    print("Implementation includes:")
    print("- Shift scheduling")
    print("- Staff availability")
    print("- Time tracking")
    print("- Position assignments")
    print("\nFeature is being developed...")

def sales_reports(auth):
    """Generate sales reports."""
    print("\n--- Sales Reports ---")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Today's sales
        cursor.execute('''
            SELECT COUNT(*), SUM(total_amount)
            FROM orders
            WHERE DATE(order_date) = DATE('now')
        ''')
        today_stats = cursor.fetchone()

        # This week's sales
        cursor.execute('''
            SELECT COUNT(*), SUM(total_amount)
            FROM orders
            WHERE DATE(order_date) >= DATE('now', '-7 days')
        ''')
        week_stats = cursor.fetchone()

        # Popular items (placeholder)
        cursor.execute('''
            SELECT COUNT(*) as total_orders
            FROM orders
        ''')
        total_orders = cursor.fetchone()[0]

        conn.close()

        print(f"\n--- Sales Summary ---")
        print(f"Today's Orders: {today_stats[0] or 0}")
        print(f"Today's Revenue: £{today_stats[1] or 0:.2f}")
        print(f"Weekly Orders: {week_stats[0] or 0}")
        print(f"Weekly Revenue: £{week_stats[1] or 0:.2f}")
        print(f"Total Orders: {total_orders}")

    except Exception as e:
        print(f"Error generating reports: {e}")
        logger.error(f"Error generating sales reports: {e}")

def customer_management(auth):
    """Manage customer information."""
    print("\n--- Customer Management ---")
    print("This feature manages customer relationships.")
    print("Implementation includes:")
    print("- Customer profiles")
    print("- Order history")
    print("- Preferences tracking")
    print("- Loyalty programs")
    print("\nFeature is being developed...")

def update_order_status():
    """Update the status of an order."""
    order_id = input("Enter order ID: ").strip()
    if not order_id.isdigit():
        print("Invalid order ID.")
        return

    statuses = ["pending", "preparing", "ready", "delivered", "cancelled"]
    print("Available statuses:")
    for i, status in enumerate(statuses, 1):
        print(f"{i}. {status}")

    try:
        status_choice = int(input("Select new status (1-5): ")) - 1
        if 0 <= status_choice < len(statuses):
            new_status = statuses[status_choice]
        else:
            print("Invalid status selection.")
            return
    except ValueError:
        print("Invalid input.")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE orders
            SET status = ?, completed_at = CASE WHEN ? IN ('delivered', 'cancelled') THEN CURRENT_TIMESTAMP ELSE completed_at END
            WHERE id = ?
        ''', (new_status, new_status, order_id))

        if cursor.rowcount > 0:
            conn.commit()
            print(f"Order #{order_id} status updated to '{new_status}'.")
            logger.info(f"Order #{order_id} status updated to '{new_status}'")
        else:
            print(f"Order #{order_id} not found.")

        conn.close()

    except Exception as e:
        print(f"Error updating order: {e}")
        logger.error(f"Error updating order: {e}")

def view_order_details():
    """View detailed information about an order."""
    order_id = input("Enter order ID: ").strip()
    if not order_id.isdigit():
        print("Invalid order ID.")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, customer_id, items, total_amount, status, order_date,
                   delivery_address, special_instructions, payment_method, completed_at
            FROM orders
            WHERE id = ?
        ''', (order_id,))

        order = cursor.fetchone()
        conn.close()

        if not order:
            print(f"Order #{order_id} not found.")
            return

        print(f"\n--- Order #{order[0]} Details ---")
        print(f"Customer: {order[1]}")
        print(f"Items: {order[2]}")
        print(f"Total Amount: £{order[3]:.2f}")
        print(f"Status: {order[4]}")
        print(f"Order Date: {order[5]}")
        if order[6]:
            print(f"Delivery Address: {order[6]}")
        if order[7]:
            print(f"Special Instructions: {order[7]}")
        if order[8]:
            print(f"Payment Method: {order[8]}")
        if order[9]:
            print(f"Completed At: {order[9]}")

    except Exception as e:
        print(f"Error viewing order details: {e}")
        logger.error(f"Error viewing order details: {e}")

def daily_order_summary():
    """Show daily order summary."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT status, COUNT(*), SUM(total_amount)
            FROM orders
            WHERE DATE(order_date) = DATE('now')
            GROUP BY status
        ''')

        summary = cursor.fetchall()
        conn.close()

        if not summary:
            print("\nNo orders today.")
            return

        print(f"\n--- Today's Order Summary ---")
        total_orders = 0
        total_revenue = 0

        for status, count, amount in summary:
            print(f"{status.capitalize()}: {count} orders, £{amount or 0:.2f}")
            total_orders += count
            total_revenue += amount or 0

        print(f"\nTotal: {total_orders} orders, £{total_revenue:.2f}")

    except Exception as e:
        print(f"Error generating daily summary: {e}")
        logger.error(f"Error generating daily summary: {e}")

def update_menu_item():
    """Update an existing menu item."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Get menu item ID to update
        item_id = input("\nEnter menu item ID to update: ").strip()

        # Check if item exists
        cursor.execute("SELECT * FROM menu_items WHERE id = ?", (item_id,))
        item = cursor.fetchone()

        if not item:
            print(f"Menu item with ID {item_id} not found.")
            return

        print(f"\nCurrent item details:")
        print(f"Name: {item[1]}")
        print(f"Description: {item[2]}")
        print(f"Price: £{item[3]:.2f}")
        print(f"Category: {item[4]}")
        print(f"Available: {'Yes' if item[5] else 'No'}")

        # Get updated values (press Enter to keep current)
        print("\nEnter new values (press Enter to keep current):")
        name = input(f"Name [{item[1]}]: ").strip() or item[1]
        description = input(f"Description [{item[2]}]: ").strip() or item[2]
        price_input = input(f"Price [{item[3]:.2f}]: ").strip()
        price = float(price_input) if price_input else item[3]
        category = input(f"Category [{item[4]}]: ").strip() or item[4]
        available_input = input(f"Available (y/n) [{'y' if item[5] else 'n'}]: ").strip().lower()
        available = 1 if available_input == 'y' else (0 if available_input == 'n' else item[5])

        # Update the item
        cursor.execute("""
            UPDATE menu_items
            SET name = ?, description = ?, price = ?, category = ?,
                available = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (name, description, price, category, available, item_id))

        conn.commit()
        print(f"\n✓ Menu item '{name}' updated successfully!")
        logger.info(f"Menu item {item_id} updated: {name}")

    except Exception as e:
        print(f"Error updating menu item: {e}")
        logger.error(f"Error updating menu item: {e}")
    finally:
        if conn:
            conn.close()

def remove_menu_item():
    """Remove a menu item."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Get menu item ID to remove
        item_id = input("\nEnter menu item ID to remove: ").strip()

        # Check if item exists
        cursor.execute("SELECT name FROM menu_items WHERE id = ?", (item_id,))
        item = cursor.fetchone()

        if not item:
            print(f"Menu item with ID {item_id} not found.")
            return

        item_name = item[0]

        # Confirm deletion
        confirm = input(f"Are you sure you want to remove '{item_name}'? (y/n): ").strip().lower()

        if confirm == 'y':
            cursor.execute("DELETE FROM menu_items WHERE id = ?", (item_id,))
            conn.commit()
            print(f"\n✓ Menu item '{item_name}' removed successfully!")
            logger.info(f"Menu item {item_id} ({item_name}) removed")
        else:
            print("Removal cancelled.")

    except Exception as e:
        print(f"Error removing menu item: {e}")
        logger.error(f"Error removing menu item: {e}")
    finally:
        if conn:
            conn.close()

def toggle_availability():
    """Toggle menu item availability."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Get menu item ID to toggle
        item_id = input("\nEnter menu item ID to toggle availability: ").strip()

        # Check if item exists and get current status
        cursor.execute("SELECT name, available FROM menu_items WHERE id = ?", (item_id,))
        item = cursor.fetchone()

        if not item:
            print(f"Menu item with ID {item_id} not found.")
            return

        item_name, current_status = item[0], item[1]
        new_status = 0 if current_status else 1

        # Toggle availability
        cursor.execute("""
            UPDATE menu_items
            SET available = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_status, item_id))

        conn.commit()
        status_text = "available" if new_status else "unavailable"
        print(f"\n✓ Menu item '{item_name}' is now {status_text}!")
        logger.info(f"Menu item {item_id} ({item_name}) availability toggled to {status_text}")

    except Exception as e:
        print(f"Error toggling availability: {e}")
        logger.error(f"Error toggling availability: {e}")
    finally:
        if conn:
            conn.close()