from education_system.university_system.infrastructure.auth import UserAuth, display_auth_menu
from education_system.university_system.infrastructure.database.data_backup import display_backup_menu, backup_before_operation
from education_system.university_system.infrastructure.email import send_confirmation_email
from education_system.university_system.infrastructure.email.template_utils import render_template
from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager
from education_system.university_system.modules.domain.commerce.services.restaurant.operations.audit import log_audit_action
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
from education_system.university_system.infrastructure.logging.log_config import configure_logging
from education_system.university_system.modules.domain.commerce.services.restaurant.operations.connection import get_db_connection

# Configure logging
logger = configure_logging(name=__name__)
warnings.filterwarnings('ignore')

# CONSOLIDATED DATABASE FILE - Using the same database as main system
from education_system.university_system.core.paths import DEFAULT_DB_PATH
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


def create_customer():
    """Create a new customer profile"""
    global auth

    try:
        if not auth or not auth.current_user:
            print("You must be logged in to create customers.")
            return

        if not auth.check_permission('manage_customers'):
            print("You don't have permission to create customers.")
            return

        backup_before_operation('create_customer')
        conn = get_db_connection()
        cursor = conn.cursor()

        # Generate customer ID
        customer_prefix = "CUST"
        cursor.execute('SELECT MAX(customer_id) FROM restaurant_customers WHERE customer_id LIKE ?', (f'{customer_prefix}%',))
        result = cursor.fetchone()[0]

        if result:
            try:
                number = int(result[len(customer_prefix):]) + 1
            except ValueError:
                number = 1
        else:
            number = 1

        customer_id = f"{customer_prefix}{number:06d}"

        # Get customer details
        print("\n" + "="*50)
        print("CREATE NEW CUSTOMER")
        print("="*50)

        name = input("Enter customer name: ").strip()
        if not name:
            print("Customer name is required.")
            conn.close()
            return

        email = input("Enter email address: ").strip()
        if email:
            # Validate email format
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                print("Invalid email format.")
                conn.close()
                return

            # Check if email already exists
            cursor.execute('SELECT customer_id FROM restaurant_customers WHERE email = ?', (email,))
            if cursor.fetchone():
                print("Email already exists in the system.")
                conn.close()
                return

        phone = input("Enter phone number: ").strip()

        # Dietary restrictions
        print("\nCommon dietary restrictions:")
        print("1. None")
        print("2. Vegetarian")
        print("3. Vegan")
        print("4. Gluten-free")
        print("5. Dairy-free")
        print("6. Nut allergies")
        print("7. Custom")

        restriction_choice = input("Choose dietary restrictions (1-7): ")
        restrictions_map = {
            '1': 'None',
            '2': 'Vegetarian',
            '3': 'Vegan',
            '4': 'Gluten-free',
            '5': 'Dairy-free',
            '6': 'Nut allergies'
        }

        if restriction_choice in restrictions_map:
            dietary_restrictions = restrictions_map[restriction_choice]
        elif restriction_choice == '7':
            dietary_restrictions = input("Enter custom dietary restrictions: ").strip()
        else:
            dietary_restrictions = 'None'

        # Birthday (optional)
        birthday = input("Enter birthday (YYYY-MM-DD) or press Enter to skip: ").strip()
        if birthday:
            try:
                datetime.strptime(birthday, '%Y-%m-%d')
            except ValueError:
                print("Invalid date format. Birthday not set.")
                birthday = None

        address = input("Enter address (optional): ").strip()
        emergency_contact = input("Enter emergency contact (optional): ").strip()

        # Create customer record
        registration_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            INSERT INTO restaurant_customers VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            customer_id, name, email, phone, dietary_restrictions, 0, 'Bronze',
            birthday, registration_date, None, 0, 0, None, address,
            emergency_contact, None
        ))

        conn.commit()
        conn.close()

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'CREATE_CUSTOMER',
            'restaurant_customers',
            customer_id,
            None,
            {'name': name, 'email': email, 'phone': phone}
        )

        print(f"\n✅ Customer created successfully!")
        print(f"Customer ID: {customer_id}")
        print(f"Name: {name}")
        print(f"Email: {email}")
        print(f"Phone: {phone}")
        print(f"Dietary Restrictions: {dietary_restrictions}")
        print(f"Loyalty Tier: Bronze")

        # Send welcome email if email provided
        if email:
            try:
                subject, message = render_template("restaurant_customer_welcome", {
                    "name": name,
                    "customer_id": customer_id
                })
                if subject and message:
                    send_confirmation_email(email, subject, message)
                    print("Welcome email sent successfully.")
                else:
                    print("Could not load email template.")
            except Exception as e:
                print(f"Could not send welcome email: {e}")

    except sqlite3.Error as e:
        logging.error(f"Database error in create_customer: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Error in create_customer: {e}")
        print(f"An error occurred: {e}")

