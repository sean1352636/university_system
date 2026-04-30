from education_system.university_system.infrastructure.auth import UserAuth, display_auth_menu
from education_system.university_system.infrastructure.database.data_backup import display_backup_menu, backup_before_operation
from education_system.university_system.infrastructure.email import send_confirmation_email
from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager
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
from education_system.university_system.modules.shared.utils.finance_integration import record_payment_to_finance
from collections import defaultdict
from education_system.university_system.modules.domain.commerce.services.restaurant.operations.connection import get_db_connection
import warnings
from education_system.university_system.infrastructure.logging.log_config import configure_logging

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


def view_orders():
    """View orders with filtering options"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\nFilter options:")
        print("1. All orders")
        print("2. Today's orders")
        print("3. Pending orders")
        print("4. Completed orders")
        print("5. By customer")
        print("6. By table")
        print("7. By date range")

        filter_choice = input("Choose filter (1-7): ")

        if filter_choice == '1':
            cursor.execute('''
                SELECT o.*, c.name as customer_name
                FROM orders o
                LEFT JOIN restaurant_customers c ON o.customer_id = c.customer_id
                ORDER BY o.order_date DESC
                LIMIT 50
            ''')
        elif filter_choice == '2':
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT o.*, c.name as customer_name
                FROM orders o
                LEFT JOIN restaurant_customers c ON o.customer_id = c.customer_id
                WHERE DATE(o.order_date) = ?
                ORDER BY o.order_date DESC
            ''', (today,))
        elif filter_choice == '3':
            cursor.execute('''
                SELECT o.*, c.name as customer_name
                FROM orders o
                LEFT JOIN restaurant_customers c ON o.customer_id = c.customer_id
                WHERE o.order_status = 'Pending'
                ORDER BY o.order_date DESC
            ''')
        elif filter_choice == '4':
            cursor.execute('''
                SELECT o.*, c.name as customer_name
                FROM orders o
                LEFT JOIN restaurant_customers c ON o.customer_id = c.customer_id
                WHERE o.order_status = 'Completed'
                ORDER BY o.order_date DESC
                LIMIT 50
            ''')
        elif filter_choice == '5':
            customer_id = input("Enter customer ID: ")
            cursor.execute('''
                SELECT o.*, c.name as customer_name
                FROM orders o
                LEFT JOIN restaurant_customers c ON o.customer_id = c.customer_id
                WHERE o.customer_id = ?
                ORDER BY o.order_date DESC
            ''', (customer_id,))
        elif filter_choice == '6':
            table_id = input("Enter table ID: ")
            cursor.execute('''
                SELECT o.*, c.name as customer_name
                FROM orders o
                LEFT JOIN restaurant_customers c ON o.customer_id = c.customer_id
                WHERE o.table_id = ?
                ORDER BY o.order_date DESC
            ''', (table_id,))
        elif filter_choice == '7':
            start_date = input("Enter start date (YYYY-MM-DD): ")
            end_date = input("Enter end date (YYYY-MM-DD): ")
            cursor.execute('''
                SELECT o.*, c.name as customer_name
                FROM orders o
                LEFT JOIN restaurant_customers c ON o.customer_id = c.customer_id
                WHERE DATE(o.order_date) BETWEEN ? AND ?
                ORDER BY o.order_date DESC
            ''', (start_date, end_date))
        else:
            cursor.execute('''
                SELECT o.*, c.name as customer_name
                FROM orders o
                LEFT JOIN restaurant_customers c ON o.customer_id = c.customer_id
                ORDER BY o.order_date DESC
                LIMIT 50
            ''')

        orders = cursor.fetchall()

        if not orders:
            print("No orders found.")
            conn.close()
            return

        print(f"\n" + "="*120)
        print("ORDERS")
        print("="*120)
        print(f"{'Order ID':<12} {'Date/Time':<17} {'Customer':<20} {'Table':<8} {'Total':<10} {'Status':<12} {'Payment':<12}")
        print("-"*120)

        for order in orders:
            order_time = order[3][:16] if order[3] else 'N/A'
            customer_name = order[15] if order[15] else 'Walk-in'
            table_id = order[2] if order[2] else 'N/A'

            print(f"{order[0]:<12} {order_time:<17} {customer_name:<20} {table_id:<8} £{order[4]:<9.2f} {order[5]:<12} {order[6]:<12}")

        print("="*120)
        print(f"Total orders: {len(orders)}")

        # Option to view order details
        order_id = input("\nEnter order ID to view details (or press Enter to return): ")
        if order_id:
            view_order_details(order_id)

        conn.close()

    except Exception as e:
        logging.error(f"Error in view_orders: {e}")
        print(f"An error occurred: {e}")

def view_order_details(order_id):
    """View detailed information about a specific order"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get order information
        cursor.execute('''
            SELECT o.*, c.name as customer_name, c.email as customer_email
            FROM orders o
            LEFT JOIN restaurant_customers c ON o.customer_id = c.customer_id
            WHERE o.order_id = ?
        ''', (order_id,))

        order = cursor.fetchone()

        if not order:
            print("Order not found.")
            conn.close()
            return

        print(f"\n" + "="*60)
        print(f"ORDER DETAILS: {order_id}")
        print("="*60)

        print(f"Order Date/Time: {order[3]}")
        print(f"Customer: {order[15] if order[15] else 'Walk-in'}")
        if order[16]:
            print(f"Customer Email: {order[16]}")
        print(f"Table: {order[2] if order[2] else 'Takeaway/Delivery'}")
        print(f"Order Type: {order[7] if len(order) > 7 else 'N/A'}")
        print(f"Status: {order[5]}")
        print(f"Payment Method: {order[6]}")
        print(f"Estimated Time: {order[8] if len(order) > 8 else 'N/A'} minutes")

        if len(order) > 9 and order[9]:
            print(f"Actual Time: {order[9]} minutes")

        print(f"Subtotal: £{order[4] - (order[13] if len(order) > 13 and order[13] else 0):.2f}")
        if len(order) > 13 and order[13]:
            print(f"Tax: £{order[13]:.2f}")
        if len(order) > 12 and order[12]:
            print(f"Discount: £{order[12]:.2f}")
        if len(order) > 14 and order[14]:
            print(f"Tip: £{order[14]:.2f}")
        print(f"Total: £{order[4]:.2f}")

        if len(order) > 10 and order[10]:
            print(f"Rating: {'⭐' * order[10]} ({order[10]}/5)")
        if len(order) > 11 and order[11]:
            print(f"Feedback: {order[11]}")

        # Get order items
        cursor.execute('''
            SELECT oi.*, mi.name
            FROM order_items oi
            JOIN menu_items mi ON oi.item_id = mi.item_id
            WHERE oi.order_id = ?
            ORDER BY oi.id
        ''', (order_id,))

        items = cursor.fetchall()

        if items:
            print(f"\nOrder Items:")
            print("-"*60)
            print(f"{'Item':<30} {'Qty':<5} {'Price':<8} {'Total':<10}")
            print("-"*60)

            for item in items:
                total = item[3] * item[2]
                print(f"{item[5]:<30} {item[2]:<5} £{item[3]:<7.2f} £{total:<9.2f}")

                if item[4]:  # special instructions
                    print(f"  Note: {item[4]}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in view_order_details: {e}")
        print(f"An error occurred: {e}")

