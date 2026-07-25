from education_system.systems.university.infrastructure.auth import UserAuth, display_auth_menu
from education_system.systems.university.infrastructure.database.data_backup import display_backup_menu, backup_before_operation
from education_system.systems.university.infrastructure.email import send_confirmation_email
from education_system.systems.university.infrastructure.database.db import sqlite3, DatabaseManager
from education_system.systems.university.domain.operations.commerce.services.restaurant.operations.connection import get_db_connection
from education_system.systems.university.domain.operations.commerce.services.restaurant.operations.audit import log_audit_action
from education_system.systems.university.domain.operations.commerce.services.restaurant.operations.order_processing import (
    view_orders,
    update_order_status,
    process_payments,
)
from education_system.systems.university.domain.operations.commerce.services.restaurant.customer.reservation_system import display_table_management
from education_system.systems.university.domain.operations.commerce.services.restaurant.staff.staff_administration import display_staff_management
from education_system.systems.university.domain.operations.commerce.services.restaurant.operations.inventory_management import display_inventory_management
from education_system.systems.university.domain.operations.commerce.services.restaurant.operations.financial_reporting import display_financial_reports
from education_system.systems.university.domain.operations.commerce.services.restaurant.operations.settings import display_system_settings

import random
import re
import os
import csv
import json
import hashlib
import logging
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from PIL import Image
from decimal import Decimal, ROUND_HALF_UP
import threading
import time
from collections import defaultdict
import warnings
from education_system.systems.university.infrastructure.logging.log_config import configure_logging

# Configure logging
logger = configure_logging(name=__name__)
warnings.filterwarnings('ignore')

# CONSOLIDATED DATABASE FILE - Using the same database as main system
from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import auth instance management from user_authentication
try:
    from education_system.systems.university.infrastructure.auth import get_current_user, set_auth_instance
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


def display_menu_items_menu():
    """Display menu items management menu"""
    global auth

    while True:
        print("\n" + "="*50)
        print("MENU ITEMS MANAGEMENT")
        print("="*50)

        print("\nOptions:")
        print("1. View all menu items")
        print("2. Create menu item")
        print("3. Update menu item")
        print("4. Delete menu item")
        print("5. Menu analytics")
        print("6. Import/Export menu")
        print("7. Return to main menu")

        choice = input("Choose an option (1-7): ")

        if choice == '1':
            view_all_menu_items()
        elif choice == '2':
            create_menu_item()
        elif choice == '3':
            update_menu_item()
        elif choice == '4':
            delete_menu_item()
        elif choice == '5':
            menu_analytics()
        elif choice == '6':
            import_export_menu()
        elif choice == '7':
            return
        else:
            print("Invalid choice. Please try again.")

def view_all_menu_items():
    """View all menu items with filtering options"""
    try:
        conn = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor()

        print("\nFilter options:")
        print("1. All items")
        print("2. By category")
        print("3. Available items only")
        print("4. Vegetarian items")
        print("5. Vegan items")
        print("6. By price range")

        filter_choice = input("Choose filter (1-6): ")

        if filter_choice == '1':
            cursor.execute('SELECT * FROM menu_items ORDER BY category, name')
        elif filter_choice == '2':
            category = input("Enter category (Main/Side/Dessert/Beverage): ")
            cursor.execute('SELECT * FROM menu_items WHERE category = ? ORDER BY name', (category,))
        elif filter_choice == '3':
            cursor.execute('SELECT * FROM menu_items WHERE available = 1 ORDER BY category, name')
        elif filter_choice == '4':
            cursor.execute('SELECT * FROM menu_items WHERE vegetarian = 1 ORDER BY category, name')
        elif filter_choice == '5':
            cursor.execute('SELECT * FROM menu_items WHERE vegan = 1 ORDER BY category, name')
        elif filter_choice == '6':
            min_price = float(input("Enter minimum price: "))
            max_price = float(input("Enter maximum price: "))
            cursor.execute('SELECT * FROM menu_items WHERE price BETWEEN ? AND ? ORDER BY price', (min_price, max_price))
        else:
            cursor.execute('SELECT * FROM menu_items ORDER BY category, name')

        items = cursor.fetchall()

        if not items:
            print("No menu items found.")
            conn.close()
            return

        print("\n" + "="*120)
        print("MENU ITEMS")
        print("="*120)
        print(f"{'ID':<8} {'Name':<25} {'Category':<12} {'Price':<8} {'Cost':<8} {'Margin':<8} {'Available':<10} {'V':<3} {'VG':<3}")
        print("-"*120)

        for item in items:
            margin = ((item[3] - (item[15] or 0)) / item[3] * 100) if item[3] > 0 else 0
            available = "Yes" if item[8] else "No"
            veg = "✓" if item[6] else ""
            vegan = "✓" if item[7] else ""

            print(f"{item[0]:<8} {item[1]:<25} {item[2]:<12} £{item[3]:<7.2f} £{item[15] or 0:<7.2f} {margin:<7.1f}% {available:<10} {veg:<3} {vegan:<3}")

        print("="*120)
        print(f"Total items: {len(items)}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in view_all_menu_items: {e}")
        print(f"An error occurred: {e}")