def view_customers():
    """View customer profiles with various filters"""
    global auth

    try:
        if not auth or not auth.current_user:
            print("You must be logged in to view customers.")
            return

        conn = get_db_connection()
        cursor = conn.cursor()

        print("\n" + "="*50)
        print("CUSTOMER MANAGEMENT")
        print("="*50)

        print("\nView Options:")
        print("1. View all customers")
        print("2. Search by name")
        print("3. Search by email")
        print("4. View by loyalty tier")
        print("5. View recent customers")
        print("6. View customers with birthdays this month")

        choice = input("Choose an option (1-6): ")

        if choice == '1':
            cursor.execute('SELECT * FROM restaurant_customers ORDER BY registration_date DESC')
        elif choice == '2':
            search_name = input("Enter name to search: ")
            cursor.execute('SELECT * FROM restaurant_customers WHERE name LIKE ? ORDER BY name', (f'%{search_name}%',))
        elif choice == '3':
            search_email = input("Enter email to search: ")
            cursor.execute('SELECT * FROM restaurant_customers WHERE email LIKE ? ORDER BY email', (f'%{search_email}%',))
        elif choice == '4':
            print("\nLoyalty Tiers:")
            print("1. Bronze")
            print("2. Silver")
            print("3. Gold")
            print("4. Platinum")

            tier_choice = input("Choose tier (1-4): ")
            tiers = {'1': 'Bronze', '2': 'Silver', '3': 'Gold', '4': 'Platinum'}
            tier = tiers.get(tier_choice, 'Bronze')

            cursor.execute('SELECT * FROM restaurant_customers WHERE loyalty_tier = ? ORDER BY loyalty_points DESC', (tier,))
        elif choice == '5':
            cursor.execute('''
                SELECT * FROM restaurant_customers
                WHERE last_visit >= date('now', '-30 days')
                ORDER BY last_visit DESC
            ''')
        elif choice == '6':
            current_month = datetime.now().strftime('%m')
            cursor.execute('''
                SELECT * FROM restaurant_customers
                WHERE substr(birthday, 6, 2) = ?
                ORDER BY birthday
            ''', (current_month,))
        else:
            cursor.execute('SELECT * FROM restaurant_customers ORDER BY registration_date DESC')

        customers = cursor.fetchall()

        if not customers:
            print("No customers found matching the criteria.")
            conn.close()
            return

        # Display customers in a formatted table
        print("\n" + "="*120)
        print(f"{'ID':<12} {'Name':<20} {'Email':<25} {'Phone':<15} {'Tier':<8} {'Points':<8} {'Visits':<7} {'Last Visit':<12}")
        print("-"*120)

        for customer in customers:
            last_visit = customer[9][:10] if customer[9] else 'Never'
            print(f"{customer[0]:<12} {customer[1]:<20} {customer[2] or 'N/A':<25} {customer[3] or 'N/A':<15} {customer[6]:<8} {customer[5]:<8} {customer[11]:<7} {last_visit:<12}")

        print("="*120)
        print(f"Total customers: {len(customers)}")

        # Option to view detailed customer info
        customer_id = input("\nEnter customer ID to view details (or press Enter to return): ")
        if customer_id:
            view_customer_details(customer_id)

        conn.close()

    except sqlite3.Error as e:
        logging.error(f"Database error in view_customers: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Error in view_customers: {e}")
        print(f"An error occurred: {e}")

