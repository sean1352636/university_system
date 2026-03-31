from education_system.university_system.infrastructure.auth import UserAuth, display_auth_menu
from education_system.university_system.infrastructure.database.data_backup import display_backup_menu, backup_before_operation
from education_system.university_system.infrastructure.email import send_confirmation_email
from education_system.university_system.modules.domain.commerce.services.restaurant.operations.connection import get_db_connection
from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608
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


def display_staff_management():
    """Staff management menu with full functionality"""
    global auth

    while True:
        print("\n" + "="*50)
        print("STAFF MANAGEMENT")
        print("="*50)

        print("\nOptions:")
        print("1. View all staff")
        print("2. Add new staff member")
        print("3. Update staff information")
        print("4. Delete staff member")
        print("5. Manage schedules")
        print("6. Staff performance")
        print("7. Payroll calculations")
        print("8. Staff analytics")
        print("9. Return to main menu")

        choice = input("Choose an option (1-9): ")

        if choice == '1':
            view_all_staff()
        elif choice == '2':
            add_new_staff()
        elif choice == '3':
            update_staff_info()
        elif choice == '4':
            delete_staff()
        elif choice == '5':
            manage_staff_schedules()
        elif choice == '6':
            staff_performance()
        elif choice == '7':
            payroll_calculations()
        elif choice == '8':
            staff_analytics()
        elif choice == '9':
            return
        else:
            print("Invalid choice. Please try again.")