def create_menu_item():
    """Enhanced create menu item with nutritional info and cost tracking"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to create menu items.")
        return

    if not auth.check_permission('manage_menu'):
        print("You don't have permission to create menu items.")
        return

    try:
        backup_before_operation('create_menu_item')
        conn = get_db_connection()
        cursor = conn.cursor()

        # Generate item ID
        category_code = input("Enter category code (M=Main, S=Side, D=Dessert, B=Beverage): ").upper()
        if category_code not in ['M', 'S', 'D', 'B']:
            print("Invalid category code. Using 'M' as default.")
            category_code = 'M'

        cursor.execute(
            'SELECT MAX(item_id) FROM menu_items WHERE item_id LIKE ?',
            (f'{category_code}%',)
        )
        result = cursor.fetchone()[0]

        if result:
            number = int(result[1:]) + 1
            item_id = f"{category_code}{number:03d}"
        else:
            item_id = f"{category_code}001"

        # Get basic item details
        name = input("Enter item name: ").strip()
        if not name:
            print("Item name is required.")
            conn.close()
            return

        description = input("Enter item description: ").strip()

        # Get and validate price
        while True:
            try:
                price = float(input("Enter selling price (£): "))
                if price < 0:
                    raise ValueError
                break
            except ValueError:
                print("Invalid price. Please enter a positive number.")

        # Get cost price for profit calculations
        while True:
            try:
                cost_price = float(input("Enter cost price (£): "))
                if cost_price < 0:
                    raise ValueError
                if cost_price > price:
                    confirm = input("Cost price is higher than selling price. Continue? (y/n): ")
                    if confirm.lower() != 'y':
                        continue
                break
            except ValueError:
                print("Invalid cost price. Please enter a positive number.")

        # Get category
        print("\nCategories:")
        print("1. Main")
        print("2. Side")
        print("3. Dessert")
        print("4. Beverage")
        category_choice = input("Choose category (1-4): ")
        categories = {
            '1': 'Main',
            '2': 'Side',
            '3': 'Dessert',
            '4': 'Beverage'
        }
        category = categories.get(category_choice, 'Main')

        # Get allergens
        allergens = input("Enter allergens (comma separated, or 'None'): ").strip()

        # Get dietary info
        vegetarian = input("Is this item vegetarian? (y/n): ").lower() == 'y'
        vegan = input("Is this item vegan? (y/n): ").lower() == 'y'
        available = input("Is this item available? (y/n): ").lower() == 'y'

        # Get nutritional information
        print("\nNutritional Information (optional):")

        try:
            calories = int(input("Enter calories (or 0 to skip): ") or "0")
        except ValueError:
            calories = 0

        try:
            protein = float(input("Enter protein in grams (or 0 to skip): ") or "0")
        except ValueError:
            protein = 0

        try:
            carbs = float(input("Enter carbohydrates in grams (or 0 to skip): ") or "0")
        except ValueError:
            carbs = 0

        try:
            fat = float(input("Enter fat in grams (or 0 to skip): ") or "0")
        except ValueError:
            fat = 0

        # Get preparation time
        try:
            prep_time = int(input("Enter preparation time in minutes (or 0 to skip): ") or "0")
        except ValueError:
            prep_time = 0

        # Get current time
        creation_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Insert into database
        cursor.execute('''
            INSERT INTO menu_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            item_id, name, description, price, category, allergens,
            int(vegetarian), int(vegan), int(available), creation_date,
            calories, protein, carbs, fat, prep_time, cost_price, None, 0
        ))

        conn.commit()
        conn.close()

        # Calculate profit margin
        profit_margin = ((price - cost_price) / price * 100) if price > 0 else 0

        print("\n✅ Menu item created successfully!")
        print(f"Item ID: {item_id}")
        print(f"Name: {name}")
        print(f"Description: {description}")
        print(f"Selling Price: £{price:.2f}")
        print(f"Cost Price: £{cost_price:.2f}")
        print(f"Profit Margin: {profit_margin:.1f}%")
        print(f"Category: {category}")
        print(f"Allergens: {allergens}")
        print(f"Vegetarian: {'Yes' if vegetarian else 'No'}")
        print(f"Vegan: {'Yes' if vegan else 'No'}")
        print(f"Available: {'Yes' if available else 'No'}")

        if calories > 0:
            print(f"Calories: {calories}")
        if protein > 0:
            print(f"Protein: {protein}g")
        if carbs > 0:
            print(f"Carbohydrates: {carbs}g")
        if fat > 0:
            print(f"Fat: {fat}g")
        if prep_time > 0:
            print(f"Preparation Time: {prep_time} minutes")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'CREATE_MENU_ITEM',
            'menu_items',
            item_id,
            None,
            {'name': name, 'price': price, 'cost_price': cost_price, 'category': category}
        )

    except sqlite3.Error as e:
        logging.error(f"Database error in create_menu_item: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Error in create_menu_item: {e}")
        print(f"An error occurred: {e}")

def update_menu_item():
    """Update existing menu item"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to update menu items.")
        return

    if not auth.check_permission('manage_menu'):
        print("You don't have permission to update menu items.")
        return

    try:
        backup_before_operation('update_menu_item')

        item_id = input("Enter item ID to update: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM menu_items WHERE item_id = ?', (item_id,))
        item = cursor.fetchone()

        if not item:
            print("Menu item not found.")
            conn.close()
            return

        # Store old values for audit
        old_values = {
            'name': item[1],
            'price': item[3],
            'description': item[2],
            'available': item[8]
        }

        print(f"\nUpdating item: {item[1]}")
        print("Current values:")
        print(f"1. Name: {item[1]}")
        print(f"2. Description: {item[2]}")
        print(f"3. Price: £{item[3]:.2f}")
        print(f"4. Cost Price: £{item[15] or 0:.2f}")
        print(f"5. Category: {item[4]}")
        print(f"6. Allergens: {item[5]}")
        print(f"7. Available: {'Yes' if item[8] else 'No'}")
        print(f"8. Vegetarian: {'Yes' if item[6] else 'No'}")
        print(f"9. Vegan: {'Yes' if item[7] else 'No'}")
        print("10. Cancel update")

        choice = input("Enter field number to update (1-10): ")

        new_values = old_values.copy()

        if choice == '1':
            new_name = input("Enter new name: ").strip()
            if new_name:
                cursor.execute('UPDATE menu_items SET name = ? WHERE item_id = ?', (new_name, item_id))
                new_values['name'] = new_name
                print("Name updated successfully.")
        elif choice == '2':
            new_desc = input("Enter new description: ").strip()
            cursor.execute('UPDATE menu_items SET description = ? WHERE item_id = ?', (new_desc, item_id))
            print("Description updated successfully.")
        elif choice == '3':
            try:
                new_price = float(input("Enter new price: "))
                cursor.execute('UPDATE menu_items SET price = ? WHERE item_id = ?', (new_price, item_id))
                new_values['price'] = new_price
                print("Price updated successfully.")
            except ValueError:
                print("Invalid price format.")
        elif choice == '4':
            try:
                new_cost = float(input("Enter new cost price: "))
                cursor.execute('UPDATE menu_items SET cost_price = ? WHERE item_id = ?', (new_cost, item_id))
                print("Cost price updated successfully.")
            except ValueError:
                print("Invalid cost price format.")
        elif choice == '7':
            available = input("Is item available? (y/n): ").lower() == 'y'
            cursor.execute('UPDATE menu_items SET available = ? WHERE item_id = ?', (int(available), item_id))
            new_values['available'] = available
            print("Availability updated successfully.")
        elif choice == '10':
            print("Update cancelled.")
            conn.close()
            return
        else:
            print("Invalid choice.")
            conn.close()
            return

        conn.commit()
        conn.close()

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'UPDATE_MENU_ITEM',
            'menu_items',
            item_id,
            old_values,
            new_values
        )

    except Exception as e:
        logging.error(f"Error in update_menu_item: {e}")
        print(f"An error occurred: {e}")

