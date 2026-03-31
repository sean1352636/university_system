from education_system.university_system.infrastructure.auth import UserAuth, display_auth_menu
from education_system.university_system.modules.domain.commerce.services.restaurant.operations.audit import log_audit_action
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
from education_system.university_system.modules.shared.constants.paths import QR_CODES_DIR
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608
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


def display_table_management():
    """Table management menu with full functionality"""
    global auth

    while True:
        print("\n" + "="*50)
        print("TABLE MANAGEMENT")
        print("="*50)

        print("\nOptions:")
        print("1. View all tables")
        print("2. Add new table")
        print("3. Update table")
        print("4. Delete table")
        print("5. View table reservations")
        print("6. Create reservation")
        print("7. Cancel reservation")
        print("8. Table analytics")
        print("9. Generate QR codes")
        print("10. Return to main menu")

        choice = input("Choose an option (1-10): ")

        if choice == '1':
            view_all_tables()
        elif choice == '2':
            add_new_table()
        elif choice == '3':
            update_table()
        elif choice == '4':
            delete_table()
        elif choice == '5':
            view_table_reservations()
        elif choice == '6':
            create_reservation()
        elif choice == '7':
            cancel_reservation()
        elif choice == '8':
            table_analytics()
        elif choice == '9':
            generate_qr_codes()
        elif choice == '10':
            return
        else:
            print("Invalid choice. Please try again.")