def view_all_staff():
    """View all staff members"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\nFilter options:")
        print("1. All staff")
        print("2. Active staff only")
        print("3. By role")
        print("4. By performance score")

        filter_choice = input("Choose filter (1-4): ")

        if filter_choice == '1':
            cursor.execute('SELECT * FROM restaurant_staff ORDER BY name')
        elif filter_choice == '2':
            cursor.execute('SELECT * FROM restaurant_staff WHERE status = ? ORDER BY name', ('Active',))
        elif filter_choice == '3':
            role = input("Enter role (Manager/Chef/Server/Cashier/Kitchen/Cleaner): ")
            cursor.execute('SELECT * FROM restaurant_staff WHERE role = ? ORDER BY name', (role,))
        elif filter_choice == '4':
            cursor.execute('SELECT * FROM restaurant_staff ORDER BY performance_score DESC')
        else:
            cursor.execute('SELECT * FROM restaurant_staff ORDER BY name')

        staff = cursor.fetchall()

        if not staff:
            print("No staff found.")
            conn.close()
            return

        print(f"\n" + "="*120)
        print("STAFF MEMBERS")
        print("="*120)
        print(f"{'Staff ID':<10} {'Name':<20} {'Role':<12} {'Hourly Rate':<12} {'Email':<25} {'Performance':<12} {'Status':<8}")
        print("-"*120)

        for member in staff:
            performance = f"{member[10]:.1f}/10" if member[10] else "N/A"
            hourly_rate = f"£{member[3]:.2f}" if member[3] else "N/A"

            print(f"{member[0]:<10} {member[1]:<20} {member[2]:<12} {hourly_rate:<12} {member[4] or 'N/A':<25} {performance:<12} {member[7]:<8}")

        print("="*120)
        print(f"Total staff: {len(staff)}")

        # Staff summary by role
        cursor.execute('''
            SELECT role, COUNT(*) as count, AVG(hourly_rate) as avg_rate
            FROM restaurant_staff
            WHERE status = 'Active'
            GROUP BY role
        ''')

        role_summary = cursor.fetchall()
        print("\nStaff Summary by Role:")
        print("-"*40)
        for role, count, avg_rate in role_summary:
            rate_str = f"£{avg_rate:.2f}" if avg_rate else "N/A"
            print(f"{role}: {count} staff, Avg Rate: {rate_str}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in view_all_staff: {e}")
        print(f"An error occurred: {e}")

def add_new_staff():
    """Add new staff member"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to add staff.")
        return

    if not auth.check_permission('manage_staff'):
        print("You don't have permission to add staff.")
        return

    try:
        backup_before_operation('add_new_staff')

        print("\n" + "="*50)
        print("ADD NEW STAFF MEMBER")
        print("="*50)

        # Generate staff ID
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT MAX(staff_id) FROM restaurant_staff WHERE staff_id LIKE ?', ('STF%',))
        result = cursor.fetchone()[0]

        if result:
            number = int(result[3:]) + 1
            staff_id = f"STF{number:04d}"
        else:
            staff_id = "STF0001"

        # Get staff details
        name = input("Enter staff name: ").strip()
        if not name:
            print("Name is required.")
            conn.close()
            return

        print("\nRoles:")
        print("1. Manager")
        print("2. Chef")
        print("3. Server")
        print("4. Cashier")
        print("5. Kitchen Staff")
        print("6. Cleaner")
        print("7. Other")

        role_choice = input("Choose role (1-7): ")
        roles = {
            '1': 'Manager',
            '2': 'Chef',
            '3': 'Server',
            '4': 'Cashier',
            '5': 'Kitchen Staff',
            '6': 'Cleaner'
        }

        if role_choice == '7':
            role = input("Enter custom role: ").strip()
        else:
            role = roles.get(role_choice, 'Server')

        try:
            hourly_rate = float(input("Enter hourly rate (£): "))
            if hourly_rate < 0:
                raise ValueError
        except ValueError:
            print("Invalid hourly rate.")
            conn.close()
            return

        email = input("Enter email address: ").strip()
        if email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            print("Invalid email format.")
            conn.close()
            return

        phone = input("Enter phone number: ").strip()
        address = input("Enter address: ").strip()
        emergency_contact = input("Enter emergency contact: ").strip()

        hire_date = datetime.now().strftime('%Y-%m-%d')

        # Insert new staff member
        cursor.execute('''
            INSERT INTO restaurant_staff VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            staff_id, name, role, hourly_rate, email, phone, hire_date,
            'Active', emergency_contact, address, 0.0
        ))

        conn.commit()
        conn.close()

        print(f"\n✅ Staff member added successfully!")
        print(f"Staff ID: {staff_id}")
        print(f"Name: {name}")
        print(f"Role: {role}")
        print(f"Hourly Rate: £{hourly_rate:.2f}")
        print(f"Hire Date: {hire_date}")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'ADD_STAFF',
            'restaurant_staff',
            staff_id,
            None,
            {'name': name, 'role': role, 'hourly_rate': hourly_rate}
        )

    except Exception as e:
        logging.error(f"Error in add_new_staff: {e}")
        print(f"An error occurred: {e}")

def update_staff_info():
    """Update staff member information"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to update staff.")
        return

    if not auth.check_permission('manage_staff'):
        print("You don't have permission to update staff.")
        return

    try:
        backup_before_operation('update_staff_info')

        staff_id = input("Enter staff ID to update: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM restaurant_staff WHERE staff_id = ?', (staff_id,))
        staff = cursor.fetchone()

        if not staff:
            print("Staff member not found.")
            conn.close()
            return

        print(f"\nCurrent Staff Information:")
        print(f"1. Name: {staff[1]}")
        print(f"2. Role: {staff[2]}")
        print(f"3. Hourly Rate: £{staff[3]:.2f}")
        print(f"4. Email: {staff[4] or 'Not set'}")
        print(f"5. Phone: {staff[5] or 'Not set'}")
        print(f"6. Status: {staff[7]}")
        print(f"7. Performance Score: {staff[10]:.1f}/10")
        print("8. Cancel update")

        choice = input("Enter field number to update (1-8): ")

        if choice == '8':
            print("Update cancelled.")
            conn.close()
            return

        if choice == '1':
            new_name = input("Enter new name: ").strip()
            if new_name:
                cursor.execute('UPDATE restaurant_staff SET name = ? WHERE staff_id = ?',
                              (new_name, staff_id))
                print("Name updated successfully.")
        elif choice == '2':
            print("\nRoles:")
            print("1. Manager")
            print("2. Chef")
            print("3. Server")
            print("4. Cashier")
            print("5. Kitchen Staff")
            print("6. Cleaner")

            role_choice = input("Choose role (1-6): ")
            roles = {
                '1': 'Manager',
                '2': 'Chef',
                '3': 'Server',
                '4': 'Cashier',
                '5': 'Kitchen Staff',
                '6': 'Cleaner'
            }
            new_role = roles.get(role_choice)

            if new_role:
                cursor.execute('UPDATE restaurant_staff SET role = ? WHERE staff_id = ?',
                              (new_role, staff_id))
                print("Role updated successfully.")
            else:
                print("Invalid role choice.")
        elif choice == '3':
            try:
                new_rate = float(input("Enter new hourly rate: £"))
                cursor.execute('UPDATE restaurant_staff SET hourly_rate = ? WHERE staff_id = ?',
                              (new_rate, staff_id))
                print("Hourly rate updated successfully.")
            except ValueError:
                print("Invalid hourly rate.")
        elif choice == '4':
            new_email = input("Enter new email: ").strip()
            if new_email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', new_email):
                print("Invalid email format.")
            else:
                cursor.execute('UPDATE restaurant_staff SET email = ? WHERE staff_id = ?',
                              (new_email, staff_id))
                print("Email updated successfully.")
        elif choice == '5':
            new_phone = input("Enter new phone: ").strip()
            cursor.execute('UPDATE restaurant_staff SET phone = ? WHERE staff_id = ?',
                          (new_phone, staff_id))
            print("Phone updated successfully.")
        elif choice == '6':
            print("\nStatus options:")
            print("1. Active")
            print("2. Inactive")
            print("3. On Leave")
            print("4. Terminated")

            status_choice = input("Choose status (1-4): ")
            statuses = {
                '1': 'Active',
                '2': 'Inactive',
                '3': 'On Leave',
                '4': 'Terminated'
            }
            new_status = statuses.get(status_choice)

            if new_status:
                cursor.execute('UPDATE restaurant_staff SET status = ? WHERE staff_id = ?',
                              (new_status, staff_id))
                print("Status updated successfully.")
            else:
                print("Invalid status choice.")
        elif choice == '7':
            try:
                new_score = float(input("Enter performance score (0-10): "))
                if 0 <= new_score <= 10:
                    cursor.execute('UPDATE restaurant_staff SET performance_score = ? WHERE staff_id = ?',
                                  (new_score, staff_id))
                    print("Performance score updated successfully.")
                else:
                    print("Score must be between 0 and 10.")
            except ValueError:
                print("Invalid score format.")

        conn.commit()
        conn.close()

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'UPDATE_STAFF',
            'restaurant_staff',
            staff_id,
            None,
            {'updated': True}
        )

    except Exception as e:
        logging.error(f"Error in update_staff_info: {e}")
        print(f"An error occurred: {e}")

def delete_staff():
    """Delete staff member"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to delete staff.")
        return

    if not auth.check_permission('manage_staff'):
        print("You don't have permission to delete staff.")
        return

    try:
        backup_before_operation('delete_staff')

        staff_id = input("Enter staff ID to delete: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT name, role FROM restaurant_staff WHERE staff_id = ?', (staff_id,))
        staff = cursor.fetchone()

        if not staff:
            print("Staff member not found.")
            conn.close()
            return

        print(f"Staff Member: {staff[0]} ({staff[1]})")
        confirm = input("Type 'DELETE' to confirm deletion: ")

        if confirm == 'DELETE':
            # Set status to terminated instead of deleting for audit purposes
            cursor.execute('UPDATE restaurant_staff SET status = ? WHERE staff_id = ?',
                          ('Terminated', staff_id))
            conn.commit()
            print(f"Staff member {staff[0]} terminated successfully.")

            # Log audit action
            log_audit_action(
                auth.current_user['id'],
                'TERMINATE_STAFF',
                'restaurant_staff',
                staff_id,
                {'name': staff[0], 'role': staff[1]},
                {'status': 'Terminated'}
            )
        else:
            print("Deletion cancelled.")

        conn.close()

    except Exception as e:
        logging.error(f"Error in delete_staff: {e}")
        print(f"An error occurred: {e}")

def manage_staff_schedules():
    """Manage staff schedules"""
    try:
        print("\n" + "="*50)
        print("STAFF SCHEDULES")
        print("="*50)

        print("\nOptions:")
        print("1. View schedules")
        print("2. Create schedule")
        print("3. Update schedule")
        print("4. Delete schedule")
        print("5. View schedule conflicts")
        print("6. Return to staff menu")

        choice = input("Choose an option (1-6): ")

        if choice == '1':
            view_staff_schedules()
        elif choice == '2':
            create_staff_schedule()
        elif choice == '3':
            update_staff_schedule()
        elif choice == '4':
            delete_staff_schedule()
        elif choice == '5':
            view_schedule_conflicts()
        elif choice == '6':
            return
        else:
            print("Invalid choice.")

    except Exception as e:
        logging.error(f"Error in manage_staff_schedules: {e}")
        print(f"An error occurred: {e}")

def view_staff_schedules():
    """View staff schedules"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\nFilter options:")
        print("1. Today's schedules")
        print("2. This week's schedules")
        print("3. By staff member")
        print("4. By date range")

        filter_choice = input("Choose filter (1-4): ")

        if filter_choice == '1':
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT ss.*, s.name, s.role
                FROM restaurant_staff_schedules ss
                JOIN restaurant_staff s ON ss.staff_id = s.staff_id
                WHERE ss.date = ?
                ORDER BY ss.start_time
            ''', (today,))
        elif filter_choice == '2':
            start_week = datetime.now().strftime('%Y-%m-%d')
            end_week = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT ss.*, s.name, s.role
                FROM restaurant_staff_schedules ss
                JOIN restaurant_staff s ON ss.staff_id = s.staff_id
                WHERE ss.date BETWEEN ? AND ?
                ORDER BY ss.date, ss.start_time
            ''', (start_week, end_week))
        elif filter_choice == '3':
            staff_id = input("Enter staff ID: ")
            cursor.execute('''
                SELECT ss.*, s.name, s.role
                FROM restaurant_staff_schedules ss
                JOIN restaurant_staff s ON ss.staff_id = s.staff_id
                WHERE ss.staff_id = ?
                ORDER BY ss.date, ss.start_time
            ''', (staff_id,))
        elif filter_choice == '4':
            start_date = input("Enter start date (YYYY-MM-DD): ")
            end_date = input("Enter end date (YYYY-MM-DD): ")
            cursor.execute('''
                SELECT ss.*, s.name, s.role
                FROM restaurant_staff_schedules ss
                JOIN restaurant_staff s ON ss.staff_id = s.staff_id
                WHERE ss.date BETWEEN ? AND ?
                ORDER BY ss.date, ss.start_time
            ''', (start_date, end_date))

        schedules = cursor.fetchall()

        if not schedules:
            print("No schedules found.")
            conn.close()
            return

        print(f"\n" + "="*120)
        print("STAFF SCHEDULES")
        print("="*120)
        print(f"{'Schedule ID':<15} {'Date':<12} {'Staff':<20} {'Role':<12} {'Start':<8} {'End':<8} {'Status':<10}")
        print("-"*120)

        for schedule in schedules:
            print(f"{schedule[0]:<15} {schedule[2]:<12} {schedule[10]:<20} {schedule[11]:<12} {schedule[3]:<8} {schedule[4]:<8} {schedule[6]:<10}")

        print("="*120)
        print(f"Total schedules: {len(schedules)}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in view_staff_schedules: {e}")
        print(f"An error occurred: {e}")

def supplier_performance():
    """View supplier performance metrics - FIXED"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\n" + "="*80)
        print("SUPPLIER PERFORMANCE METRICS")
        print("="*80)

        # Overall supplier statistics
        cursor.execute('''
            SELECT
                COUNT(*) as total_suppliers,
                COUNT(CASE WHEN status = 'Active' THEN 1 END) as active_suppliers,
                AVG(rating) as avg_rating
            FROM restaurant_suppliers
        ''')

        stats = cursor.fetchone()

        print("Supplier Overview:")
        print("-"*30)
        print(f"Total Suppliers: {stats[0]}")
        print(f"Active Suppliers: {stats[1]}")
        print(f"Average Rating: {stats[2]:.2f}/5" if stats[2] else "Average Rating: N/A")

        # Top performing suppliers
        cursor.execute('''
            SELECT s.name, s.rating, COUNT(po.po_id) as order_count,
                   SUM(po.total_amount) as total_value,
                   AVG(CASE WHEN po.actual_delivery IS NOT NULL AND po.expected_delivery IS NOT NULL
                       THEN julianday(po.actual_delivery) - julianday(po.expected_delivery)
                       ELSE NULL END) as avg_delay
            FROM restaurant_suppliers s
            LEFT JOIN restaurant_purchase_orders po ON s.supplier_id = po.supplier_id
            WHERE s.status = 'Active'
            GROUP BY s.supplier_id, s.name, s.rating
            ORDER BY s.rating DESC, total_value DESC
            LIMIT 10
        ''')

        top_suppliers = cursor.fetchall()

        if top_suppliers:
            print(f"\nTop Performing Suppliers:")
            print("-"*100)
            print(f"{'Supplier':<25} {'Rating':<8} {'Orders':<8} {'Total Value':<15} {'Avg Delay':<12}")
            print("-"*100)

            for supplier, rating, orders, value, delay in top_suppliers:
                rating_str = f"{rating:.1f}/5" if rating else "N/A"
                value_str = f"£{value:.2f}" if value else "£0.00"
                delay_str = f"{delay:.1f} days" if delay is not None else "N/A"

                print(f"{supplier:<25} {rating_str:<8} {orders:<8} {value_str:<15} {delay_str:<12}")

        # Delivery performance by supplier
        cursor.execute('''
            SELECT s.name,
                   COUNT(po.po_id) as total_orders,
                   COUNT(CASE WHEN po.actual_delivery <= po.expected_delivery THEN 1 END) as on_time,
                   COUNT(CASE WHEN po.actual_delivery > po.expected_delivery THEN 1 END) as late
            FROM restaurant_suppliers s
            JOIN restaurant_purchase_orders po ON s.supplier_id = po.supplier_id
            WHERE po.actual_delivery IS NOT NULL AND po.expected_delivery IS NOT NULL
            GROUP BY s.supplier_id, s.name
            HAVING total_orders >= 3
            ORDER BY (CAST(on_time AS FLOAT) / total_orders) DESC
        ''')

        delivery_performance = cursor.fetchall()

        if delivery_performance:
            print(f"\nDelivery Performance (min 3 orders):")
            print("-"*70)
            print(f"{'Supplier':<25} {'Total':<8} {'On Time':<10} {'Late':<8} {'On Time %':<10}")
            print("-"*70)

            for supplier, total, on_time, late in delivery_performance:
                on_time_pct = (on_time / total * 100) if total > 0 else 0
                print(f"{supplier:<25} {total:<8} {on_time:<10} {late:<8} {on_time_pct:<9.1f}%")

        conn.close()

    except Exception as e:
        logging.error(f"Error in supplier_performance: {e}")
        print(f"An error occurred: {e}")

def create_staff_schedule():
    """Create new staff schedule - FIXED"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to create schedules.")
        return

    if not auth.check_permission('manage_staff'):
        print("You don't have permission to create schedules.")
        return

    try:
        backup_before_operation('create_staff_schedule')

        print("\n" + "="*50)
        print("CREATE STAFF SCHEDULE")
        print("="*50)

        # Get active staff list
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT staff_id, name, role FROM restaurant_staff WHERE status = ?', ('Active',))
        staff_list = cursor.fetchall()

        if not staff_list:
            print("No active staff found.")
            conn.close()
            return

        print("Active Staff:")
        for i, staff in enumerate(staff_list, 1):
            print(f"{i}. {staff[1]} ({staff[2]}) - ID: {staff[0]}")

        try:
            staff_choice = int(input("Choose staff member (enter number): ")) - 1
            if staff_choice < 0 or staff_choice >= len(staff_list):
                raise ValueError
            selected_staff = staff_list[staff_choice]
        except ValueError:
            print("Invalid staff choice.")
            conn.close()
            return

        # Get schedule details
        schedule_date = input("Enter schedule date (YYYY-MM-DD): ")
        try:
            datetime.strptime(schedule_date, '%Y-%m-%d')
        except ValueError:
            print("Invalid date format.")
            conn.close()
            return

        start_time = input("Enter start time (HH:MM): ")
        try:
            datetime.strptime(start_time, '%H:%M')
        except ValueError:
            print("Invalid time format.")
            conn.close()
            return

        end_time = input("Enter end time (HH:MM): ")
        try:
            datetime.strptime(end_time, '%H:%M')
        except ValueError:
            print("Invalid time format.")
            conn.close()
            return

        try:
            break_duration = int(input("Enter break duration in minutes (default 30): ") or "30")
            if break_duration < 0:
                raise ValueError
        except ValueError:
            print("Invalid break duration.")
            conn.close()
            return

        # Generate schedule ID
        schedule_id = f"SCH{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"

        # Check for conflicts
        cursor.execute('''
            SELECT schedule_id FROM restaurant_staff_schedules
            WHERE staff_id = ? AND date = ? AND status != 'Cancelled'
            AND ((start_time <= ? AND end_time > ?) OR (start_time < ? AND end_time >= ?))
        ''', (selected_staff[0], schedule_date, start_time, start_time, end_time, end_time))

        if cursor.fetchone():
            print("Schedule conflict detected for this staff member.")
            confirm = input("Continue anyway? (y/n): ")
            if confirm.lower() != 'y':
                conn.close()
                return

        # Create schedule
        cursor.execute('''
            INSERT INTO restaurant_staff_schedules VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            schedule_id, selected_staff[0], schedule_date, start_time, end_time,
            break_duration, 'Scheduled', None, None
        ))

        conn.commit()
        conn.close()

        print(f"\n✅ Schedule created successfully!")
        print(f"Schedule ID: {schedule_id}")
        print(f"Staff: {selected_staff[1]} ({selected_staff[2]})")
        print(f"Date: {schedule_date}")
        print(f"Time: {start_time} - {end_time}")
        print(f"Break: {break_duration} minutes")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'CREATE_SCHEDULE',
            'restaurant_staff_schedules',
            schedule_id,
            None,
            {'staff_id': selected_staff[0], 'date': schedule_date, 'start_time': start_time}
        )

    except Exception as e:
        logging.error(f"Error in create_staff_schedule: {e}")
        print(f"An error occurred: {e}")