def delete_menu_item():
    """Delete menu item"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to delete menu items.")
        return

    if not auth.check_permission('manage_menu'):
        print("You don't have permission to delete menu items.")
        return

    try:
        backup_before_operation('delete_menu_item')

        item_id = input("Enter item ID to delete: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT name FROM menu_items WHERE item_id = ?', (item_id,))
        item = cursor.fetchone()

        if not item:
            print("Menu item not found.")
            conn.close()
            return

        print(f"Are you sure you want to delete '{item[0]}'?")
        confirm = input("Type 'DELETE' to confirm: ")

        if confirm == 'DELETE':
            cursor.execute('DELETE FROM menu_items WHERE item_id = ?', (item_id,))
            conn.commit()
            print(f"Menu item '{item[0]}' deleted successfully.")

            # Log audit action
            log_audit_action(
                auth.current_user['id'],
                'DELETE_MENU_ITEM',
                'menu_items',
                item_id,
                {'name': item[0]},
                None
            )
        else:
            print("Deletion cancelled.")

        conn.close()

    except Exception as e:
        logging.error(f"Error in delete_menu_item: {e}")
        print(f"An error occurred: {e}")

def menu_analytics():
    """Menu performance analytics"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\n" + "="*60)
        print("MENU ANALYTICS")
        print("="*60)

        # Best selling items
        cursor.execute('''
            SELECT mi.name, SUM(oi.quantity) as total_sold, SUM(oi.quantity * oi.unit_price) as revenue
            FROM menu_items mi
            JOIN order_items oi ON mi.item_id = oi.item_id
            JOIN orders o ON oi.order_id = o.order_id
            WHERE o.order_status = 'Completed' AND o.order_date >= date('now', '-30 days')
            GROUP BY mi.item_id, mi.name
            ORDER BY total_sold DESC
            LIMIT 10
        ''')

        top_items = cursor.fetchall()

        if top_items:
            print("\nTop 10 Best Selling Items (Last 30 Days):")
            print("-"*60)
            print(f"{'Item':<30} {'Sold':<8} {'Revenue':<12}")
            print("-"*60)

            for item in top_items:
                print(f"{item[0]:<30} {item[1]:<8} £{item[2]:<11.2f}")

        # Category performance
        cursor.execute('''
            SELECT mi.category, COUNT(mi.item_id) as item_count,
                   AVG(mi.price) as avg_price, SUM(COALESCE(oi.quantity, 0)) as total_sold
            FROM menu_items mi
            LEFT JOIN order_items oi ON mi.item_id = oi.item_id
            LEFT JOIN orders o ON oi.order_id = o.order_id
                AND o.order_status = 'Completed' AND o.order_date >= date('now', '-30 days')
            GROUP BY mi.category
        ''')

        categories = cursor.fetchall()

        if categories:
            print("\nCategory Performance:")
            print("-"*70)
            print(f"{'Category':<12} {'Items':<8} {'Avg Price':<12} {'Total Sold':<12}")
            print("-"*70)

            for cat in categories:
                print(f"{cat[0]:<12} {cat[1]:<8} £{cat[2]:<11.2f} {cat[3]:<12}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in menu_analytics: {e}")
        print(f"An error occurred: {e}")

def import_export_menu():
    """Import/Export menu functionality"""
    try:
        print("\n" + "="*50)
        print("IMPORT/EXPORT MENU")
        print("="*50)

        print("\nOptions:")
        print("1. Export menu to CSV")
        print("2. Import menu from CSV")
        print("3. Export menu to JSON")
        print("4. Print menu PDF")
        print("5. Return to menu management")

        choice = input("Choose an option (1-5): ")

        if choice == '1':
            export_menu_csv()
        elif choice == '2':
            import_menu_csv()
        elif choice == '3':
            export_menu_json()
        elif choice == '4':
            print_menu_pdf()
        elif choice == '5':
            return
        else:
            print("Invalid choice.")

    except Exception as e:
        logging.error(f"Error in import_export_menu: {e}")
        print(f"An error occurred: {e}")

