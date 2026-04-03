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
from education_system.university_system.utils.logging.log_config import configure_logging, get_log_file
from education_system.university_system.modules.shared.utils.i18n import get_text
from education_system.university_system.modules.domain.finance.core.students import student_exists, get_student_name
from education_system.university_system.modules.domain.finance.core.security_automation import log_audit_action
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



def calculate_late_fees():
    """Calculate and apply late fees for overdue payments"""
    global auth

    if not auth or not auth.current_user:
        print(get_text("finance.fee_structure.login_required_late_fees"))
        return

    if not auth.check_permission('manage_finances'):
        print(get_text("finance.fee_structure.permission_denied_late_fees"))
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        current_date = datetime.now().date()

        # Find overdue fees
        cursor.execute('''
        SELECT sf.student_fee_id, sf.student_id, sf.amount, sf.due_date, sf.status,
               ft.fee_name, ft.late_fee_calculation, ft.late_fee_amount, ft.grace_period_days,
               s.first_name, s.last_name
        FROM student_fees sf
        JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
        JOIN students s ON sf.student_id = s.student_id
        WHERE sf.status IN ('unpaid', 'partial')
        AND sf.due_date IS NOT NULL
        AND date(sf.due_date) < date('now')
        AND ft.late_fee_amount > 0
        ''')

        overdue_fees = cursor.fetchall()

        if not overdue_fees:
            print(get_text("finance.fee_structure.no_overdue_fees"))
            conn.close()
            return

        late_fees_applied = 0
        total_late_fees = 0

        print(get_text("finance.fee_structure.calculating_late_fees", count=len(overdue_fees)))

        for fee_data in overdue_fees:
            (student_fee_id, student_id, amount, due_date, status, fee_name,
             calculation_method, late_fee_amount, grace_period_days, first_name, last_name) = fee_data

            # Parse due date
            due_date_obj = datetime.strptime(due_date, '%Y-%m-%d').date()
            days_overdue = (current_date - due_date_obj).days

            # Apply grace period
            if grace_period_days and days_overdue <= grace_period_days:
                continue

            effective_days_overdue = days_overdue - (grace_period_days or 0)

            # Check if late fee already applied for this period
            cursor.execute('''
            SELECT COUNT(*) FROM late_fees
            WHERE student_fee_id = ? AND applied_date = ?
            ''', (student_fee_id, current_date.strftime('%Y-%m-%d')))

            if cursor.fetchone()[0] > 0:
                continue  # Late fee already applied today

            # Calculate late fee based on method
            calculated_late_fee = 0

            if calculation_method == 'fixed':
                calculated_late_fee = late_fee_amount
            elif calculation_method == 'percentage':
                calculated_late_fee = amount * (late_fee_amount / 100)
            elif calculation_method == 'daily':
                calculated_late_fee = late_fee_amount * effective_days_overdue

            if calculated_late_fee > 0:
                # Apply late fee
                cursor.execute('''
                INSERT INTO late_fees
                (student_fee_id, late_fee_amount, calculation_method, days_overdue, applied_date, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (student_fee_id, calculated_late_fee, calculation_method, effective_days_overdue,
                      current_date.strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                late_fees_applied += 1
                total_late_fees += calculated_late_fee

                print(get_text("finance.fee_structure.applied_late_fee", amount=calculated_late_fee, first_name=first_name, last_name=last_name, fee_name=fee_name, days=effective_days_overdue))

        conn.commit()

        print(get_text("finance.fee_structure.late_fee_calculation_completed"))
        print(get_text("finance.fee_structure.late_fees_applied_count", count=late_fees_applied))
        print(get_text("finance.fee_structure.total_late_fees", amount=total_late_fees))

        conn.close()

    except sqlite3.Error as e:
        print(get_text("finance.fee_structure.database_error", error=e))

def waive_late_fee():
    """Waive a late fee for a student"""
    global auth

    if not auth or not auth.current_user:
        print(get_text("finance.fee_structure.login_required_waive"))
        return

    if not auth.check_permission('manage_finances'):
        print(get_text("finance.fee_structure.permission_denied_waive"))
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student ID
        student_id = input(get_text("finance.fee_structure.enter_student_id")).strip()

        if not student_exists(student_id):
            print(get_text("finance.fee_structure.student_not_found", student_id=student_id))
            conn.close()
            return

        # Get late fees for this student
        cursor.execute('''
        SELECT lf.late_fee_id, lf.late_fee_amount, lf.applied_date, lf.waived,
               ft.fee_name, sf.amount
        FROM late_fees lf
        JOIN student_fees sf ON lf.student_fee_id = sf.student_fee_id
        JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
        WHERE sf.student_id = ? AND lf.waived = 0
        ORDER BY lf.applied_date DESC
        ''', (student_id,))

        late_fees = cursor.fetchall()

        if not late_fees:
            print(f"No active late fees found for student {student_id}.")
            conn.close()
            return

        print(f"\nLate fees for student {student_id} ({get_student_name(student_id)}):")
        for i, (late_fee_id, amount, applied_date, waived, fee_name, original_amount) in enumerate(late_fees, 1):
            print(f"{i}. {fee_name} - Late fee: £{amount:.2f} (applied on {applied_date})")

        # Select late fee to waive
        fee_choice = input("\nEnter late fee number to waive (or 'all' for all fees): ").strip()

        if fee_choice.lower() == 'all':
            selected_fees = late_fees
        else:
            try:
                fee_index = int(fee_choice) - 1
                if 0 <= fee_index < len(late_fees):
                    selected_fees = [late_fees[fee_index]]
                else:
                    print("Invalid selection.")
                    conn.close()
                    return
            except ValueError:
                print("Invalid input.")
                conn.close()
                return

        # Get waiver reason
        reason = input("Enter reason for waiving late fee(s): ").strip()
        if not reason:
            print("Waiver reason is required.")
            conn.close()
            return

        # Waive selected late fees
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        total_waived = 0

        for late_fee_data in selected_fees:
            late_fee_id, amount, applied_date, waived, fee_name, original_amount = late_fee_data

            cursor.execute('''
            UPDATE late_fees
            SET waived = 1, waived_by = ?, waived_date = ?, waiver_reason = ?
            WHERE late_fee_id = ?
            ''', (auth.current_user['username'], now, reason, late_fee_id))

            total_waived += amount
            print(f"Waived late fee of £{amount:.2f} for {fee_name}")

        conn.commit()

        print(f"\nTotal late fees waived: £{total_waived:.2f}")
        print(f"Reason: {reason}")

        # Log the action
        log_audit_action('waive_late_fee', 'late_fees', str(late_fee_id),
                        {'student_id': student_id, 'amount_waived': total_waived, 'reason': reason})

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def update_exchange_rates():
    """Update exchange rates from external API"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to update exchange rates.")
        return

    if not auth.check_permission('manage_finances'):
        print("You don't have permission to update exchange rates.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get base currency
        cursor.execute('SELECT base_currency FROM currency_settings LIMIT 1')
        result = cursor.fetchone()
        base_currency = result[0] if result else 'GBP'

        print(f"Updating exchange rates from {base_currency}...")

        # Simulate API call (replace with actual API integration)
        # Example using exchangerate-api.com
        # api_url = f"https://api.exchangerate-api.com/v4/latest/{base_currency}"

        try:
            # In production, you would make an actual API call
            # For demo, using sample rates
            sample_rates = {
                'USD': 1.27,
                'EUR': 1.17,
                'CAD': 1.71,
                'AUD': 1.91,
                'JPY': 188.50,
                'CHF': 1.14
            }

            current_date = datetime.now().strftime('%Y-%m-%d')
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            rates_updated = 0

            for currency, rate in sample_rates.items():
                if currency != base_currency:
                    # Check if rate already exists for today
                    cursor.execute('''
                    SELECT COUNT(*) FROM exchange_rates
                    WHERE from_currency = ? AND to_currency = ? AND rate_date = ?
                    ''', (base_currency, currency, current_date))

                    if cursor.fetchone()[0] == 0:
                        # Insert new rate
                        cursor.execute('''
                        INSERT INTO exchange_rates
                        (from_currency, to_currency, exchange_rate, rate_date, source, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ''', (base_currency, currency, rate, current_date, 'api', current_time))

                        print(f"Updated {base_currency}/{currency}: {rate}")
                        rates_updated += 1
                    else:
                        # Update existing rate
                        cursor.execute('''
                        UPDATE exchange_rates
                        SET exchange_rate = ?, created_at = ?
                        WHERE from_currency = ? AND to_currency = ? AND rate_date = ?
                        ''', (rate, current_time, base_currency, currency, current_date))

                        print(f"Updated {base_currency}/{currency}: {rate}")
                        rates_updated += 1

            # Update last update time
            cursor.execute('''
            UPDATE currency_settings
            SET last_rate_update = ?, updated_at = ?
            ''', (current_time, current_time))

            conn.commit()

            print(f"\nExchange rates updated successfully!")
            print(f"Rates updated: {rates_updated}")

        except Exception as e:
            print(f"Error fetching exchange rates: {e}")
            print("Using manual rate update instead.")
            manual_rate_update(cursor, base_currency)
            conn.commit()

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def convert_currency(amount, from_currency, to_currency):
    """Convert amount from one currency to another"""
    if from_currency == to_currency:
        return amount

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get latest exchange rate
        cursor.execute('''
        SELECT exchange_rate FROM exchange_rates
        WHERE from_currency = ? AND to_currency = ?
        ORDER BY rate_date DESC, created_at DESC
        LIMIT 1
        ''', (from_currency, to_currency))

        result = cursor.fetchone()

        if result:
            rate = result[0]
            converted_amount = amount * rate
            conn.close()
            return converted_amount
        else:
            # Try reverse conversion
            cursor.execute('''
            SELECT exchange_rate FROM exchange_rates
            WHERE from_currency = ? AND to_currency = ?
            ORDER BY rate_date DESC, created_at DESC
            LIMIT 1
            ''', (to_currency, from_currency))

            result = cursor.fetchone()

            if result:
                rate = 1 / result[0]
                converted_amount = amount * rate
                conn.close()
                return converted_amount
            else:
                conn.close()
                print(f"Exchange rate not found for {from_currency}/{to_currency}")
                return amount

    except sqlite3.Error as e:
        print(f"Database error in currency conversion: {e}")
        return amount

@app.route('/api/exchange-rates', methods=['GET'])
def api_get_exchange_rates():
    """API endpoint to get current exchange rates"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT from_currency, to_currency, exchange_rate, rate_date
        FROM exchange_rates
        WHERE rate_date = (SELECT MAX(rate_date) FROM exchange_rates)
        ''')

        rates = cursor.fetchall()

        exchange_rates = {}
        for rate in rates:
            from_curr, to_curr, rate_value, rate_date = rate
            if from_curr not in exchange_rates:
                exchange_rates[from_curr] = {}
            exchange_rates[from_curr][to_curr] = {
                'rate': float(rate_value),
                'date': rate_date
            }

        conn.close()
        return jsonify(exchange_rates)

    except Exception as e:
        logger.error("Exchange rate retrieval failed: %s", e)
        return jsonify({'error': 'Internal server error'}), 500

def currency_conversion_tool():
    """Interactive currency conversion tool"""
    try:
        print("\nCurrency Conversion Tool")
        print("Supported currencies:", ", ".join(SUPPORTED_CURRENCIES))

        from_currency = input("From currency: ").strip().upper()
        to_currency = input("To currency: ").strip().upper()

        if from_currency not in SUPPORTED_CURRENCIES or to_currency not in SUPPORTED_CURRENCIES:
            print("Unsupported currency.")
            return

        amount = float(input("Amount: "))

        converted_amount = convert_currency(amount, from_currency, to_currency)

        print(f"{amount} {from_currency} = {converted_amount:.2f} {to_currency}")

    except ValueError:
        print("Invalid amount entered.")
    except Exception as e:
        print(f"Conversion error: {e}")