def view_all_tables():
    """View all tables with their current status"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT t.*, o.order_date, o.customer_id
            FROM restaurant_tables t
            LEFT JOIN orders o ON t.current_order_id = o.order_id
            ORDER BY t.table_id
        ''')

        tables = cursor.fetchall()

        if not tables:
            print("No tables found.")
            conn.close()
            return

        print(f"\n" + "="*100)
        print("TABLE STATUS")
        print("="*100)
        print(f"{'Table ID':<10} {'Capacity':<10} {'Status':<12} {'Location':<15} {'Type':<12} {'Order Since':<15}")
        print("-"*100)

        for table in tables:
            order_time = table[7][:16] if table[7] else ''
            print(f"{table[0]:<10} {table[1]:<10} {table[2]:<12} {table[4] or 'N/A':<15} {table[5] or 'Standard':<12} {order_time:<15}")

        print("="*100)
        print(f"Total tables: {len(tables)}")

        # Summary by status
        cursor.execute('''
            SELECT status, COUNT(*) as count
            FROM restaurant_tables
            GROUP BY status
        ''')

        status_summary = cursor.fetchall()
        print("\nTable Status Summary:")
        for status, count in status_summary:
            print(f"{status}: {count} tables")

        conn.close()

    except Exception as e:
        logging.error(f"Error in view_all_tables: {e}")
        print(f"An error occurred: {e}")

def add_new_table():
    """Add a new table"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to add tables.")
        return

    if not auth.check_permission('manage_tables'):
        print("You don't have permission to add tables.")
        return

    try:
        backup_before_operation('add_new_table')

        print("\n" + "="*50)
        print("ADD NEW TABLE")
        print("="*50)

        # Generate table ID
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT MAX(table_id) FROM restaurant_tables WHERE table_id LIKE ?', ('T%',))
        result = cursor.fetchone()[0]

        if result:
            number = int(result[1:]) + 1
            table_id = f"T{number:03d}"
        else:
            table_id = "T001"

        # Get table details
        try:
            capacity = int(input("Enter table capacity (number of seats): "))
            if capacity <= 0:
                raise ValueError
        except ValueError:
            print("Invalid capacity.")
            conn.close()
            return

        location = input("Enter location (e.g., Main Dining, Patio, Private Room): ").strip()

        print("\nTable types:")
        print("1. Standard")
        print("2. High-top")
        print("3. Booth")
        print("4. VIP")
        print("5. Outdoor")

        type_choice = input("Choose table type (1-5): ")
        types = {
            '1': 'Standard',
            '2': 'High-top',
            '3': 'Booth',
            '4': 'VIP',
            '5': 'Outdoor'
        }
        table_type = types.get(type_choice, 'Standard')

        # Insert new table
        cursor.execute('''
            INSERT INTO restaurant_tables VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            table_id, capacity, 'Available', None, location, table_type,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))

        conn.commit()
        conn.close()

        print(f"\n✅ Table added successfully!")
        print(f"Table ID: {table_id}")
        print(f"Capacity: {capacity}")
        print(f"Location: {location}")
        print(f"Type: {table_type}")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'ADD_TABLE',
            'restaurant_tables',
            table_id,
            None,
            {'capacity': capacity, 'location': location, 'type': table_type}
        )

    except Exception as e:
        logging.error(f"Error in add_new_table: {e}")
        print(f"An error occurred: {e}")

def update_table():
    """Update table information"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to update tables.")
        return

    if not auth.check_permission('manage_tables'):
        print("You don't have permission to update tables.")
        return

    try:
        backup_before_operation('update_table')

        table_id = input("Enter table ID to update: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM restaurant_tables WHERE table_id = ?', (table_id,))
        table = cursor.fetchone()

        if not table:
            print("Table not found.")
            conn.close()
            return

        print(f"\nCurrent Table Information:")
        print(f"1. Capacity: {table[1]}")
        print(f"2. Status: {table[2]}")
        print(f"3. Location: {table[4] or 'Not set'}")
        print(f"4. Type: {table[5] or 'Standard'}")
        print("5. Cancel update")

        choice = input("Enter field number to update (1-5): ")

        if choice == '5':
            print("Update cancelled.")
            conn.close()
            return

        if choice == '1':
            try:
                new_capacity = int(input("Enter new capacity: "))
                cursor.execute('UPDATE restaurant_tables SET capacity = ? WHERE table_id = ?',
                              (new_capacity, table_id))
                print("Capacity updated successfully.")
            except ValueError:
                print("Invalid capacity.")
        elif choice == '2':
            print("\nStatus options:")
            print("1. Available")
            print("2. Occupied")
            print("3. Reserved")
            print("4. Cleaning")
            print("5. Out of Order")

            status_choice = input("Choose status (1-5): ")
            statuses = {
                '1': 'Available',
                '2': 'Occupied',
                '3': 'Reserved',
                '4': 'Cleaning',
                '5': 'Out of Order'
            }
            new_status = statuses.get(status_choice)

            if new_status:
                cursor.execute('UPDATE restaurant_tables SET status = ? WHERE table_id = ?',
                              (new_status, table_id))
                print("Status updated successfully.")
            else:
                print("Invalid status choice.")
        elif choice == '3':
            new_location = input("Enter new location: ").strip()
            cursor.execute('UPDATE restaurant_tables SET location = ? WHERE table_id = ?',
                          (new_location, table_id))
            print("Location updated successfully.")
        elif choice == '4':
            print("\nTable types:")
            print("1. Standard")
            print("2. High-top")
            print("3. Booth")
            print("4. VIP")
            print("5. Outdoor")

            type_choice = input("Choose table type (1-5): ")
            types = {
                '1': 'Standard',
                '2': 'High-top',
                '3': 'Booth',
                '4': 'VIP',
                '5': 'Outdoor'
            }
            new_type = types.get(type_choice)

            if new_type:
                cursor.execute('UPDATE restaurant_tables SET table_type = ? WHERE table_id = ?',
                              (new_type, table_id))
                print("Type updated successfully.")
            else:
                print("Invalid type choice.")

        conn.commit()
        conn.close()

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'UPDATE_TABLE',
            'restaurant_tables',
            table_id,
            None,
            {'updated': True}
        )

    except Exception as e:
        logging.error(f"Error in update_table: {e}")
        print(f"An error occurred: {e}")

def delete_table():
    """Delete a table"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to delete tables.")
        return

    if not auth.check_permission('manage_tables'):
        print("You don't have permission to delete tables.")
        return

    try:
        backup_before_operation('delete_table')

        table_id = input("Enter table ID to delete: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM restaurant_tables WHERE table_id = ?', (table_id,))
        table = cursor.fetchone()

        if not table:
            print("Table not found.")
            conn.close()
            return

        if table[2] == 'Occupied':
            print("Cannot delete occupied table.")
            conn.close()
            return

        print(f"Table {table_id} - Capacity: {table[1]}, Location: {table[4]}")
        confirm = input("Type 'DELETE' to confirm deletion: ")

        if confirm == 'DELETE':
            cursor.execute('DELETE FROM restaurant_tables WHERE table_id = ?', (table_id,))
            conn.commit()
            print(f"Table {table_id} deleted successfully.")

            # Log audit action
            log_audit_action(
                auth.current_user['id'],
                'DELETE_TABLE',
                'restaurant_tables',
                table_id,
                {'capacity': table[1], 'location': table[4]},
                None
            )
        else:
            print("Deletion cancelled.")

        conn.close()

    except Exception as e:
        logging.error(f"Error in delete_table: {e}")
        print(f"An error occurred: {e}")

def view_table_reservations():
    """View table reservations"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\nFilter options:")
        print("1. All reservations")
        print("2. Today's reservations")
        print("3. Tomorrow's reservations")
        print("4. This week's reservations")
        print("5. By date range")

        choice = input("Choose filter (1-5): ")

        if choice == '1':
            cursor.execute('''
                SELECT r.*, c.name as customer_name, t.capacity
                FROM restaurant_reservations r
                JOIN restaurant_customers c ON r.customer_id = c.customer_id
                JOIN restaurant_tables t ON r.table_id = t.table_id
                ORDER BY r.reservation_date, r.reservation_time
            ''')
        elif choice == '2':
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT r.*, c.name as customer_name, t.capacity
                FROM restaurant_reservations r
                JOIN restaurant_customers c ON r.customer_id = c.customer_id
                JOIN restaurant_tables t ON r.table_id = t.table_id
                WHERE r.reservation_date = ?
                ORDER BY r.reservation_time
            ''', (today,))
        elif choice == '3':
            tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT r.*, c.name as customer_name, t.capacity
                FROM restaurant_reservations r
                JOIN restaurant_customers c ON r.customer_id = c.customer_id
                JOIN restaurant_tables t ON r.table_id = t.table_id
                WHERE r.reservation_date = ?
                ORDER BY r.reservation_time
            ''', (tomorrow,))
        elif choice == '4':
            start_week = datetime.now().strftime('%Y-%m-%d')
            end_week = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT r.*, c.name as customer_name, t.capacity
                FROM restaurant_reservations r
                JOIN restaurant_customers c ON r.customer_id = c.customer_id
                JOIN restaurant_tables t ON r.table_id = t.table_id
                WHERE r.reservation_date BETWEEN ? AND ?
                ORDER BY r.reservation_date, r.reservation_time
            ''', (start_week, end_week))
        elif choice == '5':
            start_date = input("Enter start date (YYYY-MM-DD): ")
            end_date = input("Enter end date (YYYY-MM-DD): ")
            cursor.execute('''
                SELECT r.*, c.name as customer_name, t.capacity
                FROM restaurant_reservations r
                JOIN restaurant_customers c ON r.customer_id = c.customer_id
                JOIN restaurant_tables t ON r.table_id = t.table_id
                WHERE r.reservation_date BETWEEN ? AND ?
                ORDER BY r.reservation_date, r.reservation_time
            ''', (start_date, end_date))

        reservations = cursor.fetchall()

        if not reservations:
            print("No reservations found.")
            conn.close()
            return

        print(f"\n" + "="*120)
        print("RESERVATIONS")
        print("="*120)
        print(f"{'Reservation ID':<15} {'Date':<12} {'Time':<8} {'Customer':<20} {'Table':<8} {'Party':<6} {'Status':<10}")
        print("-"*120)

        for res in reservations:
            print(f"{res[0]:<15} {res[3]:<12} {res[4]:<8} {res[10]:<20} {res[2]:<8} {res[5]:<6} {res[6]:<10}")

        print("="*120)
        print(f"Total reservations: {len(reservations)}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in view_table_reservations: {e}")
        print(f"An error occurred: {e}")

