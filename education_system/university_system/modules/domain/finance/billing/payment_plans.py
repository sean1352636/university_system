from education_system.university_system.infrastructure.database.db import sqlite3
import os
import csv
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
import json
import hashlib
import hmac
import requests
import smtplib
import ssl
import threading
import schedule
import time
import warnings
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
from cryptography.fernet import Fernet
import logging
from flask import Flask, request, jsonify
import qrcode
from io import BytesIO
import base64
from education_system.university_system.infrastructure.email import send_email
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.infrastructure.logging.log_config import configure_logging, get_log_file
from education_system.university_system.infrastructure.email.template_utils import render_template
# Configure logging
log_path = get_log_file("analytics.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler()
    ]
)

logger = configure_logging(name=__name__)
warnings.filterwarnings('ignore')

try:
    auth = get_auth()
except Exception:
    auth = None
app = Flask(__name__)

# Initialize security headers for all responses
try:
    from education_system.university_system.infrastructure.security.flask_security_headers import init_security_headers
    init_security_headers(app)
except ImportError:
    pass  # Security headers module not available

# Encryption key for sensitive data
ENCRYPTION_KEY = Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

# Payment gateway configurations
PAYMENT_GATEWAYS = {
    'stripe': {
        'public_key': os.getenv('STRIPE_PUBLIC_KEY', ''),
        'secret_key': os.getenv('STRIPE_SECRET_KEY', ''),
        'webhook_secret': os.getenv('STRIPE_WEBHOOK_SECRET', '')
    },
    'paypal': {
        'client_id': os.getenv('PAYPAL_CLIENT_ID', ''),
        'client_secret': os.getenv('PAYPAL_CLIENT_SECRET', ''),
        'environment': os.getenv('PAYPAL_ENVIRONMENT', 'sandbox')
    }
}

# Currency exchange API configuration
# WARNING: Never commit real API keys to version control!
# Set these environment variables in your deployment environment
SUPPORTED_CURRENCIES = ['GBP', 'USD', 'EUR', 'CAD', 'AUD']
PAYMENT_GATEWAYS = {
    'stripe': {'public_key': '', 'secret_key': '', 'webhook_secret': ''},
    'paypal': {'client_id': '', 'client_secret': '', 'environment': 'sandbox'}
}
# Load exchange API key from environment variable
EXCHANGE_API_KEY = os.getenv('EXCHANGE_API_KEY', '')



