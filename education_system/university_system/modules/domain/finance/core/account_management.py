from education_system.university_system.infrastructure.database.db import sqlite3
import os
import csv
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns

# Import immutable audit logging for compliance
try:
    from education_system.university_system.infrastructure.security.audit_helpers import safe_log_security_event
    from education_system.university_system.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False
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
from education_system.university_system.modules.domain.finance.core.students import student_exists, get_student_name

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



def assign_fees_to_student():
    """Assign fees to a student"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to assign fees.")
        return

    if not auth.check_permission('manage_finances'):
        print("You don't have permission to assign fees.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id = input("Enter student ID: ").strip()
        if not student_exists(student_id):
            print(f"Student with ID {student_id} does not exist.")
            conn.close()
            return

        # Get available fee types
        cursor.execute('''
        SELECT fee_type_id, fee_name, description
        FROM fee_types
        ORDER BY fee_name
        ''')

        fee_types = cursor.fetchall()

        if not fee_types:
            print("No fee types available.")
            conn.close()
            return

        print(f"\nAvailable Fee Types:")
        for i, (fee_id, fee_name, description) in enumerate(fee_types, 1):
            print(f"{i}. {fee_name} - {description}")

        fee_choice = input("Select fee type (number): ").strip()
        try:
            fee_index = int(fee_choice) - 1
            if 0 <= fee_index < len(fee_types):
                selected_fee = fee_types[fee_index]
                fee_type_id = selected_fee[0]
            else:
                print("Invalid selection.")
                conn.close()
                return
        except ValueError:
            print("Invalid input.")
            conn.close()
            return

        amount = float(input("Enter fee amount: £"))
        due_date = input("Enter due date (YYYY-MM-DD): ").strip()

        # Create student fee
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO student_fees
        (student_id, fee_type_id, amount, due_date, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (student_id, fee_type_id, amount, due_date, now, now))

        fee_id = cursor.lastrowid

        conn.commit()

        # Immutable audit log for fee assignment
        if IMMUTABLE_AUDIT_AVAILABLE:
            admin_id = str(auth.current_user.get('id', '')) if auth and auth.current_user else 'system'
            safe_log_security_event(
                action=AuditAction.RECORD_CREATE,
                user_id=admin_id,
                resource_type='student_fee',
                resource_id=str(fee_id),
                details={
                    'student_id': student_id,
                    'fee_type_id': fee_type_id,
                    'amount': amount,
                    'due_date': due_date
                }
            )

        print(f"Fee assigned successfully! Fee ID: {fee_id}")
        print(f"Student: {get_student_name(student_id)}")
        print(f"Amount: £{amount:.2f}")
        print(f"Due Date: {due_date}")

        conn.close()

    except Exception as e:
        print(f"Error assigning fee: {e}")

def record_payment():
    """Record a payment from a student"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to record payments.")
        return

    if not auth.check_permission('manage_finances'):
        print("You don't have permission to record payments.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id = input("Enter student ID: ").strip()
        if not student_exists(student_id):
            print(f"Student with ID {student_id} does not exist.")
            conn.close()
            return

        amount = float(input("Enter payment amount: £"))
        payment_method = input("Enter payment method (Cash/Card/Bank Transfer): ").strip()
        payment_date = input("Enter payment date (YYYY-MM-DD) or press Enter for today: ").strip()

        if not payment_date:
            payment_date = datetime.now().strftime('%Y-%m-%d')

        transaction_id = input("Enter transaction ID (optional): ").strip()
        notes = input("Enter notes (optional): ").strip()

        # Record payment
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO payments
        (student_id, amount, payment_method, payment_date, transaction_id, notes, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (student_id, amount, payment_method, payment_date, transaction_id, notes,
              auth.current_user['username'], now))

        payment_id = cursor.lastrowid

        # Get outstanding fees to allocate payment
        cursor.execute('''
        SELECT sf.student_fee_id, ft.fee_name, sf.amount,
               COALESCE(SUM(pa.amount), 0) as paid_amount,
               (sf.amount - COALESCE(SUM(pa.amount), 0)) as outstanding
        FROM student_fees sf
        JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
        LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
        WHERE sf.student_id = ? AND sf.status != 'paid'
        GROUP BY sf.student_fee_id
        HAVING outstanding > 0
        ORDER BY sf.due_date
        ''', (student_id,))

        outstanding_fees = cursor.fetchall()

        if outstanding_fees:
            print(f"\nAllocating payment to outstanding fees:")
            remaining_payment = amount

            for fee_id, fee_name, total_amount, paid_amount, outstanding in outstanding_fees:
                if remaining_payment <= 0:
                    break

                allocation_amount = min(remaining_payment, outstanding)

                # Create payment allocation
                cursor.execute('''
                INSERT INTO payment_allocations
                (payment_id, student_fee_id, amount, created_at)
                VALUES (?, ?, ?, ?)
                ''', (payment_id, fee_id, allocation_amount, now))

                # Update fee status
                new_paid_amount = paid_amount + allocation_amount
                new_status = 'paid' if new_paid_amount >= total_amount else 'partial'

                cursor.execute('''
                UPDATE student_fees
                SET status = ?, updated_at = ?
                WHERE student_fee_id = ?
                ''', (new_status, now, fee_id))

                remaining_payment -= allocation_amount
                print(f"  Allocated £{allocation_amount:.2f} to {fee_name}")

            if remaining_payment > 0:
                print(f"  Overpayment: £{remaining_payment:.2f} (creating credit)")
                # Create credit for overpayment
                cursor.execute('''
                INSERT INTO student_credits
                (student_id, credit_amount, remaining_amount, credit_source, description, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, remaining_payment, remaining_payment, 'overpayment',
                      f'Overpayment from payment ID {payment_id}', auth.current_user['username'], now, now))

        conn.commit()

        # Immutable audit log for payment recording
        if IMMUTABLE_AUDIT_AVAILABLE:
            admin_id = str(auth.current_user.get('id', '')) if auth and auth.current_user else 'system'
            safe_log_security_event(
                action=AuditAction.RECORD_CREATE,
                user_id=admin_id,
                resource_type='payment',
                resource_id=str(payment_id),
                details={
                    'student_id': student_id,
                    'amount': amount,
                    'payment_method': payment_method,
                    'transaction_id': transaction_id
                }
            )

        print(f"\nPayment recorded successfully! Payment ID: {payment_id}")
        print(f"Student: {get_student_name(student_id)}")
        print(f"Amount: £{amount:.2f}")
        print(f"Method: {payment_method}")
        print(f"Date: {payment_date}")

        conn.close()

    except Exception as e:
        print(f"Error recording payment: {e}")

def generate_invoice():
    """Generate an invoice for a student"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to generate invoices.")
        return

    if not auth.check_permission('manage_finances'):
        print("You don't have permission to generate invoices.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id = input("Enter student ID: ").strip()
        if not student_exists(student_id):
            print(f"Student with ID {student_id} does not exist.")
            conn.close()
            return

        # Get student details
        cursor.execute('''
        SELECT first_name, last_name, email_address, course
        FROM students
        WHERE student_id = ?
        ''', (student_id,))

        student = cursor.fetchone()
        first_name, last_name, email, course = student

        # Get outstanding fees
        cursor.execute('''
        SELECT ft.fee_name, sf.amount, sf.due_date, sf.status
        FROM student_fees sf
        JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
        WHERE sf.student_id = ? AND sf.status != 'paid'
        ORDER BY sf.due_date
        ''', (student_id,))

        fees = cursor.fetchall()

        if not fees:
            print(f"No outstanding fees for student {student_id}")
            conn.close()
            return

        # Create invoice content
        invoice_date = datetime.now().strftime('%Y-%m-%d')
        invoice_number = f"INV-{student_id}-{datetime.now().strftime('%Y%m%d')}"

        invoice_content = f"""

INVOICE
===============================================

Invoice Number: {invoice_number}
Invoice Date: {invoice_date}

BILL TO:
{first_name} {last_name}
Student ID: {student_id}
Course: {course}
Email: {email}

ITEMIZED CHARGES:
===============================================
"""

        total_amount = 0
        for fee_name, amount, due_date, status in fees:
            invoice_content += f"{fee_name:<30} £{amount:>10.2f}  Due: {due_date}\n"
            total_amount += amount

        invoice_content += f"""
===============================================
TOTAL AMOUNT DUE:                £{total_amount:>10.2f}
===============================================

PAYMENT INSTRUCTIONS:
- Payment can be made online via student portal
- Bank transfer details available on request
- For payment plans, contact finance office

Thank you for your prompt payment.
        """

        print(invoice_content)

        # Save invoice to file
        filename = f"invoice_{invoice_number}.txt"
        with open(filename, 'w') as f:
            f.write(invoice_content)

        print(f"\nInvoice saved as {filename}")

        # Send invoice via email (simulated)
        send_email_notification(email, f"Invoice {invoice_number}", invoice_content)

        conn.close()

    except Exception as e:
        print(f"Error generating invoice: {e}")

def view_student_financial_statement():
    """View complete financial statement for a student"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id = input("Enter student ID: ").strip()
        if not student_exists(student_id):
            print(f"Student with ID {student_id} does not exist.")
            conn.close()
            return

        # Get student details
        cursor.execute('''
        SELECT first_name, last_name, email_address, course, enrollment_date, status
        FROM students
        WHERE student_id = ?
        ''', (student_id,))

        student = cursor.fetchone()
        first_name, last_name, email, course, enrollment_date, status = student

        print(f"\n" + "=" * 80)
        print(f"FINANCIAL STATEMENT")
        print(f"=" * 80)
        print(f"Student: {first_name} {last_name}")
        print(f"Student ID: {student_id}")
        print(f"Course: {course}")
        print(f"Enrollment Date: {enrollment_date}")
        print(f"Status: {status}")
        print(f"Statement Date: {datetime.now().strftime('%Y-%m-%d')}")
        print(f"=" * 80)

        # Get all fees
        cursor.execute('''
        SELECT ft.fee_name, sf.amount, sf.due_date, sf.status, sf.created_at
        FROM student_fees sf
        JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
        WHERE sf.student_id = ?
        ORDER BY sf.created_at
        ''', (student_id,))

        fees = cursor.fetchall()

        print(f"\nFEES CHARGED:")
        print(f"-" * 80)
        total_fees = 0
        for fee_name, amount, due_date, fee_status, created_at in fees:
            status_indicator = "✓" if fee_status == 'paid' else "○" if fee_status == 'partial' else "×"
            print(f"{status_indicator} {fee_name:<30} £{amount:>10.2f}  Due: {due_date}")
            total_fees += amount

        print(f"-" * 80)
        print(f"Total Fees Charged: £{total_fees:>10.2f}")

        # Get all payments
        cursor.execute('''
        SELECT amount, payment_method, payment_date, transaction_id
        FROM payments
        WHERE student_id = ? AND status = 'completed'
        ORDER BY payment_date
        ''', (student_id,))

        payments = cursor.fetchall()

        print(f"\nPAYMENTS RECEIVED:")
        print(f"-" * 80)
        total_payments = 0
        for amount, method, date, trans_id in payments:
            trans_display = trans_id if trans_id else "N/A"
            print(f"{date} {method:<15} £{amount:>10.2f}  Ref: {trans_display}")
            total_payments += amount

        print(f"-" * 80)
        print(f"Total Payments: £{total_payments:>10.2f}")

        # Get credits
        cursor.execute('''
        SELECT credit_amount, remaining_amount, credit_source, created_at, status
        FROM student_credits
        WHERE student_id = ?
        ORDER BY created_at
        ''', (student_id,))

        credits = cursor.fetchall()

        if credits:
            print(f"\nCREDITS:")
            print(f"-" * 80)
            total_credits = 0
            active_credits = 0
            for credit_amount, remaining, source, created_at, credit_status in credits:
                status_display = credit_status.upper()
                print(f"{created_at} {source:<15} £{credit_amount:>10.2f}  Remaining: £{remaining:.2f} ({status_display})")
                total_credits += credit_amount
                if credit_status == 'active':
                    active_credits += remaining

            print(f"-" * 80)
            print(f"Total Credits Issued: £{total_credits:>10.2f}")
            print(f"Active Credits Available: £{active_credits:>10.2f}")

        # Calculate balance
        balance = total_fees - total_payments

        print(f"\n" + "=" * 80)
        print(f"ACCOUNT SUMMARY:")
        print(f"Total Fees: £{total_fees:>10.2f}")
        print(f"Total Payments: £{total_payments:>10.2f}")
        if credits:
            print(f"Available Credits: £{active_credits:>10.2f}")
        print(f"-" * 30)
        if balance > 0:
            print(f"BALANCE DUE: £{balance:>10.2f}")
        elif balance < 0:
            print(f"CREDIT BALANCE: £{abs(balance):>10.2f}")
        else:
            print(f"ACCOUNT BALANCE: £0.00")
        print(f"=" * 80)

        conn.close()

    except Exception as e:
        print(f"Error viewing financial statement: {e}")

def process_refund():
    """Process a refund for a student"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to process refunds.")
        return

    if not auth.check_permission('manage_finances'):
        print("You don't have permission to process refunds.")
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

        # Get student's payment history
        cursor.execute('''
        SELECT p.payment_id, p.amount, p.payment_method, p.payment_date, p.transaction_id
        FROM payments p
        WHERE p.student_id = ? AND p.status = 'completed'
        ORDER BY p.payment_date DESC
        ''', (student_id,))

        payments = cursor.fetchall()

        if not payments:
            print(f"No payments found for student {student_id}.")
            conn.close()
            return

        print(f"\nPayment history for student {student_id} ({get_student_name(student_id)}):")
        for i, (payment_id, amount, method, date, transaction_id) in enumerate(payments, 1):
            trans_id = transaction_id if transaction_id else "N/A"
            print(f"{i}. Payment ID {payment_id} - £{amount:.2f} via {method} on {date} (Ref: {trans_id})")

        print(f"{len(payments) + 1}. Create refund without specific payment reference")

        # Select payment for refund
        payment_choice = input("\nSelect payment to refund (number): ").strip()

        original_payment_id = None
        if payment_choice != str(len(payments) + 1):
            try:
                payment_index = int(payment_choice) - 1
                if 0 <= payment_index < len(payments):
                    original_payment_id = payments[payment_index][0]
                    original_amount = payments[payment_index][1]
                    print(f"Selected payment of £{original_amount:.2f}")
                else:
                    print("Invalid selection.")
                    conn.close()
                    return
            except ValueError:
                print("Invalid input.")
                conn.close()
                return

        # Get refund details
        refund_types = ['full', 'partial', 'withdrawal', 'overpayment']
        print("\nRefund types:")
        for i, refund_type in enumerate(refund_types, 1):
            print(f"{i}. {refund_type.title()}")

        type_choice = input("Select refund type (1-4): ").strip()
        try:
            type_index = int(type_choice) - 1
            if 0 <= type_index < len(refund_types):
                refund_type = refund_types[type_index]
            else:
                print("Invalid selection.")
                conn.close()
                return
        except ValueError:
            print("Invalid input.")
            conn.close()
            return

        # Get refund amount
        while True:
            try:
                refund_amount = float(input("Enter refund amount (£): "))
                if refund_amount <= 0:
                    print("Refund amount must be greater than zero.")
                    continue
                if original_payment_id and refund_amount > original_amount:
                    print(f"Refund amount cannot exceed original payment (£{original_amount:.2f}).")
                    continue
                break
            except ValueError:
                print("Invalid input. Please enter a valid amount.")

        # Get refund reason
        reason = input("Enter refund reason: ").strip()
        if not reason:
            print("Refund reason is required.")
            conn.close()
            return

        # Get refund method
        refund_methods = ['bank_transfer', 'original_payment_method', 'check', 'cash']
        print("\nRefund methods:")
        for i, method in enumerate(refund_methods, 1):
            print(f"{i}. {method.replace('_', ' ').title()}")

        method_choice = input("Select refund method (1-4): ").strip()
        try:
            method_index = int(method_choice) - 1
            if 0 <= method_index < len(refund_methods):
                refund_method = refund_methods[method_index]
            else:
                print("Invalid selection.")
                conn.close()
                return
        except ValueError:
            print("Invalid input.")
            conn.close()
            return

        # Create refund request
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        request_date = datetime.now().strftime('%Y-%m-%d')

        cursor.execute('''
        INSERT INTO unified_refunds
        (source_type, reference_type, reference_id, student_id, amount, original_amount,
         currency, refund_type, refund_method, reason, status, department,
         requested_by, request_date, created_at)
        VALUES ('general', 'payment', ?, ?, ?, ?, 'GBP', ?, ?, ?, 'pending', 'finance',
                ?, ?, ?)
        ''', (original_payment_id, student_id, refund_amount, refund_amount,
              refund_type, refund_method, reason, auth.current_user['username'], request_date, now))

        refund_id = cursor.lastrowid

        # If user has approval permissions, can approve immediately
        if auth.check_permission('approve_refunds'):
            approve_now = input("\nApprove this refund now? (y/n): ").strip().lower()
            if approve_now == 'y':
                cursor.execute('''
                UPDATE unified_refunds
                SET status = 'approved', approved_by = ?, approval_date = ?
                WHERE refund_id = ?
                ''', (auth.current_user['username'], request_date, refund_id))
                print("Refund approved and ready for processing.")

        conn.commit()

        # Immutable audit log for refund processing
        if IMMUTABLE_AUDIT_AVAILABLE:
            admin_id = str(auth.current_user.get('id', '')) if auth and auth.current_user else 'system'
            safe_log_security_event(
                action=AuditAction.RECORD_CREATE,
                user_id=admin_id,
                resource_type='refund',
                resource_id=str(refund_id),
                details={
                    'student_id': student_id,
                    'refund_amount': refund_amount,
                    'refund_type': refund_type,
                    'refund_method': refund_method,
                    'reason': reason,
                    'original_payment_id': original_payment_id
                }
            )

        print(f"\nRefund request created successfully! Refund ID: {refund_id}")
        print(f"Amount: £{refund_amount:.2f}")
        print(f"Method: {refund_method.replace('_', ' ').title()}")
        print(f"Status: {'Approved' if auth.check_permission('approve_refunds') and approve_now == 'y' else 'Pending Approval'}")

        # Log the action
        log_audit_action('create_refund', 'unified_refunds', str(refund_id),
                        {'student_id': student_id, 'amount': refund_amount, 'type': refund_type})

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

@app.route('/api/payments', methods=['POST'])
def api_record_payment():
    """API endpoint to record a payment"""
    try:
        verify_jwt_in_request()

        data = request.get_json()
        required_fields = ['student_id', 'amount', 'payment_method']

        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400

        conn = get_connection()
        cursor = conn.cursor()

        # Record payment
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        payment_date = data.get('payment_date', datetime.now().strftime('%Y-%m-%d'))

        cursor.execute('''
        INSERT INTO payments
        (student_id, amount, payment_method, payment_date, transaction_id, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (data['student_id'], data['amount'], data['payment_method'],
              payment_date, data.get('transaction_id'), data.get('notes'), now))

        payment_id = cursor.lastrowid

        conn.commit()
        conn.close()

        return jsonify({
            'payment_id': payment_id,
            'status': 'success',
            'message': 'Payment recorded successfully'
        })

    except Exception as e:
        logger.error("Payment recording failed: %s", e)
        return jsonify({'error': 'Internal server error'}), 500

def manage_student_credits():
    """Manage student credit balances"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to manage student credits.")
        return

    if not auth.check_permission('manage_finances'):
        print("You don't have permission to manage student credits.")
        return

    while True:
        print("\nStudent Credits Management:")
        print("1. View student credits")
        print("2. Add credit to student account")
        print("3. Apply credit to outstanding fees")
        print("4. View credit history")
        print("5. Return to Finance Menu")

        choice = input("Enter your choice (1-5): ").strip()

        if choice == '1':
            view_student_credits()
        elif choice == '2':
            add_student_credit()
        elif choice == '3':
            apply_credit_to_fees()
        elif choice == '4':
            view_credit_history()
        elif choice == '5':
            return
        else:
            print("Invalid choice. Please try again.")
