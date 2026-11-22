from education_system.systems.university.infrastructure.database.db import sqlite3, DatabaseManager, get_connection as get_db_conn
from education_system.systems.university.infrastructure.shared_context import get_auth
import os
import re
import csv
import random
import json
import requests
from datetime import datetime, timedelta
from education_system.paths import UNIVERSITY_QR_CODES_DIR, UNIVERSITY_BACKUP_DIR
from education_system.systems.university.infrastructure.email import (
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
from education_system.systems.university.infrastructure.logging.log_config import configure_logging

# CONSOLIDATED DATABASE FILE - Using the same database as main system
from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH
from education_system.systems.university.domains.finance.infrastructure.finance_integration import record_payment_to_finance
from education_system.systems.university.infrastructure.i18n import (
    get_text,
    get_current_language,
)
from education_system.systems.university.infrastructure.utils.language_selector import (
    display_language_menu_option,
)
from education_system.systems.university.domains.library.domain.library.database import get_db_connection, log_audit_event
from education_system.systems.university.domains.library.domain.library.settings import get_current_user_id, update_reading_goals, record_usage_analytics
from education_system.systems.university.domains.library.domain.library.notifications import send_enhanced_checkout_notification, send_reservation_available_notification, send_reservation_confirmation
from education_system.systems.university.domains.library.domain.library.recommendations import get_similar_books
DATABASE_FILE = str(UNIVERSITY_DEFAULT_DB_PATH)

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


def _desk(fn, *args, **kwargs):
    """Run a shared circulation rule (``application/library/circulation``) in
    one transaction, send its notices, and print a refusal instead of raising."""
    from education_system.systems.university.application.teaching import (
        occurrences as timetable_occurrences,
    )
    conn = get_db_connection()
    if not conn:
        return None
    try:
        result = fn(conn, *args, **kwargs)
        conn.commit()
    except ValueError as exc:
        conn.rollback()
        print(f"Refused: {exc}")
        return None
    finally:
        conn.close()
    emails = result.get("emails") if isinstance(result, dict) else None
    if emails:
        timetable_occurrences.send_emails(emails)
    return result


def _staff_ok(auth, *permissions):
    if not auth or not auth.current_user:
        print("You must be logged in.")
        return False
    if permissions and not any(auth.check_permission(p) for p in permissions):
        print("You don't have permission to do that.")
        return False
    return True


def enhanced_checkout_book(book_id=None):
    """Lend a copy: scan its barcode (or give a title's book ID / ISBN for the
    first copy on the shelf) and the borrower — a student ID, or a staff
    username. Loan length, limits and blocks come from the borrower's
    category and the item type."""
    from education_system.systems.university.application.library import circulation as circ
    auth = get_auth()
    if not _staff_ok(auth, 'manage_loans', 'checkout_books'):
        return
    item = book_id or input("Scan copy barcode (or Book ID / ISBN): ").strip()
    if item.startswith("LIBRARY_BOOK:"):
        item = item.split(":")[1]
    borrower = input("Borrower (student ID or staff username): ").strip()
    if not item or not borrower:
        return
    staff = get_current_user_id()
    loan = _desk(circ.checkout, item, borrower, staff=staff, method="cli")
    if loan is None and input("Lend anyway as a staff override? (y/N): ").strip().lower() == "y":
        loan = _desk(circ.checkout, item, borrower, staff=staff, method="cli", override=True)
    if not loan:
        return
    print("=" * 60)
    print(f"✅ {loan['barcode']} lent to {loan['borrower']['name'] or loan['borrower']['ref']} "
          f"({loan['borrower']['category']})")
    print(f"   Due: {loan['due_date'][:16]}")
    print("=" * 60)
    log_audit_event(staff, f"Checked out {loan['barcode']} to {loan['borrower']['ref']}",
                    "book_loans", str(loan["loan_id"]))

def checkout_book():
    """Check out a book (calls enhanced version)"""
    enhanced_checkout_book()


def enhanced_return_book():
    """Check a copy back in: overdue fine, damage, and hand-off to the next
    person waiting (holds shelf) all follow the shared rules."""
    from education_system.systems.university.application.library import circulation as circ
    auth = get_auth()
    if not _staff_ok(auth, 'manage_loans', 'checkout_books'):
        return
    item = input("Scan copy barcode (or loan ID): ").strip()
    if not item:
        return
    damaged = input("Is it damaged? (y/N): ").strip().lower() == "y"
    notes = input("Condition notes (optional): ").strip() or None
    result = _desk(circ.return_item, item, condition="damaged" if damaged else "good",
                   notes=notes, staff=get_current_user_id())
    if not result:
        return
    print(f"✅ Returned (loan {result['loan_id']})."
          + (f" Overdue fine £{result['fine']:.2f}." if result["fine"] else " No fine."))
    if result["held"]:
        print("📌 Requested by another reader — put it on the holds shelf (they have been told).")
    log_audit_event(get_current_user_id(), f"Returned loan {result['loan_id']}", "book_loans")

def return_book():
    """Return a book (calls enhanced version)"""
    enhanced_return_book()


def renew_book():
    """Renew a loan unless it is recalled, not renewable, at its limit or
    wanted by someone else."""
    from education_system.systems.university.application.library import circulation as circ
    if not _staff_ok(get_auth()):
        return
    item = input("Copy barcode or loan ID to renew: ").strip()
    result = _desk(circ.renew, item) if item else None
    if result:
        print(f"✅ Renewed. New due date {result['due_date'][:16]}; "
              f"{result['renewals_left']} renewal(s) left.")

def reserve_book(book_id: str = None):
    """Request a title: straight to the holds shelf if a copy is in, otherwise
    queued — and the loan held longest is recalled."""
    from education_system.systems.university.application.library import circulation as circ
    if not _staff_ok(get_auth()):
        return
    book_id = book_id or input("Book ID: ").strip()
    borrower = input("For (student ID or staff username): ").strip()
    result = _desk(circ.place_hold, book_id, borrower) if book_id and borrower else None
    if result:
        print("✅ A copy is in — it is on the holds shelf now." if result["ready"] else
              f"✅ Request placed: #{result['position']} in the queue.")

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
                    from education_system.systems.university.application.library import (
                        circulation as circ,
                    )
                    from education_system.systems.university.application.teaching import (
                        occurrences as timetable_occurrences,
                    )
                    try:
                        emails = circ.cancel_hold(conn, int(reservation_id))
                    except ValueError as exc:
                        print(f"Refused: {exc}")
                        continue
                    conn.commit()
                    timetable_occurrences.send_emails(emails)
                    log_audit_event(get_current_user_id(), f"Cancelled reservation {reservation_id}", "book_reservations", reservation_id)
                    print("✅ Reservation cancelled successfully!")

            elif choice == '4':
                # Uncollected holds pass to the next reader; requests past
                # their expiry date close.
                from education_system.systems.university.application.library import (
                    circulation as circ,
                )
                from education_system.systems.university.application.teaching import (
                    occurrences as timetable_occurrences,
                )
                result = circ.expire_holds(conn)
                conn.commit()
                timetable_occurrences.send_emails(result["emails"])
                print(f"✅ {len(result['expired'])} uncollected hold(s) and "
                      f"{result['lapsed']} lapsed request(s) closed.")

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