def add_tip():
    """Add tip to an order"""
    global auth

    try:
        order_id = input("Enter order ID: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT total_amount, tip_amount FROM orders WHERE order_id = ?', (order_id,))
        order = cursor.fetchone()

        if not order:
            print("Order not found.")
            conn.close()
            return

        print(f"Order total: £{order[0]:.2f}")
        if order[1] and order[1] > 0:
            print(f"Current tip: £{order[1]:.2f}")

        print("\nTip options:")
        print("1. Custom amount")
        print("2. 10%")
        print("3. 15%")
        print("4. 20%")

        tip_choice = input("Choose tip option (1-4): ")

        if tip_choice == '1':
            try:
                tip_amount = float(input("Enter tip amount: £"))
            except ValueError:
                print("Invalid amount.")
                conn.close()
                return
        elif tip_choice == '2':
            tip_amount = order[0] * 0.10
        elif tip_choice == '3':
            tip_amount = order[0] * 0.15
        elif tip_choice == '4':
            tip_amount = order[0] * 0.20
        else:
            print("Invalid choice.")
            conn.close()
            return

        # Update order with tip
        cursor.execute('UPDATE orders SET tip_amount = ? WHERE order_id = ?',
                      (tip_amount, order_id))

        conn.commit()
        conn.close()

        print(f"✅ Tip added!")
        print(f"Tip amount: £{tip_amount:.2f}")
        print(f"Total with tip: £{order[0] + tip_amount:.2f}")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'ADD_TIP',
            'orders',
            order_id,
            {'old_tip': order[1] or 0},
            {'new_tip': tip_amount}
        )

    except Exception as e:
        logging.error(f"Error in add_tip: {e}")
        print(f"An error occurred: {e}")