def view_customer_details(customer_id):
    """View detailed information about a specific customer"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get customer information
        cursor.execute('SELECT * FROM restaurant_customers WHERE customer_id = ?', (customer_id,))
        customer = cursor.fetchone()

        if not customer:
            print("Customer not found.")
            conn.close()
            return

        print("\n" + "="*60)
        print(f"CUSTOMER DETAILS: {customer[1]}")
        print("="*60)

        print(f"Customer ID: {customer[0]}")
        print(f"Name: {customer[1]}")
        print(f"Email: {customer[2] or 'Not provided'}")
        print(f"Phone: {customer[3] or 'Not provided'}")
        print(f"Dietary Restrictions: {customer[4]}")
        print(f"Loyalty Points: {customer[5]}")
        print(f"Loyalty Tier: {customer[6]}")
        print(f"Birthday: {customer[7] or 'Not provided'}")
        print(f"Registration Date: {customer[8]}")
        print(f"Last Visit: {customer[9] or 'Never'}")
        print(f"Total Spent: £{customer[10]:.2f}")
        print(f"Visit Count: {customer[11]}")
        print(f"Address: {customer[13] or 'Not provided'}")
        print(f"Emergency Contact: {customer[14] or 'Not provided'}")

        # Get order history
        cursor.execute('''
            SELECT order_id, order_date, total_amount, order_status
            FROM orders
            WHERE customer_id = ?
            ORDER BY order_date DESC
            LIMIT 10
        ''', (customer_id,))

        orders = cursor.fetchall()

        if orders:
            print(f"\nRecent Orders (Last 10):")
            print("-"*60)
            print(f"{'Order ID':<15} {'Date':<12} {'Amount':<10} {'Status':<10}")
            print("-"*60)

            for order in orders:
                order_date = order[1][:10] if order[1] else 'N/A'
                print(f"{order[0]:<15} {order_date:<12} £{order[2]:<9.2f} {order[3]:<10}")

        # Get favorite items
        cursor.execute('''
            SELECT mi.name, cf.frequency, cf.last_ordered
            FROM restaurant_customer_favorites cf
            JOIN menu_items mi ON cf.item_id = mi.item_id
            WHERE cf.customer_id = ?
            ORDER BY cf.frequency DESC
            LIMIT 5
        ''', (customer_id,))

        favorites = cursor.fetchall()

        if favorites:
            print(f"\nFavorite Items:")
            print("-"*60)
            print(f"{'Item':<30} {'Times Ordered':<15} {'Last Ordered':<15}")
            print("-"*60)

            for favorite in favorites:
                last_ordered = favorite[2][:10] if favorite[2] else 'N/A'
                print(f"{favorite[0]:<30} {favorite[1]:<15} {last_ordered:<15}")

        # Get recent feedback
        cursor.execute('''
            SELECT rating, feedback_text, feedback_date, mi.name as item_name
            FROM restaurant_customer_feedback cf
            LEFT JOIN menu_items mi ON cf.item_id = mi.item_id
            WHERE cf.customer_id = ?
            ORDER BY cf.feedback_date DESC
            LIMIT 5
        ''', (customer_id,))

        feedback = cursor.fetchall()

        if feedback:
            print(f"\nRecent Feedback:")
            print("-"*60)

            for fb in feedback:
                print(f"Rating: {'⭐' * fb[0]} ({fb[0]}/5)")
                if fb[3]:
                    print(f"Item: {fb[3]}")
                if fb[1]:
                    print(f"Comment: {fb[1]}")
                print(f"Date: {fb[2][:10] if fb[2] else 'N/A'}")
                print("-"*30)

        conn.close()

    except sqlite3.Error as e:
        logging.error(f"Database error in view_customer_details: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Error in view_customer_details: {e}")
        print(f"An error occurred: {e}")

def update_customer():
    """Update customer information"""
    global auth

    try:
        if not auth or not auth.current_user:
            print("You must be logged in to update customers.")
            return

        if not auth.check_permission('manage_customers'):
            print("You don't have permission to update customers.")
            return

        backup_before_operation('update_customer')

        customer_id = input("Enter customer ID to update: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if customer exists
        cursor.execute('SELECT * FROM restaurant_customers WHERE customer_id = ?', (customer_id,))
        customer = cursor.fetchone()

        if not customer:
            print("Customer not found.")
            conn.close()
            return

        # Store old values for audit
        old_values = {
            'name': customer[1],
            'email': customer[2],
            'phone': customer[3],
            'dietary_restrictions': customer[4],
            'loyalty_tier': customer[6]
        }

        print("\nCurrent Customer Information:")
        print(f"1. Name: {customer[1]}")
        print(f"2. Email: {customer[2] or 'Not set'}")
        print(f"3. Phone: {customer[3] or 'Not set'}")
        print(f"4. Dietary Restrictions: {customer[4]}")
        print(f"5. Loyalty Tier: {customer[6]}")
        print(f"6. Birthday: {customer[7] or 'Not set'}")
        print(f"7. Address: {customer[13] or 'Not set'}")
        print(f"8. Emergency Contact: {customer[14] or 'Not set'}")
        print("9. Cancel update")

        choice = input("\nEnter the number of the field to update (1-9): ")

        if choice == '9':
            print("Update cancelled.")
            conn.close()
            return

        new_values = old_values.copy()

        if choice == '1':
            new_name = input("Enter new name: ").strip()
            if new_name:
                cursor.execute('UPDATE restaurant_customers SET name = ? WHERE customer_id = ?', (new_name, customer_id))
                new_values['name'] = new_name
                print("Name updated successfully.")
        elif choice == '2':
            new_email = input("Enter new email: ").strip()
            if new_email:
                if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', new_email):
                    print("Invalid email format.")
                else:
                    cursor.execute('UPDATE restaurant_customers SET email = ? WHERE customer_id = ?', (new_email, customer_id))
                    new_values['email'] = new_email
                    print("Email updated successfully.")
        elif choice == '3':
            new_phone = input("Enter new phone: ").strip()
            cursor.execute('UPDATE restaurant_customers SET phone = ? WHERE customer_id = ?', (new_phone, customer_id))
            print("Phone updated successfully.")
        elif choice == '4':
            new_restrictions = input("Enter new dietary restrictions: ").strip()
            cursor.execute('UPDATE restaurant_customers SET dietary_restrictions = ? WHERE customer_id = ?', (new_restrictions, customer_id))
            new_values['dietary_restrictions'] = new_restrictions
            print("Dietary restrictions updated successfully.")
        elif choice == '5':
            print("\nLoyalty tiers:")
            print("1. Bronze")
            print("2. Silver")
            print("3. Gold")
            print("4. Platinum")
            tier_choice = input("Choose tier (1-4): ")
            tiers = {'1': 'Bronze', '2': 'Silver', '3': 'Gold', '4': 'Platinum'}
            new_tier = tiers.get(tier_choice)
            if new_tier:
                cursor.execute('UPDATE restaurant_customers SET loyalty_tier = ? WHERE customer_id = ?', (new_tier, customer_id))
                new_values['loyalty_tier'] = new_tier
                print("Loyalty tier updated successfully.")
            else:
                print("Invalid tier choice.")
        elif choice == '6':
            new_birthday = input("Enter new birthday (YYYY-MM-DD): ").strip()
            if new_birthday:
                try:
                    datetime.strptime(new_birthday, '%Y-%m-%d')
                    cursor.execute('UPDATE restaurant_customers SET birthday = ? WHERE customer_id = ?', (new_birthday, customer_id))
                    print("Birthday updated successfully.")
                except ValueError:
                    print("Invalid date format.")
        elif choice == '7':
            new_address = input("Enter new address: ").strip()
            cursor.execute('UPDATE restaurant_customers SET address = ? WHERE customer_id = ?', (new_address, customer_id))
            print("Address updated successfully.")
        elif choice == '8':
            new_emergency = input("Enter new emergency contact: ").strip()
            cursor.execute('UPDATE restaurant_customers SET emergency_contact = ? WHERE customer_id = ?', (new_emergency, customer_id))
            print("Emergency contact updated successfully.")

        conn.commit()
        conn.close()

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'UPDATE_CUSTOMER',
            'restaurant_customers',
            customer_id,
            old_values,
            new_values
        )

    except Exception as e:
        logging.error(f"Error in update_customer: {e}")
        print(f"An error occurred: {e}")

def manage_customer_feedback():
    """Manage customer feedback"""
    try:
        print("\n" + "="*50)
        print("CUSTOMER FEEDBACK")
        print("="*50)

        print("\nOptions:")
        print("1. View recent feedback")
        print("2. Respond to feedback")
        print("3. Feedback analytics")
        print("4. Export feedback report")
        print("5. Return to customer menu")

        choice = input("Choose an option (1-5): ")

        if choice == '1':
            view_recent_feedback()
        elif choice == '2':
            respond_to_feedback()
        elif choice == '3':
            feedback_analytics()
        elif choice == '4':
            export_feedback_report()
        elif choice == '5':
            return
        else:
            print("Invalid choice.")

    except Exception as e:
        logging.error(f"Error in manage_customer_feedback: {e}")
        print(f"An error occurred: {e}")

def view_recent_feedback():
    """View recent customer feedback"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT cf.*, c.name as customer_name, mi.name as item_name
            FROM restaurant_customer_feedback cf
            LEFT JOIN restaurant_customers c ON cf.customer_id = c.customer_id
            LEFT JOIN menu_items mi ON cf.item_id = mi.item_id
            ORDER BY cf.feedback_date DESC
            LIMIT 20
        ''')

        feedback = cursor.fetchall()

        if not feedback:
            print("No feedback found.")
            conn.close()
            return

        print(f"\n" + "="*100)
        print("RECENT CUSTOMER FEEDBACK")
        print("="*100)

        for fb in feedback:
            print(f"Date: {fb[6][:10] if fb[6] else 'N/A'}")
            print(f"Customer: {fb[11] if fb[11] else 'Anonymous'}")
            print(f"Rating: {'⭐' * fb[4]} ({fb[4]}/5)")
            if fb[12]:  # item_name
                print(f"Item: {fb[12]}")
            if fb[5]:  # feedback_text
                print(f"Feedback: {fb[5]}")
            if fb[7]:  # response_text
                print(f"Response: {fb[7]} (on {fb[8][:10] if fb[8] else 'N/A'})")
            print("-" * 50)

        conn.close()

    except Exception as e:
        logging.error(f"Error in view_recent_feedback: {e}")
        print(f"An error occurred: {e}")

def respond_to_feedback():
    """Respond to customer feedback"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to respond to feedback.")
        return

    try:
        feedback_id = input("Enter feedback ID: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT cf.*, c.name as customer_name
            FROM restaurant_customer_feedback cf
            LEFT JOIN restaurant_customers c ON cf.customer_id = c.customer_id
            WHERE cf.feedback_id = ?
        ''', (feedback_id,))

        feedback = cursor.fetchone()

        if not feedback:
            print("Feedback not found.")
            conn.close()
            return

        print(f"\nFeedback Details:")
        print(f"Customer: {feedback[11] if feedback[11] else 'Anonymous'}")
        print(f"Rating: {'⭐' * feedback[4]} ({feedback[4]}/5)")
        print(f"Feedback: {feedback[5] or 'No text provided'}")
        print(f"Date: {feedback[6][:10] if feedback[6] else 'N/A'}")

        if feedback[7]:
            print(f"Existing Response: {feedback[7]}")
            print(f"Response Date: {feedback[8][:10] if feedback[8] else 'N/A'}")

            overwrite = input("Overwrite existing response? (y/n): ")
            if overwrite.lower() != 'y':
                conn.close()
                return

        response_text = input("Enter your response: ").strip()

        if not response_text:
            print("Response cannot be empty.")
            conn.close()
            return

        # Update feedback with response
        response_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            UPDATE restaurant_customer_feedback
            SET response_text = ?, response_date = ?
            WHERE feedback_id = ?
        ''', (response_text, response_date, feedback_id))

        conn.commit()
        conn.close()

        print(f"✅ Response added successfully!")

        # Try to send email notification if customer has email
        if feedback[11]:  # customer exists
            try:
                conn2 = get_db_connection()
                cursor2 = conn2.cursor()
                cursor2.execute('SELECT email FROM restaurant_customers WHERE customer_id = ?', (feedback[1],))
                email_result = cursor2.fetchone()

                if email_result and email_result[0]:
                    send_confirmation_email(
                        email_result[0],
                        "Response to Your Feedback",
                        f"Dear {feedback[11]},\n\nThank you for your feedback. We have responded to your review.\n\nYour Rating: {feedback[4]}/5\nYour Feedback: {feedback[5]}\n\nOur Response: {response_text}\n\nBest regards,\nUniversity Restaurant Team"
                    )
                    print("Email notification sent to customer.")
                conn2.close()
            except Exception:
                print("Could not send email notification.")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'RESPOND_TO_FEEDBACK',
            'restaurant_customer_feedback',
            feedback_id,
            None,
            {'response_added': True}
        )

    except Exception as e:
        logging.error(f"Error in respond_to_feedback: {e}")
        print(f"An error occurred: {e}")

def export_feedback_report(days: int = 90, filename: str | None = None) -> str | None:
    """
    Export feedback from the last `days` days to a CSV.
    Returns the filename if exported, otherwise None.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()

        cursor.execute(
            """
            SELECT cf.feedback_id,
                   cf.feedback_date,
                   COALESCE(c.name, 'Anonymous') AS customer_name,
                   cf.rating,
                   COALESCE(cf.feedback_text, '') AS feedback_text,
                   COALESCE(cf.response_text, '') AS response_text,
                   cf.response_date,
                   COALESCE(mi.name, '') AS item_name,
                   COALESCE(cf.category, '') AS category
            FROM restaurant_customer_feedback cf
            LEFT JOIN restaurant_customers c ON cf.customer_id = c.customer_id
            LEFT JOIN menu_items mi ON cf.item_id = mi.item_id
            WHERE date(cf.feedback_date) >= ?
            ORDER BY cf.feedback_date DESC
            """,
            (cutoff,),
        )

        feedback = cursor.fetchall()

        if not feedback:
            print(f"No feedback found in the last {days} days.")
            return None

        if not filename:
            filename = f"feedback_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        with open(filename, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                "Feedback ID", "Date", "Customer", "Rating", "Feedback Text",
                "Response", "Response Date", "Item", "Category"
            ])

            for fb_id, fb_date, customer, rating, fb_text, resp_text, resp_date, item_name, category in feedback:
                # Normalize dates to YYYY-MM-DD if present
                fb_date_str = str(fb_date)[:10] if fb_date else "N/A"
                resp_date_str = str(resp_date)[:10] if resp_date else ""
                writer.writerow([
                    fb_id, fb_date_str, customer, rating, fb_text, resp_text, resp_date_str, item_name, category
                ])

        print(f"Feedback report exported to {filename}")
        return filename

    except Exception as e:
        logging.error(f"Error in export_feedback_report: {e}")
        print(f"An error occurred: {e}")
        return None
    finally:
        if conn:
            conn.close()

def manage_loyalty_program():
    """Manage customer loyalty program"""
    try:
        print("\n" + "="*50)
        print("LOYALTY PROGRAM MANAGEMENT")
        print("="*50)

        print("\nOptions:")
        print("1. View loyalty tiers")
        print("2. Update customer loyalty points")
        print("3. Promote customers to higher tier")
        print("4. Loyalty program analytics")
        print("5. Award bonus points")
        print("6. Return to customer menu")

        choice = input("Choose an option (1-6): ")

        if choice == '1':
            view_loyalty_tiers()
        elif choice == '2':
            update_loyalty_points()
        elif choice == '3':
            promote_customer_tier()
        elif choice == '4':
            loyalty_analytics()
        elif choice == '5':
            award_bonus_points()
        elif choice == '6':
            return
        else:
            print("Invalid choice.")

    except Exception as e:
        logging.error(f"Error in manage_loyalty_program: {e}")
        print(f"An error occurred: {e}")

def view_loyalty_tiers():
    """View loyalty tier information and customers in each tier"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\n" + "="*60)
        print("LOYALTY TIER INFORMATION")
        print("="*60)

        # Define tier requirements
        print("Tier Requirements:")
        print("Bronze: 0-499 points")
        print("Silver: 500-999 points")
        print("Gold: 1000-1999 points")
        print("Platinum: 2000+ points")
        print()

        # Get customer count by tier
        cursor.execute('''
            SELECT loyalty_tier, COUNT(*) as customer_count, AVG(loyalty_points) as avg_points
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

        print(f"{'Tier':<12} {'Customers':<12} {'Avg Points':<12}")
        print("-"*40)

        for tier in tiers:
            print(f"{tier[0]:<12} {tier[1]:<12} {tier[2]:<12.0f}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in view_loyalty_tiers: {e}")
        print(f"An error occurred: {e}")

