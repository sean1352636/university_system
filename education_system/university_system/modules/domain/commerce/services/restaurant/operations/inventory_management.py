from education_system.university_system.infrastructure.auth import UserAuth, display_auth_menu
from education_system.university_system.infrastructure.database.data_backup import display_backup_menu, backup_before_operation
from education_system.university_system.infrastructure.email import send_confirmation_email
from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager
from education_system.university_system.modules.domain.commerce.services.restaurant.operations.connection import get_db_connection
import random
import re
import os
import csv
import pandas as pd
import json
import hashlib
import logging
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.barcharts import VerticalBarChart
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import qrcode
from PIL import Image
import matplotlib.pyplot as plt
from decimal import Decimal, ROUND_HALF_UP
import threading
import time
from collections import defaultdict
import warnings
from education_system.university_system.utils.logging.log_config import configure_logging

# Configure logging
logger = configure_logging(name=__name__)
warnings.filterwarnings('ignore')

# CONSOLIDATED DATABASE FILE - Using the same database as main system
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import auth instance management from user_authentication
try:
    from education_system.university_system.infrastructure.auth import get_current_user, set_auth_instance
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


def manage_suppliers():
    """Manage suppliers"""
    try:
        print("\n" + "="*50)
        print("SUPPLIER MANAGEMENT")
        print("="*50)

        print("\nOptions:")
        print("1. View all suppliers")
        print("2. Add new supplier")
        print("3. Update supplier")
        print("4. Supplier performance")
        print("5. Return to inventory menu")

        choice = input("Choose an option (1-5): ")

        if choice == '1':
            view_all_suppliers()
        elif choice == '2':
            add_new_supplier()
        elif choice == '3':
            update_supplier()
        elif choice == '4':
            supplier_performance()
        elif choice == '5':
            return
        else:
            print("Invalid choice.")

    except Exception as e:
        logging.error(f"Error in manage_suppliers: {e}")
        print(f"An error occurred: {e}")

