from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager, get_connection as get_db_conn
from education_system.university_system.infrastructure.shared_context import get_auth
import os
import re
import csv
import pandas as pd
import random
import json
import qrcode
import requests
from datetime import datetime, timedelta
from education_system.university_system.modules.shared.constants.paths import QR_CODES_DIR, BACKUP_DIR
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from education_system.university_system.infrastructure.email import (
    send_book_checkout_confirmation,
    send_book_return_reminder,
    send_overdue_notification,
)
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import hashlib
import uuid
from collections import defaultdict
import matplotlib.pyplot as plt
import seaborn as sns
import shutil
from typing import Any, List, Dict, Optional, Tuple
import logging
from education_system.university_system.utils.logging.log_config import configure_logging

# CONSOLIDATED DATABASE FILE - Using the same database as main system
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from education_system.university_system.modules.shared.utils.finance_integration import record_payment_to_finance
from education_system.university_system.modules.shared.utils.i18n import (
    get_text,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Configure logging
logger = configure_logging(name=__name__)

def automated_notifications():
    """Process and send automated notifications"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to manage notifications.")
        return

    if not auth.check_permission('system_config'):
        print("You don't have permission to manage notifications.")
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    print("\nAutomated Notifications:")
    print("=======================")
    print("1. Send Due Date Reminders")
    print("2. Send Overdue Notifications")
    print("3. Send Reservation Alerts")
    print("4. Process Notification Queue")
    print("5. Configure Notification Settings")
    print("6. Return to menu")

    choice = input("Enter your choice (1-6): ").strip()

    try:
        if choice == '1':
            # Send due date reminders
            tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

            cursor.execute('''
            SELECT bl.user_id, bl.book_id, b.title, bl.due_date
            FROM book_loans bl
            JOIN books b ON bl.book_id = b.book_id
            WHERE date(bl.due_date) = ? AND bl.status = 'active'
            ''', (tomorrow,))

            due_soon = cursor.fetchall()

            sent_count = 0
            for user_id, book_id, title, due_date in due_soon:
                try:
                    send_due_date_reminder(user_id, book_id, title, due_date[:10])
                    sent_count += 1
                except Exception as e:
                    logging.error(f"Failed to send reminder to {user_id}: {e}")

            print(f"✅ Sent {sent_count} due date reminders")

        elif choice == '2':
            # Send overdue notifications
            today = datetime.now().strftime('%Y-%m-%d')

            cursor.execute('''
            SELECT bl.user_id, bl.book_id, b.title, bl.due_date,
                   julianday('now') - julianday(bl.due_date) as days_overdue
            FROM book_loans bl
            JOIN books b ON bl.book_id = b.book_id
            WHERE date(bl.due_date) < date('now') AND bl.status IN ('active', 'overdue')
            ''')

            overdue_items = cursor.fetchall()

            sent_count = 0
            for user_id, book_id, title, due_date, days_overdue in overdue_items:
                try:
                    # Update loan status to overdue
                    cursor.execute('''
                    UPDATE book_loans SET status = 'overdue'
                    WHERE book_id = ? AND user_id = ? AND status = 'active'
                    ''', (book_id, user_id))

                    send_overdue_notification(user_id, book_id, title, due_date[:10], int(days_overdue))
                    sent_count += 1
                except Exception as e:
                    logging.error(f"Failed to send overdue notice to {user_id}: {e}")

            conn.commit()
            print(f"✅ Sent {sent_count} overdue notifications")

        elif choice == '3':
            # Send reservation alerts for available books
            cursor.execute('''
            SELECT br.user_id, br.book_id, b.title, br.reservation_id
            FROM book_reservations br
            JOIN books b ON br.book_id = b.book_id
            WHERE b.status = 'available' AND br.status = 'active'
            AND br.priority_order = 1 AND br.notification_sent = 0
            ''')

            available_reservations = cursor.fetchall()

            sent_count = 0
            for user_id, book_id, title, reservation_id in available_reservations:
                try:
                    send_reservation_available_notification(user_id, book_id, title)

                    # Mark notification as sent and update book status
                    cursor.execute('''
                    UPDATE book_reservations SET notification_sent = 1
                    WHERE reservation_id = ?
                    ''', (reservation_id,))

                    cursor.execute('''
                    UPDATE books SET status = 'reserved' WHERE book_id = ?
                    ''', (book_id,))

                    sent_count += 1
                except Exception as e:
                    logging.error(f"Failed to send reservation alert to {user_id}: {e}")

            conn.commit()
            print(f"✅ Sent {sent_count} reservation alerts")

        elif choice == '4':
            # Process notification queue
            cursor.execute('''
            SELECT notification_id, user_id, notification_type, title, message, delivery_method
            FROM notification_queue
            WHERE sent = 0 AND (send_date IS NULL OR send_date <= datetime('now'))
            ORDER BY priority DESC, created_date
            LIMIT 50
            ''')

            queued_notifications = cursor.fetchall()

            processed_count = 0
            for notification_id, user_id, notif_type, title, message, method in queued_notifications:
                try:
                    if method == 'email':
                        send_generic_email_notification(user_id, title, message)
                    elif method == 'sms':
                        send_sms_notification(user_id, message)

                    cursor.execute('''
                    UPDATE notification_queue SET sent = 1
                    WHERE notification_id = ?
                    ''', (notification_id,))

                    processed_count += 1
                except Exception as e:
                    logging.error(f"Failed to send notification {notification_id}: {e}")

            conn.commit()
            print(f"✅ Processed {processed_count} queued notifications")

        elif choice == '5':
            # Configure notification settings
            configure_notification_settings()

    except sqlite3.Error as e:
        print(f"Error processing notifications: {e}")

    conn.close()


def send_enhanced_checkout_notification(user_id: str, book_id: str, title: str, due_date: str):
    """Send enhanced checkout confirmation with QR code and tips"""
    try:
        # Get user email if available
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT email FROM students WHERE student_id = ?', (user_id,))
        user_email = cursor.fetchone()

        if user_email and user_email[0]:
            from education_system.university_system.infrastructure.email.template_utils import render_template

            subject, message = render_template('library_book_checkout', {
                'title': title,
                'book_id': book_id,
                'due_date': due_date
            })

            if subject and message:
                send_email_notification(user_email[0], subject, message)

        conn.close()

    except Exception as e:
        logging.error(f"Error sending checkout notification: {e}")


def send_overdue_notification(user_id: str, book_id: str, title: str, due_date: str, days_overdue: int):
    """Send overdue notification to user"""
    try:
        # Calculate fine amount
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "fine_per_day"')
        fine_per_day = float(cursor.fetchone()[0])
        total_fine = days_overdue * fine_per_day

        # Update fine in loan record
        cursor.execute('''
        UPDATE book_loans
        SET fine_amount = ?
        WHERE book_id = ? AND user_id = ? AND status IN ('active', 'overdue')
        ''', (total_fine, book_id, user_id))

        conn.commit()
        conn.close()

        # Send notification (implementation depends on your notification system)
        message = f"""
OVERDUE NOTICE

Book: {title} ({book_id})
Due Date: {due_date}
Days Overdue: {days_overdue}
Current Fine: ${total_fine:.2f}

Please return this book as soon as possible to avoid additional fines.

Contact the library if you have any questions.
        """

        logging.info(f"Overdue notification sent to {user_id} for book {book_id}")

    except Exception as e:
        logging.error(f"Error sending overdue notification: {e}")


def send_due_date_reminder(user_id: str, book_id: str, title: str, due_date: str):
    """
    Send due date reminder via central infrastructure.

    MIGRATED: Now uses central infrastructure helper instead of stub logging.
    """
    from education_system.university_system.modules.shared.utils.communication_integration import send_library_notification

    success = send_library_notification(
        user_id=user_id,
        notification_type='due_soon',
        book_title=title,
        due_date=due_date
    )
    if success:
        logging.info(f"Due date reminder sent to {user_id}")
    return success


def send_reservation_confirmation(user_id: str, book_id: str, title: str, position: int, expiry: str):
    """
    Send reservation confirmation via central infrastructure.

    MIGRATED: Now uses central infrastructure helper instead of stub logging.
    """
    from education_system.university_system.modules.shared.utils.communication_integration import send_library_notification

    success = send_library_notification(
        user_id=user_id,
        notification_type='reservation_ready',
        book_title=title
    )
    if success:
        logging.info(f"Reservation confirmation sent to {user_id}")
    return success


def send_reservation_available_notification(user_id: str, book_id: str, title: str):
    """
    Send notification when reserved book becomes available via central infrastructure.

    MIGRATED: Now uses central infrastructure helper instead of stub logging.
    """
    from education_system.university_system.modules.shared.utils.communication_integration import send_library_notification

    success = send_library_notification(
        user_id=user_id,
        notification_type='reservation_ready',
        book_title=title
    )
    if success:
        logging.info(f"Reservation available notification sent to {user_id}")
    return success


def send_generic_email_notification(user_id: str, title: str, message: str):
    """
    Send generic email notification via central infrastructure.

    MIGRATED: Now uses central email service instead of stub logging.
    """
    from education_system.university_system.modules.shared.utils.communication_integration import send_email_unified
    from education_system.university_system.infrastructure.database.db import get_connection

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT email_address FROM students WHERE student_id = ?", (user_id,))
            result = cursor.fetchone()

            if result and result[0]:
                email = result[0]
                success = send_email_unified(email, title, message)
                if success:
                    logging.info(f"Generic notification sent to {user_id}: {title}")
                return success
            else:
                logging.warning(f"No email found for user {user_id}")
                return False
    except Exception as e:
        logging.error(f"Error sending email to {user_id}: {e}")
        return False


def send_email_notification(email: str, subject: str, message: str):
    """
    Send email notification via central infrastructure.

    MIGRATED: Now uses central email service instead of stub logging.
    """
    from education_system.university_system.modules.shared.utils.communication_integration import send_email_unified

    success = send_email_unified(email, subject, message)
    if success:
        logging.info(f"Email sent to {email}: {subject}")
    else:
        logging.warning(f"Failed to send email to {email}")
    return success


def send_sms_notification(user_id: str, message: str):
    """
    Send SMS notification via central infrastructure.

    MIGRATED: Now uses central SMS service instead of stub logging.
    """
    from education_system.university_system.modules.shared.utils.communication_integration import send_sms_unified
    from education_system.university_system.infrastructure.database.db import get_connection

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT phone_number FROM students WHERE student_id = ?", (user_id,))
            result = cursor.fetchone()

            if result and result[0]:
                phone = result[0]
                success = send_sms_unified(phone, message, student_id=user_id, related_to='library')
                if success:
                    logging.info(f"SMS sent to {user_id}: {message}")
                return success
            else:
                logging.warning(f"No phone number found for user {user_id}")
                return False
    except Exception as e:
        logging.error(f"Error sending SMS to {user_id}: {e}")
        return False


def configure_notification_settings():
    """Configure notification settings"""
    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    print("\nNotification Settings:")
    print("=====================")

    # Current notification settings
    notification_settings = [
        'email_notifications',
        'sms_notifications',
        'auto_reminders',
        'overdue_notifications',
        'reservation_alerts'
    ]

    try:
        for setting in notification_settings:
            cursor.execute('''
            SELECT setting_value FROM library_settings WHERE setting_name = ?
            ''', (setting,))

            result = cursor.fetchone()
            current_value = result[0] if result else 'false'

            print(f"{setting.replace('_', ' ').title()}: {current_value}")

        print("\nUpdate Settings:")
        for setting in notification_settings:
            cursor.execute('''
            SELECT setting_value FROM library_settings WHERE setting_name = ?
            ''', (setting,))

            result = cursor.fetchone()
            current_value = result[0] if result else 'false'

            new_value = input(f"Enable {setting.replace('_', ' ')} (y/n) [{current_value}]: ").strip().lower()

            if new_value in ['y', 'yes']:
                new_value = 'true'
            elif new_value in ['n', 'no']:
                new_value = 'false'
            else:
                continue  # Keep current value

            cursor.execute('''
            INSERT OR REPLACE INTO library_settings (setting_name, setting_value)
            VALUES (?, ?)
            ''', (setting, new_value))

        conn.commit()
        print("✅ Notification settings updated!")

    except sqlite3.Error as e:
        print(f"Error configuring notifications: {e}")

    conn.close()