def create_payment_plan():
    """Create a new payment plan for a student"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to create payment plans.")
        return

    if not auth.check_permission('manage_finances'):
        print("You don't have permission to create payment plans.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student ID
        student_id = input("Enter student ID: ").strip()
        if not student_exists(student_id):
            print(f"Student with ID {student_id} does not exist.")
            conn.close()
            return

        # Get outstanding fees
        cursor.execute('''
        SELECT sf.student_fee_id, ft.fee_name, sf.amount, sf.status, sf.due_date
        FROM student_fees sf
        JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
        WHERE sf.student_id = ? AND sf.status != 'paid'
        ORDER BY sf.due_date
        ''', (student_id,))

        outstanding_fees = cursor.fetchall()

        if not outstanding_fees:
            print(f"No outstanding fees found for student {student_id}.")
            conn.close()
            return

        # Calculate total outstanding amount
        total_outstanding = sum(fee[2] for fee in outstanding_fees)
        print(f"\nTotal outstanding amount: £{total_outstanding:.2f}")

        # Display available payment plan templates
        cursor.execute('''
        SELECT template_id, template_name, description, number_of_installments,
               installment_frequency, setup_fee, interest_rate
        FROM payment_plan_templates
        WHERE is_active = 1
        ORDER BY number_of_installments
        ''')

        templates = cursor.fetchall()

        if not templates:
            print("No payment plan templates available.")
            conn.close()
            return

        print("\nAvailable Payment Plan Templates:")
        for i, (template_id, name, desc, installments, frequency, setup_fee, interest) in enumerate(templates, 1):
            print(f"{i}. {name} - {installments} {frequency} payments")
            print(f"   Description: {desc}")
            print(f"   Setup fee: £{setup_fee:.2f}, Interest rate: {interest}%")

        # Select template
        template_choice = input("\nSelect payment plan template (number): ").strip()
        try:
            template_index = int(template_choice) - 1
            if 0 <= template_index < len(templates):
                selected_template = templates[template_index]
            else:
                print("Invalid selection.")
                conn.close()
                return
        except ValueError:
            print("Invalid input.")
            conn.close()
            return

        template_id, template_name, description, num_installments, frequency, setup_fee, interest_rate = selected_template

        # Calculate payment plan details
        principal_amount = total_outstanding
        interest_amount = principal_amount * (interest_rate / 100)
        total_with_interest = principal_amount + interest_amount + setup_fee
        installment_amount = total_with_interest / num_installments

        print(f"\nPayment Plan Details:")
        print(f"Template: {template_name}")
        print(f"Principal amount: £{principal_amount:.2f}")
        print(f"Setup fee: £{setup_fee:.2f}")
        print(f"Interest ({interest_rate}%): £{interest_amount:.2f}")
        print(f"Total amount: £{total_with_interest:.2f}")
        print(f"Number of installments: {num_installments}")
        print(f"Amount per installment: £{installment_amount:.2f}")

        confirm = input("\nCreate this payment plan? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Payment plan creation cancelled.")
            conn.close()
            return

        # Create the payment plan
        now = datetime.now()
        start_date = now.strftime('%Y-%m-%d')

        # Calculate next due date based on frequency
        if frequency == 'weekly':
            next_due = now + timedelta(weeks=1)
        elif frequency == 'monthly':
            next_due = now + timedelta(days=30)
        elif frequency == 'quarterly':
            next_due = now + timedelta(days=90)
        else:
            next_due = now + timedelta(days=30)  # Default to monthly

        next_due_date = next_due.strftime('%Y-%m-%d')

        cursor.execute('''
        INSERT INTO student_payment_plans
        (student_id, template_id, total_amount, remaining_amount, start_date,
         next_due_date, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (student_id, template_id, total_with_interest, total_with_interest,
              start_date, next_due_date, now.strftime('%Y-%m-%d %H:%M:%S'), now.strftime('%Y-%m-%d %H:%M:%S')))

        payment_plan_id = cursor.lastrowid

        # Create installments
        current_due_date = next_due
        for i in range(num_installments):
            cursor.execute('''
            INSERT INTO payment_plan_installments
            (payment_plan_id, installment_number, amount, due_date, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (payment_plan_id, i + 1, installment_amount, current_due_date.strftime('%Y-%m-%d'),
                  now.strftime('%Y-%m-%d %H:%M:%S'), now.strftime('%Y-%m-%d %H:%M:%S')))

            # Calculate next due date
            if frequency == 'weekly':
                current_due_date += timedelta(weeks=1)
            elif frequency == 'monthly':
                current_due_date += timedelta(days=30)
            elif frequency == 'quarterly':
                current_due_date += timedelta(days=90)

        conn.commit()

        print(f"\nPayment plan created successfully! Plan ID: {payment_plan_id}")
        print(f"First installment of £{installment_amount:.2f} is due on {next_due_date}")

        # Send notification
        send_payment_plan_notification(student_id, payment_plan_id, 'payment_plan_setup')

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def manage_payment_plans():
    """Manage existing payment plans"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to manage payment plans.")
        return

    if not auth.check_permission('manage_finances'):
        print("You don't have permission to manage payment plans.")
        return

    while True:
        print("\nPayment Plan Management:")
        print("1. View active payment plans")
        print("2. Create new payment plan")
        print("3. Modify payment plan")
        print("4. Process payment plan payment")
        print("5. Cancel payment plan")
        print("6. Return to Finance Menu")

        choice = input("Enter your choice (1-6): ").strip()

        if choice == '1':
            view_active_payment_plans()
        elif choice == '2':
            create_payment_plan()
        elif choice == '3':
            modify_payment_plan()
        elif choice == '4':
            process_payment_plan_payment()
        elif choice == '5':
            cancel_payment_plan()
        elif choice == '6':
            return
        else:
            print("Invalid choice. Please try again.")