def create_reservation():
    """Create a new table reservation"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to create reservations.")
        return

    try:
        backup_before_operation('create_reservation')

        print("\n" + "="*50)
        print("CREATE RESERVATION")
        print("="*50)

        # Get customer
        customer_id = input("Enter customer ID (or 'new' to create new customer): ")

        conn = get_db_connection()
        cursor = conn.cursor()

        if customer_id.lower() == 'new':
            print("Creating new customer first...")
            create_customer()
            customer_id = input("Enter the new customer ID: ")

        # Verify customer exists
        cursor.execute('SELECT name FROM restaurant_customers WHERE customer_id = ?', (customer_id,))
        customer = cursor.fetchone()

        if not customer:
            print("Customer not found.")
            conn.close()
            return

        # Get reservation details
        reservation_date = input("Enter reservation date (YYYY-MM-DD): ")
        try:
            datetime.strptime(reservation_date, '%Y-%m-%d')
        except ValueError:
            print("Invalid date format.")
            conn.close()
            return

        reservation_time = input("Enter reservation time (HH:MM): ")
        try:
            datetime.strptime(reservation_time, '%H:%M')
        except ValueError:
            print("Invalid time format.")
            conn.close()
            return

        try:
            party_size = int(input("Enter party size: "))
            if party_size <= 0:
                raise ValueError
        except ValueError:
            print("Invalid party size.")
            conn.close()
            return

        # Find available tables
        cursor.execute('''
            SELECT table_id, capacity, location, table_type
            FROM restaurant_tables
            WHERE capacity >= ? AND status = 'Available'
            ORDER BY capacity
        ''', (party_size,))

        available_tables = cursor.fetchall()

        if not available_tables:
            print(f"No tables available for party size {party_size}.")
            conn.close()
            return

        print("\nAvailable tables:")
        for i, table in enumerate(available_tables, 1):
            print(f"{i}. {table[0]} - Capacity: {table[1]}, Location: {table[2]}, Type: {table[3]}")

        try:
            table_choice = int(input("Choose table (enter number): ")) - 1
            if table_choice < 0 or table_choice >= len(available_tables):
                raise ValueError
            selected_table = available_tables[table_choice]
        except ValueError:
            print("Invalid table choice.")
            conn.close()
            return

        special_requests = input("Enter special requests (optional): ").strip()

        # Generate reservation ID
        reservation_id = f"RES{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"

        # Create reservation
        cursor.execute('''
            INSERT INTO restaurant_reservations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            reservation_id, customer_id, selected_table[0], reservation_date,
            reservation_time, party_size, 'Active', special_requests,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))

        # Update table status
        cursor.execute('UPDATE restaurant_tables SET status = ? WHERE table_id = ?',
                      ('Reserved', selected_table[0]))

        conn.commit()
        conn.close()

        print(f"\n✅ Reservation created successfully!")
        print(f"Reservation ID: {reservation_id}")
        print(f"Customer: {customer[0]}")
        print(f"Date: {reservation_date}")
        print(f"Time: {reservation_time}")
        print(f"Table: {selected_table[0]} (Capacity: {selected_table[1]})")
        print(f"Party Size: {party_size}")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'CREATE_RESERVATION',
            'restaurant_reservations',
            reservation_id,
            None,
            {'customer_id': customer_id, 'table_id': selected_table[0], 'party_size': party_size}
        )

    except Exception as e:
        logging.error(f"Error in create_reservation: {e}")
        print(f"An error occurred: {e}")

def cancel_reservation():
    """Cancel a table reservation"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to cancel reservations.")
        return

    try:
        backup_before_operation('cancel_reservation')

        reservation_id = input("Enter reservation ID to cancel: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT r.*, c.name as customer_name
            FROM restaurant_reservations r
            JOIN restaurant_customers c ON r.customer_id = c.customer_id
            WHERE r.reservation_id = ?
        ''', (reservation_id,))

        reservation = cursor.fetchone()

        if not reservation:
            print("Reservation not found.")
            conn.close()
            return

        if reservation[6] == 'Cancelled':
            print("Reservation is already cancelled.")
            conn.close()
            return

        print(f"Reservation Details:")
        print(f"Customer: {reservation[10]}")
        print(f"Date: {reservation[3]}")
        print(f"Time: {reservation[4]}")
        print(f"Table: {reservation[2]}")
        print(f"Party Size: {reservation[5]}")

        confirm = input("Are you sure you want to cancel this reservation? (y/n): ")

        if confirm.lower() == 'y':
            # Cancel reservation
            cursor.execute('UPDATE restaurant_reservations SET status = ? WHERE reservation_id = ?',
                          ('Cancelled', reservation_id))

            # Free up table if status is Reserved
            cursor.execute('SELECT status FROM restaurant_tables WHERE table_id = ?', (reservation[2],))
            table_status = cursor.fetchone()

            if table_status and table_status[0] == 'Reserved':
                cursor.execute('UPDATE restaurant_tables SET status = ? WHERE table_id = ?',
                              ('Available', reservation[2]))

            conn.commit()
            print(f"✅ Reservation {reservation_id} cancelled successfully.")

            # Log audit action
            log_audit_action(
                auth.current_user['id'],
                'CANCEL_RESERVATION',
                'restaurant_reservations',
                reservation_id,
                {'status': reservation[6]},
                {'status': 'Cancelled'}
            )
        else:
            print("Cancellation aborted.")

        conn.close()

    except Exception as e:
        logging.error(f"Error in cancel_reservation: {e}")
        print(f"An error occurred: {e}")

def generate_qr_codes():
    """Generate QR codes for tables with actual image files"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to generate QR codes.")
        return

    try:
        print("\n" + "="*50)
        print("GENERATE QR CODES")
        print("="*50)

        print("Options:")
        print("1. Generate for all tables")
        print("2. Generate for specific table")
        print("3. View existing QR codes")
        print("4. Regenerate existing QR codes")

        choice = input("Choose option (1-4): ")

        conn = get_db_connection()
        if not conn:
            print("Database connection failed.")
            return

        cursor = conn.cursor()

        # Use canonical QR codes directory
        qr_dir = str(QR_CODES_DIR)
        os.makedirs(qr_dir, exist_ok=True)

        if choice == '1':
            # Generate for all tables
            cursor.execute('SELECT table_id, capacity, location FROM restaurant_tables ORDER BY table_id')
            tables = cursor.fetchall()

            if not tables:
                print("No tables found.")
                conn.close()
                return

            generated_count = 0
            for table in tables:
                table_id, capacity, location = table

                # Generate QR code
                qr_success, qr_filename = create_qr_code_image(table_id, capacity, location)

                if qr_success:
                    # Update/Insert QR code record in database
                    update_qr_database_record(cursor, table_id, qr_filename)
                    generated_count += 1
                    print(f"✅ Generated QR code for table {table_id}: {qr_filename}")
                else:
                    print(f"❌ Failed to generate QR code for table {table_id}")

            print(f"\n✅ Generated QR codes for {generated_count} tables.")

        elif choice == '2':
            # Generate for specific table
            table_id = input("Enter table ID: ")

            cursor.execute('SELECT table_id, capacity, location FROM restaurant_tables WHERE table_id = ?', (table_id,))
            table = cursor.fetchone()

            if not table:
                print("Table not found.")
                conn.close()
                return

            table_id, capacity, location = table

            # Generate QR code
            qr_success, qr_filename = create_qr_code_image(table_id, capacity, location)

            if qr_success:
                update_qr_database_record(cursor, table_id, qr_filename)
                print(f"✅ Generated QR code for table {table_id}: {qr_filename}")
            else:
                print(f"❌ Failed to generate QR code for table {table_id}")

        elif choice == '3':
            # View existing QR codes
            cursor.execute('''
                SELECT qr.qr_id, qr.table_id, qr.qr_data, qr.created_date,
                       qr.usage_count, qr.status, t.capacity, t.location
                FROM restaurant_qr_codes qr
                JOIN restaurant_tables t ON qr.table_id = t.table_id
                ORDER BY qr.table_id
            ''')

            qr_codes = cursor.fetchall()

            if not qr_codes:
                print("No QR codes found.")
            else:
                print(f"\n" + "="*120)
                print("EXISTING QR CODES")
                print("="*120)
                print(f"{'QR ID':<15} {'Table':<8} {'Location':<15} {'Created':<12} {'Usage':<8} {'Status':<8} {'File Exists':<12}")
                print("-"*120)

                for qr in qr_codes:
                    created_date = qr[3][:10] if qr[3] else 'N/A'

                    # Check if QR code file exists
                    qr_filename = QR_CODES_DIR / f"table_{qr[1]}_qr.png"
                    file_exists = "✅ Yes" if qr_filename.exists() else "❌ No"

                    location = qr[7] or 'N/A'

                    print(f"{qr[0]:<15} {qr[1]:<8} {location:<15} {created_date:<12} {qr[4]:<8} {qr[5]:<8} {file_exists:<12}")

        elif choice == '4':
            # Regenerate existing QR codes
            print("This will regenerate ALL existing QR codes.")
            confirm = input("Continue? (y/n): ")

            if confirm.lower() != 'y':
                print("Operation cancelled.")
                conn.close()
                return

            cursor.execute('SELECT table_id, capacity, location FROM restaurant_tables ORDER BY table_id')
            tables = cursor.fetchall()

            regenerated_count = 0
            for table in tables:
                table_id, capacity, location = table

                # Generate QR code (will overwrite existing)
                qr_success, qr_filename = create_qr_code_image(table_id, capacity, location)

                if qr_success:
                    update_qr_database_record(cursor, table_id, qr_filename)
                    regenerated_count += 1
                    print(f"🔄 Regenerated QR code for table {table_id}")

            print(f"\n✅ Regenerated {regenerated_count} QR codes.")

        conn.commit()
        conn.close()

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'GENERATE_QR_CODES',
            'restaurant_qr_codes',
            None,
            None,
            {'action': choice, 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        )

    except Exception as e:
        logging.error(f"Error in generate_qr_codes: {e}")
        print(f"An error occurred: {e}")

def create_qr_code_image(table_id, capacity, location):
    """Create actual QR code image file for a table"""
    try:
        # Create QR data - URL that links to online menu
        base_url = "/menu"
        qr_data = f"{base_url}?table={table_id}&capacity={capacity}"

        # Create QR code instance
        qr = qrcode.QRCode(
            version=1,  # Controls size (1 is smallest)
            error_correction=qrcode.constants.ERROR_CORRECT_L,  # ~7% error correction
            box_size=10,  # Size of each box in pixels
            border=4,  # Border size in boxes
        )

        # Add data and optimize
        qr.add_data(qr_data)
        qr.make(fit=True)

        # Create QR code image
        qr_image = qr.make_image(fill_color="black", back_color="white")

        # Create filename
        qr_filename = QR_CODES_DIR / f"table_{table_id}_qr.png"

        # Save the image
        qr_image.save(qr_filename)

        # Create a more detailed version with table info
        create_enhanced_qr_image(qr_image, table_id, capacity, location)

        return True, qr_filename

    except Exception as e:
        logging.error(f"Error creating QR code for table {table_id}: {e}")
        return False, None

def create_enhanced_qr_image(qr_image, table_id, capacity, location):
    """Create an enhanced QR code image with table information"""
    try:
        from PIL import Image, ImageDraw, ImageFont

        # Get QR image size
        qr_width, qr_height = qr_image.size

        # Create new image with extra space for text
        margin = 100
        total_width = qr_width + (margin * 2)
        total_height = qr_height + margin + 150  # Extra space for text

        # Create white background
        enhanced_image = Image.new('RGB', (total_width, total_height), 'white')

        # Paste QR code in center
        qr_x = margin
        qr_y = margin
        enhanced_image.paste(qr_image, (qr_x, qr_y))

        # Add text information
        draw = ImageDraw.Draw(enhanced_image)

        try:
            # Try to use a larger font
            title_font = ImageFont.truetype("arial.ttf", 24)
            info_font = ImageFont.truetype("arial.ttf", 16)
        except (OSError, IOError):
            # Fallback to default font
            title_font = ImageFont.load_default()
            info_font = ImageFont.load_default()

        # Add title
        title_text = f"Table {table_id}"
        title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (total_width - title_width) // 2
        title_y = 20
        draw.text((title_x, title_y), title_text, fill='black', font=title_font)

        # Add table information below QR code
        info_y = qr_y + qr_height + 20

        info_lines = [
            f"Capacity: {capacity} guests",
            f"Location: {location or 'Main dining'}",
            "Scan to view our menu",
            f"Generated: {datetime.now().strftime('%Y-%m-%d')}"
        ]

        line_height = 25
        for i, line in enumerate(info_lines):
            line_bbox = draw.textbbox((0, 0), line, font=info_font)
            line_width = line_bbox[2] - line_bbox[0]
            line_x = (total_width - line_width) // 2
            draw.text((line_x, info_y + (i * line_height)), line, fill='black', font=info_font)

        # Save enhanced version
        enhanced_filename = QR_CODES_DIR / f"table_{table_id}_qr_enhanced.png"
        enhanced_image.save(str(enhanced_filename))

        print(f"📱 Enhanced QR code saved: {enhanced_filename}")

    except Exception as e:
        logging.error(f"Error creating enhanced QR image for table {table_id}: {e}")

def update_qr_database_record(cursor, table_id, qr_filename):
    """Update or insert QR code record in database"""
    try:
        # Generate QR data for database
        qr_data = f"/menu?table={table_id}"
        qr_id = f"QR{table_id}{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Check if QR code record already exists
        cursor.execute('SELECT qr_id FROM restaurant_qr_codes WHERE table_id = ?', (table_id,))
        existing = cursor.fetchone()

        if existing:
            # Update existing record
            cursor.execute('''
                UPDATE restaurant_qr_codes
                SET qr_data = ?, created_date = ?, qr_id = ?, status = 'Active'
                WHERE table_id = ?
            ''', (qr_data, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), qr_id, table_id))
        else:
            # Insert new record
            cursor.execute('''
                INSERT INTO restaurant_qr_codes VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                qr_id, table_id, qr_data, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                None, 0, 'Active'
            ))

    except Exception as e:
        logging.error(f"Error updating QR database record for table {table_id}: {e}")