def update_staff_schedule():
    """Update existing staff schedule - FIXED"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to update schedules.")
        return

    if not auth.check_permission('manage_staff'):
        print("You don't have permission to update schedules.")
        return

    try:
        backup_before_operation('update_staff_schedule')

        schedule_id = input("Enter schedule ID to update: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT ss.*, s.name as staff_name
            FROM restaurant_staff_schedules ss
            JOIN restaurant_staff s ON ss.staff_id = s.staff_id
            WHERE ss.schedule_id = ?
        ''', (schedule_id,))

        schedule = cursor.fetchone()

        if not schedule:
            print("Schedule not found.")
            conn.close()
            return

        print(f"\nCurrent Schedule:")
        print(f"Staff: {schedule[9]}")
        print(f"Date: {schedule[2]}")
        print(f"Time: {schedule[3]} - {schedule[4]}")
        print(f"Status: {schedule[6]}")

        print("\nWhat would you like to update?")
        print("1. Start time")
        print("2. End time")
        print("3. Status")
        print("4. Mark actual times")
        print("5. Cancel")

        choice = input("Choose option (1-5): ")

        if choice == '1':
            new_start = input("Enter new start time (HH:MM): ")
            try:
                datetime.strptime(new_start, '%H:%M')
                cursor.execute('UPDATE restaurant_staff_schedules SET start_time = ? WHERE schedule_id = ?',
                              (new_start, schedule_id))
                print("Start time updated.")
            except ValueError:
                print("Invalid time format.")
        elif choice == '2':
            new_end = input("Enter new end time (HH:MM): ")
            try:
                datetime.strptime(new_end, '%H:%M')
                cursor.execute('UPDATE restaurant_staff_schedules SET end_time = ? WHERE schedule_id = ?',
                              (new_end, schedule_id))
                print("End time updated.")
            except ValueError:
                print("Invalid time format.")
        elif choice == '3':
            print("Status options: Scheduled, In Progress, Completed, Cancelled")
            new_status = input("Enter new status: ")
            cursor.execute('UPDATE restaurant_staff_schedules SET status = ? WHERE schedule_id = ?',
                          (new_status, schedule_id))
            print("Status updated.")
        elif choice == '4':
            actual_start = input("Enter actual start time (HH:MM:SS): ")
            actual_end = input("Enter actual end time (HH:MM:SS): ")
            cursor.execute('''
                UPDATE restaurant_staff_schedules
                SET actual_start = ?, actual_end = ?
                WHERE schedule_id = ?
            ''', (actual_start, actual_end, schedule_id))
            print("Actual times recorded.")
        elif choice == '5':
            print("Update cancelled.")
            conn.close()
            return

        conn.commit()
        conn.close()

        print("✅ Schedule updated successfully!")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'UPDATE_SCHEDULE',
            'restaurant_staff_schedules',
            schedule_id,
            None,
            {'action': choice}
        )

    except Exception as e:
        logging.error(f"Error in update_staff_schedule: {e}")
        print(f"An error occurred: {e}")

def delete_staff_schedule():
    """Delete staff schedule - FIXED"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to delete schedules.")
        return

    if not auth.check_permission('manage_staff'):
        print("You don't have permission to delete schedules.")
        return

    try:
        backup_before_operation('delete_staff_schedule')

        schedule_id = input("Enter schedule ID to delete: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT ss.*, s.name as staff_name
            FROM restaurant_staff_schedules ss
            JOIN restaurant_staff s ON ss.staff_id = s.staff_id
            WHERE ss.schedule_id = ?
        ''', (schedule_id,))

        schedule = cursor.fetchone()

        if not schedule:
            print("Schedule not found.")
            conn.close()
            return

        print(f"Schedule to delete:")
        print(f"Staff: {schedule[9]}")
        print(f"Date: {schedule[2]}")
        print(f"Time: {schedule[3]} - {schedule[4]}")

        confirm = input("Type 'DELETE' to confirm: ")

        if confirm == 'DELETE':
            cursor.execute('DELETE FROM restaurant_staff_schedules WHERE schedule_id = ?', (schedule_id,))
            conn.commit()
            print("✅ Schedule deleted successfully!")

            # Log audit action
            log_audit_action(
                auth.current_user['id'],
                'DELETE_SCHEDULE',
                'restaurant_staff_schedules',
                schedule_id,
                {'staff_name': schedule[9], 'date': schedule[2]},
                None
            )
        else:
            print("Deletion cancelled.")

        conn.close()

    except Exception as e:
        logging.error(f"Error in delete_staff_schedule: {e}")
        print(f"An error occurred: {e}")

def view_schedule_conflicts():
    """View schedule conflicts - FIXED"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\n" + "="*80)
        print("SCHEDULE CONFLICTS")
        print("="*80)

        # Find overlapping schedules for the same staff member
        cursor.execute('''
            SELECT DISTINCT s1.staff_id, s.name, s1.date,
                   s1.start_time, s1.end_time, s1.schedule_id,
                   s2.start_time, s2.end_time, s2.schedule_id
            FROM restaurant_staff_schedules s1
            JOIN restaurant_staff_schedules s2 ON s1.staff_id = s2.staff_id
                AND s1.date = s2.date
                AND s1.schedule_id != s2.schedule_id
            JOIN restaurant_staff s ON s1.staff_id = s.staff_id
            WHERE s1.status != 'Cancelled' AND s2.status != 'Cancelled'
                AND ((s1.start_time <= s2.start_time AND s1.end_time > s2.start_time)
                     OR (s1.start_time < s2.end_time AND s1.end_time >= s2.end_time))
            ORDER BY s1.date, s1.start_time
        ''')

        conflicts = cursor.fetchall()

        if not conflicts:
            print("✅ No schedule conflicts found!")
            conn.close()
            return

        print(f"Found {len(conflicts)} schedule conflicts:")
        print("-"*80)

        for conflict in conflicts:
            print(f"Staff: {conflict[1]} ({conflict[0]})")
            print(f"Date: {conflict[2]}")
            print(f"Conflict between:")
            print(f"  Schedule 1: {conflict[3]} - {conflict[4]} (ID: {conflict[5]})")
            print(f"  Schedule 2: {conflict[6]} - {conflict[7]} (ID: {conflict[8]})")
            print("-"*40)

        conn.close()

    except Exception as e:
        logging.error(f"Error in view_schedule_conflicts: {e}")
        print(f"An error occurred: {e}")

def staff_performance():
    """Manage staff performance"""
    try:
        print("\n" + "="*50)
        print("STAFF PERFORMANCE")
        print("="*50)

        print("\nOptions:")
        print("1. View performance rankings")
        print("2. Update performance scores")
        print("3. Performance analytics")
        print("4. Export performance report")
        print("5. Return to staff menu")

        choice = input("Choose an option (1-5): ")

        if choice == '1':
            view_performance_rankings()
        elif choice == '2':
            update_performance_scores()
        elif choice == '3':
            performance_analytics()
        elif choice == '4':
            export_performance_report()
        elif choice == '5':
            return
        else:
            print("Invalid choice.")

    except Exception as e:
        logging.error(f"Error in staff_performance: {e}")
        print(f"An error occurred: {e}")

def view_performance_rankings():
    """View staff performance rankings"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT staff_id, name, role, performance_score, hire_date
            FROM restaurant_staff
            WHERE status = 'Active'
            ORDER BY performance_score DESC
        ''')

        staff = cursor.fetchall()

        if not staff:
            print("No active staff found.")
            conn.close()
            return

        print(f"\n" + "="*80)
        print("STAFF PERFORMANCE RANKINGS")
        print("="*80)
        print(f"{'Rank':<6} {'Name':<20} {'Role':<15} {'Score':<8} {'Hire Date':<12}")
        print("-"*80)

        for i, member in enumerate(staff, 1):
            score = f"{member[3]:.1f}/10" if member[3] else "N/A"
            hire_date = member[4][:10] if member[4] else 'N/A'
            print(f"{i:<6} {member[1]:<20} {member[2]:<15} {score:<8} {hire_date:<12}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in view_performance_rankings: {e}")
        print(f"An error occurred: {e}")