def refund_order():
    """Process order refund"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to process refunds.")
        return

    if not auth.check_permission('manage_orders'):
        print("You don't have permission to process refunds.")
        return

    try:
        backup_before_operation('refund_order')

        order_id = input("Enter order ID to refund: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM orders WHERE order_id = ?', (order_id,))
        order = cursor.fetchone()

        if not order:
            print("Order not found.")
            conn.close()
            return

        if order[5] != 'Completed':
            print("Only completed orders can be refunded.")
            conn.close()
            return

        print(f"Order total: £{order[4]:.2f}")
        print(f"Payment method: {order[6]}")

        reason = input("Enter refund reason: ")

        print("\nRefund options:")
        print("1. Full refund")
        print("2. Partial refund")

        refund_choice = input("Choose refund type (1-2): ")

        if refund_choice == '1':
            refund_amount = order[4]
        elif refund_choice == '2':
            try:
                refund_amount = float(input(f"Enter refund amount (max £{order[4]:.2f}): "))
                if refund_amount > order[4]:
                    print("Refund amount cannot exceed order total.")
                    conn.close()
                    return
            except ValueError:
                print("Invalid amount.")
                conn.close()
                return
        else:
            print("Invalid choice.")
            conn.close()
            return

        # Process refund based on payment method
        if order[6] == 'Meal Plan' and order[1]:  # customer_id exists
            # Refund to meal plan
            cursor.execute('''
                SELECT plan_id, balance FROM restaurant_meal_plans
                WHERE student_id = ? AND status = 'Active'
                ORDER BY end_date DESC LIMIT 1
            ''', (order[1],))

            meal_plan = cursor.fetchone()

            if meal_plan:
                new_balance = meal_plan[1] + refund_amount
                cursor.execute('UPDATE restaurant_meal_plans SET balance = ? WHERE plan_id = ?',
                              (new_balance, meal_plan[0]))

                # Create refund transaction
                transaction_id = f"REF{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"
                cursor.execute('''
                    INSERT INTO restaurant_meal_plan_transactions VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    transaction_id, meal_plan[0], 'Refund', refund_amount, meal_plan[1], new_balance,
                    order_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), f'Refund for order: {order_id} - {reason}'
                ))

        # Update order status
        cursor.execute('UPDATE orders SET order_status = ? WHERE order_id = ?', ('Refunded', order_id))

        conn.commit()
        conn.close()

        print(f"✅ Refund processed!")
        print(f"Refund amount: £{refund_amount:.2f}")
        print(f"Payment method: {order[6]}")
        print(f"Reason: {reason}")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'REFUND_ORDER',
            'orders',
            order_id,
            None,
            {'refund_amount': refund_amount, 'reason': reason, 'payment_method': order[6]}
        )

    except Exception as e:
        logging.error(f"Error in refund_order: {e}")
        print(f"An error occurred: {e}")

def update_order_status():
    """Update order status"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to update order status.")
        return

    if not auth.check_permission('manage_orders'):
        print("You don't have permission to update order status.")
        return

    try:
        backup_before_operation('update_order_status')

        order_id = input("Enter order ID: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT order_status, table_id FROM orders WHERE order_id = ?', (order_id,))
        order = cursor.fetchone()

        if not order:
            print("Order not found.")
            conn.close()
            return

        print(f"Current status: {order[0]}")

        print("\nNew status options:")
        print("1. Pending")
        print("2. Preparing")
        print("3. Ready")
        print("4. Completed")
        print("5. Cancelled")

        choice = input("Choose new status (1-5): ")
        statuses = {
            '1': 'Pending',
            '2': 'Preparing',
            '3': 'Ready',
            '4': 'Completed',
            '5': 'Cancelled'
        }

        new_status = statuses.get(choice)

        if not new_status:
            print("Invalid choice.")
            conn.close()
            return

        # Update order status
        cursor.execute('UPDATE orders SET order_status = ? WHERE order_id = ?', (new_status, order_id))

        # If completing or cancelling, free up the table
        if new_status in ['Completed', 'Cancelled'] and order[1]:
            cursor.execute('UPDATE restaurant_tables SET status = ?, current_order_id = NULL WHERE table_id = ?',
                          ('Available', order[1]))

        # If completed, record actual time
        if new_status == 'Completed':
            cursor.execute('''
                UPDATE orders
                SET actual_time = CAST((julianday('now') - julianday(order_date)) * 24 * 60 AS INTEGER)
                WHERE order_id = ?
            ''', (order_id,))

        conn.commit()
        conn.close()

        print(f"✅ Order {order_id} status updated to: {new_status}")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'UPDATE_ORDER_STATUS',
            'orders',
            order_id,
            {'status': order[0]},
            {'status': new_status}
        )

    except Exception as e:
        logging.error(f"Error in update_order_status: {e}")
        print(f"An error occurred: {e}")

def process_payments():
    """Process order payments"""
    try:
        print("\n" + "="*50)
        print("PAYMENT PROCESSING")
        print("="*50)

        print("\nOptions:")
        print("1. Process cash payment")
        print("2. Process card payment")
        print("3. Process meal plan payment")
        print("4. Apply discount")
        print("5. Add tip")
        print("6. Refund order")
        print("7. Return to orders menu")

        choice = input("Choose an option (1-7): ")

        if choice == '1':
            process_cash_payment()
        elif choice == '2':
            process_card_payment()
        elif choice == '3':
            process_meal_plan_payment()
        elif choice == '4':
            apply_discount()
        elif choice == '5':
            add_tip()
        elif choice == '6':
            refund_order()
        elif choice == '7':
            return
        else:
            print("Invalid choice.")

    except Exception as e:
        logging.error(f"Error in process_payments: {e}")
        print(f"An error occurred: {e}")