def view_active_payment_plans():
    """View all active payment plans"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT spp.payment_plan_id, spp.student_id, s.first_name, s.last_name,
               spp.total_amount, spp.remaining_amount, spp.status, spp.next_due_date,
               ppt.template_name, ppt.number_of_installments
        FROM student_payment_plans spp
        JOIN students s ON spp.student_id = s.student_id
        JOIN payment_plan_templates ppt ON spp.template_id = ppt.template_id
        WHERE spp.status = 'active'
        ORDER BY spp.next_due_date
        ''')

        plans = cursor.fetchall()

        if not plans:
            print("No active payment plans found.")
            conn.close()
            return

        print("\nActive Payment Plans:")
        print("=" * 120)
        print(f"{'Plan ID':<8} {'Student ID':<12} {'Student Name':<25} {'Template':<20} {'Total':<12} {'Remaining':<12} {'Next Due':<12}")
        print("-" * 120)

        for plan in plans:
            plan_id, student_id, first_name, last_name, total, remaining, status, next_due, template, installments = plan
            student_name = f"{first_name} {last_name}"

            print(f"{plan_id:<8} {student_id:<12} {student_name:<25} {template:<20} £{total:<11.2f} £{remaining:<11.2f} {next_due:<12}")

        print("=" * 120)
        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def process_payment_plan_payment():
    """Process a payment against a payment plan"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to process payment plan payments.")
        return

    if not auth.check_permission('manage_finances'):
        print("You don't have permission to process payment plan payments.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get payment plan ID
        plan_id = input("Enter payment plan ID: ").strip()

        # Get payment plan details
        cursor.execute('''
        SELECT spp.payment_plan_id, spp.student_id, spp.remaining_amount, spp.next_due_date,
               s.first_name, s.last_name
        FROM student_payment_plans spp
        JOIN students s ON spp.student_id = s.student_id
        WHERE spp.payment_plan_id = ? AND spp.status = 'active'
        ''', (plan_id,))

        plan = cursor.fetchone()

        if not plan:
            print("Payment plan not found or not active.")
            conn.close()
            return

        plan_id, student_id, remaining_amount, next_due_date, first_name, last_name = plan
        student_name = f"{first_name} {last_name}"

        print(f"\nPayment Plan Details:")
        print(f"Student: {student_name} ({student_id})")
        print(f"Remaining amount: £{remaining_amount:.2f}")
        print(f"Next due date: {next_due_date}")

        # Get next installment details
        cursor.execute('''
        SELECT installment_id, installment_number, amount, due_date, status
        FROM payment_plan_installments
        WHERE payment_plan_id = ? AND status = 'pending'
        ORDER BY installment_number
        LIMIT 1
        ''', (plan_id,))

        installment = cursor.fetchone()

        if not installment:
            print("No pending installments found for this payment plan.")
            conn.close()
            return

        installment_id, installment_number, installment_amount, due_date, status = installment

        print(f"Next installment #{installment_number}: £{installment_amount:.2f} due on {due_date}")

        # Get payment amount
        while True:
            try:
                payment_amount = float(input(f"\nEnter payment amount (suggested: £{installment_amount:.2f}): "))
                if payment_amount <= 0:
                    print("Payment amount must be greater than zero.")
                    continue
                if payment_amount > remaining_amount:
                    print(f"Payment amount exceeds remaining balance (£{remaining_amount:.2f}).")
                    continue
                break
            except ValueError:
                print("Invalid input. Please enter a valid amount.")

        # Record the payment
        now = datetime.now()
        payment_date = now.strftime('%Y-%m-%d')

        cursor.execute('''
        INSERT INTO payments
        (student_id, amount, payment_method, payment_date, notes, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (student_id, payment_amount, 'Payment Plan', payment_date,
              f'Payment plan installment #{installment_number}',
              auth.current_user['username'], now.strftime('%Y-%m-%d %H:%M:%S')))

        payment_id = cursor.lastrowid

        # Update installment
        if payment_amount >= installment_amount:
            # Mark installment as paid
            cursor.execute('''
            UPDATE payment_plan_installments
            SET status = 'paid', payment_id = ?, updated_at = ?
            WHERE installment_id = ?
            ''', (payment_id, now.strftime('%Y-%m-%d %H:%M:%S'), installment_id))

            # If overpayment, apply to next installment or create credit
            overpayment = payment_amount - installment_amount
            if overpayment > 0:
                print(f"Overpayment of £{overpayment:.2f} will be applied to next installment.")
        else:
            # Partial payment - create adjustment
            print(f"Partial payment of £{payment_amount:.2f} recorded.")

        # Update payment plan remaining amount
        new_remaining = remaining_amount - payment_amount

        # Check if payment plan is completed
        if new_remaining <= 0:
            cursor.execute('''
            UPDATE student_payment_plans
            SET status = 'completed', remaining_amount = 0, updated_at = ?
            WHERE payment_plan_id = ?
            ''', (now.strftime('%Y-%m-%d %H:%M:%S'), plan_id))
            print("Payment plan completed!")
        else:
            # Update remaining amount and next due date
            cursor.execute('''
            SELECT due_date FROM payment_plan_installments
            WHERE payment_plan_id = ? AND status = 'pending'
            ORDER BY installment_number
            LIMIT 1
            ''', (plan_id,))

            next_installment = cursor.fetchone()
            next_due = next_installment[0] if next_installment else None

            cursor.execute('''
            UPDATE student_payment_plans
            SET remaining_amount = ?, next_due_date = ?, updated_at = ?
            WHERE payment_plan_id = ?
            ''', (new_remaining, next_due, now.strftime('%Y-%m-%d %H:%M:%S'), plan_id))

        conn.commit()
        print(f"Payment of £{payment_amount:.2f} processed successfully!")
        print(f"Remaining balance: £{new_remaining:.2f}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def send_payment_plan_notification(student_id, payment_plan_id, template="default"):
    """Send payment plan setup notification to student via email."""
    # This assumes you have a get_student_name and a way to fetch student email
    name = get_student_name(student_id)
    email = get_student_email(student_id)  # You'll need this function

    template_vars = {
        'name': name,
        'payment_plan_id': payment_plan_id
    }
    subject, body = render_template('payment_plan_confirmation', template_vars)
    send_email_notification(email, subject, body)

def modify_payment_plan():
    """Modify an existing payment plan"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to modify payment plans.")
        return

    if not auth.check_permission('manage_finances'):
        print("You don't have permission to modify payment plans.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get payment plan ID
        plan_id = input("Enter payment plan ID to modify: ").strip()

        # Get payment plan details
        cursor.execute('''
        SELECT spp.payment_plan_id, spp.student_id, spp.total_amount, spp.remaining_amount,
               spp.status, spp.next_due_date, s.first_name, s.last_name, ppt.template_name
        FROM student_payment_plans spp
        JOIN students s ON spp.student_id = s.student_id
        JOIN payment_plan_templates ppt ON spp.template_id = ppt.template_id
        WHERE spp.payment_plan_id = ?
        ''', (plan_id,))

        plan = cursor.fetchone()

        if not plan:
            print("Payment plan not found.")
            conn.close()
            return

        plan_id, student_id, total_amount, remaining_amount, status, next_due_date, first_name, last_name, template_name = plan
        student_name = f"{first_name} {last_name}"

        print(f"\nPayment Plan Details:")
        print(f"Plan ID: {plan_id}")
        print(f"Student: {student_name} ({student_id})")
        print(f"Template: {template_name}")
        print(f"Total Amount: £{total_amount:.2f}")
        print(f"Remaining: £{remaining_amount:.2f}")
        print(f"Status: {status}")
        print(f"Next Due: {next_due_date}")

        print("\nModification Options:")
        print("1. Adjust payment amount")
        print("2. Change due dates")
        print("3. Pause payment plan")
        print("4. Resume payment plan")
        print("5. Add notes")

        choice = input("Select modification (1-5): ").strip()

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if choice == '1':
            # Adjust payment amount
            new_total = float(input(f"Enter new total amount (current: £{total_amount:.2f}): £"))

            cursor.execute('''
            UPDATE student_payment_plans
            SET total_amount = ?, remaining_amount = ?, updated_at = ?
            WHERE payment_plan_id = ?
            ''', (new_total, new_total, now, plan_id))

            print(f"Payment plan amount updated to £{new_total:.2f}")

        elif choice == '2':
            # Change due dates
            new_due_date = input(f"Enter new next due date (YYYY-MM-DD, current: {next_due_date}): ").strip()

            cursor.execute('''
            UPDATE student_payment_plans
            SET next_due_date = ?, updated_at = ?
            WHERE payment_plan_id = ?
            ''', (new_due_date, now, plan_id))

            print(f"Next due date updated to {new_due_date}")

        elif choice == '3':
            # Pause payment plan
            cursor.execute('''
            UPDATE student_payment_plans
            SET status = 'paused', updated_at = ?
            WHERE payment_plan_id = ?
            ''', (now, plan_id))

            print("Payment plan paused")

        elif choice == '4':
            # Resume payment plan
            cursor.execute('''
            UPDATE student_payment_plans
            SET status = 'active', updated_at = ?
            WHERE payment_plan_id = ?
            ''', (now, plan_id))

            print("Payment plan resumed")

        elif choice == '5':
            # Add notes
            notes = input("Enter notes: ").strip()

            cursor.execute('''
            UPDATE student_payment_plans
            SET notes = COALESCE(notes, '') || ' | ' || ?, updated_at = ?
            WHERE payment_plan_id = ?
            ''', (notes, now, plan_id))

            print("Notes added to payment plan")

        conn.commit()
        conn.close()

    except Exception as e:
        print(f"Error modifying payment plan: {e}")

def cancel_payment_plan():
    """Cancel a payment plan"""
    global auth

    try:
        conn = get_connection()
        cursor = conn.cursor()

        plan_id = input("Enter payment plan ID to cancel: ").strip()

        # Get payment plan details
        cursor.execute('''
        SELECT spp.student_id, spp.remaining_amount, s.first_name, s.last_name
        FROM student_payment_plans spp
        JOIN students s ON spp.student_id = s.student_id
        WHERE spp.payment_plan_id = ? AND spp.status != 'cancelled'
        ''', (plan_id,))

        plan = cursor.fetchone()

        if not plan:
            print("Payment plan not found or already cancelled.")
            conn.close()
            return

        student_id, remaining_amount, first_name, last_name = plan
        student_name = f"{first_name} {last_name}"

        print(f"\nCancelling Payment Plan {plan_id}")
        print(f"Student: {student_name} ({student_id})")
        print(f"Remaining Amount: £{remaining_amount:.2f}")

        reason = input("Enter cancellation reason: ").strip()
        if not reason:
            print("Cancellation reason is required.")
            return

        confirm = input("Confirm cancellation? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Cancellation aborted.")
            return

        # Cancel the payment plan
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        UPDATE student_payment_plans
        SET status = 'cancelled', updated_at = ?,
            notes = COALESCE(notes, '') || ' | CANCELLED: ' || ?
        WHERE payment_plan_id = ?
        ''', (now, reason, plan_id))

        # Cancel pending installments
        cursor.execute('''
        UPDATE payment_plan_installments
        SET status = 'cancelled', updated_at = ?
        WHERE payment_plan_id = ? AND status = 'pending'
        ''', (now, plan_id))

        conn.commit()

        print(f"Payment plan {plan_id} cancelled successfully")
        print(f"Reason: {reason}")

        # Log the action
        log_audit_action('cancel_payment_plan', 'student_payment_plans', str(plan_id), {
            'student_id': student_id,
            'reason': reason,
            'cancelled_by': auth.current_user['username']
        })

        conn.close()

    except Exception as e:
        print(f"Error cancelling payment plan: {e}")