def view_all_suppliers():
    """View all suppliers"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM restaurant_suppliers ORDER BY name')
        suppliers = cursor.fetchall()

        if not suppliers:
            print("No suppliers found.")
            conn.close()
            return

        print(f"\n" + "="*120)
        print("SUPPLIERS")
        print("="*120)
        print(f"{'Supplier ID':<12} {'Name':<25} {'Contact Person':<20} {'Email':<25} {'Phone':<15} {'Rating':<8} {'Status':<8}")
        print("-"*120)

        for supplier in suppliers:
            rating = f"{supplier[6]:.1f}/5" if supplier[6] else "N/A"
            
            print(f"{supplier[0]:<12} {supplier[1]:<25} {supplier[2] or 'N/A':<20} {supplier[3] or 'N/A':<25} {supplier[4] or 'N/A':<15} {rating:<8} {supplier[10]:<8}")

        print("="*120)
        print(f"Total suppliers: {len(suppliers)}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in view_all_suppliers: {e}")
        print(f"An error occurred: {e}")

def add_new_supplier():
    """Add new supplier"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to add suppliers.")
        return

    if not auth.check_permission('manage_inventory'):
        print("You don't have permission to add suppliers.")
        return

    try:
        backup_before_operation('add_new_supplier')

        print("\n" + "="*50)
        print("ADD NEW SUPPLIER")
        print("="*50)

        # Generate supplier ID
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT MAX(supplier_id) FROM restaurant_suppliers WHERE supplier_id LIKE ?', ('SUP%',))
        result = cursor.fetchone()[0]

        if result:
            number = int(result[3:]) + 1
            supplier_id = f"SUP{number:04d}"
        else:
            supplier_id = "SUP0001"

        # Get supplier details
        name = input("Enter supplier name: ").strip()
        if not name:
            print("Supplier name is required.")
            conn.close()
            return

        contact_person = input("Enter contact person: ").strip()
        email = input("Enter email: ").strip()
        phone = input("Enter phone: ").strip()
        address = input("Enter address: ").strip()
        payment_terms = input("Enter payment terms: ").strip()
        delivery_schedule = input("Enter delivery schedule: ").strip()
        notes = input("Enter notes: ").strip()

        # Insert supplier
        cursor.execute('''
            INSERT INTO restaurant_suppliers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            supplier_id, name, contact_person, email, phone, address, 0,
            payment_terms, delivery_schedule, notes, 'Active'
        ))

        conn.commit()
        conn.close()

        print(f"\n✅ Supplier added successfully!")
        print(f"Supplier ID: {supplier_id}")
        print(f"Name: {name}")
        print(f"Contact: {contact_person}")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'ADD_SUPPLIER',
            'restaurant_suppliers',
            supplier_id,
            None,
            {'name': name, 'contact_person': contact_person}
        )

    except Exception as e:
        logging.error(f"Error in add_new_supplier: {e}")
        print(f"An error occurred: {e}")

def update_supplier():
    """Update supplier information - FIXED"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to update suppliers.")
        return

    if not auth.check_permission('manage_inventory'):
        print("You don't have permission to update suppliers.")
        return

    try:
        backup_before_operation('update_supplier')

        supplier_id = input("Enter supplier ID to update: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM restaurant_suppliers WHERE supplier_id = ?', (supplier_id,))
        supplier = cursor.fetchone()

        if not supplier:
            print("Supplier not found.")
            conn.close()
            return

        print(f"\nCurrent Supplier Information:")
        print(f"1. Name: {supplier[1]}")
        print(f"2. Contact Person: {supplier[2] or 'Not set'}")
        print(f"3. Email: {supplier[3] or 'Not set'}")
        print(f"4. Phone: {supplier[4] or 'Not set'}")
        print(f"5. Address: {supplier[5] or 'Not set'}")
        print(f"6. Rating: {supplier[6]:.1f}/5" if supplier[6] else "6. Rating: Not set")
        print(f"7. Status: {supplier[10]}")
        print("8. Cancel update")

        choice = input("Enter field number to update (1-8): ")

        if choice == '8':
            print("Update cancelled.")
            conn.close()
            return

        if choice == '1':
            new_name = input("Enter new name: ").strip()
            if new_name:
                cursor.execute('UPDATE restaurant_suppliers SET name = ? WHERE supplier_id = ?',
                              (new_name, supplier_id))
                print("Name updated successfully.")
        elif choice == '2':
            new_contact = input("Enter new contact person: ").strip()
            cursor.execute('UPDATE restaurant_suppliers SET contact_person = ? WHERE supplier_id = ?',
                          (new_contact, supplier_id))
            print("Contact person updated successfully.")
        elif choice == '3':
            new_email = input("Enter new email: ").strip()
            cursor.execute('UPDATE restaurant_suppliers SET email = ? WHERE supplier_id = ?',
                          (new_email, supplier_id))
            print("Email updated successfully.")
        elif choice == '4':
            new_phone = input("Enter new phone: ").strip()
            cursor.execute('UPDATE restaurant_suppliers SET phone = ? WHERE supplier_id = ?',
                          (new_phone, supplier_id))
            print("Phone updated successfully.")
        elif choice == '5':
            new_address = input("Enter new address: ").strip()
            cursor.execute('UPDATE restaurant_suppliers SET address = ? WHERE supplier_id = ?',
                          (new_address, supplier_id))
            print("Address updated successfully.")
        elif choice == '6':
            try:
                new_rating = float(input("Enter new rating (0-5): "))
                if 0 <= new_rating <= 5:
                    cursor.execute('UPDATE restaurant_suppliers SET rating = ? WHERE supplier_id = ?',
                                  (new_rating, supplier_id))
                    print("Rating updated successfully.")
                else:
                    print("Rating must be between 0 and 5.")
            except ValueError:
                print("Invalid rating format.")
        elif choice == '7':
            print("\nStatus options:")
            print("1. Active")
            print("2. Inactive")
            print("3. Suspended")

            status_choice = input("Choose status (1-3): ")
            statuses = {'1': 'Active', '2': 'Inactive', '3': 'Suspended'}
            new_status = statuses.get(status_choice)
            
            if new_status:
                cursor.execute('UPDATE restaurant_suppliers SET status = ? WHERE supplier_id = ?',
                              (new_status, supplier_id))
                print("Status updated successfully.")
            else:
                print("Invalid status choice.")

        conn.commit()
        conn.close()

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'UPDATE_SUPPLIER',
            'restaurant_suppliers',
            supplier_id,
            None,
            {'updated': True}
        )

    except Exception as e:
        logging.error(f"Error in update_supplier: {e}")
        print(f"An error occurred: {e}")

def waste_tracking():
    """Track food waste"""
    try:
        print("\n" + "="*50)
        print("WASTE TRACKING")
        print("="*50)

        print("\nOptions:")
        print("1. Record waste")
        print("2. View waste reports")
        print("3. Waste analytics")
        print("4. Return to inventory menu")

        choice = input("Choose an option (1-4): ")

        if choice == '1':
            record_waste()
        elif choice == '2':
            view_waste_reports()
        elif choice == '3':
            waste_analytics()
        elif choice == '4':
            return
        else:
            print("Invalid choice.")

    except Exception as e:
        logging.error(f"Error in waste_tracking: {e}")
        print(f"An error occurred: {e}")

def record_waste():
    """Record food waste"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to record waste.")
        return

    try:
        backup_before_operation('record_waste')

        print("\n" + "="*50)
        print("RECORD WASTE")
        print("="*50)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get menu items for waste tracking
        cursor.execute('SELECT item_id, name FROM menu_items ORDER BY name')
        menu_items = cursor.fetchall()

        print("Menu items:")
        for i, item in enumerate(menu_items, 1):
            print(f"{i}. {item[1]} (ID: {item[0]})")

        try:
            item_choice = int(input("Choose item (enter number, 0 for other): "))
            if item_choice == 0:
                item_id = None
                item_name = input("Enter item description: ")
            elif 1 <= item_choice <= len(menu_items):
                item_id = menu_items[item_choice - 1][0]
                item_name = menu_items[item_choice - 1][1]
            else:
                raise ValueError
        except ValueError:
            print("Invalid item choice.")
            conn.close()
            return

        try:
            quantity = float(input("Enter waste quantity: "))
            if quantity <= 0:
                raise ValueError
        except ValueError:
            print("Invalid quantity.")
            conn.close()
            return

        unit = input("Enter unit: ").strip()

        print("\nWaste reasons:")
        print("1. Expired")
        print("2. Spoiled")
        print("3. Overproduction")
        print("4. Customer return")
        print("5. Preparation error")
        print("6. Other")

        reason_choice = input("Choose reason (1-6): ")
        reasons = {
            '1': 'Expired',
            '2': 'Spoiled',
            '3': 'Overproduction',
            '4': 'Customer return',
            '5': 'Preparation error'
        }

        if reason_choice == '6':
            waste_reason = input("Enter custom reason: ").strip()
        else:
            waste_reason = reasons.get(reason_choice, 'Other')

        try:
            cost_impact = float(input("Enter estimated cost impact (£): "))
            if cost_impact < 0:
                raise ValueError
        except ValueError:
            print("Invalid cost impact.")
            cost_impact = 0

        location = input("Enter location where waste occurred: ").strip()

        # Generate waste ID
        waste_id = f"WST{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"

        # Record waste
        cursor.execute('''
            INSERT INTO restaurant_waste_tracking VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            waste_id, item_id, quantity, unit, waste_reason, cost_impact,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'), auth.current_user['id'], location
        ))

        conn.commit()
        conn.close()

        print(f"\n✅ Waste recorded successfully!")
        print(f"Waste ID: {waste_id}")
        print(f"Item: {item_name}")
        print(f"Quantity: {quantity} {unit}")
        print(f"Reason: {waste_reason}")
        print(f"Cost Impact: £{cost_impact:.2f}")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'RECORD_WASTE',
            'restaurant_waste_tracking',
            waste_id,
            None,
            {'item_id': item_id, 'quantity': quantity, 'reason': waste_reason, 'cost_impact': cost_impact}
        )

    except Exception as e:
        logging.error(f"Error in record_waste: {e}")
        print(f"An error occurred: {e}")