def process_cash_payment():
    """Process cash payment for an order"""
    global auth

    try:
        order_id = input("Enter order ID: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT total_amount, order_status, payment_method FROM orders WHERE order_id = ?', (order_id,))
        order = cursor.fetchone()

        if not order:
            print("Order not found.")
            conn.close()
            return

        if order[1] == 'Completed':
            print("Order is already completed.")
            conn.close()
            return

        print(f"Order total: £{order[0]:.2f}")

        while True:
            try:
                cash_received = float(input("Enter cash received: £"))
                if cash_received >= order[0]:
                    break
                else:
                    print("Insufficient cash amount.")
            except ValueError:
                print("Invalid amount.")

        change = cash_received - order[0]

        # Update payment method and status
        cursor.execute('''
            UPDATE orders
            SET payment_method = 'Cash', order_status = 'Completed'
            WHERE order_id = ?
        ''', (order_id,))

        conn.commit()

        # Record payment to central finance system
        finance_payment_id = record_payment_to_finance(
            student_id="EXTERNAL",  # Restaurant customers may not be students
            amount=order[0],
            payment_method='Cash',
            transaction_source='Restaurant',
            transaction_ref=order_id,
            notes=f'Restaurant order payment',
            created_by=auth.current_user['username'] if auth and auth.current_user else None
        )

        # Cross-domain: if the order's customer matches a student
        # record, post the sale through the unified commerce bus so
        # restaurant spend feeds into loyalty tier + the unified
        # finance ledger. Best-effort lookup.
        try:
            cursor.execute(
                "SELECT rc.email "
                "FROM orders o "
                "LEFT JOIN restaurant_customers rc "
                "  ON rc.customer_id = o.customer_id "
                "WHERE o.order_id = ?",
                (order_id,),
            )
            crow = cursor.fetchone()
            customer_email = crow[0] if crow else None
            student_id = None
            if customer_email:
                cursor.execute(
                    "SELECT student_id FROM students WHERE email = ?",
                    (customer_email,),
                )
                srow = cursor.fetchone()
                if srow:
                    student_id = srow[0]
            if student_id:
                from education_system.university_system.modules.services import (
                    commerce_bus,
                )
                commerce_bus.post_sale(
                    student_id,
                    source="restaurant",
                    amount=float(order[0]),
                    description=f"Restaurant order {order_id}",
                    reference_id=order_id,
                )
        except Exception:
            pass

        conn.close()

        print(f"✅ Payment processed successfully!")
        print(f"Cash received: £{cash_received:.2f}")
        print(f"Change due: £{change:.2f}")
        if finance_payment_id:
            print(f"Finance System Payment ID: {finance_payment_id}")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'PROCESS_CASH_PAYMENT',
            'orders',
            order_id,
            None,
            {'amount': order[0], 'cash_received': cash_received, 'change': change}
        )

    except Exception as e:
        logging.error(f"Error in process_cash_payment: {e}")
        print(f"An error occurred: {e}")

def process_card_payment():
    """Process card payment for an order"""
    global auth

    try:
        order_id = input("Enter order ID: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT total_amount, order_status FROM orders WHERE order_id = ?', (order_id,))
        order = cursor.fetchone()

        if not order:
            print("Order not found.")
            conn.close()
            return

        if order[1] == 'Completed':
            print("Order is already completed.")
            conn.close()
            return

        print(f"Order total: £{order[0]:.2f}")

        print("\nCard types:")
        print("1. Debit Card")
        print("2. Credit Card")
        print("3. Contactless")

        card_choice = input("Choose card type (1-3): ")
        card_types = {'1': 'Debit Card', '2': 'Credit Card', '3': 'Contactless'}
        card_type = card_types.get(card_choice, 'Card')

        # Simulate card processing
        print("Processing card payment...")
        time.sleep(2)

        # In a real system, this would integrate with a payment processor
        print("✅ Card payment approved!")

        # Update payment method and status
        cursor.execute('''
            UPDATE orders
            SET payment_method = ?, order_status = 'Completed'
            WHERE order_id = ?
        ''', (card_type, order_id))

        conn.commit()

        # Record payment to central finance system
        finance_payment_id = record_payment_to_finance(
            student_id="EXTERNAL",
            amount=order[0],
            payment_method=card_type,
            transaction_source='Restaurant',
            transaction_ref=order_id,
            notes=f'Restaurant order payment via {card_type}',
            created_by=auth.current_user['username'] if auth and auth.current_user else None
        )

        conn.close()

        print(f"Payment processed: £{order[0]:.2f} via {card_type}")
        if finance_payment_id:
            print(f"Finance System Payment ID: {finance_payment_id}")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'PROCESS_CARD_PAYMENT',
            'orders',
            order_id,
            None,
            {'amount': order[0], 'card_type': card_type}
        )

    except Exception as e:
        logging.error(f"Error in process_card_payment: {e}")
        print(f"An error occurred: {e}")