def update_loyalty_points():
    """Update customer loyalty points"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to update loyalty points.")
        return

    if not auth.check_permission('manage_customers'):
        print("You don't have permission to update loyalty points.")
        return

    try:
        backup_before_operation('update_loyalty_points')

        customer_id = input("Enter customer ID: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT name, loyalty_points, loyalty_tier FROM restaurant_customers WHERE customer_id = ?',
                      (customer_id,))
        customer = cursor.fetchone()

        if not customer:
            print("Customer not found.")
            conn.close()
            return

        print(f"Customer: {customer[0]}")
        print(f"Current Points: {customer[1]}")
        print(f"Current Tier: {customer[2]}")

        print("\nOptions:")
        print("1. Add points")
        print("2. Subtract points")
        print("3. Set exact points")

        choice = input("Choose option (1-3): ")

        try:
            if choice == '1':
                points_to_add = int(input("Enter points to add: "))
                new_points = customer[1] + points_to_add
            elif choice == '2':
                points_to_subtract = int(input("Enter points to subtract: "))
                new_points = max(0, customer[1] - points_to_subtract)
            elif choice == '3':
                new_points = int(input("Enter exact points: "))
                new_points = max(0, new_points)
            else:
                print("Invalid choice.")
                conn.close()
                return
        except ValueError:
            print("Invalid points value.")
            conn.close()
            return

        # Determine new tier
        if new_points >= 2000:
            new_tier = 'Platinum'
        elif new_points >= 1000:
            new_tier = 'Gold'
        elif new_points >= 500:
            new_tier = 'Silver'
        else:
            new_tier = 'Bronze'

        # Update customer
        cursor.execute('''
            UPDATE restaurant_customers
            SET loyalty_points = ?, loyalty_tier = ?
            WHERE customer_id = ?
        ''', (new_points, new_tier, customer_id))

        conn.commit()
        conn.close()

        print(f"✅ Loyalty points updated!")
        print(f"Previous Points: {customer[1]}")
        print(f"New Points: {new_points}")
        print(f"Previous Tier: {customer[2]}")
        print(f"New Tier: {new_tier}")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'UPDATE_LOYALTY_POINTS',
            'restaurant_customers',
            customer_id,
            {'points': customer[1], 'tier': customer[2]},
            {'points': new_points, 'tier': new_tier}
        )

    except Exception as e:
        logging.error(f"Error in update_loyalty_points: {e}")
        print(f"An error occurred: {e}")

def promote_customer_tier():
    """Promote customers to higher loyalty tier"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to promote customers.")
        return

    if not auth.check_permission('manage_customers'):
        print("You don't have permission to promote customers.")
        return

    try:
        backup_before_operation('promote_customer_tier')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Find customers eligible for promotion
        cursor.execute('''
            SELECT customer_id, name, loyalty_points, loyalty_tier
            FROM restaurant_customers
            WHERE
                (loyalty_tier = 'Bronze' AND loyalty_points >= 500) OR
                (loyalty_tier = 'Silver' AND loyalty_points >= 1000) OR
                (loyalty_tier = 'Gold' AND loyalty_points >= 2000)
            ORDER BY loyalty_points DESC
        ''')

        eligible_customers = cursor.fetchall()

        if not eligible_customers:
            print("No customers eligible for promotion.")
            conn.close()
            return

        print("\nCustomers Eligible for Promotion:")
        print("-"*60)
        print(f"{'ID':<12} {'Name':<20} {'Points':<8} {'Current Tier':<12}")
        print("-"*60)

        for customer in eligible_customers:
            print(f"{customer[0]:<12} {customer[1]:<20} {customer[2]:<8} {customer[3]:<12}")

        print("\nOptions:")
        print("1. Promote all eligible customers")
        print("2. Promote specific customer")
        print("3. Cancel")

        choice = input("Choose option (1-3): ")

        promoted_count = 0

        if choice == '1':
            for customer in eligible_customers:
                # Determine new tier
                if customer[2] >= 2000:
                    new_tier = 'Platinum'
                elif customer[2] >= 1000:
                    new_tier = 'Gold'
                elif customer[2] >= 500:
                    new_tier = 'Silver'
                else:
                    continue

                if new_tier != customer[3]:
                    cursor.execute('UPDATE restaurant_customers SET loyalty_tier = ? WHERE customer_id = ?',
                                  (new_tier, customer[0]))
                    promoted_count += 1

        elif choice == '2':
            customer_id = input("Enter customer ID to promote: ")
            customer_found = None

            for customer in eligible_customers:
                if customer[0] == customer_id:
                    customer_found = customer
                    break

            if not customer_found:
                print("Customer not found or not eligible for promotion.")
                conn.close()
                return

            # Determine new tier
            if customer_found[2] >= 2000:
                new_tier = 'Platinum'
            elif customer_found[2] >= 1000:
                new_tier = 'Gold'
            elif customer_found[2] >= 500:
                new_tier = 'Silver'
            else:
                print("Customer not eligible for promotion.")
                conn.close()
                return

            cursor.execute('UPDATE restaurant_customers SET loyalty_tier = ? WHERE customer_id = ?',
                          (new_tier, customer_id))
            promoted_count = 1

        elif choice == '3':
            print("Promotion cancelled.")
            conn.close()
            return

        conn.commit()
        conn.close()

        print(f"✅ Promoted {promoted_count} customer(s)!")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'PROMOTE_CUSTOMER_TIER',
            'restaurant_customers',
            None,
            None,
            {'promoted_count': promoted_count}
        )

    except Exception as e:
        logging.error(f"Error in promote_customer_tier: {e}")
        print(f"An error occurred: {e}")

