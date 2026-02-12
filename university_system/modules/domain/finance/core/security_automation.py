from university_system.infrastructure.database.db import sqlite3
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
from university_system.infrastructure.email import send_email
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth
from university_system.infrastructure.database.db import get_connection
from university_system.utils.logging.log_config import configure_logging, get_log_file
from university_system.infrastructure.email.template_utils import render_template
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

auth = get_auth()
app = Flask(__name__)

# Initialize security headers for all responses
try:
    from university_system.infrastructure.security.flask_security_headers import init_security_headers
    init_security_headers(app)
except ImportError:
    pass  # Security headers module not available

# Encryption key for sensitive data
ENCRYPTION_KEY = Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

# Payment gateway configurations
PAYMENT_GATEWAYS = {
    'stripe': {
        'public_key': 'pk_test_...',
        'secret_key': 'sk_test_...',
        'webhook_secret': 'whsec_...'
    },
    'paypal': {
        'client_id': 'your_paypal_client_id',
        'client_secret': 'your_paypal_client_secret',
        'environment': 'sandbox'  # or 'live'
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



def set_finance_auth(auth_instance):
    global auth
    # Store the provided authentication object instead of unconditionally
    # resetting it to ``None``.  Without this, downstream functions that
    # reference ``auth.current_user`` or ``auth.check_permission`` will crash.
    auth = auth_instance

def setup_automated_notifications():
    """Set up automated notification schedules"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to set up notifications.")
        return
    
    if not auth.check_permission('manage_finances'):
        print("You don't have permission to set up notifications.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("Setting up automated notification schedules...")
        
        # Default notification schedules
        schedules = [
            (1, '{"fee_status": "unpaid", "days_before_due": 7}', 7, 3, 7, 1),  # Payment reminder
            (2, '{"fee_status": "unpaid", "days_overdue": 1}', -1, 5, 3, 1),   # Overdue notice
            (4, '{"payment_plan_created": true}', 0, 1, 0, 1)                   # Payment plan setup
        ]
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for template_id, conditions, days_before, max_reminders, interval, is_active in schedules:
            cursor.execute('''
            INSERT OR REPLACE INTO notification_schedules 
            (template_id, trigger_condition, days_before_due, max_reminders, 
             reminder_interval_days, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (template_id, conditions, days_before, max_reminders, interval, is_active, now, now))
        
        conn.commit()
        
        print("Automated notification schedules set up successfully!")
        print("The system will now automatically send:")
        print("- Payment reminders 7 days before due date")
        print("- Overdue notices for late payments")
        print("- Payment plan confirmations")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def send_automated_notifications():
    """Send automated notifications based on schedules"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        current_date = datetime.now().date()
        
        # Get active notification schedules
        cursor.execute('''
        SELECT ns.schedule_id, ns.template_id, ns.trigger_condition, ns.days_before_due,
               ns.max_reminders, ns.reminder_interval_days,
               nt.template_name, nt.subject_template, nt.body_template, nt.send_method
        FROM notification_schedules ns
        JOIN notification_templates nt ON ns.template_id = nt.template_id
        WHERE ns.is_active = 1 AND nt.is_active = 1
        ''')
        
        schedules = cursor.fetchall()
        notifications_sent = 0
        
        for schedule in schedules:
            (schedule_id, template_id, trigger_condition, days_before, max_reminders, 
             interval_days, template_name, subject_template, body_template, send_method) = schedule
            
            conditions = json.loads(trigger_condition)
            
            # Payment reminders
            if 'days_before_due' in conditions:
                target_date = (current_date + timedelta(days=days_before)).strftime('%Y-%m-%d')
                
                cursor.execute('''
                SELECT sf.student_fee_id, sf.student_id, sf.amount, sf.due_date,
                       s.first_name, s.last_name, s.email_address,
                       ft.fee_name
                FROM student_fees sf
                JOIN students s ON sf.student_id = s.student_id
                JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                WHERE sf.status = 'unpaid' 
                AND sf.due_date = ?
                AND sf.reminder_count < ?
                ''', (target_date, max_reminders))
                
                due_fees = cursor.fetchall()
                
                for fee in due_fees:
                    student_fee_id, student_id, amount, due_date, first_name, last_name, email, fee_name = fee
                    
                    # Check if reminder already sent today
                    cursor.execute('''
                    SELECT COUNT(*) FROM sent_notifications
                    WHERE student_id = ? AND template_id = ? 
                    AND date(sent_at) = date('now')
                    ''', (student_id, template_id))
                    
                    if cursor.fetchone()[0] == 0:
                        # Send notification
                        student_name = f"{first_name} {last_name}"
                        subject = subject_template.format(
                            student_name=student_name,
                            amount=amount,
                            due_date=due_date,
                            fee_name=fee_name
                        )
                        body = body_template.format(
                            student_name=student_name,
                            amount=amount,
                            due_date=due_date,
                            fee_name=fee_name
                        )
                        
                        if send_notification(student_id, email, subject, body, send_method, template_id):
                            # Update reminder count
                            cursor.execute('''
                            UPDATE student_fees 
                            SET reminder_count = reminder_count + 1, 
                                last_reminder_sent = date('now')
                            WHERE student_fee_id = ?
                            ''', (student_fee_id,))
                            
                            notifications_sent += 1
            
            # Overdue notices
            elif 'days_overdue' in conditions:
                cursor.execute('''
                SELECT sf.student_fee_id, sf.student_id, sf.amount, sf.due_date,
                       s.first_name, s.last_name, s.email_address,
                       ft.fee_name
                FROM student_fees sf
                JOIN students s ON sf.student_id = s.student_id
                JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                WHERE sf.status IN ('unpaid', 'partial')
                AND date(sf.due_date) < date('now')
                AND sf.reminder_count < ?
                ''', (max_reminders,))
                
                overdue_fees = cursor.fetchall()
                
                for fee in overdue_fees:
                    student_fee_id, student_id, amount, due_date, first_name, last_name, email, fee_name = fee
                    
                    # Check interval since last reminder
                    cursor.execute('''
                    SELECT last_reminder_sent FROM student_fees
                    WHERE student_fee_id = ?
                    ''', (student_fee_id,))
                    
                    last_reminder = cursor.fetchone()[0]
                    
                    if (not last_reminder or 
                        (current_date - datetime.strptime(last_reminder, '%Y-%m-%d').date()).days >= interval_days):
                        
                        student_name = f"{first_name} {last_name}"
                        subject = subject_template.format(
                            student_name=student_name,
                            amount=amount,
                            due_date=due_date,
                            fee_name=fee_name
                        )
                        body = body_template.format(
                            student_name=student_name,
                            amount=amount,
                            due_date=due_date,
                            fee_name=fee_name
                        )
                        
                        if send_notification(student_id, email, subject, body, send_method, template_id):
                            cursor.execute('''
                            UPDATE student_fees 
                            SET reminder_count = reminder_count + 1, 
                                last_reminder_sent = date('now')
                            WHERE student_fee_id = ?
                            ''', (student_fee_id,))
                            
                            notifications_sent += 1
        
        conn.commit()
        conn.close()
        
        if notifications_sent > 0:
            print(f"Sent {notifications_sent} automated notifications")
        
        return notifications_sent
        
    except Exception as e:
        print(f"Error sending automated notifications: {e}")
        return 0

def send_notification(student_id, email, subject, body, method, template_id):
    """Send a notification to a student"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if method == 'email':
            # Simulate email sending (replace with actual email service)
            success = send_email_notification(email, subject, body)
            status = 'sent' if success else 'failed'
        elif method == 'sms':
            # Simulate SMS sending
            success = send_sms_notification(student_id, body)
            status = 'sent' if success else 'failed'
        else:
            success = False
            status = 'failed'
        
        # Log the notification
        cursor.execute('''
        INSERT INTO sent_notifications 
        (student_id, template_id, recipient_email, subject, message_body, 
         send_method, status, sent_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (student_id, template_id, email, subject, body, method, status, now, now))
        
        conn.commit()
        conn.close()
        
        return success
        
    except Exception as e:
        print(f"Error sending notification: {e}")
        return False

def send_email_notification(email, subject, body, method='smtp'):
    """Safe wrapper for email notifications"""
    try:
        # Try to use your email_manager
        from university_system.modules.shared.utils.infrastructure.email import send_email
        return send_email(recipient=email, subject=subject, body=body)
    except ImportError:
        print(f"📧 EMAIL NOTIFICATION: {email}")
        print(f"📨 Subject: {subject}")
        print(f"📝 Message: {body[:100]}...")
        return True
    except Exception as e:
        print(f"❌ Email failed: {e}")
        return False

def send_sms_notification(student_id, message, method='twilio'):
    """Safe wrapper for SMS notifications"""
    try:
        phone = get_student_phone(student_id)
        print(f"📱 SMS to {phone}: {message}")
        return True
    except Exception as e:
        print(f"❌ SMS failed: {e}")
        return False

def enhanced_notification_system():
    """Enhanced notification system with both email and SMS"""
    while True:
        print("\n📞 Enhanced Notification System")
        print("=" * 40)
        print("1. Send Email Notification")
        print("2. Send SMS Notification")
        print("3. Send Both Email & SMS")
        print("4. Setup Email Configuration")
        print("5. Setup SMS Configuration")
        print("6. Test Email Service")
        print("7. Test SMS Service")
        print("8. Create Budget Category")
        print("9. Return to Main Menu")
        
        choice = input("Enter your choice (1-9): ").strip()
        
        if choice == '1':
            email = input("Enter email address: ").strip()
            subject = input("Enter subject: ").strip()
            body = input("Enter message: ").strip()
            send_email_notification(email, subject, body)
            
        elif choice == '2':
            student_id = input("Enter student ID: ").strip()
            message = input("Enter SMS message: ").strip()
            send_sms_notification(student_id, message)
            
        elif choice == '3':
            email = input("Enter email address: ").strip()
            student_id = input("Enter student ID: ").strip()
            subject = input("Enter email subject: ").strip()
            message = input("Enter message: ").strip()
            
            print("Sending email...")
            send_email_notification(email, subject, message)
            print("Sending SMS...")
            send_sms_notification(student_id, message)
            
        elif choice == '4':
            setup_email_config()
        elif choice == '5':
            setup_sms_config()
        elif choice == '6':
            test_email_service()
        elif choice == '7':
            test_sms_service()
        elif choice == '8':
            create_budget_category()
        elif choice == '9':
            return
        else:
            print("Invalid choice. Please try again.")

def detect_payment_fraud():
    """Detect potentially fraudulent payments using machine learning"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to run fraud detection.")
        return
    
    if not auth.check_permission('manage_finances'):
        print("You don't have permission to run fraud detection.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("Running fraud detection analysis...")
        
        # Get payment data for analysis
        cursor.execute('''
        SELECT p.payment_id, p.student_id, p.amount, p.payment_method, 
               p.payment_date, p.created_at, p.gateway_transaction_id,
               julianday(p.created_at) - julianday(p.payment_date) as processing_delay,
               s.course, s.enrollment_date
        FROM payments p
        JOIN students s ON p.student_id = s.student_id
        WHERE p.status = 'completed'
        AND p.created_at >= date('now', '-30 days')
        ''')
        
        payments = cursor.fetchall()
        
        if len(payments) < 10:
            print("Insufficient payment data for fraud detection.")
            conn.close()
            return
        
        # Prepare features for fraud detection
        features = []
        payment_ids = []
        
        for payment in payments:
            (payment_id, student_id, amount, method, payment_date, created_at, 
             transaction_id, processing_delay, course, enrollment_date) = payment
            
            # Calculate features
            features.append([
                amount,
                processing_delay or 0,
                1 if method == 'Card' else 0,  # Online payment flag
                1 if amount > 5000 else 0,     # Large amount flag
                len(transaction_id) if transaction_id else 0,  # Transaction ID length
            ])
            payment_ids.append(payment_id)
        
        # Run isolation forest for anomaly detection
        X = np.array(features)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        isolation_forest = IsolationForest(contamination=0.05, random_state=42)
        anomalies = isolation_forest.fit_predict(X_scaled)
        
        # Calculate fraud scores
        fraud_scores = []
        for i, feature_set in enumerate(features):
            amount, delay, online_flag, large_flag, tx_len = feature_set
            
            fraud_score = 0.0
            
            # Amount-based scoring
            if amount > 10000:
                fraud_score += 0.3
            elif amount > 5000:
                fraud_score += 0.1
            
            # Processing delay scoring
            if delay > 1:  # More than 1 day delay
                fraud_score += 0.2
            
            # Transaction ID scoring
            if tx_len < 10:  # Short transaction ID
                fraud_score += 0.1
            
            # Anomaly scoring
            if anomalies[i] == -1:
                fraud_score += 0.4
            
            fraud_scores.append(min(fraud_score, 1.0))
        
        # Update fraud scores in database
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        suspicious_payments = 0
        
        for i, payment_id in enumerate(payment_ids):
            fraud_score = fraud_scores[i]
            is_suspicious = fraud_score >= 0.5
            
            cursor.execute('''
            UPDATE payments 
            SET fraud_score = ?, is_suspicious = ?
            WHERE payment_id = ?
            ''', (fraud_score, is_suspicious, payment_id))
            
            if is_suspicious:
                suspicious_payments += 1
                
                # Log suspicious payment
                cursor.execute('''
                SELECT student_id, amount, payment_method, payment_date
                FROM payments WHERE payment_id = ?
                ''', (payment_id,))
                
                payment_details = cursor.fetchone()
                
                log_audit_action('fraud_detection', 'payments', str(payment_id), {
                    'fraud_score': fraud_score,
                    'student_id': payment_details[0],
                    'amount': payment_details[1],
                    'flagged_for_review': True
                })
        
        conn.commit()
        
        print(f"Fraud detection completed!")
        print(f"Payments analyzed: {len(payments)}")
        print(f"Suspicious payments flagged: {suspicious_payments}")
        
        if suspicious_payments > 0:
            print(f"\nSuspicious payments require manual review:")
            
            cursor.execute('''
            SELECT p.payment_id, p.student_id, p.amount, p.payment_method, 
                   p.payment_date, p.fraud_score,
                   s.first_name, s.last_name
            FROM payments p
            JOIN students s ON p.student_id = s.student_id
            WHERE p.is_suspicious = 1
            ORDER BY p.fraud_score DESC
            ''')
            
            suspicious = cursor.fetchall()
            
            for payment in suspicious:
                payment_id, student_id, amount, method, date, score, first_name, last_name = payment
                print(f"  Payment {payment_id}: £{amount:.2f} by {first_name} {last_name} "
                      f"({method}) on {date} - Risk: {score*100:.1f}%")
        
        conn.close()
        
    except Exception as e:
        print(f"Error in fraud detection: {e}")

def log_audit_action(action, table_name, record_id, details):
    """Log audit action for compliance"""
    global auth
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        user_id = auth.current_user['username'] if auth and auth.current_user else 'system'
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO audit_log 
        (user_id, action, table_name, record_id, new_values, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, action, table_name, record_id, json.dumps(details), timestamp))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Error logging audit action: {e}")

def create_approval_workflow():
    """Create approval workflow for refunds and other financial operations"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to create workflows.")
        return
    
    if not auth.check_permission('manage_workflows'):
        print("You don't have permission to create workflows.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Define refund approval workflow
        refund_workflow = {
            'name': 'Refund Approval Workflow',
            'type': 'approval',
            'trigger_conditions': {'entity_type': 'refund', 'status': 'pending'},
            'steps': [
                {
                    'step': 1,
                    'name': 'Manager Review',
                    'required_permission': 'approve_refunds',
                    'action': 'review_and_approve',
                    'escalation_hours': 48
                },
                {
                    'step': 2,
                    'name': 'Finance Director Approval',
                    'required_permission': 'approve_large_refunds',
                    'condition': 'amount > 1000',
                    'action': 'final_approval',
                    'escalation_hours': 24
                },
                {
                    'step': 3,
                    'name': 'Process Refund',
                    'required_permission': 'process_refunds',
                    'action': 'process_payment',
                    'auto_execute': True
                }
            ]
        }
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO workflows 
        (workflow_name, workflow_type, trigger_conditions, workflow_steps, 
         is_active, created_by, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('Refund Approval Workflow', 'approval', 
              json.dumps(refund_workflow['trigger_conditions']),
              json.dumps(refund_workflow['steps']),
              1, auth.current_user['username'], now, now))
        
        workflow_id = cursor.lastrowid
        
        conn.commit()
        
        print(f"Refund approval workflow created successfully! Workflow ID: {workflow_id}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def send_aid_decision_notification(student_id, aid_id, status, amount):
    """Send notification about aid decision"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student and aid details
        cursor.execute('''
        SELECT s.first_name, s.last_name, s.email_address, fat.aid_name
        FROM students s
        JOIN student_financial_aid sfa ON s.student_id = sfa.student_id
        JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
        WHERE sfa.aid_id = ?
        ''', (aid_id,))

        result = cursor.fetchone()

        if result:
            first_name, last_name, email, aid_name = result
            student_name = f"{first_name} {last_name}"

            template_vars = {
                'name': student_name,
                'aid_name': aid_name,
                'amount': amount,
                'aid_id': aid_id,
                'status': status
            }
            subject, body = render_template('financial_aid_approved', template_vars)

            if send_email_notification(email, subject, body):
                print(f"Aid decision notification sent to {email}")
            else:
                print("Failed to send aid decision notification")

        conn.close()

    except Exception as e:
        print(f"Error sending aid decision notification: {e}")

def send_disbursement_notification(student_id, aid_id, amount, method):
    """Send notification about aid disbursement"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get student and aid details
        cursor.execute('''
        SELECT s.first_name, s.last_name, s.email_address, fat.aid_name
        FROM students s
        JOIN student_financial_aid sfa ON s.student_id = sfa.student_id
        JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
        WHERE sfa.aid_id = ?
        ''', (aid_id,))
        
        result = cursor.fetchone()
        
        if result:
            first_name, last_name, email, aid_name = result
            student_name = f"{first_name} {last_name}"

            from university_system.infrastructure.email.template_utils import render_template
            subject, body = render_template("financial_aid_disbursement", {
                "student_name": student_name,
                "aid_name": aid_name,
                "amount": f"{amount:.2f}",
                "method": method.replace('_', ' ').title(),
                "aid_id": aid_id
            })
            
            if send_email_notification(email, subject, body):
                print(f"Disbursement notification sent to {email}")
            else:
                print("Failed to send disbursement notification")
        
        conn.close()
        
    except Exception as e:
        print(f"Error sending disbursement notification: {e}")

def budget_approval_workflow():
    """Budget approval workflow"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get budgets pending approval
        cursor.execute('''
        SELECT budget_id, plan_name, academic_year, total_revenue_budget, 
               total_expense_budget, created_by
        FROM budget_plans
        WHERE status = 'draft'
        ORDER BY created_at
        ''')
        
        pending_budgets = cursor.fetchall()
        
        if not pending_budgets:
            print("No budgets pending approval.")
            return
        
        print(f"\nBudgets Pending Approval:")
        print("=" * 90)
        for i, budget in enumerate(pending_budgets, 1):
            budget_id, plan_name, academic_year, revenue, expenses, created_by = budget
            net = (revenue or 0) - (expenses or 0)
            
            print(f"{i}. Budget ID {budget_id}: {plan_name} ({academic_year})")
            print(f"   Revenue: £{revenue or 0:,.2f}, Expenses: £{expenses or 0:,.2f}, Net: £{net:,.2f}")
            print(f"   Created by: {created_by}")
            print("-" * 90)
        
        # Select budget to review
        budget_choice = input(f"Select budget to review (1-{len(pending_budgets)}): ").strip()
        try:
            budget_index = int(budget_choice) - 1
            if 0 <= budget_index < len(pending_budgets):
                selected_budget = pending_budgets[budget_index]
                budget_id = selected_budget[0]
            else:
                print("Invalid selection.")
                return
        except ValueError:
            print("Invalid input.")
            return
        
        # Show detailed budget for review
        view_budget_plan_detail(budget_id)
        
        # Approval decision
        print("\nApproval Options:")
        print("1. Approve budget")
        print("2. Request changes")
        print("3. Reject budget")
        
        decision = input("Enter decision (1-3): ").strip()
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if decision == '1':
            # Approve budget
            cursor.execute('''
            UPDATE budget_plans 
            SET status = 'approved', approved_by = ?, updated_at = ?
            WHERE budget_id = ?
            ''', (auth.current_user['username'], now, budget_id))
            
            print(f"Budget {budget_id} approved successfully!")
            
        elif decision == '2':
            # Request changes
            changes_required = input("Enter required changes: ").strip()
            
            cursor.execute('''
            UPDATE budget_plans 
            SET notes = COALESCE(notes, '') || ' | CHANGES REQUIRED: ' || ?, updated_at = ?
            WHERE budget_id = ?
            ''', (changes_required, now, budget_id))
            
            print(f"Changes requested for budget {budget_id}")
            
        elif decision == '3':
            # Reject budget
            rejection_reason = input("Enter rejection reason: ").strip()
            
            cursor.execute('''
            UPDATE budget_plans 
            SET status = 'rejected', 
                notes = COALESCE(notes, '') || ' | REJECTED: ' || ?, 
                updated_at = ?
            WHERE budget_id = ?
            ''', (rejection_reason, now, budget_id))
            
            print(f"Budget {budget_id} rejected")
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Error in budget approval workflow: {e}")

def verify_jwt_in_request():
    """Dummy JWT verification for API endpoints"""
    # This is a placeholder - in production you'd verify actual JWT tokens
    return True

def api_endpoint(func):
    """Simple API endpoint decorator"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            return {"error": str(e)}, 500
    return wrapper