def print_qr_codes():
    """Generate a printable sheet with all QR codes - FIXED"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to print QR codes.")
        return

    try:
        conn = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor()

        # Get all tables with QR codes
        cursor.execute('''
            SELECT t.table_id, t.capacity, t.location, qr.qr_id
            FROM restaurant_tables t
            LEFT JOIN restaurant_qr_codes qr ON t.table_id = qr.table_id
            ORDER BY t.table_id
        ''')

        tables = cursor.fetchall()

        if not tables:
            print("No tables found.")
            conn.close()
            return

        # Create PDF with QR codes
        filename = f"qr_codes_printable_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        doc = SimpleDocTemplate(filename, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)

        # Build content for PDF
        content = []

        # Title
        styles = getSampleStyleSheet()
        title = f"Restaurant Table QR Codes - Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        content.append(Paragraph(title, styles['Title']))
        content.append(Spacer(1, 20))

        # Create simple table without complex colWidths
        table_data = [['Table ID', 'QR Code Status', 'Capacity', 'Location']]

        for table in tables:
            table_id, capacity, location, qr_id = table

            # Check if QR code file exists
            qr_filename = QR_CODES_DIR / f"table_{table_id}_qr.png"
            qr_status = "✓ Available" if qr_filename.exists() else "✗ Missing"

            table_data.append([
                table_id,
                qr_status,
                str(capacity),
                location or 'Main dining'
            ])

        # Create simple table
        pdf_table = Table(table_data)

        pdf_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))

        content.append(pdf_table)
        content.append(Spacer(1, 20))

        # Instructions
        instructions = [
            "Instructions:",
            "1. QR codes are stored in the 'qr_codes' directory",
            "2. Print individual QR code files for table display",
            "3. Each QR code links to the restaurant menu system",
            "4. Replace missing QR codes using the QR generation function"
        ]

        for instruction in instructions:
            content.append(Paragraph(instruction, styles['Normal']))
            content.append(Spacer(1, 6))

        # Build PDF
        doc.build(content)

        conn.close()

        print(f"✅ Printable QR codes summary generated: {filename}")
        print(f"Tables included: {len(tables)}")
        print("Note: Actual QR code images should be printed separately from the qr_codes folder")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'PRINT_QR_CODES_SUMMARY',
            'restaurant_qr_codes',
            None,
            None,
            {'filename': filename, 'table_count': len(tables)}
        )

    except Exception as e:
        logging.error(f"Error in print_qr_codes: {e}")
        print(f"An error occurred: {e}")

def scan_qr_code_usage():
    """Simulate QR code scanning and update usage statistics"""
    try:
        table_id = input("Enter table ID that was scanned: ")

        conn = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor()

        # Check if QR code exists
        cursor.execute('SELECT qr_id, usage_count FROM restaurant_qr_codes WHERE table_id = ?', (table_id,))
        qr_record = cursor.fetchone()

        if not qr_record:
            print(f"No QR code found for table {table_id}")
            conn.close()
            return

        # Update usage count and last used time
        new_usage_count = qr_record[1] + 1
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            UPDATE restaurant_qr_codes
            SET usage_count = ?, last_used = ?
            WHERE table_id = ?
        ''', (new_usage_count, current_time, table_id))

        conn.commit()
        conn.close()

        print(f"✅ QR code scan recorded for table {table_id}")
        print(f"Total scans: {new_usage_count}")

    except Exception as e:
        logging.error(f"Error in scan_qr_code_usage: {e}")
        print(f"An error occurred: {e}")

def optimize_table_structure():
    """Optimize table structure - FIXED"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to optimize table structure.")
        return

    if not auth.check_permission('admin'):
        print("You don't have permission to optimize table structure.")
        return

    try:
        print("\n" + "="*60)
        print("TABLE STRUCTURE OPTIMIZATION")
        print("="*60)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Analyze table structures and suggest optimizations
        tables_to_analyze = [
            'orders', 'restaurant_customers', 'menu_items',
            'restaurant_inventory', 'restaurant_staff', 'restaurant_audit_logs'
        ]

        print("Analyzing table structures...")
        print("-"*60)

        optimizations_made = 0

        for table in tables_to_analyze:
            try:
                safe_table = validate_identifier(table, "table")
                # Get table info
                cursor.execute("PRAGMA table_info([" + safe_table + "])")
                columns = cursor.fetchall()

                # Get table size
                cursor.execute('SELECT COUNT(*) FROM [' + safe_table + ']')
                row_count = cursor.fetchone()[0]

                print(f"\nTable: {table}")
                print(f"Rows: {row_count:,}")
                print(f"Columns: {len(columns)}")

                # Check for missing indexes on frequently queried columns
                index_suggestions = []

                if table == 'orders':
                    # Check for date index
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='orders' AND name LIKE '%order_date%'")
                    if not cursor.fetchone():
                        index_suggestions.append("order_date (for date queries)")

                    # Check for customer index
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='orders' AND name LIKE '%customer%'")
                    if not cursor.fetchone():
                        index_suggestions.append("customer_id (for customer lookups)")

                elif table == 'restaurant_customers':
                    # Check for email index
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='restaurant_customers' AND name LIKE '%email%'")
                    if not cursor.fetchone():
                        index_suggestions.append("email (for customer lookups)")

                elif table == 'restaurant_inventory':
                    # Check for reorder level index
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='restaurant_inventory' AND name LIKE '%reorder%'")
                    if not cursor.fetchone():
                        index_suggestions.append("reorder_level (for low stock queries)")

                if index_suggestions:
                    print(f"Suggested indexes:")
                    for suggestion in index_suggestions:
                        print(f"  • {suggestion}")
                else:
                    print("✅ Table structure appears optimized")

                # Check for potential data issues
                if table == 'orders' and row_count > 0:
                    # Check for orders without customer info
                    cursor.execute('SELECT COUNT(*) FROM orders WHERE customer_id IS NULL')
                    null_customers = cursor.fetchone()[0]
                    if null_customers > 0:
                        print(f"⚠️  {null_customers} orders without customer information")

                if table == 'restaurant_customers' and row_count > 0:
                    # Check for duplicate emails
                    cursor.execute('''
                        SELECT email, COUNT(*)
                        FROM restaurant_customers
                        WHERE email IS NOT NULL
                        GROUP BY email
                        HAVING COUNT(*) > 1
                    ''')
                    duplicates = cursor.fetchall()
                    if duplicates:
                        print(f"⚠️  {len(duplicates)} duplicate email addresses found")

            except Exception as e:
                print(f"Error analyzing {table}: {e}")
                continue

        # Suggest maintenance operations
        print(f"\nMaintenance Recommendations:")
        print("-"*40)
        print("1. Run VACUUM to reclaim space and defragment")
        print("2. Update table statistics with ANALYZE")
        print("3. Consider archiving old data")
        print("4. Review and add suggested indexes")
        print("5. Clean up duplicate or orphaned records")

        # Offer to perform VACUUM
        if input("\nWould you like to run VACUUM now? (y/n): ").lower() == 'y':
            print("Running VACUUM...")
            cursor.execute('VACUUM')
            print("✅ VACUUM completed")
            optimizations_made += 1

        # Offer to run ANALYZE
        if input("Would you like to run ANALYZE now? (y/n): ").lower() == 'y':
            print("Running ANALYZE...")
            cursor.execute('ANALYZE')
            print("✅ ANALYZE completed")
            optimizations_made += 1

        conn.commit()
        conn.close()

        print(f"\n✅ Table structure analysis completed!")
        print(f"Optimizations performed: {optimizations_made}")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'OPTIMIZE_TABLE_STRUCTURE',
            None,
            None,
            None,
            {'optimizations_made': optimizations_made}
        )

    except Exception as e:
        logging.error(f"Error in optimize_table_structure: {e}")
        print(f"An error occurred: {e}")