def process_meal_plan_payment():
    """Process meal plan payment for an order"""
    global auth

    try:
        order_id = input("Enter order ID: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT total_amount, order_status, customer_id FROM orders WHERE order_id = ?', (order_id,))
        order = cursor.fetchone()

        if not order:
            print("Order not found.")
            conn.close()
            return

        if order[1] == 'Completed':
            print("Order is already completed.")
            conn.close()
            return

        if not order[2]:
            print("Customer ID required for meal plan payment.")
            conn.close()
            return

        # Check if customer has an active meal plan
        cursor.execute('''
            SELECT plan_id, balance FROM restaurant_meal_plans
            WHERE student_id = ? AND status = 'Active'
            ORDER BY balance DESC LIMIT 1
        ''', (order[2],))

        meal_plan = cursor.fetchone()

        if not meal_plan:
            print("No active meal plan found for this customer.")
            conn.close()
            return

        if meal_plan[1] < order[0]:
            print(f"Insufficient meal plan balance. Available: £{meal_plan[1]:.2f}, Required: £{order[0]:.2f}")
            conn.close()
            return

        # Process meal plan payment
        new_balance = meal_plan[1] - order[0]

        # Update meal plan balance
        cursor.execute('UPDATE restaurant_meal_plans SET balance = ? WHERE plan_id = ?',
                      (new_balance, meal_plan[0]))

        # Create meal plan transaction
        transaction_id = f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"
        cursor.execute('''
            INSERT INTO restaurant_meal_plan_transactions VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            transaction_id, meal_plan[0], 'Purchase', order[0], meal_plan[1], new_balance,
            order_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), f'Order payment: {order_id}'
        ))

        # Update order
        cursor.execute('''
            UPDATE orders
            SET payment_method = 'Meal Plan', order_status = 'Completed'
            WHERE order_id = ?
        ''', (order_id,))

        conn.commit()

        # Record payment to central finance system
        finance_payment_id = record_payment_to_finance(
            student_id=order[2],  # customer_id (student_id)
            amount=order[0],
            payment_method='Meal Plan',
            transaction_source='Restaurant',
            transaction_ref=order_id,
            notes=f'Restaurant order via Meal Plan (Plan ID: {meal_plan[0]})',
            created_by=auth.current_user['username'] if auth and auth.current_user else None
        )

        conn.close()

        print(f"✅ Meal plan payment processed!")
        print(f"Amount charged: £{order[0]:.2f}")
        print(f"Remaining balance: £{new_balance:.2f}")
        if finance_payment_id:
            print(f"Finance System Payment ID: {finance_payment_id}")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'PROCESS_MEAL_PLAN_PAYMENT',
            'orders',
            order_id,
            None,
            {'amount': order[0], 'plan_id': meal_plan[0], 'new_balance': new_balance}
        )

    except Exception as e:
        logging.error(f"Error in process_meal_plan_payment: {e}")
        print(f"An error occurred: {e}")

def apply_discount():
    """Apply discount to an order"""
    global auth

    try:
        order_id = input("Enter order ID: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT total_amount, order_status, discount_applied FROM orders WHERE order_id = ?', (order_id,))
        order = cursor.fetchone()

        if not order:
            print("Order not found.")
            conn.close()
            return

        if order[1] == 'Completed':
            print("Cannot apply discount to completed order.")
            conn.close()
            return

        print(f"Current total: £{order[0]:.2f}")
        if order[2] and order[2] > 0:
            print(f"Current discount: £{order[2]:.2f}")

        print("\nDiscount types:")
        print("1. Percentage discount")
        print("2. Fixed amount discount")
        print("3. Student discount (10%)")
        print("4. Senior discount (15%)")

        discount_choice = input("Choose discount type (1-4): ")

        if discount_choice == '1':
            try:
                percentage = float(input("Enter discount percentage (e.g., 10 for 10%): "))
                discount_amount = (order[0] * percentage) / 100
            except ValueError:
                print("Invalid percentage.")
                conn.close()
                return
        elif discount_choice == '2':
            try:
                discount_amount = float(input("Enter discount amount: £"))
            except ValueError:
                print("Invalid amount.")
                conn.close()
                return
        elif discount_choice == '3':
            discount_amount = order[0] * 0.10  # 10% student discount
        elif discount_choice == '4':
            discount_amount = order[0] * 0.15  # 15% senior discount
        else:
            print("Invalid choice.")
            conn.close()
            return

        if discount_amount >= order[0]:
            print("Discount cannot be greater than or equal to order total.")
            conn.close()
            return

        new_total = order[0] - discount_amount

        # Update order with discount
        cursor.execute('''
            UPDATE orders
            SET discount_applied = ?, total_amount = ?
            WHERE order_id = ?
        ''', (discount_amount, new_total, order_id))

        conn.commit()
        conn.close()

        print(f"✅ Discount applied!")
        print(f"Discount amount: £{discount_amount:.2f}")
        print(f"New total: £{new_total:.2f}")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'APPLY_DISCOUNT',
            'orders',
            order_id,
            {'original_total': order[0]},
            {'discount': discount_amount, 'new_total': new_total}
        )

    except Exception as e:
        logging.error(f"Error in apply_discount: {e}")
        print(f"An error occurred: {e}")

def manage_purchase_orders():
    """Manage purchase orders"""
    try:
        print("\n" + "="*50)
        print("PURCHASE ORDER MANAGEMENT")
        print("="*50)

        print("\nOptions:")
        print("1. View purchase orders")
        print("2. Create purchase order")
        print("3. Update purchase order")
        print("4. Receive order")
        print("5. Purchase order reports")
        print("6. Return to inventory menu")

        choice = input("Choose an option (1-6): ")

        if choice == '1':
            view_purchase_orders()
        elif choice == '2':
            create_purchase_order()
        elif choice == '3':
            update_purchase_order()
        elif choice == '4':
            receive_purchase_order()
        elif choice == '5':
            purchase_order_reports()
        elif choice == '6':
            return
        else:
            print("Invalid choice.")

    except Exception as e:
        logging.error(f"Error in manage_purchase_orders: {e}")
        print(f"An error occurred: {e}")

def view_purchase_orders():
    """View purchase orders"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\nFilter options:")
        print("1. All orders")
        print("2. Pending orders")
        print("3. By supplier")
        print("4. By status")

        filter_choice = input("Choose filter (1-4): ")

        if filter_choice == '1':
            cursor.execute('''
                SELECT po.*, s.name as supplier_name
                FROM restaurant_purchase_orders po
                JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
                ORDER BY po.order_date DESC
            ''')
        elif filter_choice == '2':
            cursor.execute('''
                SELECT po.*, s.name as supplier_name
                FROM restaurant_purchase_orders po
                JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
                WHERE po.status = 'Pending'
                ORDER BY po.order_date DESC
            ''')
        elif filter_choice == '3':
            supplier_id = input("Enter supplier ID: ")
            cursor.execute('''
                SELECT po.*, s.name as supplier_name
                FROM restaurant_purchase_orders po
                JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
                WHERE po.supplier_id = ?
                ORDER BY po.order_date DESC
            ''', (supplier_id,))
        elif filter_choice == '4':
            status = input("Enter status (Pending/Delivered/Cancelled): ")
            cursor.execute('''
                SELECT po.*, s.name as supplier_name
                FROM restaurant_purchase_orders po
                JOIN restaurant_suppliers s ON po.supplier_id = s.supplier_id
                WHERE po.status = ?
                ORDER BY po.order_date DESC
            ''', (status,))

        orders = cursor.fetchall()

        if not orders:
            print("No purchase orders found.")
            conn.close()
            return

        print(f"\n" + "="*120)
        print("PURCHASE ORDERS")
        print("="*120)
        print(f"{'PO ID':<12} {'Date':<12} {'Supplier':<20} {'Total':<10} {'Status':<12} {'Expected':<12} {'Actual':<12}")
        print("-"*120)

        for order in orders:
            order_date = order[2][:10] if order[2] else 'N/A'
            expected = order[3][:10] if order[3] else 'N/A'
            actual = order[4][:10] if order[4] else 'N/A'

            print(f"{order[0]:<12} {order_date:<12} {order[9]:<20} £{order[5]:<9.2f} {order[6]:<12} {expected:<12} {actual:<12}")

        print("="*120)
        print(f"Total orders: {len(orders)}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in view_purchase_orders: {e}")
        print(f"An error occurred: {e}")

def create_purchase_order():
    """Create new purchase order"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to create purchase orders.")
        return

    if not auth.check_permission('manage_inventory'):
        print("You don't have permission to create purchase orders.")
        return

    try:
        backup_before_operation('create_purchase_order')

        print("\n" + "="*50)
        print("CREATE PURCHASE ORDER")
        print("="*50)

        # Get suppliers
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT supplier_id, name FROM restaurant_suppliers WHERE status = ?', ('Active',))
        suppliers = cursor.fetchall()

        if not suppliers:
            print("No active suppliers found.")
            conn.close()
            return

        print("Available suppliers:")
        for i, supplier in enumerate(suppliers, 1):
            print(f"{i}. {supplier[1]} (ID: {supplier[0]})")

        try:
            supplier_choice = int(input("Choose supplier (enter number): ")) - 1
            if supplier_choice < 0 or supplier_choice >= len(suppliers):
                raise ValueError
            selected_supplier = suppliers[supplier_choice]
        except ValueError:
            print("Invalid supplier choice.")
            conn.close()
            return

        # Generate PO ID
        po_id = f"PO{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"

        expected_delivery = input("Enter expected delivery date (YYYY-MM-DD): ")
        try:
            datetime.strptime(expected_delivery, '%Y-%m-%d')
        except ValueError:
            print("Invalid date format.")
            conn.close()
            return

        notes = input("Enter notes (optional): ").strip()

        # Create PO
        cursor.execute('''
            INSERT INTO restaurant_purchase_orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            po_id, selected_supplier[0], datetime.now().strftime('%Y-%m-%d'),
            expected_delivery, None, 0, 'Pending', notes, auth.current_user['id']
        ))

        print(f"\nPurchase Order {po_id} created. Now add items:")

        total_amount = 0
        item_count = 0

        while True:
            print(f"\nItem #{item_count + 1}")
            item_name = input("Enter item name (or 'done' to finish): ").strip()

            if item_name.lower() == 'done':
                break

            try:
                quantity = float(input("Enter quantity: "))
                if quantity <= 0:
                    raise ValueError
            except ValueError:
                print("Invalid quantity, skipping item.")
                continue

            unit = input("Enter unit: ").strip()

            try:
                unit_cost = float(input("Enter unit cost (£): "))
                if unit_cost < 0:
                    raise ValueError
            except ValueError:
                print("Invalid cost, skipping item.")
                continue

            total_cost = quantity * unit_cost
            total_amount += total_cost

            # Add item to PO
            cursor.execute('''
                INSERT INTO restaurant_purchase_order_items VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                None, po_id, item_name, quantity, unit, unit_cost, total_cost, 0
            ))

            item_count += 1
            print(f"Added: {quantity} {unit} of {item_name} at £{unit_cost:.2f} each = £{total_cost:.2f}")

        if item_count == 0:
            print("No items added. Cancelling purchase order.")
            cursor.execute('DELETE FROM restaurant_purchase_orders WHERE po_id = ?', (po_id,))
            conn.commit()
            conn.close()
            return

        # Update total amount
        cursor.execute('UPDATE restaurant_purchase_orders SET total_amount = ? WHERE po_id = ?',
                      (total_amount, po_id))

        conn.commit()
        conn.close()

        print(f"\n✅ Purchase Order created successfully!")
        print(f"PO ID: {po_id}")
        print(f"Supplier: {selected_supplier[1]}")
        print(f"Items: {item_count}")
        print(f"Total: £{total_amount:.2f}")
        print(f"Expected Delivery: {expected_delivery}")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'CREATE_PURCHASE_ORDER',
            'restaurant_purchase_orders',
            po_id,
            None,
            {'supplier_id': selected_supplier[0], 'total_amount': total_amount, 'item_count': item_count}
        )

    except Exception as e:
        logging.error(f"Error in create_purchase_order: {e}")
        print(f"An error occurred: {e}")

def update_purchase_order():
    """Update purchase order status - FIXED"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to update purchase orders.")
        return

    if not auth.check_permission('manage_inventory'):
        print("You don't have permission to update purchase orders.")
        return

    try:
        backup_before_operation('update_purchase_order')

        po_id = input("Enter purchase order ID: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM restaurant_purchase_orders WHERE po_id = ?', (po_id,))
        po = cursor.fetchone()

        if not po:
            print("Purchase order not found.")
            conn.close()
            return

        print(f"Current PO Status: {po[6]}")

        print("\nNew status options:")
        print("1. Pending")
        print("2. Ordered")
        print("3. Shipped")
        print("4. Delivered")
        print("5. Cancelled")

        choice = input("Choose new status (1-5): ")
        statuses = {
            '1': 'Pending',
            '2': 'Ordered',
            '3': 'Shipped',
            '4': 'Delivered',
            '5': 'Cancelled'
        }

        new_status = statuses.get(choice)
        if not new_status:
            print("Invalid choice.")
            conn.close()
            return

        # If delivered, record actual delivery date
        if new_status == 'Delivered':
            actual_delivery = datetime.now().strftime('%Y-%m-%d')
            cursor.execute('''
                UPDATE restaurant_purchase_orders
                SET status = ?, actual_delivery = ?
                WHERE po_id = ?
            ''', (new_status, actual_delivery, po_id))
        else:
            cursor.execute('UPDATE restaurant_purchase_orders SET status = ? WHERE po_id = ?',
                          (new_status, po_id))

        conn.commit()
        conn.close()

        print(f"✅ Purchase order {po_id} status updated to: {new_status}")

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'UPDATE_PURCHASE_ORDER',
            'restaurant_purchase_orders',
            po_id,
            {'old_status': po[6]},
            {'new_status': new_status}
        )

    except Exception as e:
        logging.error(f"Error in update_purchase_order: {e}")
        print(f"An error occurred: {e}")

def receive_purchase_order():
    """Receive and process purchase order - FIXED"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to receive purchase orders.")
        return

    if not auth.check_permission('manage_inventory'):
        print("You don't have permission to receive purchase orders.")
        return

    try:
        backup_before_operation('receive_purchase_order')

        po_id = input("Enter purchase order ID to receive: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get PO details
        cursor.execute('SELECT * FROM restaurant_purchase_orders WHERE po_id = ?', (po_id,))
        po = cursor.fetchone()

        if not po:
            print("Purchase order not found.")
            conn.close()
            return

        if po[6] not in ['Ordered', 'Shipped']:
            print(f"Cannot receive PO with status: {po[6]}")
            conn.close()
            return

        # Get PO items
        cursor.execute('SELECT * FROM restaurant_purchase_order_items WHERE po_id = ?', (po_id,))
        po_items = cursor.fetchall()

        print(f"\nReceiving Purchase Order: {po_id}")
        print(f"Supplier: {po[1]}")
        print(f"Expected items: {len(po_items)}")

        for item in po_items:
            print(f"\nItem: {item[2]}")
            print(f"Expected quantity: {item[3]} {item[4]}")
            print(f"Received quantity so far: {item[7]}")

            try:
                received_qty = float(input(f"Enter quantity received for {item[2]}: "))
                if received_qty < 0:
                    received_qty = 0
            except ValueError:
                print("Invalid quantity, skipping item.")
                continue

            # Update received quantity
            total_received = item[7] + received_qty
            cursor.execute('''
                UPDATE restaurant_purchase_order_items
                SET received_quantity = ?
                WHERE id = ?
            ''', (total_received, item[0]))

            # Update inventory if item exists
            cursor.execute('SELECT item_id FROM restaurant_inventory WHERE name = ?', (item[2],))
            inventory_item = cursor.fetchone()

            if inventory_item:
                cursor.execute('''
                    UPDATE restaurant_inventory
                    SET quantity = quantity + ?, last_updated = ?
                    WHERE item_id = ?
                ''', (received_qty, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), inventory_item[0]))

                # Create inventory transaction
                transaction_id = f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"
                cursor.execute('''
                    INSERT INTO restaurant_inventory_transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    transaction_id, inventory_item[0], 'Stock In', received_qty,
                    item[5], po_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    f'Received from PO: {po_id}', auth.current_user['id']
                ))

        # Check if all items fully received
        cursor.execute('''
            SELECT COUNT(*) FROM restaurant_purchase_order_items
            WHERE po_id = ? AND received_quantity < quantity
        ''', (po_id,))

        pending_items = cursor.fetchone()[0]

        if pending_items == 0:
            # Mark PO as delivered
            cursor.execute('''
                UPDATE restaurant_purchase_orders
                SET status = ?, actual_delivery = ?
                WHERE po_id = ?
            ''', ('Delivered', datetime.now().strftime('%Y-%m-%d'), po_id))
            print("\n✅ All items received. Purchase order marked as delivered.")
        else:
            print(f"\n📦 Partial delivery received. {pending_items} items still pending.")

        conn.commit()
        conn.close()

        # Log audit action
        log_audit_action(
            auth.current_user['id'],
            'RECEIVE_PURCHASE_ORDER',
            'restaurant_purchase_orders',
            po_id,
            None,
            {'items_received': len(po_items), 'fully_received': pending_items == 0}
        )

    except Exception as e:
        logging.error(f"Error in receive_purchase_order: {e}")
        print(f"An error occurred: {e}")