def view_waste_reports():
    """View waste reports - FIXED"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\n" + "="*50)
        print("WASTE REPORTS")
        print("="*50)

        print("\nReport options:")
        print("1. Daily waste summary")
        print("2. Waste by category")
        print("3. Waste trends (last 30 days)")
        print("4. Cost impact analysis")
        print("5. Return to waste tracking")

        choice = input("Choose option (1-5): ")

        if choice == '1':
            # Daily waste summary
            report_date = input("Enter date (YYYY-MM-DD) or press Enter for today: ").strip()
            if not report_date:
                report_date = datetime.now().strftime('%Y-%m-%d')

            cursor.execute('''
                SELECT COUNT(*) as waste_entries, SUM(cost_impact) as total_cost
                FROM restaurant_waste_tracking
                WHERE DATE(recorded_date) = ?
            ''', (report_date,))

            daily_stats = cursor.fetchone()

            cursor.execute('''
                SELECT waste_reason, COUNT(*) as count, SUM(cost_impact) as cost
                FROM restaurant_waste_tracking
                WHERE DATE(recorded_date) = ?
                GROUP BY waste_reason
                ORDER BY cost DESC
            ''', (report_date,))

            daily_waste = cursor.fetchall()

            print(f"\nDaily Waste Summary - {report_date}")
            print("-"*50)
            print(f"Total Waste Entries: {daily_stats[0]}")
            print(f"Total Cost Impact: £{daily_stats[1]:.2f}" if daily_stats[1] else "Total Cost Impact: £0.00")

            if daily_waste:
                print(f"\nWaste by Reason:")
                for reason, count, cost in daily_waste:
                    print(f"  {reason}: {count} entries, £{cost:.2f}")

        elif choice == '2':
            # Waste by category
            cursor.execute('''
                SELECT mi.category, COUNT(wt.waste_id) as waste_count, 
                       SUM(wt.cost_impact) as total_cost
                FROM restaurant_waste_tracking wt
                LEFT JOIN menu_items mi ON wt.item_id = mi.item_id
                WHERE DATE(wt.recorded_date) >= date('now', '-30 days')
                GROUP BY mi.category
                ORDER BY total_cost DESC
            ''')

            category_waste = cursor.fetchall()

            print(f"\nWaste by Category (Last 30 Days):")
            print("-"*50)
            print(f"{'Category':<15} {'Count':<8} {'Cost Impact':<15}")
            print("-"*50)

            for category, count, cost in category_waste:
                cat_name = category or 'Uncategorized'
                cost_val = cost or 0
                print(f"{cat_name:<15} {count:<8} £{cost_val:<14.2f}")

        elif choice == '3':
            # Waste trends
            cursor.execute('''
                SELECT DATE(recorded_date) as waste_date, 
                       COUNT(*) as entries, SUM(cost_impact) as daily_cost
                FROM restaurant_waste_tracking
                WHERE DATE(recorded_date) >= date('now', '-30 days')
                GROUP BY DATE(recorded_date)
                ORDER BY waste_date DESC
                LIMIT 10
            ''')

            trends = cursor.fetchall()

            print(f"\nWaste Trends (Last 10 Days):")
            print("-"*40)
            print(f"{'Date':<12} {'Entries':<8} {'Cost':<10}")
            print("-"*40)

            for date, entries, cost in trends:
                cost_val = cost or 0
                print(f"{date:<12} {entries:<8} £{cost_val:<9.2f}")

        elif choice == '4':
            # Cost impact analysis
            cursor.execute('''
                SELECT SUM(cost_impact) as total_waste_cost
                FROM restaurant_waste_tracking
                WHERE DATE(recorded_date) >= date('now', '-30 days')
            ''')

            total_waste_cost = cursor.fetchone()[0] or 0

            cursor.execute('''
                SELECT SUM(total_price) as total_revenue
                FROM restaurant_orders
                WHERE DATE(order_time) >= date('now', '-30 days') AND status = 'Completed'
            ''')

            total_revenue = cursor.fetchone()[0] or 0

            print(f"\nCost Impact Analysis (Last 30 Days):")
            print("-"*40)
            print(f"Total Waste Cost: £{total_waste_cost:.2f}")
            print(f"Total Revenue: £{total_revenue:.2f}")
            
            if total_revenue > 0:
                waste_percentage = (total_waste_cost / total_revenue) * 100
                print(f"Waste as % of Revenue: {waste_percentage:.2f}%")

        elif choice == '5':
            return
        else:
            print("Invalid choice.")

        conn.close()

    except Exception as e:
        logging.error(f"Error in view_waste_reports: {e}")
        print(f"An error occurred: {e}")

def inventory_reports():
    """Generate inventory reports"""
    try:
        print("\n" + "="*50)
        print("INVENTORY REPORTS")
        print("="*50)

        print("\nOptions:")
        print("1. Inventory valuation report")
        print("2. Stock movement report")
        print("3. Low stock report")
        print("4. Expiry report")
        print("5. ABC analysis")
        print("6. Return to inventory menu")

        choice = input("Choose an option (1-6): ")

        if choice == '1':
            inventory_valuation_report()
        elif choice == '2':
            stock_movement_report()
        elif choice == '3':
            low_stock_report()
        elif choice == '4':
            expiry_report()
        elif choice == '5':
            abc_analysis()
        elif choice == '6':
            return
        else:
            print("Invalid choice.")

    except Exception as e:
        logging.error(f"Error in inventory_reports: {e}")
        print(f"An error occurred: {e}")

def inventory_valuation_report():
    """Generate inventory valuation report"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT i.category, 
                   COUNT(*) as item_count,
                   SUM(i.quantity * i.cost_per_unit) as total_value,
                   AVG(i.quantity * i.cost_per_unit) as avg_value
            FROM restaurant_inventory i
            WHERE i.cost_per_unit IS NOT NULL
            GROUP BY i.category
            ORDER BY total_value DESC
        ''')

        categories = cursor.fetchall()

        # Get total inventory value
        cursor.execute('SELECT SUM(quantity * cost_per_unit) FROM restaurant_inventory WHERE cost_per_unit IS NOT NULL')
        total_value = cursor.fetchone()[0] or 0

        print(f"\n" + "="*80)
        print("INVENTORY VALUATION REPORT")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        print(f"{'Category':<20} {'Items':<8} {'Total Value':<15} {'Avg Value':<12} {'% of Total':<10}")
        print("-"*80)

        for category in categories:
            percentage = (category[2] / total_value * 100) if total_value > 0 else 0
            cat_name = category[0] or 'Uncategorized'
            
            print(f"{cat_name:<20} {category[1]:<8} £{category[2]:<14.2f} £{category[3]:<11.2f} {percentage:<9.1f}%")

        print("-"*80)
        print(f"{'TOTAL':<20} {'':<8} £{total_value:<14.2f}")
        print("="*80)

        conn.close()

    except Exception as e:
        logging.error(f"Error in inventory_valuation_report: {e}")
        print(f"An error occurred: {e}")

def stock_movement_report():
    """Generate stock movement report - FIXED"""
    try:
        print("\n" + "="*50)
        print("STOCK MOVEMENT REPORT")
        print("="*50)

        start_date = input("Enter start date (YYYY-MM-DD): ")
        end_date = input("Enter end date (YYYY-MM-DD): ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT it.item_id, i.name, it.transaction_type, 
                   SUM(it.quantity) as total_quantity, 
                   COUNT(*) as transaction_count
            FROM restaurant_inventory_transactions it
            JOIN restaurant_inventory i ON it.item_id = i.item_id
            WHERE DATE(it.transaction_date) BETWEEN ? AND ?
            GROUP BY it.item_id, i.name, it.transaction_type
            ORDER BY i.name, it.transaction_type
        ''', (start_date, end_date))

        movements = cursor.fetchall()

        if not movements:
            print(f"No stock movements found between {start_date} and {end_date}")
            conn.close()
            return

        print(f"\nStock Movement Report ({start_date} to {end_date})")
        print("="*80)
        print(f"{'Item':<25} {'Type':<15} {'Total Qty':<12} {'Transactions':<12}")
        print("-"*80)

        current_item = None
        for movement in movements:
            item_name = movement[1]
            if item_name != current_item:
                if current_item is not None:
                    print("-"*40)
                current_item = item_name

            print(f"{item_name[:24]:<25} {movement[2]:<15} {movement[3]:<12.2f} {movement[4]:<12}")

        print("="*80)

        # Summary by transaction type
        cursor.execute('''
            SELECT transaction_type, COUNT(*) as transaction_count, 
                   SUM(quantity) as total_quantity
            FROM restaurant_inventory_transactions
            WHERE DATE(transaction_date) BETWEEN ? AND ?
            GROUP BY transaction_type
            ORDER BY transaction_count DESC
        ''', (start_date, end_date))

        summary = cursor.fetchall()

        print(f"\nSummary by Transaction Type:")
        print("-"*50)
        print(f"{'Type':<15} {'Transactions':<12} {'Total Qty':<12}")
        print("-"*50)

        for trans_type, count, qty in summary:
            print(f"{trans_type:<15} {count:<12} {qty:<12.2f}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in stock_movement_report: {e}")
        print(f"An error occurred: {e}")