def export_menu_csv():
    """Export menu to CSV file"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM menu_items ORDER BY category, name')
        items = cursor.fetchall()

        if not items:
            print("No menu items to export.")
            conn.close()
            return

        filename = f"menu_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            # Header
            writer.writerow([
                'Item ID', 'Name', 'Description', 'Price', 'Category', 'Allergens',
                'Vegetarian', 'Vegan', 'Available', 'Calories', 'Protein', 'Carbs',
                'Fat', 'Prep Time', 'Cost Price'
            ])

            # Data
            for item in items:
                writer.writerow([
                    item[0], item[1], item[2], item[3], item[4], item[5],
                    'Yes' if item[6] else 'No',
                    'Yes' if item[7] else 'No',
                    'Yes' if item[8] else 'No',
                    item[10] or 0, item[11] or 0, item[12] or 0,
                    item[13] or 0, item[14] or 0, item[15] or 0
                ])

        conn.close()
        print(f"Menu exported successfully to {filename}")

    except Exception as e:
        logging.error(f"Error in export_menu_csv: {e}")
        print(f"An error occurred: {e}")

def import_menu_csv():
    """Import menu from CSV file"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to import menu items.")
        return

    if not auth.check_permission('manage_menu'):
        print("You don't have permission to import menu items.")
        return

    try:
        filename = input("Enter CSV filename: ")

        if not os.path.exists(filename):
            print("File not found.")
            return

        backup_before_operation('import_menu_csv')

        conn = get_db_connection()
        cursor = conn.cursor()

        imported_count = 0

        with open(filename, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)

            for row in reader:
                try:
                    # Check if item already exists
                    cursor.execute('SELECT item_id FROM menu_items WHERE item_id = ?', (row['Item ID'],))
                    if cursor.fetchone():
                        print(f"Item {row['Item ID']} already exists, skipping...")
                        continue

                    cursor.execute('''
                        INSERT INTO menu_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        row['Item ID'], row['Name'], row['Description'],
                        float(row['Price']), row['Category'], row['Allergens'],
                        1 if row['Vegetarian'].lower() == 'yes' else 0,
                        1 if row['Vegan'].lower() == 'yes' else 0,
                        1 if row['Available'].lower() == 'yes' else 0,
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        int(row['Calories']) if row['Calories'] else 0,
                        float(row['Protein']) if row['Protein'] else 0,
                        float(row['Carbs']) if row['Carbs'] else 0,
                        float(row['Fat']) if row['Fat'] else 0,
                        int(row['Prep Time']) if row['Prep Time'] else 0,
                        float(row['Cost Price']) if row['Cost Price'] else 0,
                        None, 0
                    ))

                    imported_count += 1

                except Exception as e:
                    print(f"Error importing row {row.get('Item ID', 'Unknown')}: {e}")
                    continue

        conn.commit()
        conn.close()

        print(f"Successfully imported {imported_count} menu items.")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'IMPORT_MENU_CSV',
            'menu_items',
            None,
            None,
            {'filename': filename, 'imported_count': imported_count}
        )

    except Exception as e:
        logging.error(f"Error in import_menu_csv: {e}")
        print(f"An error occurred: {e}")

def export_menu_json():
    """Export menu to JSON file"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM menu_items ORDER BY category, name')
        items = cursor.fetchall()

        if not items:
            print("No menu items to export.")
            conn.close()
            return

        menu_data = []

        for item in items:
            menu_data.append({
                'item_id': item[0],
                'name': item[1],
                'description': item[2],
                'price': item[3],
                'category': item[4],
                'allergens': item[5],
                'vegetarian': bool(item[6]),
                'vegan': bool(item[7]),
                'available': bool(item[8]),
                'nutritional_info': {
                    'calories': item[10] or 0,
                    'protein': item[11] or 0,
                    'carbs': item[12] or 0,
                    'fat': item[13] or 0
                },
                'prep_time': item[14] or 0,
                'cost_price': item[15] or 0
            })

        filename = f"menu_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(filename, 'w', encoding='utf-8') as jsonfile:
            json.dump({
                'export_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'menu_items': menu_data
            }, jsonfile, indent=2, ensure_ascii=False)

        conn.close()
        print(f"Menu exported successfully to {filename}")

    except Exception as e:
        logging.error(f"Error in export_menu_json: {e}")
        print(f"An error occurred: {e}")

def print_menu_pdf():
    """Generate printable menu PDF - FIXED"""
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM menu_items WHERE available = 1 ORDER BY category, name')
        items = cursor.fetchall()

        if not items:
            print("No available menu items to print.")
            conn.close()
            return

        filename = f"menu_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        doc = SimpleDocTemplate(filename, pagesize=letter)
        styles = getSampleStyleSheet()

        # Build content
        content = []

        # Title
        title = Paragraph("University Restaurant Menu", styles['Title'])
        content.append(title)
        content.append(Spacer(1, 20))

        # Group by category
        categories = {}
        for item in items:
            if item[4] not in categories:
                categories[item[4]] = []
            categories[item[4]].append(item)

        for category, cat_items in categories.items():
            # Category header
            content.append(Paragraph(category, styles['Heading2']))
            content.append(Spacer(1, 10))

            # Category items table - FIXED: Use colWidths parameter correctly
            table_data = [['Item', 'Description', 'Price']]

            for item in cat_items:
                table_data.append([
                    item[1],  # name
                    item[2] or '',  # description
                    f"£{item[3]:.2f}"  # price
                ])

            # Create table with proper colWidths parameter
            table = Table(table_data)

            # Set column widths manually after creation
            if hasattr(table, '_colWidths'):
                table._colWidths = [2.5*inch, 3*inch, 1*inch]

            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (2, 0), (2, -1), 'RIGHT'),  # Right align prices
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))

            content.append(table)
            content.append(Spacer(1, 20))

        # Footer
        footer = Paragraph("Thank you for dining with us!", styles['Normal'])
        content.append(Spacer(1, 30))
        content.append(footer)

        # Build PDF
        doc.build(content)

        conn.close()
        print(f"Menu PDF generated successfully: {filename}")

    except Exception as e:
        logging.error(f"Error in print_menu_pdf: {e}")
        print(f"An error occurred: {e}")

def display_orders_menu():
    """Display orders management menu"""
    global auth

    while True:
        print("\n" + "="*50)
        print("ORDERS MANAGEMENT")
        print("="*50)

        print("\nOptions:")
        print("1. View orders")
        print("2. Update order status")
        print("3. Process payments")
        print("4. Order analytics")
        print("5. Return to main menu")

        choice = input("Choose an option (1-5): ")

        if choice == '1':
            view_orders()
        elif choice == '2':
            update_order_status()
        elif choice == '3':
            process_payments()
        elif choice == '4':
            order_analytics()
        elif choice == '5':
            return
        else:
            print("Invalid choice.")

def order_analytics():
    """Order analytics and reporting (interactive)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    while True:
        print("\n" + "="*50)
        print("ORDER ANALYTICS")
        print("="*50)
        print("\nOptions:")
        print("1. Daily order summary (last 7 days)")
        print("2. Peak hours (last 30 days)")
        print("3. Payment method breakdown (last 30 days)")
        print("4. Average order value trends (last 30 days)")
        print("5. Customer feedback summary (last 30 days)")
        print("6. Back")
        choice = input("Choose an option (1-6): ").strip()

        if choice == '1':
            cursor.execute("""
                SELECT date(order_date) as d, COUNT(*) as cnt, SUM(total_amount) as revenue,
                       AVG(total_amount) as aov
                FROM orders
                WHERE order_date >= date('now','-7 days')
                GROUP BY date(order_date)
                ORDER BY d DESC
            """)
            rows = cursor.fetchall()
            print("\nDate        Orders   Revenue    AOV")
            print("-"*40)
            for d, cnt, rev, aov in rows:
                print(f"{d:<12} {cnt:<7} £{(rev or 0):<9.2f} £{(aov or 0):.2f}")

        elif choice == '2':
            cursor.execute("""
                SELECT strftime('%H', order_date) as hour, COUNT(*) as cnt
                FROM orders
                WHERE order_date >= date('now','-30 days')
                GROUP BY hour
                ORDER BY cnt DESC
                LIMIT 10
            """)
            rows = cursor.fetchall()
            print("\nPeak Hours (Top 10 in last 30 days):")
            for hour, cnt in rows:
                print(f"{hour}:00 - {cnt} orders")

        elif choice == '3':
            cursor.execute("""
                SELECT COALESCE(payment_method,'Unknown') as method, COUNT(*) as cnt, SUM(total_amount) as revenue
                FROM orders
                WHERE order_date >= date('now','-30 days')
                GROUP BY method
                ORDER BY revenue DESC
            """)
            rows = cursor.fetchall()
            print("\nPayment Method Breakdown (last 30 days):")
            print("Method         Orders   Revenue")
            print("-"*40)
            for method, cnt, rev in rows:
                print(f"{method:<14} {cnt:<7} £{(rev or 0):.2f}")

        elif choice == '4':
            cursor.execute("""
                SELECT date(order_date) as d, AVG(total_amount) as aov
                FROM orders
                WHERE order_date >= date('now','-30 days')
                GROUP BY date(order_date)
                ORDER BY d DESC
            """)
            rows = cursor.fetchall()
            print("\nAOV Trend (last 30 days):")
            for d, aov in rows:
                print(f"{d}: £{(aov or 0):.2f}")

        elif choice == '5':
            # Feedback summary for last 30 days
            cursor.execute("""
                SELECT COUNT(*) as total_reviews,
                       AVG(rating) as avg_rating,
                       SUM(CASE WHEN rating=5 THEN 1 ELSE 0 END) as r5,
                       SUM(CASE WHEN rating=4 THEN 1 ELSE 0 END) as r4,
                       SUM(CASE WHEN rating=3 THEN 1 ELSE 0 END) as r3,
                       SUM(CASE WHEN rating=2 THEN 1 ELSE 0 END) as r2,
                       SUM(CASE WHEN rating=1 THEN 1 ELSE 0 END) as r1
                FROM restaurant_customer_feedback
                WHERE feedback_date >= date('now','-30 days')
            """)
            stats = cursor.fetchone()
            if stats and stats[0] and stats[0] > 0:
                print("\nFeedback Summary (Last 30 Days):")
                print(f"Total Reviews: {stats[0]}")
                print(f"Average Rating: {stats[1]:.2f}/5.0")
                print("Rating Distribution:")
                print(f"5★: {stats[2]}  4★: {stats[3]}  3★: {stats[4]}  2★: {stats[5]}  1★: {stats[6]}")
            else:
                print("No feedback in the last 30 days.")

            # Top-rated items (min 3 reviews)
            cursor.execute("""
                SELECT mi.name, COUNT(*) as feedback_count, AVG(cf.rating) as avg_rating
                FROM restaurant_customer_feedback cf
                JOIN menu_items mi ON cf.item_id = mi.item_id
                WHERE cf.feedback_date >= date('now','-30 days')
                GROUP BY mi.item_id, mi.name
                HAVING feedback_count >= 3
                ORDER BY avg_rating DESC
                LIMIT 10
            """)
            rows = cursor.fetchall()
            if rows:
                print("\nTop Rated Items:")
                for name, count, avg in rows:
                    print(f"{name} — {count} reviews, {avg:.2f}★")
            else:
                print("No items meet the threshold.")

        elif choice == '6':
            break
        else:
            print("Invalid choice. Try again.")

    conn.close()

def display_customer_menu():
    """Display customer management menu"""
    global auth

    while True:
        print("\n" + "="*50)
        print("CUSTOMER MANAGEMENT")
        print("="*50)

        print("\nOptions:")
        print("1. Create new customer")
        print("2. View customers")
        print("3. Update customer")
        print("4. Customer feedback")
        print("5. Loyalty program")
        print("6. Return to main menu")

        choice = input("Choose an option (1-6): ")

        if choice == '1':
            # Import locally to avoid circular import issues
            from education_system.systems.university.domain.operations.commerce.services.restaurant.customer.loyalty_program import create_customer
            create_customer()
        elif choice == '2':
            from education_system.systems.university.domain.operations.commerce.services.restaurant.customer.loyalty_program import view_customers
            view_customers()
        elif choice == '3':
            from education_system.systems.university.domain.operations.commerce.services.restaurant.customer.loyalty_program import update_customer
            update_customer()
        elif choice == '4':
            from education_system.systems.university.domain.operations.commerce.services.restaurant.customer.loyalty_program import manage_customer_feedback
            manage_customer_feedback()
        elif choice == '5':
            from education_system.systems.university.domain.operations.commerce.services.restaurant.customer.loyalty_program import manage_loyalty_program
            manage_loyalty_program()
        elif choice == '6':
            return
        else:
            print("Invalid choice. Please try again.")

def feedback_analytics(days: int = 30, min_reviews: int = 3):
    """
    Analyze customer feedback for the last `days` days.
    Prints a quick summary and returns a dict with stats + list of top items.

    Returns:
        {
          "summary": {
            "total": int,
            "avg_rating": float|None,
            "r5": int, "r4": int, "r3": int, "r2": int, "r1": int
          },
          "top_items": [(name:str, count:int, avg:float)]
        }
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()

        # Summary stats
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_feedback,
                AVG(rating) AS avg_rating,
                SUM(CASE WHEN rating = 5 THEN 1 ELSE 0 END) AS r5,
                SUM(CASE WHEN rating = 4 THEN 1 ELSE 0 END) AS r4,
                SUM(CASE WHEN rating = 3 THEN 1 ELSE 0 END) AS r3,
                SUM(CASE WHEN rating = 2 THEN 1 ELSE 0 END) AS r2,
                SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END) AS r1
            FROM restaurant_customer_feedback
            WHERE date(feedback_date) >= ?
            """,
            (cutoff,),
        )
        stats = cursor.fetchone() or (0, None, 0, 0, 0, 0, 0)

        total = int(stats[0] or 0)
        avg_rating = float(stats[1]) if stats[1] is not None else None
        r5, r4, r3, r2, r1 = (int(stats[i] or 0) for i in range(2, 7))

        print("\n" + "=" * 60)
        print(f"FEEDBACK ANALYTICS (Last {days} Days)")
        print("=" * 60)

        if total > 0:
            print(f"Total Reviews: {total}")
            print(f"Average Rating: {avg_rating:.2f}/5.0" if avg_rating is not None else "Average Rating: N/A")
            print("Rating Distribution:")
            print(f"5★: {r5}  4★: {r4}  3★: {r3}  2★: {r2}  1★: {r1}")
        else:
            print("No feedback in the selected window.")

        # Top-rated items
        cursor.execute(
            """
            SELECT mi.name, COUNT(*) AS feedback_count, AVG(cf.rating) AS avg_rating
            FROM restaurant_customer_feedback cf
            JOIN menu_items mi ON cf.item_id = mi.item_id
            WHERE date(cf.feedback_date) >= ?
            GROUP BY mi.item_id, mi.name
            HAVING feedback_count >= ?
            ORDER BY avg_rating DESC, feedback_count DESC, mi.name ASC
            LIMIT 10
            """,
            (cutoff, min_reviews),
        )
        rows = cursor.fetchall()

        if rows:
            print(f"\nTop Rated Items (min {min_reviews} reviews):")
            for name, count, avg in rows:
                count = int(count or 0)
                avg = float(avg) if avg is not None else 0.0
                print(f"{name} — {count} reviews, {avg:.2f}★")
        else:
            print(f"\nTop Rated Items: none (need ≥{min_reviews} reviews).")

        return {
            "summary": {
                "total": total,
                "avg_rating": avg_rating,
                "r5": r5, "r4": r4, "r3": r3, "r2": r2, "r1": r1,
            },
            "top_items": [(n, int(c or 0), float(a or 0.0)) for (n, c, a) in rows],
        }

    except Exception:
        logging.exception("Error in feedback_analytics")
        raise
    finally:
        if conn:
            conn.close()

def loyalty_analytics():
    """Display loyalty program analytics"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\n" + "="*60)
        print("LOYALTY PROGRAM ANALYTICS")
        print("="*60)

        # Overall statistics
        cursor.execute('''
            SELECT
                COUNT(*) as total_customers,
                AVG(loyalty_points) as avg_points,
                SUM(total_spent) as total_revenue,
                AVG(total_spent) as avg_spent_per_customer
            FROM restaurant_customers
        ''')

        stats = cursor.fetchone()

        print(f"Total Customers: {stats[0]}")
        print(f"Average Points: {stats[1]:.0f}")
        print(f"Total Revenue: £{stats[2]:.2f}")
        print(f"Average Spent per Customer: £{stats[3]:.2f}")

        # Tier distribution
        cursor.execute('''
            SELECT loyalty_tier, COUNT(*) as count,
                   SUM(total_spent) as tier_revenue,
                   AVG(total_spent) as avg_spent
            FROM restaurant_customers
            GROUP BY loyalty_tier
            ORDER BY
                CASE loyalty_tier
                    WHEN 'Bronze' THEN 1
                    WHEN 'Silver' THEN 2
                    WHEN 'Gold' THEN 3
                    WHEN 'Platinum' THEN 4
                    ELSE 5
                END
        ''')

        tiers = cursor.fetchall()

        print("\nTier Performance:")
        print("-"*70)
        print(f"{'Tier':<12} {'Count':<8} {'Revenue':<12} {'Avg Spent':<12}")
        print("-"*70)

        for tier in tiers:
            print(f"{tier[0]:<12} {tier[1]:<8} £{tier[2]:<11.2f} £{tier[3]:<11.2f}")

        # Top customers by points
        cursor.execute('''
            SELECT name, loyalty_points, loyalty_tier, total_spent
            FROM restaurant_customers
            ORDER BY loyalty_points DESC
            LIMIT 10
        ''')

        top_customers = cursor.fetchall()

        print("\nTop 10 Customers by Points:")
        print("-"*70)
        print(f"{'Name':<20} {'Points':<8} {'Tier':<12} {'Total Spent':<12}")
        print("-"*70)

        for customer in top_customers:
            print(f"{customer[0]:<20} {customer[1]:<8} {customer[2]:<12} £{customer[3]:<11.2f}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in loyalty_analytics: {e}")
        print(f"An error occurred: {e}")

def display_main_menu():
    """Display main menu for the restaurant management system"""
    global auth

    while True:
        print("\n" + "="*60)
        print("UNIVERSITY RESTAURANT MANAGEMENT SYSTEM")
        print("="*60)
        print(f"Welcome, {auth.current_user['username']}!")
        print(f"Role: {auth.current_user['role']}")

        print("\nMain Menu:")
        print("1. Menu Items Management")
        print("2. Orders Management")
        print("3. Customer Management")
        print("4. Table Management")
        print("5. Staff Management")
        print("6. Inventory Management")
        print("7. Financial Reports")
        print("8. System Settings")
        print("9. Data Backup & Recovery")
        print("10. Logout")
        print("11. Exit")

        choice = input("Choose an option (1-11): ")

        if choice == '1':
            display_menu_items_menu()
        elif choice == '2':
            display_orders_menu()
        elif choice == '3':
            display_customer_menu()
        elif choice == '4':
            display_table_management()
        elif choice == '5':
            display_staff_management()
        elif choice == '6':
            display_inventory_management()
        elif choice == '7':
            display_financial_reports()
        elif choice == '8':
            display_system_settings()
        elif choice == '9':
            display_backup_menu()
        elif choice == '10':
            auth.logout()
            print("Logged out successfully.")
            break
        elif choice == '11':
            print("Thank you for using the Restaurant Management System!")
            return
        else:
            print("Invalid choice. Please try again.")

def table_analytics():
    """Display table analytics"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\n" + "="*60)
        print("TABLE ANALYTICS")
        print("="*60)

        # Table utilization
        cursor.execute('''
            SELECT status, COUNT(*) as count
            FROM restaurant_tables
            GROUP BY status
        ''')

        status_counts = cursor.fetchall()

        print("Current Table Status:")
        print("-"*30)
        for status, count in status_counts:
            print(f"{status}: {count} tables")

        # Capacity analysis
        cursor.execute('''
            SELECT
                COUNT(*) as total_tables,
                SUM(capacity) as total_capacity,
                AVG(capacity) as avg_capacity,
                MIN(capacity) as min_capacity,
                MAX(capacity) as max_capacity
            FROM restaurant_tables
        ''')

        capacity_stats = cursor.fetchone()

        print("\nCapacity Analysis:")
        print("-"*30)
        print(f"Total Tables: {capacity_stats[0]}")
        print(f"Total Capacity: {capacity_stats[1]}")
        print(f"Average Capacity: {capacity_stats[2]:.1f}")
        print(f"Smallest Table: {capacity_stats[3]} seats")
        print(f"Largest Table: {capacity_stats[4]} seats")

        # Reservation trends (last 30 days)
        cursor.execute('''
            SELECT DATE(reservation_date) as date, COUNT(*) as reservations
            FROM restaurant_reservations
            WHERE reservation_date >= date('now', '-30 days')
            GROUP BY DATE(reservation_date)
            ORDER BY date DESC
            LIMIT 10
        ''')

        reservation_trends = cursor.fetchall()

        if reservation_trends:
            print("\nReservation Trends (Last 10 Days):")
            print("-"*30)
            for date, count in reservation_trends:
                print(f"{date}: {count} reservations")

        # Popular table locations
        cursor.execute('''
            SELECT location, COUNT(*) as table_count, SUM(capacity) as total_capacity
            FROM restaurant_tables
            WHERE location IS NOT NULL
            GROUP BY location
            ORDER BY table_count DESC
        ''')

        locations = cursor.fetchall()

        if locations:
            print("\nTables by Location:")
            print("-"*50)
            print(f"{'Location':<20} {'Tables':<8} {'Capacity':<10}")
            print("-"*50)
            for location, count, capacity in locations:
                print(f"{location:<20} {count:<8} {capacity:<10}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in table_analytics: {e}")
        print(f"An error occurred: {e}")

def waste_analytics():
    """Waste analytics and trends - FIXED"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\n" + "="*60)
        print("WASTE ANALYTICS")
        print("="*60)

        # Overall waste statistics
        cursor.execute('''
            SELECT
                COUNT(*) as total_entries,
                SUM(cost_impact) as total_cost,
                AVG(cost_impact) as avg_cost_per_entry
            FROM restaurant_waste_tracking
            WHERE DATE(recorded_date) >= date('now', '-30 days')
        ''')

        stats = cursor.fetchone()

        print("Waste Overview (Last 30 Days):")
        print("-"*40)
        print(f"Total Waste Entries: {stats[0]}")
        print(f"Total Cost Impact: £{stats[1]:.2f}" if stats[1] else "Total Cost Impact: £0.00")
        print(f"Average Cost per Entry: £{stats[2]:.2f}" if stats[2] else "Average Cost per Entry: £0.00")

        # Most common waste reasons
        cursor.execute('''
            SELECT waste_reason, COUNT(*) as frequency, SUM(cost_impact) as total_cost
            FROM restaurant_waste_tracking
            WHERE DATE(recorded_date) >= date('now', '-30 days')
            GROUP BY waste_reason
            ORDER BY frequency DESC
        ''')

        waste_reasons = cursor.fetchall()

        if waste_reasons:
            print("\nMost Common Waste Reasons:")
            print("-"*50)
            print(f"{'Reason':<20} {'Frequency':<10} {'Cost':<10}")
            print("-"*50)

            for reason, frequency, cost in waste_reasons:
                cost_val = cost or 0
                print(f"{reason:<20} {frequency:<10} £{cost_val:<9.2f}")

        # Most wasted items
        cursor.execute('''
            SELECT mi.name, COUNT(wt.waste_id) as waste_count,
                   SUM(wt.cost_impact) as total_cost
            FROM restaurant_waste_tracking wt
            JOIN menu_items mi ON wt.item_id = mi.item_id
            WHERE DATE(wt.recorded_date) >= date('now', '-30 days')
            GROUP BY mi.item_id, mi.name
            ORDER BY waste_count DESC
            LIMIT 10
        ''')

        wasted_items = cursor.fetchall()

        if wasted_items:
            print("\nMost Wasted Items:")
            print("-"*60)
            print(f"{'Item':<30} {'Waste Count':<12} {'Cost':<10}")
            print("-"*60)

            for item, count, cost in wasted_items:
                cost_val = cost or 0
                print(f"{item:<30} {count:<12} £{cost_val:<9.2f}")

        # Waste by location
        cursor.execute('''
            SELECT location, COUNT(*) as waste_count, SUM(cost_impact) as total_cost
            FROM restaurant_waste_tracking
            WHERE DATE(recorded_date) >= date('now', '-30 days')
                AND location IS NOT NULL
            GROUP BY location
            ORDER BY waste_count DESC
        ''')

        location_waste = cursor.fetchall()

        if location_waste:
            print("\nWaste by Location:")
            print("-"*50)
            print(f"{'Location':<20} {'Count':<8} {'Cost':<10}")
            print("-"*50)

            for location, count, cost in location_waste:
                cost_val = cost or 0
                print(f"{location:<20} {count:<8} £{cost_val:<9.2f}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in waste_analytics: {e}")
        print(f"An error occurred: {e}")

def performance_analytics():
    """Staff performance analytics - FIXED"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\n" + "="*60)
        print("STAFF PERFORMANCE ANALYTICS")
        print("="*60)

        # Overall performance statistics
        cursor.execute('''
            SELECT
                COUNT(*) as total_staff,
                AVG(performance_score) as avg_score,
                MIN(performance_score) as min_score,
                MAX(performance_score) as max_score
            FROM restaurant_staff
            WHERE status = 'Active' AND performance_score IS NOT NULL
        ''')

        stats = cursor.fetchone()

        print("Performance Overview:")
        print("-"*30)
        print(f"Total Active Staff: {stats[0]}")
        print(f"Average Score: {stats[1]:.2f}/10" if stats[1] else "Average Score: N/A")
        print(f"Lowest Score: {stats[2]:.1f}/10" if stats[2] else "Lowest Score: N/A")
        print(f"Highest Score: {stats[3]:.1f}/10" if stats[3] else "Highest Score: N/A")

        # Performance by role
        cursor.execute('''
            SELECT
                role,
                COUNT(*) as staff_count,
                AVG(performance_score) as avg_score
            FROM restaurant_staff
            WHERE status = 'Active' AND performance_score IS NOT NULL
            GROUP BY role
            ORDER BY avg_score DESC
        ''')

        role_performance = cursor.fetchall()

        if role_performance:
            print("\nPerformance by Role:")
            print("-"*40)
            print(f"{'Role':<15} {'Staff':<8} {'Avg Score':<10}")
            print("-"*40)
            for role, count, avg_score in role_performance:
                print(f"{role:<15} {count:<8} {avg_score:<10.2f}")

        # Performance distribution
        cursor.execute('''
            SELECT
                CASE
                    WHEN performance_score >= 9 THEN 'Excellent (9-10)'
                    WHEN performance_score >= 7 THEN 'Good (7-8.9)'
                    WHEN performance_score >= 5 THEN 'Average (5-6.9)'
                    ELSE 'Below Average (<5)'
                END as performance_band,
                COUNT(*) as staff_count
            FROM restaurant_staff
            WHERE status = 'Active' AND performance_score IS NOT NULL
            GROUP BY performance_band
            ORDER BY MIN(performance_score) DESC
        ''')

        distribution = cursor.fetchall()

        if distribution:
            print("\nPerformance Distribution:")
            print("-"*30)
            for band, count in distribution:
                print(f"{band}: {count} staff")

        conn.close()

    except Exception as e:
        logging.error(f"Error in performance_analytics: {e}")
        print(f"An error occurred: {e}")

def staff_analytics():
    """Display staff analytics"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\n" + "="*60)
        print("STAFF ANALYTICS")
        print("="*60)

        # Staff overview
        cursor.execute('''
            SELECT
                COUNT(*) as total_staff,
                COUNT(CASE WHEN status = 'Active' THEN 1 END) as active_staff,
                AVG(hourly_rate) as avg_hourly_rate,
                AVG(performance_score) as avg_performance
            FROM restaurant_staff
        ''')

        overview = cursor.fetchone()

        print("Staff Overview:")
        print("-"*30)
        print(f"Total Staff: {overview[0]}")
        print(f"Active Staff: {overview[1]}")
        print(f"Average Hourly Rate: £{overview[2]:.2f}" if overview[2] else "Average Hourly Rate: N/A")
        print(f"Average Performance: {overview[3]:.1f}/10" if overview[3] else "Average Performance: N/A")

        # Staff by role
        cursor.execute('''
            SELECT role, COUNT(*) as count, AVG(hourly_rate) as avg_rate
            FROM restaurant_staff
            WHERE status = 'Active'
            GROUP BY role
            ORDER BY count DESC
        ''')

        roles = cursor.fetchall()

        print("\nStaff by Role:")
        print("-"*50)
        print(f"{'Role':<15} {'Count':<8} {'Avg Rate':<12}")
        print("-"*50)
        for role, count, avg_rate in roles:
            rate_str = f"£{avg_rate:.2f}" if avg_rate else "N/A"
            print(f"{role:<15} {count:<8} {rate_str:<12}")

        # Performance distribution
        cursor.execute('''
            SELECT
                COUNT(CASE WHEN performance_score >= 9 THEN 1 END) as excellent,
                COUNT(CASE WHEN performance_score >= 7 AND performance_score < 9 THEN 1 END) as good,
                COUNT(CASE WHEN performance_score >= 5 AND performance_score < 7 THEN 1 END) as average,
                COUNT(CASE WHEN performance_score < 5 THEN 1 END) as below_avg
            FROM restaurant_staff
            WHERE status = 'Active' AND performance_score IS NOT NULL
        ''')

        performance = cursor.fetchone()

        print("\nPerformance Distribution:")
        print("-"*30)
        print(f"Excellent (9-10): {performance[0]}")
        print(f"Good (7-8.9): {performance[1]}")
        print(f"Average (5-6.9): {performance[2]}")
        print(f"Below Average (<5): {performance[3]}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in staff_analytics: {e}")
        print(f"An error occurred: {e}")

def revenue_analytics():
    """Revenue analytics and trends"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\n" + "="*60)
        print("REVENUE ANALYTICS")
        print("="*60)

        # Revenue trends (last 30 days)
        cursor.execute('''
            SELECT
                DATE(order_date) as date,
                COUNT(*) as orders,
                SUM(total_amount) as revenue,
                AVG(total_amount) as aov
            FROM orders
            WHERE DATE(order_date) >= date('now', '-30 days') AND order_status = 'Completed'
            GROUP BY DATE(order_date)
            ORDER BY date DESC
            LIMIT 10
        ''', )

        daily_trends = cursor.fetchall()

        print("Daily Revenue Trends (Last 10 Days):")
        print("-"*60)
        print(f"{'Date':<12} {'Orders':<8} {'Revenue':<12} {'AOV':<8}")
        print("-"*60)
        for date, orders, revenue, aov in daily_trends:
            print(f"{date:<12} {orders:<8} £{revenue:<11.2f} £{aov:<7.2f}")

        # Revenue by payment method
        cursor.execute('''
            SELECT
                payment_method,
                COUNT(*) as transactions,
                SUM(total_amount) as revenue,
                AVG(total_amount) as avg_value
            FROM orders
            WHERE DATE(order_date) >= date('now', '-30 days') AND order_status = 'Completed'
            GROUP BY payment_method
            ORDER BY revenue DESC
        ''')

        payment_methods = cursor.fetchall()

        print("\nRevenue by Payment Method (Last 30 Days):")
        print("-"*70)
        print(f"{'Method':<15} {'Transactions':<12} {'Revenue':<12} {'Avg Value':<10}")
        print("-"*70)
        for method, transactions, revenue, avg_val in payment_methods:
            method_name = method or 'Unknown'
            print(f"{method_name:<15} {transactions:<12} £{revenue:<11.2f} £{avg_val:<9.2f}")

        # Peak hours analysis
        cursor.execute('''
            SELECT
                strftime('%H', order_date) as hour,
                COUNT(*) as orders,
                SUM(total_amount) as revenue
            FROM orders
            WHERE DATE(order_date) >= date('now', '-30 days') AND order_status = 'Completed'
            GROUP BY hour
            ORDER BY revenue DESC
            LIMIT 5
        ''')

        peak_hours = cursor.fetchall()

        print("\nTop Revenue Hours (Last 30 Days):")
        print("-"*40)
        for hour, orders, revenue in peak_hours:
            print(f"{hour}:00 - {orders} orders, £{revenue:.2f}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in revenue_analytics: {e}")
        print(f"An error occurred: {e}")

def expense_analytics():
    """Expense analytics"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\n" + "="*60)
        print("EXPENSE ANALYTICS")
        print("="*60)

        # Expenses by category (last 30 days)
        cursor.execute('''
            SELECT
                category,
                COUNT(*) as expense_count,
                SUM(amount) as total_amount,
                AVG(amount) as avg_amount
            FROM restaurant_expenses
            WHERE DATE(expense_date) >= date('now', '-30 days')
            GROUP BY category
            ORDER BY total_amount DESC
        ''')

        categories = cursor.fetchall()

        print("Expenses by Category (Last 30 Days):")
        print("-"*60)
        print(f"{'Category':<20} {'Count':<8} {'Total':<12} {'Average':<10}")
        print("-"*60)
        for category, count, total, avg in categories:
            print(f"{category:<20} {count:<8} £{total:<11.2f} £{avg:<9.2f}")

        # Monthly expense trends
        cursor.execute('''
            SELECT
                strftime('%Y-%m', expense_date) as month,
                COUNT(*) as expense_count,
                SUM(amount) as total_amount
            FROM restaurant_expenses
            WHERE DATE(expense_date) >= date('now', '-6 months')
            GROUP BY month
            ORDER BY month DESC
        ''')

        monthly_trends = cursor.fetchall()

        print("\nMonthly Expense Trends:")
        print("-"*40)
        print(f"{'Month':<10} {'Count':<8} {'Total':<12}")
        print("-"*40)
        for month, count, total in monthly_trends:
            print(f"{month:<10} {count:<8} £{total:<11.2f}")

        # Top vendors
        cursor.execute('''
            SELECT
                vendor,
                COUNT(*) as transaction_count,
                SUM(amount) as total_spent
            FROM restaurant_expenses
            WHERE DATE(expense_date) >= date('now', '-30 days')
            AND vendor IS NOT NULL
            GROUP BY vendor
            ORDER BY total_spent DESC
            LIMIT 10
        ''')

        vendors = cursor.fetchall()

        if vendors:
            print("\nTop Vendors (Last 30 Days):")
            print("-"*50)
            print(f"{'Vendor':<25} {'Transactions':<12} {'Total':<10}")
            print("-"*50)
            for vendor, count, total in vendors:
                vendor_name = vendor[:24] if len(vendor) > 24 else vendor
                print(f"{vendor_name:<25} {count:<12} £{total:<9.2f}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in expense_analytics: {e}")
        print(f"An error occurred: {e}")