def purchase_order_reports():
    """Purchase order reports - FIXED"""
    try:
        print("\n" + "="*50)
        print("PURCHASE ORDER REPORTS")
        print("="*50)

        print("\nReport options:")
        print("1. PO summary by status")
        print("2. Supplier performance")
        print("3. Delivery performance")
        print("4. PO value analysis")
        print("5. Return to purchase orders menu")

        choice = input("Choose option (1-5): ")

        conn = get_db_connection()
        cursor = conn.cursor()

        if choice == '1':
            # PO summary by status
            cursor.execute('''
                SELECT status, COUNT(*) as count, SUM(total_amount) as total_value
                FROM restaurant_purchase_orders
                GROUP BY status
                ORDER BY count DESC
            ''')

            status_data = cursor.fetchall()

            print("\nPurchase Order Summary by Status:")
            print("-"*50)
            print(f"{'Status':<15} {'Count':<8} {'Total Value':<15}")
            print("-"*50)

            for status, count, total_value in status_data:
                print(f"{status:<15} {count:<8} £{total_value:<14.2f}")

        elif choice == '2':
            # Supplier performance
            cursor.execute('''
                SELECT s.name, COUNT(po.po_id) as order_count,
                       SUM(po.total_amount) as total_value,
                       AVG(CASE WHEN po.actual_delivery IS NOT NULL AND po.expected_delivery IS NOT NULL
                           THEN julianday(po.actual_delivery) - julianday(po.expected_delivery)
                           ELSE NULL END) as avg_delay_days
                FROM restaurant_suppliers s
                LEFT JOIN restaurant_purchase_orders po ON s.supplier_id = po.supplier_id
                WHERE po.po_id IS NOT NULL
                GROUP BY s.supplier_id, s.name
                ORDER BY total_value DESC
            ''')

            supplier_data = cursor.fetchall()

            print("\nSupplier Performance:")
            print("-"*80)
            print(f"{'Supplier':<25} {'Orders':<8} {'Total Value':<15} {'Avg Delay (days)':<15}")
            print("-"*80)

            for supplier, orders, value, delay in supplier_data:
                delay_str = f"{delay:.1f}" if delay is not None else "N/A"
                print(f"{supplier:<25} {orders:<8} £{value:<14.2f} {delay_str:<15}")

        elif choice == '3':
            # Delivery performance
            cursor.execute('''
                SELECT
                    COUNT(*) as total_orders,
                    COUNT(CASE WHEN actual_delivery <= expected_delivery THEN 1 END) as on_time,
                    COUNT(CASE WHEN actual_delivery > expected_delivery THEN 1 END) as late,
                    COUNT(CASE WHEN actual_delivery IS NULL AND status != 'Cancelled' THEN 1 END) as pending
                FROM restaurant_purchase_orders
                WHERE expected_delivery IS NOT NULL
            ''')

            delivery_stats = cursor.fetchone()

            print("\nDelivery Performance:")
            print("-"*40)
            print(f"Total Orders: {delivery_stats[0]}")
            print(f"On Time: {delivery_stats[1]}")
            print(f"Late: {delivery_stats[2]}")
            print(f"Pending: {delivery_stats[3]}")

            if delivery_stats[0] > 0:
                on_time_pct = (delivery_stats[1] / delivery_stats[0]) * 100
                print(f"On-Time Percentage: {on_time_pct:.1f}%")

        elif choice == '4':
            # PO value analysis
            cursor.execute('''
                SELECT
                    COUNT(*) as total_pos,
                    SUM(total_amount) as total_value,
                    AVG(total_amount) as avg_value,
                    MIN(total_amount) as min_value,
                    MAX(total_amount) as max_value
                FROM restaurant_purchase_orders
            ''')

            value_stats = cursor.fetchone()

            print("\nPurchase Order Value Analysis:")
            print("-"*40)
            print(f"Total POs: {value_stats[0]}")
            print(f"Total Value: £{value_stats[1]:.2f}")
            print(f"Average Value: £{value_stats[2]:.2f}")
            print(f"Minimum Value: £{value_stats[3]:.2f}")
            print(f"Maximum Value: £{value_stats[4]:.2f}")

        elif choice == '5':
            conn.close()
            return
        else:
            print("Invalid choice.")

        conn.close()

    except Exception as e:
        logging.error(f"Error in purchase_order_reports: {e}")
        print(f"An error occurred: {e}")