def update_performance_scores():
    """Update staff performance scores - FIXED"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to update performance scores.")
        return

    if not auth.check_permission('manage_staff'):
        print("You don't have permission to update performance scores.")
        return

    try:
        backup_before_operation('update_performance_scores')

        staff_id = input("Enter staff ID: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT name, performance_score FROM restaurant_staff WHERE staff_id = ?', (staff_id,))
        staff = cursor.fetchone()

        if not staff:
            print("Staff member not found.")
            conn.close()
            return

        print(f"Staff: {staff[0]}")
        print(f"Current performance score: {staff[1]:.1f}/10")

        try:
            new_score = float(input("Enter new performance score (0-10): "))
            if not 0 <= new_score <= 10:
                print("Score must be between 0 and 10.")
                conn.close()
                return
        except ValueError:
            print("Invalid score format.")
            conn.close()
            return

        notes = input("Enter performance notes (optional): ").strip()

        cursor.execute('UPDATE restaurant_staff SET performance_score = ? WHERE staff_id = ?',
                      (new_score, staff_id))

        conn.commit()
        conn.close()

        print(f"✅ Performance score updated!")
        print(f"Previous score: {staff[1]:.1f}/10")
        print(f"New score: {new_score:.1f}/10")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'UPDATE_PERFORMANCE_SCORE',
            'restaurant_staff',
            staff_id,
            {'old_score': staff[1]},
            {'new_score': new_score, 'notes': notes}
        )

    except Exception as e:
        logging.error(f"Error in update_performance_scores: {e}")
        print(f"An error occurred: {e}")

def export_performance_report():
    """Export performance report - FIXED"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT staff_id, name, role, performance_score, hire_date,
                   hourly_rate, status
            FROM restaurant_staff
            ORDER BY performance_score DESC
        ''')

        staff_data = cursor.fetchall()

        if not staff_data:
            print("No staff data found.")
            conn.close()
            return

        filename = f"staff_performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            # Header
            writer.writerow([
                'Staff ID', 'Name', 'Role', 'Performance Score', 'Hire Date',
                'Hourly Rate', 'Status'
            ])

            # Data
            for staff in staff_data:
                writer.writerow([
                    staff[0], staff[1], staff[2],
                    f"{staff[3]:.1f}" if staff[3] else "N/A",
                    staff[4] or "N/A",
                    f"£{staff[5]:.2f}" if staff[5] else "N/A",
                    staff[6]
                ])

        conn.close()
        print(f"Performance report exported to {filename}")

    except Exception as e:
        logging.error(f"Error in export_performance_report: {e}")
        print(f"An error occurred: {e}")

def analyze_query_performance():
    """Analyze query performance - FIXED"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to analyze query performance.")
        return

    if not auth.check_permission('admin'):
        print("You don't have permission to analyze query performance.")
        return

    try:
        print("\n" + "="*60)
        print("QUERY PERFORMANCE ANALYSIS")
        print("="*60)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Test common queries and measure execution time
        test_queries = [
            ("Daily Sales Query", '''
                SELECT COUNT(*), SUM(total_amount)
                FROM orders
                WHERE DATE(order_date) = date('now') AND order_status = 'Completed'
            '''),
            ("Menu Items Lookup", '''
                SELECT * FROM menu_items WHERE available = 1 ORDER BY category, name
            '''),
            ("Customer Orders", '''
                SELECT o.*, c.name
                FROM orders o
                LEFT JOIN restaurant_customers c ON o.customer_id = c.customer_id
                ORDER BY o.order_date DESC LIMIT 50
            '''),
            ("Inventory Low Stock", '''
                SELECT * FROM restaurant_inventory
                WHERE quantity <= reorder_level
            '''),
            ("Staff Schedules", '''
                SELECT ss.*, s.name
                FROM restaurant_staff_schedules ss
                JOIN restaurant_staff s ON ss.staff_id = s.staff_id
                WHERE ss.date = date('now')
            ''')
        ]

        print("Testing query performance...")
        print("-"*60)
        print(f"{'Query':<25} {'Execution Time':<15} {'Rows':<8} {'Status':<10}")
        print("-"*60)

        for query_name, query_sql in test_queries:
            try:
                start_time = time.time()
                cursor.execute(query_sql)
                results = cursor.fetchall()
                end_time = time.time()

                execution_time = (end_time - start_time) * 1000  # Convert to milliseconds
                row_count = len(results)

                if execution_time < 100:
                    status = "✅ Fast"
                elif execution_time < 500:
                    status = "🟡 OK"
                else:
                    status = "🔴 Slow"

                print(f"{query_name[:24]:<25} {execution_time:<14.2f}ms {row_count:<8} {status:<10}")

            except Exception as e:
                print(f"{query_name[:24]:<25} {'ERROR':<15} {0:<8} {'❌ Failed':<10}")
                logging.error(f"Query failed: {query_name} - {e}")

        # Check table sizes
        print(f"\nTable Size Analysis:")
        print("-"*40)
        print(f"{'Table':<25} {'Row Count':<12}")
        print("-"*40)

        tables = [
            'menu_items', 'orders', 'restaurant_customers',
            'restaurant_tables', 'restaurant_staff', 'restaurant_inventory',
            'restaurant_suppliers', 'restaurant_audit_logs'
        ]

        for table in tables:
            try:
                safe_table = validate_identifier(table, "table")
                cursor.execute('SELECT COUNT(*) FROM [' + safe_table + ']')
                count = cursor.fetchone()[0]
                print(f"{table:<25} {count:<12,}")
            except Exception:
                print(f"{table:<25} {'ERROR':<12}")

        # Index analysis
        print(f"\nIndex Analysis:")
        print("-"*40)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
        indexes = cursor.fetchall()

        print(f"Custom indexes found: {len(indexes)}")
        for index in indexes:
            print(f"  - {index[0]}")

        # Recommendations
        print(f"\nPerformance Recommendations:")
        print("-"*40)

        # Check for large tables without proper indexing
        cursor.execute('SELECT COUNT(*) FROM orders')
        order_count = cursor.fetchone()[0]

        if order_count > 1000:
            print("• Consider archiving old completed orders")

        cursor.execute('SELECT COUNT(*) FROM restaurant_audit_logs')
        log_count = cursor.fetchone()[0]

        if log_count > 10000:
            print("• Consider purging old audit logs")

        print("• Run VACUUM regularly to optimize database")
        print("• Consider adding indexes for frequently queried columns")
        print("• Monitor query performance during peak hours")

        conn.close()

    except Exception as e:
        logging.error(f"Error in analyze_query_performance: {e}")
        print(f"An error occurred: {e}")