def low_stock_report():
    """Generate low stock report - FIXED"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\n" + "="*60)
        print("LOW STOCK REPORT")
        print("="*60)

        # Get all low stock items with additional details
        cursor.execute('''
            SELECT i.item_id, i.name, i.quantity, i.unit, i.reorder_level, 
                   i.max_level, s.name as supplier_name, i.cost_per_unit,
                   (i.quantity / i.reorder_level) as stock_ratio
            FROM restaurant_inventory i
            LEFT JOIN restaurant_suppliers s ON i.supplier_id = s.supplier_id
            WHERE i.quantity <= i.reorder_level
            ORDER BY stock_ratio, i.name
        ''')

        low_stock_items = cursor.fetchall()

        if not low_stock_items:
            print("✅ No low stock items found!")
            conn.close()
            return

        print(f"Found {len(low_stock_items)} items with low stock:")
        print("-"*100)
        print(f"{'Item':<20} {'Current':<10} {'Reorder':<10} {'Max':<8} {'Supplier':<20} {'Cost/Unit':<12} {'Status':<15}")
        print("-"*100)

        total_reorder_cost = 0

        for item in low_stock_items:
            stock_ratio = item[8] if item[8] else 0
            
            if item[2] == 0:
                status = "❌ OUT OF STOCK"
            elif stock_ratio <= 0.25:
                status = "🔴 CRITICAL"
            elif stock_ratio <= 0.5:
                status = "🟡 LOW"
            else:
                status = "⚠️  REORDER"

            supplier_name = item[6][:19] if item[6] else "No supplier"
            cost_str = f"£{item[7]:.2f}" if item[7] else "N/A"
            
            # Calculate suggested reorder quantity and cost
            if item[5]:  # max_level exists
                reorder_qty = item[5] - item[2]  # max - current
                if item[7]:  # cost_per_unit exists
                    reorder_cost = reorder_qty * item[7]
                    total_reorder_cost += reorder_cost

            print(f"{item[1][:19]:<20} {item[2]:<10.1f} {item[4]:<10.1f} {item[5] or 'N/A':<8} {supplier_name:<20} {cost_str:<12} {status:<15}")

        print("-"*100)

        # Reorder recommendations
        print(f"\nReorder Recommendations:")
        print("-"*60)

        cursor.execute('''
            SELECT i.name, i.quantity, i.max_level, i.cost_per_unit, s.name as supplier
            FROM restaurant_inventory i
            LEFT JOIN restaurant_suppliers s ON i.supplier_id = s.supplier_id
            WHERE i.quantity <= i.reorder_level AND i.max_level IS NOT NULL
            ORDER BY i.quantity
        ''')

        reorder_items = cursor.fetchall()

        for item in reorder_items:
            reorder_qty = item[2] - item[1]  # max - current
            cost = reorder_qty * item[3] if item[3] else 0
            supplier = item[4] or "No supplier"
            
            print(f"• {item[0]}: Order {reorder_qty:.0f} units from {supplier} (Cost: £{cost:.2f})")

        print(f"\nTotal estimated reorder cost: £{total_reorder_cost:.2f}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in low_stock_report: {e}")
        print(f"An error occurred: {e}")

def expiry_report():
    """Generate expiry report - FIXED"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\n" + "="*60)
        print("EXPIRY REPORT")
        print("="*60)

        # Items expiring in next 7 days
        cursor.execute('''
            SELECT item_id, name, quantity, unit, expiry_date,
                   (julianday(expiry_date) - julianday('now')) as days_until_expiry
            FROM restaurant_inventory
            WHERE expiry_date IS NOT NULL 
                AND expiry_date <= date('now', '+7 days')
            ORDER BY expiry_date
        ''')

        expiring_items = cursor.fetchall()

        if not expiring_items:
            print("✅ No items expiring in the next 7 days!")
            conn.close()
            return

        print(f"Items expiring in the next 7 days:")
        print("-"*80)
        print(f"{'Item':<25} {'Quantity':<12} {'Expiry Date':<12} {'Days Left':<12} {'Status':<15}")
        print("-"*80)

        for item in expiring_items:
            days_left = int(item[5]) if item[5] else 0
            
            if days_left < 0:
                status = "❌ EXPIRED"
            elif days_left == 0:
                status = "🔴 EXPIRES TODAY"
            elif days_left <= 2:
                status = "🟠 URGENT"
            else:
                status = "🟡 SOON"

            quantity_str = f"{item[2]:.1f} {item[3]}"
            print(f"{item[1][:24]:<25} {quantity_str:<12} {item[4]:<12} {days_left:<12} {status:<15}")

        print("-"*80)

        # Summary by urgency
        cursor.execute('''
            SELECT 
                COUNT(CASE WHEN expiry_date < date('now') THEN 1 END) as expired,
                COUNT(CASE WHEN expiry_date = date('now') THEN 1 END) as expires_today,
                COUNT(CASE WHEN expiry_date BETWEEN date('now', '+1 day') AND date('now', '+2 days') THEN 1 END) as urgent,
                COUNT(CASE WHEN expiry_date BETWEEN date('now', '+3 days') AND date('now', '+7 days') THEN 1 END) as soon
            FROM restaurant_inventory
            WHERE expiry_date IS NOT NULL
        ''')

        summary = cursor.fetchone()

        print(f"\nExpiry Summary:")
        print("-"*30)
        print(f"Expired: {summary[0]} items")
        print(f"Expires Today: {summary[1]} items")
        print(f"Urgent (1-2 days): {summary[2]} items")
        print(f"Soon (3-7 days): {summary[3]} items")

        conn.close()

    except Exception as e:
        logging.error(f"Error in expiry_report: {e}")
        print(f"An error occurred: {e}")

