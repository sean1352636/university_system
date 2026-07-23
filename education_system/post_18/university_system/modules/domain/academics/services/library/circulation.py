from education_system.post_18.university_system.infrastructure.database.db import sqlite3, DatabaseManager, get_connection as get_db_conn
from education_system.post_18.university_system.infrastructure.shared_context import get_auth
import os
import re
import csv
import random
import json
import requests
from datetime import datetime, timedelta
from education_system.post_18.university_system.core.paths import QR_CODES_DIR, BACKUP_DIR
from education_system.post_18.university_system.infrastructure.email import (
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
import shutil
from typing import Any, List, Dict, Optional, Tuple
import logging
from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging

# CONSOLIDATED DATABASE FILE - Using the same database as main system
from education_system.post_18.university_system.core.paths import DEFAULT_DB_PATH
from education_system.post_18.university_system.modules.shared.utils.finance_integration import record_payment_to_finance
from education_system.post_18.university_system.core.i18n import (
    get_text,
    get_current_language,
)
from education_system.post_18.university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)
from education_system.post_18.university_system.modules.domain.academics.services.library.database import get_db_connection, log_audit_event
from education_system.post_18.university_system.modules.domain.academics.services.library.settings import get_current_user_id, update_reading_goals, record_usage_analytics
from education_system.post_18.university_system.modules.domain.academics.services.library.notifications import send_enhanced_checkout_notification, send_reservation_available_notification, send_reservation_confirmation
from education_system.post_18.university_system.modules.domain.academics.services.library.recommendations import get_similar_books
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Configure logging
logger = configure_logging(name=__name__)

def check_loan_eligibility(cursor, user_id: str, user_type: str) -> Dict:
    """Check if user is eligible for new loans"""
    try:
        # Get max loans setting
        cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "max_loans"')
        max_loans = int(cursor.fetchone()[0])

        # Count current active loans
        cursor.execute('''
        SELECT COUNT(*) FROM book_loans
        WHERE user_id = ? AND status IN ('active', 'overdue')
        ''', (user_id,))

        current_loans = cursor.fetchone()[0]

        # Check for overdue books
        cursor.execute('''
        SELECT COUNT(*) FROM book_loans
        WHERE user_id = ? AND status = 'overdue'
        ''', (user_id,))

        overdue_count = cursor.fetchone()[0]

        # Check for outstanding fines
        cursor.execute('''
        SELECT SUM(fine_amount) FROM book_loans
        WHERE user_id = ? AND fine_amount > 0 AND status != 'returned'
        ''', (user_id,))

        outstanding_fines = cursor.fetchone()[0] or 0

        # Apply eligibility rules
        if current_loans >= max_loans:
            return {
                'eligible': False,
                'reason': f'Maximum loan limit reached ({current_loans}/{max_loans})',
                'current_loans': current_loans,
                'max_loans': max_loans
            }

        if overdue_count > 0:
            return {
                'eligible': False,
                'reason': f'User has {overdue_count} overdue book(s)',
                'current_loans': current_loans,
                'max_loans': max_loans
            }

        if outstanding_fines > 10.00:  # £10 fine limit
            return {
                'eligible': False,
                'reason': f'Outstanding fines: £{outstanding_fines:.2f} (limit: £10.00)',
                'current_loans': current_loans,
                'max_loans': max_loans
            }

        return {
            'eligible': True,
            'reason': 'User is eligible for checkout',
            'current_loans': current_loans,
            'max_loans': max_loans
        }

    except sqlite3.Error as e:
        logging.error(f"Error checking loan eligibility: {e}")
        return {
            'eligible': False,
            'reason': 'Unable to verify loan eligibility',
            'current_loans': 0,
            'max_loans': max_loans
        }


def check_reading_level_compatibility(book_level: str, grade_level: str) -> Dict:
    """Check if book reading level is appropriate for student grade"""
    grade_mappings = {
        'K': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5,
        '6': 6, '7': 7, '8': 8, '9': 9, '10': 10, '11': 11, '12': 12
    }

    level_mappings = {
        'Elementary': (0, 5),
        'Middle School': (6, 8),
        'High School': (9, 12),
        'College': (13, 20)
    }

    try:
        grade_num = grade_mappings.get(str(grade_level), 0)
        level_range = level_mappings.get(book_level, (0, 20))

        if level_range[0] <= grade_num <= level_range[1]:
            return {'suitable': True, 'message': 'Reading level matches grade level'}
        elif grade_num < level_range[0]:
            return {'suitable': False, 'message': f'This book may be too advanced for grade {grade_level}'}
        else:
            return {'suitable': False, 'message': f'This book may be too easy for grade {grade_level}'}

    except Exception:
        return {'suitable': True, 'message': 'Unable to assess reading level compatibility'}