def award_bonus_points():
    """Award bonus points to customers"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to award bonus points.")
        return

    if not auth.check_permission('manage_customers'):
        print("You don't have permission to award bonus points.")
        return

    try:
        backup_before_operation('award_bonus_points')

        print("\n" + "="*50)
        print("AWARD BONUS POINTS")
        print("="*50)

        print("\nOptions:")
        print("1. Award points to specific customer")
        print("2. Award points to all customers in a tier")
        print("3. Award points to customers with birthdays this month")
        print("4. Cancel")

        choice = input("Choose option (1-4): ")

        if choice == '4':
            print("Cancelled.")
            return

        try:
            bonus_points = int(input("Enter bonus points to award: "))
            if bonus_points <= 0:
                print("Bonus points must be positive.")
                return
        except ValueError:
            print("Invalid points value.")
            return

        reason = input("Enter reason for bonus points: ").strip()

        conn = get_db_connection()
        cursor = conn.cursor()

        awarded_count = 0

        if choice == '1':
            customer_id = input("Enter customer ID: ")
            cursor.execute('SELECT name, loyalty_points FROM restaurant_customers WHERE customer_id = ?',
                          (customer_id,))
            customer = cursor.fetchone()

            if not customer:
                print("Customer not found.")
                conn.close()
                return

            new_points = customer[1] + bonus_points

            # Determine new tier
            if new_points >= 2000:
                new_tier = 'Platinum'
            elif new_points >= 1000:
                new_tier = 'Gold'
            elif new_points >= 500:
                new_tier = 'Silver'
            else:
                new_tier = 'Bronze'

            cursor.execute('''
                UPDATE restaurant_customers
                SET loyalty_points = ?, loyalty_tier = ?
                WHERE customer_id = ?
            ''', (new_points, new_tier, customer_id))

            awarded_count = 1

        elif choice == '2':
            tier = input("Enter tier (Bronze/Silver/Gold/Platinum): ")
            cursor.execute('SELECT customer_id, loyalty_points FROM restaurant_customers WHERE loyalty_tier = ?',
                          (tier,))
            customers = cursor.fetchall()

            for customer in customers:
                new_points = customer[1] + bonus_points

                # Determine new tier
                if new_points >= 2000:
                    new_tier = 'Platinum'
                elif new_points >= 1000:
                    new_tier = 'Gold'
                elif new_points >= 500:
                    new_tier = 'Silver'
                else:
                    new_tier = 'Bronze'

                cursor.execute('''
                    UPDATE restaurant_customers
                    SET loyalty_points = ?, loyalty_tier = ?
                    WHERE customer_id = ?
                ''', (new_points, new_tier, customer[0]))

                awarded_count += 1

        elif choice == '3':
            current_month = datetime.now().strftime('%m')
            cursor.execute('''
                SELECT customer_id, loyalty_points
                FROM restaurant_customers
                WHERE substr(birthday, 6, 2) = ?
            ''', (current_month,))
            customers = cursor.fetchall()

            for customer in customers:
                new_points = customer[1] + bonus_points

                # Determine new tier
                if new_points >= 2000:
                    new_tier = 'Platinum'
                elif new_points >= 1000:
                    new_tier = 'Gold'
                elif new_points >= 500:
                    new_tier = 'Silver'
                else:
                    new_tier = 'Bronze'

                cursor.execute('''
                    UPDATE restaurant_customers
                    SET loyalty_points = ?, loyalty_tier = ?
                    WHERE customer_id = ?
                ''', (new_points, new_tier, customer[0]))

                awarded_count += 1

        conn.commit()
        conn.close()

        print(f"✅ Awarded {bonus_points} bonus points to {awarded_count} customer(s)!")
        print(f"Reason: {reason}")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'AWARD_BONUS_POINTS',
            'restaurant_customers',
            None,
            None,
            {'bonus_points': bonus_points, 'awarded_count': awarded_count, 'reason': reason}
        )

    except Exception as e:
        logging.error(f"Error in award_bonus_points: {e}")
        print(f"An error occurred: {e}")

def export_feedback_report_pdf(days=90, filename=None):
    """Export feedback report as PDF"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()

        cursor.execute('''
            SELECT cf.feedback_id,
                   cf.feedback_date,
                   COALESCE(c.name, 'Anonymous') AS customer_name,
                   cf.rating,
                   COALESCE(cf.feedback_text, '') AS feedback_text,
                   COALESCE(mi.name, '') AS item_name
            FROM restaurant_customer_feedback cf
            LEFT JOIN restaurant_customers c ON cf.customer_id = c.customer_id
            LEFT JOIN menu_items mi ON cf.item_id = mi.item_id
            WHERE date(cf.feedback_date) >= ?
            ORDER BY cf.feedback_date DESC
            LIMIT 50
        ''', (cutoff,))

        feedback = cursor.fetchall()

        if not feedback:
            print(f"No feedback found in the last {days} days.")
            conn.close()
            return None

        if not filename:
            filename = f"feedback_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        doc = SimpleDocTemplate(filename, pagesize=A4)
        styles = getSampleStyleSheet()
        content = []

        # Title
        title = f"Customer Feedback Report - Last {days} Days"
        content.append(Paragraph(title, styles['Title']))
        content.append(Spacer(1, 20))

        # Summary
        total_feedback = len(feedback)
        avg_rating = sum(fb[3] for fb in feedback) / total_feedback if total_feedback > 0 else 0

        summary_text = f"Total Feedback: {total_feedback} | Average Rating: {avg_rating:.1f}/5"
        content.append(Paragraph(summary_text, styles['Heading2']))
        content.append(Spacer(1, 15))

        # Feedback table
        table_data = [['Date', 'Customer', 'Rating', 'Item', 'Feedback']]

        for fb in feedback[:20]:  # Limit to first 20 for PDF
            fb_date = str(fb[1])[:10] if fb[1] else "N/A"
            rating_stars = "★" * fb[3] + "☆" * (5 - fb[3])
            feedback_text = fb[4][:50] + "..." if len(fb[4]) > 50 else fb[4]

            table_data.append([
                fb_date,
                fb[2][:15],  # Truncate long names
                rating_stars,
                fb[5][:15] if fb[5] else "",
                feedback_text
            ])

        feedback_table = Table(table_data)
        feedback_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))

        content.append(feedback_table)

        if total_feedback > 20:
            content.append(Spacer(1, 10))
            content.append(Paragraph(f"Note: Showing first 20 of {total_feedback} feedback entries", styles['Normal']))

        # Build PDF
        doc.build(content)

        conn.close()
        print(f"Feedback report PDF generated: {filename}")
        return filename

    except Exception as e:
        logging.error(f"Error in export_feedback_report_pdf: {e}")
        print(f"An error occurred: {e}")
        return None