def abc_analysis():
    """ABC analysis of inventory - FIXED"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\n" + "="*60)
        print("ABC INVENTORY ANALYSIS")
        print("="*60)

        # Calculate inventory value for each item
        cursor.execute('''
            SELECT item_id, name, quantity, cost_per_unit,
                   (quantity * cost_per_unit) as total_value
            FROM restaurant_inventory
            WHERE cost_per_unit IS NOT NULL AND quantity > 0
            ORDER BY total_value DESC
        ''')

        items = cursor.fetchall()

        if not items:
            print("No inventory items with cost data found.")
            conn.close()
            return

        # Calculate total value
        total_value = sum(item[4] for item in items)
        
        # Classify items into A, B, C categories
        # A items: Top 20% by value (typically 70-80% of total value)
        # B items: Next 30% by value (typically 15-25% of total value)
        # C items: Remaining 50% by value (typically 5-10% of total value)
        
        a_threshold = len(items) * 0.2
        b_threshold = len(items) * 0.5
        
        a_items = []
        b_items = []
        c_items = []
        
        cumulative_value = 0
        
        for i, item in enumerate(items):
            cumulative_value += item[4]
            cumulative_percentage = (cumulative_value / total_value) * 100
            
            if i < a_threshold:
                category = 'A'
                a_items.append((item, cumulative_percentage))
            elif i < b_threshold:
                category = 'B'
                b_items.append((item, cumulative_percentage))
            else:
                category = 'C'
                c_items.append((item, cumulative_percentage))

        # Display results
        print(f"Total Inventory Value: £{total_value:.2f}")
        print(f"Total Items Analyzed: {len(items)}")
        print()

        # Category A - High Value Items
        if a_items:
            a_value = sum(item[0][4] for item in a_items)
            a_percentage = (a_value / total_value) * 100
            
            print(f"CATEGORY A - HIGH VALUE ITEMS ({len(a_items)} items, {a_percentage:.1f}% of value)")
            print("-"*80)
            print(f"{'Item':<25} {'Quantity':<12} {'Unit Cost':<12} {'Total Value':<15} {'Cum %':<8}")
            print("-"*80)
            
            for item, cum_pct in a_items[:10]:  # Show top 10
                print(f"{item[1][:24]:<25} {item[2]:<12.1f} £{item[3]:<11.2f} £{item[4]:<14.2f} {cum_pct:<7.1f}%")
            
            if len(a_items) > 10:
                print(f"... and {len(a_items) - 10} more items")
            print()

        # Category B - Medium Value Items
        if b_items:
            b_value = sum(item[0][4] for item in b_items)
            b_percentage = (b_value / total_value) * 100
            
            print(f"CATEGORY B - MEDIUM VALUE ITEMS ({len(b_items)} items, {b_percentage:.1f}% of value)")
            print("-"*80)
            print(f"Sample items (showing first 5):")
            
            for item, cum_pct in b_items[:5]:
                print(f"{item[1][:24]:<25} {item[2]:<12.1f} £{item[3]:<11.2f} £{item[4]:<14.2f} {cum_pct:<7.1f}%")
            print()

        # Category C - Low Value Items
        if c_items:
            c_value = sum(item[0][4] for item in c_items)
            c_percentage = (c_value / total_value) * 100
            
            print(f"CATEGORY C - LOW VALUE ITEMS ({len(c_items)} items, {c_percentage:.1f}% of value)")
            print("-"*40)
            print(f"Total value of all C items: £{c_value:.2f}")
            print()

        # Management recommendations
        print("MANAGEMENT RECOMMENDATIONS:")
        print("-"*50)
        print("Category A Items:")
        print("• Tight inventory control and frequent monitoring")
        print("• Accurate demand forecasting")
        print("• Strong supplier relationships")
        print("• Daily/weekly stock checks")
        print()
        print("Category B Items:")
        print("• Normal inventory control")
        print("• Regular monitoring (weekly/bi-weekly)")
        print("• Standard ordering procedures")
        print()
        print("Category C Items:")
        print("• Simple inventory control")
        print("• Larger order quantities, less frequent orders")
        print("• Focus on cost-effective ordering")

        conn.close()

    except Exception as e:
        logging.error(f"Error in abc_analysis: {e}")
        print(f"An error occurred: {e}")

def display_inventory_management():
    """Inventory management menu with full functionality"""
    global auth

    while True:
        print("\n" + "="*50)
        print("INVENTORY MANAGEMENT")
        print("="*50)

        print("\nOptions:")
        print("1. View inventory")
        print("2. Add inventory item")
        print("3. Update stock levels")
        print("4. Low stock alerts")
        print("5. Inventory transactions")
        print("6. Purchase orders")
        print("7. Supplier management")
        print("8. Waste tracking")
        print("9. Inventory reports")
        print("10. Return to main menu")

        choice = input("Choose an option (1-10): ")

        if choice == '1':
            view_inventory()
        elif choice == '2':
            add_inventory_item()
        elif choice == '3':
            update_stock_levels()
        elif choice == '4':
            low_stock_alerts()
        elif choice == '5':
            inventory_transactions()
        elif choice == '6':
            manage_purchase_orders()
        elif choice == '7':
            manage_suppliers()
        elif choice == '8':
            waste_tracking()
        elif choice == '9':
            inventory_reports()
        elif choice == '10':
            return
        else:
            print("Invalid choice. Please try again.")

def view_inventory():
    """View inventory items"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\nFilter options:")
        print("1. All items")
        print("2. Low stock items")
        print("3. By category")
        print("4. Expiring soon")
        print("5. By supplier")

        filter_choice = input("Choose filter (1-5): ")

        if filter_choice == '1':
            cursor.execute('''
                SELECT i.*, s.name as supplier_name
                FROM restaurant_inventory i
                LEFT JOIN restaurant_suppliers s ON i.supplier_id = s.supplier_id
                ORDER BY i.name
            ''')
        elif filter_choice == '2':
            cursor.execute('''
                SELECT i.*, s.name as supplier_name
                FROM restaurant_inventory i
                LEFT JOIN restaurant_suppliers s ON i.supplier_id = s.supplier_id
                WHERE i.quantity <= i.reorder_level
                ORDER BY i.quantity
            ''')
        elif filter_choice == '3':
            category = input("Enter category: ")
            cursor.execute('''
                SELECT i.*, s.name as supplier_name
                FROM restaurant_inventory i
                LEFT JOIN restaurant_suppliers s ON i.supplier_id = s.supplier_id
                WHERE i.category = ?
                ORDER BY i.name
            ''', (category,))
        elif filter_choice == '4':
            cursor.execute('''
                SELECT i.*, s.name as supplier_name
                FROM restaurant_inventory i
                LEFT JOIN restaurant_suppliers s ON i.supplier_id = s.supplier_id
                WHERE i.expiry_date <= date('now', '+7 days')
                ORDER BY i.expiry_date
            ''')
        elif filter_choice == '5':
            supplier_id = input("Enter supplier ID: ")
            cursor.execute('''
                SELECT i.*, s.name as supplier_name
                FROM restaurant_inventory i
                LEFT JOIN restaurant_suppliers s ON i.supplier_id = s.supplier_id
                WHERE i.supplier_id = ?
                ORDER BY i.name
            ''', (supplier_id,))

        items = cursor.fetchall()

        if not items:
            print("No inventory items found.")
            conn.close()
            return

        print(f"\n" + "="*140)
        print("INVENTORY")
        print("="*140)
        print(f"{'Item ID':<10} {'Name':<25} {'Quantity':<10} {'Unit':<8} {'Cost/Unit':<10} {'Reorder':<8} {'Category':<12} {'Supplier':<15}")
        print("-"*140)

        for item in items:
            cost_str = f"£{item[4]:.2f}" if item[4] else "N/A"
            supplier_name = item[14] if item[14] else "N/A"
            
            print(f"{item[0]:<10} {item[1]:<25} {item[2]:<10.1f} {item[3]:<8} {cost_str:<10} {item[5]:<8.1f} {item[8] or 'N/A':<12} {supplier_name:<15}")

        print("="*140)
        print(f"Total items: {len(items)}")

        # Inventory value
        cursor.execute('SELECT SUM(quantity * cost_per_unit) FROM restaurant_inventory WHERE cost_per_unit IS NOT NULL')
        total_value = cursor.fetchone()[0]
        if total_value:
            print(f"Total Inventory Value: £{total_value:.2f}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in view_inventory: {e}")
        print(f"An error occurred: {e}")