def enhanced_checkout_book(book_id=None):
    """Enhanced checkout with barcode scanning and smart validation"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to check out books.")
        return

    if not (auth.check_permission('manage_loans') or auth.check_permission('checkout_books')):
        print("You don't have permission to check out books.")
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    try:
        # Get book ID if not provided
        if book_id is None:
            print("\nCheckout Options:")
            print("1. Enter Book ID")
            print("2. Scan Barcode")
            print("3. Scan QR Code")

            method = input("Select method (1-3): ").strip()

            if method == '1':
                book_id = input("Enter Book ID: ").strip()
            elif method == '2':
                barcode = input("Scan/Enter Barcode: ").strip()
                cursor.execute('SELECT book_id FROM books WHERE barcode = ?', (barcode,))
                result = cursor.fetchone()
                if result:
                    book_id = result[0]
                else:
                    print("Book not found with that barcode.")
                    conn.close()
                    return
            elif method == '3':
                qr_data = input("Scan QR Code: ").strip()
                if qr_data.startswith("LIBRARY_BOOK:"):
                    parts = qr_data.split(":")
                    if len(parts) >= 2:
                        book_id = parts[1]
                    else:
                        print("Invalid QR code format.")
                        conn.close()
                        return
                else:
                    print("Invalid QR code.")
                    conn.close()
                    return
            else:
                print("Invalid method selection.")
                conn.close()
                return

        # Validate book
        cursor.execute('''
        SELECT title, status, category, reading_level
        FROM books WHERE book_id = ?
        ''', (book_id,))

        book = cursor.fetchone()

        if not book:
            print(f"No book found with ID: {book_id}")
            conn.close()
            return

        title, status, category, reading_level = book

        if status != 'available':
            print(f"This book is currently {status} and cannot be checked out.")

            # Check if there are reservations
            cursor.execute('''
            SELECT COUNT(*) FROM book_reservations
            WHERE book_id = ? AND status = 'active'
            ''', (book_id,))

            reservation_count = cursor.fetchone()[0]
            if reservation_count > 0:
                print(f"There are {reservation_count} reservation(s) for this book.")

            conn.close()
            return

        # Get user information
        user_type = input("Is this for a student (S) or staff (T)? ").strip().upper()
        user_name = "Unknown User"
        user_validated = False

        if user_type == 'S':
            user_id = input("Enter Student ID: ").strip()

            if not user_id:
                print("Error: Student ID cannot be empty.")
                conn.close()
                return

            # Verify student exists
            try:
                cursor.execute('SELECT first_name, last_name, grade_level FROM students WHERE student_id = ?', (user_id,))
                student = cursor.fetchone()

                if student:
                    user_name = f"{student[0]} {student[1]}"
                    grade_level = student[2]
                    user_validated = True
                    print(f"Student found: {user_name} (Grade {grade_level})")

                    # Check reading level compatibility
                    if reading_level and grade_level:
                        compatibility = check_reading_level_compatibility(reading_level, grade_level)
                        if not compatibility['suitable']:
                            print(f"⚠️  Warning: {compatibility['message']}")
                            confirm = input("Do you want to proceed anyway? (y/n): ").strip().lower()
                            if confirm != 'y':
                                print("Checkout cancelled.")
                                conn.close()
                                return
                else:
                    print(f"Warning: No student found with ID: {user_id}")
                    confirm = input("Do you want to proceed anyway? (y/n): ").strip().lower()
                    if confirm != 'y':
                        print("Checkout cancelled.")
                        conn.close()
                        return
                    user_name = f"Student {user_id}"
                    user_validated = True

            except sqlite3.Error as e:
                print(f"Unable to verify student ID: {e}")
                confirm = input("Do you want to proceed anyway? (y/n): ").strip().lower()
                if confirm != 'y':
                    print("Checkout cancelled.")
                    conn.close()
                    return
                user_name = f"Student {user_id}"
                user_validated = True

        elif user_type == 'T':
            user_id = input("Enter Staff/User ID: ").strip()

            if not user_id:
                print("Error: Staff ID cannot be empty.")
                conn.close()
                return

            user_name = input("Enter User Name: ").strip()
            if not user_name:
                user_name = f"Staff {user_id}"

            user_validated = True
        else:
            print("Invalid user type.")
            conn.close()
            return

        if not user_validated:
            print("User validation failed.")
            conn.close()
            return

        # Check loan limits and restrictions
        loan_check = check_loan_eligibility(cursor, user_id, user_type)
        if not loan_check['eligible']:
            print(f"Cannot checkout book: {loan_check['reason']}")
            conn.close()
            return

        # Get loan settings
        cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "loan_period_days"')
        loan_setting = cursor.fetchone()
        loan_period = int(loan_setting[0]) if loan_setting else 14  # Default to 14 days

        # Set dates
        checkout_date = datetime.now()
        due_date = checkout_date + timedelta(days=loan_period)

        # Check for existing reservation by this user
        cursor.execute('''
        SELECT reservation_id FROM book_reservations
        WHERE book_id = ? AND user_id = ? AND status = 'active'
        ''', (book_id, user_id))

        user_reservation = cursor.fetchone()

        # Create loan record
        cursor.execute('''
        INSERT INTO book_loans
        (book_id, user_id, checkout_date, due_date, status, checkout_method, staff_id)
        VALUES (?, ?, ?, ?, 'active', 'enhanced', ?)
        ''', (
            book_id, user_id,
            checkout_date.strftime('%Y-%m-%d %H:%M:%S'),
            due_date.strftime('%Y-%m-%d %H:%M:%S'),
            get_current_user_id()
        ))

        loan_id = cursor.lastrowid

        # Update book status
        cursor.execute('''
        UPDATE books SET status = 'checked_out', last_updated = ?
        WHERE book_id = ?
        ''', (checkout_date.strftime('%Y-%m-%d %H:%M:%S'), book_id))

        # If user had a reservation, mark it as fulfilled
        if user_reservation:
            cursor.execute('''
            UPDATE book_reservations SET status = 'fulfilled'
            WHERE reservation_id = ?
            ''', (user_reservation[0],))

        # Update user reading goals
        update_reading_goals(cursor, user_id, 'books_read')

        # Record analytics
        record_usage_analytics(cursor, 'checkout', category, user_type)

        conn.commit()

        # Log the action
        log_audit_event(get_current_user_id(), f"Checked out book {book_id} to {user_id}", "book_loans", str(loan_id))

        print("\n✅ Book checked out successfully!")
        print("=" * 60)
        print(f"Book: '{title}' ({book_id})")
        print(f"Loan ID: {loan_id}")
        print(f"User: {user_name} ({user_id})")
        print(f"Checkout Date: {checkout_date.strftime('%Y-%m-%d %H:%M')}")
        print(f"Due Date: {due_date.strftime('%Y-%m-%d')}")
        print(f"Reading Level: {reading_level}")
        print(f"Active Loans: {loan_check['current_loans'] + 1}/{loan_check['max_loans']}")
        print("=" * 60)

        # Send notifications
        try:
            send_enhanced_checkout_notification(user_id, book_id, title, due_date.strftime('%Y-%m-%d'))
            print("✅ Checkout confirmation sent.")
        except Exception as e:
            print(f"⚠️  Could not send notification: {e}")

        # Suggest related books
        similar_books = get_similar_books(book_id, category, title.split()[0])
        if similar_books:
            print("\n📚 You might also like:")
            for similar in similar_books[:2]:
                print(f"   • {similar[1]} by {similar[2]} ({similar[0]})")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error during checkout: {e}")
        log_audit_event(get_current_user_id(), f"Failed checkout for book {book_id}", success=False)

    conn.close()


def checkout_book():
    """Check out a book (calls enhanced version)"""
    enhanced_checkout_book()


def enhanced_return_book():
    """Enhanced book return with reading progress tracking"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print(get_text("auth.login_required", action=get_text("return.title")))
        return

    if not (auth.check_permission('manage_loans') or auth.check_permission('checkout_books')):
        print(get_text("auth.permission_denied", action=get_text("return.title")))
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    try:
        print("\n" + get_text("return.options_title") + ":")
        print("1. " + get_text("return.enter_book_id"))
        print("2. " + get_text("return.scan_barcode"))
        print("3. " + get_text("return.enter_loan_id"))

        method = input(get_text("return.select_method") + ": ").strip()

        if method == '1':
            book_id = input(get_text("return.enter_book_id") + ": ").strip()

            cursor.execute('''
            SELECT loan_id, user_id, checkout_date, due_date, status, book_id
            FROM book_loans
            WHERE book_id = ? AND status IN ('active', 'overdue')
            ''', (book_id,))

        elif method == '2':
            barcode = input(get_text("return.scan_barcode") + ": ").strip()

            cursor.execute('''
            SELECT bl.loan_id, bl.user_id, bl.checkout_date, bl.due_date, bl.status, bl.book_id
            FROM book_loans bl
            JOIN books b ON bl.book_id = b.book_id
            WHERE b.barcode = ? AND bl.status IN ('active', 'overdue')
            ''', (barcode,))

        elif method == '3':
            loan_id = input(get_text("return.enter_loan_id") + ": ").strip()

            cursor.execute('''
            SELECT loan_id, user_id, checkout_date, due_date, status, book_id
            FROM book_loans
            WHERE loan_id = ? AND status IN ('active', 'overdue')
            ''', (loan_id,))

        else:
            print(get_text("return.invalid_method"))
            conn.close()
            return

        loan = cursor.fetchone()

        if not loan:
            print(get_text("return.no_active_loan"))
            conn.close()
            return

        loan_id, user_id, checkout_date, due_date, status, book_id = loan

        # Get book details
        cursor.execute('SELECT title, category FROM books WHERE book_id = ?', (book_id,))
        book_info = cursor.fetchone()
        title, category = book_info

        print("\n" + get_text("return.returning", title=title, book_id=book_id))
        print(get_text("return.borrower", user_id=user_id))
        print(get_text("return.checkout_date", date=checkout_date[:10]))
        print(get_text("return.due_date", date=due_date[:10]))

        # Calculate fine if overdue
        fine_amount = 0.0
        now = datetime.now()
        due_date_obj = datetime.strptime(due_date, '%Y-%m-%d %H:%M:%S')

        if now > due_date_obj:
            cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "fine_per_day"')
            fine_per_day = float(cursor.fetchone()[0])
            days_overdue = (now - due_date_obj).days
            fine_amount = days_overdue * fine_per_day

            print("⚠️  " + get_text("return.overdue_warning", days=days_overdue))
            print(get_text("return.fine_amount", amount=f"{fine_amount:.2f}"))

        # Ask about reading progress
        try:
            progress = input(get_text("return.reading_progress_prompt") + ": ").strip()
            if progress and progress.isdigit():
                reading_progress = min(100, max(0, int(progress)))
            else:
                reading_progress = 100  # Assume completed if not specified
        except (ValueError, EOFError, KeyboardInterrupt) as e:
            logger.debug(f"Failed to get reading progress input: {e}")
            reading_progress = 100

        # Ask about book condition
        condition_ok = input(get_text("return.condition_prompt") + " " + get_text("common.yes_no_prompt") + ": ").strip().lower()
        condition_notes = None

        if condition_ok != get_text("common.yes"):
            condition_notes = input(get_text("return.condition_issues") + ": ").strip()

            # Update book condition
            cursor.execute('''
            UPDATE books SET condition_notes = COALESCE(condition_notes || '; ', '') || ?
            WHERE book_id = ?
            ''', (f"Returned {now.strftime('%Y-%m-%d')}: {condition_notes}", book_id))

        # Process return
        now_str = now.strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        UPDATE book_loans
        SET return_date = ?, status = 'returned', fine_amount = ?,
            reading_progress = ?, notes = ?
        WHERE loan_id = ?
        ''', (now_str, fine_amount, reading_progress, condition_notes, loan_id))

        # Update book status
        new_status = 'available'
        if condition_notes and any(word in condition_notes.lower() for word in ['damaged', 'torn', 'missing', 'broken']):
            new_status = 'damaged'

        cursor.execute('''
        UPDATE books SET status = ?, last_updated = ?
        WHERE book_id = ?
        ''', (new_status, now_str, book_id))

        # Update reading goals
        if reading_progress >= 100:
            update_reading_goals(cursor, user_id, 'books_read')

        # Check for reservations and notify next user
        cursor.execute('''
        SELECT user_id, reservation_id
        FROM book_reservations
        WHERE book_id = ? AND status = 'active'
        ORDER BY priority_order, reservation_date
        LIMIT 1
        ''', (book_id,))

        next_reservation = cursor.fetchone()

        if next_reservation and new_status == 'available':
            next_user_id, reservation_id = next_reservation

            # Update book status to reserved
            cursor.execute('UPDATE books SET status = "reserved" WHERE book_id = ?', (book_id,))

            # Send notification to next user
            try:
                send_reservation_available_notification(next_user_id, book_id, title)
                print("✅ " + get_text("return.next_user_notification", user_id=next_user_id))
            except Exception as e:
                print("⚠️  " + get_text("return.next_user_notify_failed", error=str(e)))

        # Record analytics
        record_usage_analytics(cursor, 'return', category)

        conn.commit()

        # FIXED: Log the action using get_current_user_id() helper function
        log_audit_event(get_current_user_id(), f"Returned book {book_id} from {user_id}", "book_loans", str(loan_id))

        print("\n✅ " + get_text("return.success"))
        print(get_text("return.reading_progress_info", progress=reading_progress))
        if fine_amount > 0:
            print(get_text("return.fine_info", amount=f"{fine_amount:.2f}"))
        if next_reservation:
            print(get_text("return.reserved_for_next", user_id=next_reservation[0]))

    except sqlite3.Error as e:
        conn.rollback()
        print(get_text("return.error", error=str(e)))
        log_audit_event(get_current_user_id(), get_text("return.failed_audit"), success=False)

    conn.close()


def return_book():
    """Return a book (calls enhanced version)"""
    enhanced_return_book()


def renew_book():
    """Renew a book loan"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to renew books.")
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    try:
        book_id = input("Enter Book ID to renew: ").strip()
        user_id = input("Enter User ID: ").strip()

        # Get loan details
        cursor.execute('''
        SELECT loan_id, due_date, renewal_count, status
        FROM book_loans
        WHERE book_id = ? AND user_id = ? AND status IN ('active', 'overdue')
        ''', (book_id, user_id))

        loan = cursor.fetchone()

        if not loan:
            print("No active loan found for this book and user.")
            conn.close()
            return

        loan_id, due_date, renewal_count, status = loan

        # Check renewal limits
        cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "max_renewals"')
        max_renewals = int(cursor.fetchone()[0])

        if renewal_count >= max_renewals:
            print(f"Maximum renewals ({max_renewals}) already reached.")
            conn.close()
            return

        # Check for reservations
        cursor.execute('''
        SELECT COUNT(*) FROM book_reservations
        WHERE book_id = ? AND status = 'active'
        ''', (book_id,))

        reservations = cursor.fetchone()[0]

        if reservations > 0:
            print("Cannot renew: Book has active reservations.")
            conn.close()
            return

        # Get loan period
        cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "loan_period_days"')
        loan_period = int(cursor.fetchone()[0])

        # Calculate new due date
        current_due = datetime.strptime(due_date, '%Y-%m-%d %H:%M:%S')
        new_due_date = current_due + timedelta(days=loan_period)

        # Update loan
        cursor.execute('''
        UPDATE book_loans
        SET due_date = ?, renewal_count = renewal_count + 1, status = 'active'
        WHERE loan_id = ?
        ''', (new_due_date.strftime('%Y-%m-%d %H:%M:%S'), loan_id))

        conn.commit()

        # FIXED: Log the action using get_current_user_id() helper function
        log_audit_event(get_current_user_id(), f"Renewed book {book_id} for {user_id}", "book_loans", str(loan_id))

        print("✅ Book renewed successfully!")
        print(f"New due date: {new_due_date.strftime('%Y-%m-%d')}")
        print(f"Renewals used: {renewal_count + 1}/{max_renewals}")

    except sqlite3.Error as e:
        print(f"Error renewing book: {e}")

    conn.close()


def reserve_book(book_id: str = None):
    """Enhanced book reservation system with priority queue"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print(get_text("auth.login_required", action=get_text("reservation.title")))
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    try:
        if book_id is None:
            book_id = input(get_text("reservation.enter_book_id") + ": ").strip()

        # Check if book exists
        cursor.execute('SELECT title, status FROM books WHERE book_id = ?', (book_id,))
        book = cursor.fetchone()

        if not book:
            print(get_text("reservation.not_found", book_id=book_id))
            conn.close()
            return

        title, status = book

        if status == 'available':
            print(get_text("reservation.book_available"))
            checkout_now = input(get_text("reservation.checkout_now_prompt") + " " + get_text("common.yes_no_prompt") + ": ").strip().lower()
            if checkout_now == 'y':
                enhanced_checkout_book(book_id)
                conn.close()
                return

        # Get user ID
        user_id = input(get_text("reservation.enter_user_id") + ": ").strip()

        # Check if user already has a reservation for this book
        cursor.execute('''
        SELECT reservation_id FROM book_reservations
        WHERE book_id = ? AND user_id = ? AND status = 'active'
        ''', (book_id, user_id))

        existing_reservation = cursor.fetchone()

        if existing_reservation:
            print(get_text("reservation.already_reserved"))
            conn.close()
            return

        # Get next priority order
        cursor.execute('''
        SELECT COALESCE(MAX(priority_order), 0) + 1
        FROM book_reservations
        WHERE book_id = ? AND status = 'active'
        ''', (book_id,))

        priority_order = cursor.fetchone()[0]

        # Get reservation period
        cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = "reservation_period_days"')
        reservation_days = int(cursor.fetchone()[0])

        # Create reservation
        reservation_date = datetime.now()
        expiry_date = reservation_date + timedelta(days=reservation_days)

        cursor.execute('''
        INSERT INTO book_reservations
        (book_id, user_id, reservation_date, expiry_date, status, priority_order)
        VALUES (?, ?, ?, ?, 'active', ?)
        ''', (
            book_id, user_id,
            reservation_date.strftime('%Y-%m-%d %H:%M:%S'),
            expiry_date.strftime('%Y-%m-%d %H:%M:%S'),
            priority_order
        ))

        reservation_id = cursor.lastrowid

        # Count total reservations for this book
        cursor.execute('''
        SELECT COUNT(*) FROM book_reservations
        WHERE book_id = ? AND status = 'active'
        ''', (book_id,))

        total_reservations = cursor.fetchone()[0]

        conn.commit()

        # FIXED: Log the action using get_current_user_id() helper function
        log_audit_event(get_current_user_id(), f"Created reservation for book {book_id}", "book_reservations", str(reservation_id))

        print("\n✅ " + get_text("reservation.success"))
        print(get_text("reservation.book_info", title=title, book_id=book_id))
        print(get_text("reservation.user_info", user_id=user_id))
        print(get_text("reservation.position_info", position=priority_order))
        print(get_text("reservation.total_reservations", count=total_reservations))
        print(get_text("reservation.expiry_info", date=expiry_date.strftime('%Y-%m-%d')))

        # Send confirmation
        try:
            send_reservation_confirmation(user_id, book_id, title, priority_order, expiry_date.strftime('%Y-%m-%d'))
            print("✅ " + get_text("reservation.confirmation_sent"))
        except Exception as e:
            print("⚠️  " + get_text("reservation.confirmation_failed", error=str(e)))

    except sqlite3.Error as e:
        conn.rollback()
        print(get_text("reservation.error", error=str(e)))
        log_audit_event(get_current_user_id(), get_text("reservation.failed_audit"), success=False)

    conn.close()


def manage_reservations():
    """Manage book reservations"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to manage reservations.")
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    while True:
        print("\nReservation Management:")
        print("======================")
        print("1. View All Reservations")
        print("2. View User Reservations")
        print("3. Cancel Reservation")
        print("4. Process Expired Reservations")
        print("5. Return to menu")

        choice = input("Enter your choice (1-5): ").strip()

        if choice == '5':
            break

        try:
            if choice == '1':
                # View all reservations
                cursor.execute('''
                SELECT br.reservation_id, br.book_id, b.title, br.user_id,
                       br.reservation_date, br.expiry_date, br.priority_order, br.status
                FROM book_reservations br
                JOIN books b ON br.book_id = b.book_id
                WHERE br.status = 'active'
                ORDER BY br.book_id, br.priority_order
                ''')

                reservations = cursor.fetchall()

                if not reservations:
                    print("No active reservations found.")
                    continue

                print(f"\nActive Reservations ({len(reservations)}):")
                print("-" * 90)
                print(f"{'ID':<4} {'Book ID':<8} {'Title':<25} {'User':<12} {'Reserved':<12} {'Expires':<12} {'Pos':<3}")
                print("-" * 90)

                for res in reservations:
                    res_id, book_id, title, user_id, res_date, exp_date, priority, status = res
                    title_display = title[:24] if len(title) > 25 else title
                    print(f"{res_id:<4} {book_id:<8} {title_display:<25} {user_id:<12} {res_date[:10]:<12} {exp_date[:10]:<12} {priority:<3}")

                print("-" * 90)

            elif choice == '2':
                # View user reservations
                user_id = input("Enter User ID: ").strip()

                cursor.execute('''
                SELECT br.reservation_id, br.book_id, b.title, b.status,
                       br.reservation_date, br.expiry_date, br.priority_order
                FROM book_reservations br
                JOIN books b ON br.book_id = b.book_id
                WHERE br.user_id = ? AND br.status = 'active'
                ORDER BY br.reservation_date
                ''', (user_id,))

                user_reservations = cursor.fetchall()

                if not user_reservations:
                    print(f"No active reservations found for {user_id}.")
                    continue

                print(f"\nReservations for {user_id}:")
                print("-" * 80)
                print(f"{'ID':<4} {'Book ID':<8} {'Title':<25} {'Status':<12} {'Position':<8} {'Expires':<12}")
                print("-" * 80)

                for res in user_reservations:
                    res_id, book_id, title, book_status, res_date, exp_date, priority = res
                    title_display = title[:24] if len(title) > 25 else title
                    print(f"{res_id:<4} {book_id:<8} {title_display:<25} {book_status:<12} {priority:<8} {exp_date[:10]:<12}")

                print("-" * 80)

            elif choice == '3':
                # Cancel reservation
                reservation_id = input("Enter Reservation ID to cancel: ").strip()

                cursor.execute('''
                SELECT br.user_id, b.title FROM book_reservations br
                JOIN books b ON br.book_id = b.book_id
                WHERE br.reservation_id = ? AND br.status = 'active'
                ''', (reservation_id,))

                reservation = cursor.fetchone()

                if not reservation:
                    print("No active reservation found with that ID.")
                    continue

                user_id, title = reservation

                confirm = input(f"Cancel reservation for '{title}' by {user_id}? (y/n): ").strip().lower()

                if confirm == 'y':
                    cursor.execute('''
                    UPDATE book_reservations SET status = 'cancelled'
                    WHERE reservation_id = ?
                    ''', (reservation_id,))

                    # Update priority order for remaining reservations
                    cursor.execute('''
                    SELECT book_id FROM book_reservations WHERE reservation_id = ?
                    ''', (reservation_id,))
                    book_id = cursor.fetchone()[0]

                    cursor.execute('''
                    UPDATE book_reservations
                    SET priority_order = priority_order - 1
                    WHERE book_id = ? AND status = 'active'
                    AND priority_order > (
                        SELECT priority_order FROM book_reservations
                        WHERE reservation_id = ?
                    )
                    ''', (book_id, reservation_id))

                    conn.commit()

                    # FIXED: Log the action using get_current_user_id() helper function
                    log_audit_event(get_current_user_id(), f"Cancelled reservation {reservation_id}", "book_reservations", reservation_id)
                    print("✅ Reservation cancelled successfully!")

            elif choice == '4':
                # Process expired reservations
                cursor.execute('''
                SELECT reservation_id, user_id, book_id
                FROM book_reservations
                WHERE status = 'active' AND expiry_date < datetime('now')
                ''')

                expired_reservations = cursor.fetchall()

                if not expired_reservations:
                    print("No expired reservations found.")
                    continue

                print(f"Found {len(expired_reservations)} expired reservations.")

                for res_id, user_id, book_id in expired_reservations:
                    cursor.execute('''
                    UPDATE book_reservations SET status = 'expired'
                    WHERE reservation_id = ?
                    ''', (res_id,))

                    # Check if book should become available
                    cursor.execute('''
                    SELECT COUNT(*) FROM book_reservations
                    WHERE book_id = ? AND status = 'active'
                    ''', (book_id,))

                    remaining_reservations = cursor.fetchone()[0]

                    if remaining_reservations == 0:
                        cursor.execute('''
                        UPDATE books SET status = 'available' WHERE book_id = ?
                        ''', (book_id,))

                conn.commit()
                print(f"✅ Processed {len(expired_reservations)} expired reservations.")

        except sqlite3.Error as e:
            print(f"Error managing reservations: {e}")

    conn.close()


def view_overdue_books():
    """View all overdue books"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to view overdue books.")
        return

    if not auth.check_permission('view_reports'):
        print("You don't have permission to view overdue books.")
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    try:
        cursor.execute('''
        SELECT bl.user_id, bl.book_id, b.title, bl.due_date,
               julianday('now') - julianday(bl.due_date) as days_overdue,
               bl.fine_amount
        FROM book_loans bl
        JOIN books b ON bl.book_id = b.book_id
        WHERE bl.status = 'overdue'
        ORDER BY days_overdue DESC
        ''')

        overdue_books = cursor.fetchall()

        if not overdue_books:
            print("No overdue books found.")
            return

        print(f"\nOverdue Books ({len(overdue_books)} total):")
        print("=" * 90)
        print(f"{'User ID':<12} {'Book ID':<10} {'Title':<30} {'Due Date':<12} {'Days Over':<10} {'Fine':<8}")
        print("-" * 90)

        total_fines = 0
        for book in overdue_books:
            user_id, book_id, title, due_date, days_overdue, fine = book
            title_display = (title[:27] + '...') if len(title) > 30 else title
            fine_amount = fine if fine else 0
            total_fines += fine_amount

            print(f"{user_id:<12} {book_id:<10} {title_display:<30} {due_date[:10]:<12} {int(days_overdue):<10} £{fine_amount:.2f}")

        print("-" * 90)
        print(f"Total Outstanding Fines: £{total_fines:.2f}")
        print("=" * 90)

    except sqlite3.Error as e:
        print(f"Error viewing overdue books: {e}")

    conn.close()


def view_loan_history():
    """View loan history"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to view loan history.")
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    print("\nLoan History Options:")
    print("1. View all recent loans")
    print("2. View loans by user")
    print("3. View loans by book")

    choice = input("Enter your choice (1-3): ").strip()

    try:
        if choice == '1':
            # Recent loans
            cursor.execute('''
            SELECT bl.loan_id, bl.user_id, bl.book_id, b.title,
                   bl.checkout_date, bl.due_date, bl.return_date, bl.status
            FROM book_loans bl
            JOIN books b ON bl.book_id = b.book_id
            ORDER BY bl.checkout_date DESC
            LIMIT 50
            ''')

            title = "Recent Loans (Last 50)"

        elif choice == '2':
            # Loans by user
            user_id = input("Enter User ID: ").strip()
            cursor.execute('''
            SELECT bl.loan_id, bl.book_id, b.title,
                   bl.checkout_date, bl.due_date, bl.return_date, bl.status
            FROM book_loans bl
            JOIN books b ON bl.book_id = b.book_id
            WHERE bl.user_id = ?
            ORDER BY bl.checkout_date DESC
            ''', (user_id,))

            title = f"Loans for User: {user_id}"

        elif choice == '3':
            # Loans by book
            book_id = input("Enter Book ID: ").strip()
            cursor.execute('''
            SELECT bl.loan_id, bl.user_id, bl.checkout_date,
                   bl.due_date, bl.return_date, bl.status
            FROM book_loans bl
            WHERE bl.book_id = ?
            ORDER BY bl.checkout_date DESC
            ''', (book_id,))

            title = f"Loans for Book: {book_id}"

        else:
            print("Invalid choice.")
            conn.close()
            return

        loans = cursor.fetchall()

        if not loans:
            print("No loan history found.")
            return

        print(f"\n{title}")
        print("=" * 100)

        if choice == '1':
            print(f"{'Loan ID':<8} {'User':<12} {'Book ID':<10} {'Title':<25} {'Checkout':<12} {'Status':<10}")
        elif choice == '2':
            print(f"{'Loan ID':<8} {'Book ID':<10} {'Title':<25} {'Checkout':<12} {'Due':<12} {'Status':<10}")
        elif choice == '3':
            print(f"{'Loan ID':<8} {'User':<12} {'Checkout':<12} {'Due':<12} {'Returned':<12} {'Status':<10}")

        print("-" * 100)

        for loan in loans:
            if choice == '1':
                loan_id, user_id, book_id, title, checkout, due, returned, status = loan
                title_display = (title[:22] + '...') if len(title) > 25 else title
                print(f"{loan_id:<8} {user_id:<12} {book_id:<10} {title_display:<25} {checkout[:10]:<12} {status:<10}")
            elif choice == '2':
                loan_id, book_id, title, checkout, due, returned, status = loan
                title_display = (title[:22] + '...') if len(title) > 25 else title
                print(f"{loan_id:<8} {book_id:<10} {title_display:<25} {checkout[:10]:<12} {due[:10]:<12} {status:<10}")
            elif choice == '3':
                loan_id, user_id, checkout, due, returned, status = loan
                returned_display = returned[:10] if returned else "N/A"
                print(f"{loan_id:<8} {user_id:<12} {checkout[:10]:<12} {due[:10]:<12} {returned_display:<12} {status:<10}")

        print("=" * 100)

    except sqlite3.Error as e:
        print(f"Error viewing loan history: {e}")

    conn.close()