def add_inventory_item():
    """Add new inventory item"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to add inventory items.")
        return

    if not auth.check_permission('manage_inventory'):
        print("You don't have permission to add inventory items.")
        return

    try:
        backup_before_operation('add_inventory_item')

        print("\n" + "="*50)
        print("ADD INVENTORY ITEM")
        print("="*50)

        # Generate item ID
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT MAX(item_id) FROM restaurant_inventory WHERE item_id LIKE ?', ('INV%',))
        result = cursor.fetchone()[0]

        if result:
            number = int(result[3:]) + 1
            item_id = f"INV{number:04d}"
        else:
            item_id = "INV0001"

        # Get item details
        name = input("Enter item name: ").strip()
        if not name:
            print("Item name is required.")
            conn.close()
            return

        try:
            quantity = float(input("Enter initial quantity: "))
            if quantity < 0:
                raise ValueError
        except ValueError:
            print("Invalid quantity.")
            conn.close()
            return

        unit = input("Enter unit (kg, lbs, pieces, liters, etc.): ").strip()

        try:
            cost_per_unit = float(input("Enter cost per unit (£): "))
            if cost_per_unit < 0:
                raise ValueError
        except ValueError:
            print("Invalid cost.")
            conn.close()
            return

        try:
            reorder_level = float(input("Enter reorder level: "))
            if reorder_level < 0:
                raise ValueError
        except ValueError:
            print("Invalid reorder level.")
            conn.close()
            return

        try:
            max_level = float(input("Enter maximum stock level: "))
            if max_level < reorder_level:
                raise ValueError
        except ValueError:
            print("Invalid maximum level (must be >= reorder level).")
            conn.close()
            return

        # Get suppliers
        cursor.execute('SELECT supplier_id, name FROM restaurant_suppliers WHERE status = ?', ('Active',))
        suppliers = cursor.fetchall()

        if suppliers:
            print("\nAvailable suppliers:")
            for i, supplier in enumerate(suppliers, 1):
                print(f"{i}. {supplier[1]} (ID: {supplier[0]})")
            
            try:
                supplier_choice = int(input("Choose supplier (enter number, 0 for none): "))
                if supplier_choice == 0:
                    supplier_id = None
                elif 1 <= supplier_choice <= len(suppliers):
                    supplier_id = suppliers[supplier_choice - 1][0]
                else:
                    raise ValueError
            except ValueError:
                print("Invalid supplier choice.")
                supplier_id = None
        else:
            supplier_id = None

        category = input("Enter category: ").strip()
        expiry_date = input("Enter expiry date (YYYY-MM-DD, optional): ").strip()
        if expiry_date:
            try:
                datetime.strptime(expiry_date, '%Y-%m-%d')
            except ValueError:
                print("Invalid date format, skipping expiry date.")
                expiry_date = None

        batch_number = input("Enter batch number (optional): ").strip()
        location = input("Enter storage location (optional): ").strip()
        temperature_req = input("Enter temperature requirements (optional): ").strip()

        # Insert new item
        cursor.execute('''
            INSERT INTO restaurant_inventory VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            item_id, name, quantity, unit, cost_per_unit, reorder_level, max_level,
            supplier_id, category, expiry_date, batch_number,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'), location, temperature_req
        ))

        # Create initial transaction record
        transaction_id = f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"
        cursor.execute('''
            INSERT INTO restaurant_inventory_transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            transaction_id, item_id, 'Initial Stock', quantity, cost_per_unit,
            None, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'Initial inventory entry', auth.current_user['id']
        ))

        conn.commit()
        conn.close()

        print(f"\n✅ Inventory item added successfully!")
        print(f"Item ID: {item_id}")
        print(f"Name: {name}")
        print(f"Quantity: {quantity} {unit}")
        print(f"Cost per unit: £{cost_per_unit:.2f}")
        print(f"Reorder level: {reorder_level}")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'ADD_INVENTORY_ITEM',
            'restaurant_inventory',
            item_id,
            None,
            {'name': name, 'quantity': quantity, 'cost_per_unit': cost_per_unit}
        )

    except Exception as e:
        logging.error(f"Error in add_inventory_item: {e}")
        print(f"An error occurred: {e}")

def update_stock_levels():
    """Update inventory stock levels"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to update stock levels.")
        return

    if not auth.check_permission('manage_inventory'):
        print("You don't have permission to update stock levels.")
        return

    try:
        backup_before_operation('update_stock_levels')

        item_id = input("Enter item ID to update: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT name, quantity, unit FROM restaurant_inventory WHERE item_id = ?', (item_id,))
        item = cursor.fetchone()

        if not item:
            print("Item not found.")
            conn.close()
            return

        print(f"Item: {item[0]}")
        print(f"Current quantity: {item[1]} {item[2]}")

        print("\nUpdate options:")
        print("1. Add stock (received)")
        print("2. Remove stock (used/sold)")
        print("3. Set exact quantity")
        print("4. Stock adjustment")

        choice = input("Choose option (1-4): ")

        try:
            if choice == '1':
                quantity_change = float(input("Enter quantity to add: "))
                new_quantity = item[1] + quantity_change
                transaction_type = 'Stock In'
                notes = input("Enter notes (e.g., supplier delivery): ")
            elif choice == '2':
                quantity_change = float(input("Enter quantity to remove: "))
                new_quantity = max(0, item[1] - quantity_change)
                quantity_change = -quantity_change
                transaction_type = 'Stock Out'
                notes = input("Enter notes (e.g., used in kitchen): ")
            elif choice == '3':
                new_quantity = float(input("Enter exact quantity: "))
                quantity_change = new_quantity - item[1]
                transaction_type = 'Adjustment'
                notes = input("Enter reason for adjustment: ")
            elif choice == '4':
                quantity_change = float(input("Enter adjustment (+/-): "))
                new_quantity = max(0, item[1] + quantity_change)
                transaction_type = 'Adjustment'
                notes = input("Enter reason for adjustment: ")
            else:
                print("Invalid choice.")
                conn.close()
                return
        except ValueError:
            print("Invalid quantity.")
            conn.close()
            return

        # Update inventory
        cursor.execute('UPDATE restaurant_inventory SET quantity = ?, last_updated = ? WHERE item_id = ?',
                      (new_quantity, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), item_id))

        # Create transaction record
        transaction_id = f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"
        cursor.execute('''
            INSERT INTO restaurant_inventory_transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            transaction_id, item_id, transaction_type, abs(quantity_change), None,
            None, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            notes, auth.current_user['id']
        ))

        conn.commit()
        conn.close()

        print(f"\n✅ Stock level updated!")
        print(f"Previous quantity: {item[1]} {item[2]}")
        print(f"New quantity: {new_quantity} {item[2]}")
        print(f"Change: {quantity_change:+.1f} {item[2]}")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'UPDATE_STOCK_LEVEL',
            'restaurant_inventory',
            item_id,
            {'old_quantity': item[1]},
            {'new_quantity': new_quantity, 'change': quantity_change}
        )

    except Exception as e:
        logging.error(f"Error in update_stock_levels: {e}")
        print(f"An error occurred: {e}")

def low_stock_alerts():
    """Show low stock alerts"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT i.*, s.name as supplier_name
            FROM restaurant_inventory i
            LEFT JOIN restaurant_suppliers s ON i.supplier_id = s.supplier_id
            WHERE i.quantity <= i.reorder_level
            ORDER BY (i.quantity / i.reorder_level), i.name
        ''')

        low_stock_items = cursor.fetchall()

        if not low_stock_items:
            print("✅ No low stock alerts!")
            conn.close()
            return

        print(f"\n" + "="*120)
        print("⚠️  LOW STOCK ALERTS")
        print("="*120)
        print(f"{'Item ID':<10} {'Name':<25} {'Current':<10} {'Reorder':<10} {'Unit':<8} {'Supplier':<20} {'Status':<15}")
        print("-"*120)

        for item in low_stock_items:
            current_qty = item[2]
            reorder_level = item[5]
            supplier_name = item[14] if item[14] else "No supplier"
            
            if current_qty == 0:
                status = "❌ OUT OF STOCK"
            elif current_qty <= reorder_level * 0.5:
                status = "🔴 CRITICAL LOW"
            else:
                status = "🟡 LOW STOCK"

            print(f"{item[0]:<10} {item[1]:<25} {current_qty:<10.1f} {reorder_level:<10.1f} {item[3]:<8} {supplier_name:<20} {status:<15}")

        print("="*120)
        print(f"Total low stock items: {len(low_stock_items)}")

        # Show suggestion for automatic reorder
        print("\nRecommended actions:")
        for item in low_stock_items:
            if item[6]:  # max_level exists
                suggest_qty = item[6] - item[2]  # max level - current quantity
                print(f"• Reorder {suggest_qty:.0f} {item[3]} of {item[1]}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in low_stock_alerts: {e}")
        print(f"An error occurred: {e}")

def inventory_transactions():
    """View inventory transaction history"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\nFilter options:")
        print("1. All transactions (last 50)")
        print("2. By item")
        print("3. By transaction type")
        print("4. By date range")
        print("5. Today's transactions")

        filter_choice = input("Choose filter (1-5): ")

        if filter_choice == '1':
            cursor.execute('''
                SELECT it.*, i.name as item_name
                FROM restaurant_inventory_transactions it
                JOIN restaurant_inventory i ON it.item_id = i.item_id
                ORDER BY it.transaction_date DESC
                LIMIT 50
            ''')
        elif filter_choice == '2':
            item_id = input("Enter item ID: ")
            cursor.execute('''
                SELECT it.*, i.name as item_name
                FROM restaurant_inventory_transactions it
                JOIN restaurant_inventory i ON it.item_id = i.item_id
                WHERE it.item_id = ?
                ORDER BY it.transaction_date DESC
            ''', (item_id,))
        elif filter_choice == '3':
            print("Transaction types: Stock In, Stock Out, Adjustment, Initial Stock")
            trans_type = input("Enter transaction type: ")
            cursor.execute('''
                SELECT it.*, i.name as item_name
                FROM restaurant_inventory_transactions it
                JOIN restaurant_inventory i ON it.item_id = i.item_id
                WHERE it.transaction_type = ?
                ORDER BY it.transaction_date DESC
            ''', (trans_type,))
        elif filter_choice == '4':
            start_date = input("Enter start date (YYYY-MM-DD): ")
            end_date = input("Enter end date (YYYY-MM-DD): ")
            cursor.execute('''
                SELECT it.*, i.name as item_name
                FROM restaurant_inventory_transactions it
                JOIN restaurant_inventory i ON it.item_id = i.item_id
                WHERE DATE(it.transaction_date) BETWEEN ? AND ?
                ORDER BY it.transaction_date DESC
            ''', (start_date, end_date))
        elif filter_choice == '5':
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT it.*, i.name as item_name
                FROM restaurant_inventory_transactions it
                JOIN restaurant_inventory i ON it.item_id = i.item_id
                WHERE DATE(it.transaction_date) = ?
                ORDER BY it.transaction_date DESC
            ''', (today,))

        transactions = cursor.fetchall()

        if not transactions:
            print("No transactions found.")
            conn.close()
            return

        print(f"\n" + "="*120)
        print("INVENTORY TRANSACTIONS")
        print("="*120)
        print(f"{'Transaction ID':<15} {'Date':<12} {'Item':<25} {'Type':<12} {'Quantity':<10} {'Notes':<25}")
        print("-"*120)

        for trans in transactions:
            trans_date = trans[6][:10] if trans[6] else 'N/A'
            quantity_str = f"{trans[3]:.1f}" if trans[3] else "N/A"
            notes = trans[7][:24] if trans[7] else ""
            
            print(f"{trans[0]:<15} {trans_date:<12} {trans[9]:<25} {trans[2]:<12} {quantity_str:<10} {notes:<25}")

        print("="*120)
        print(f"Total transactions: {len(transactions)}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in inventory_transactions: {e}")
        print(f"An error occurred: {e}")
