"""Library notification emails."""

from __future__ import annotations

from datetime import datetime

from education_system.university_system.infrastructure.database.db import sqlite3

from education_system.university_system.infrastructure.email.email_db_utilities import execute_db_operation
from education_system.university_system.core.logs import handle_exception, log_event
from education_system.university_system.infrastructure.email.templates import render_template


def _get_user_info(cursor, user_id):
    """Get user info from students or users table"""
    cursor.execute('''
    SELECT email_address, title, first_name, last_name
    FROM students WHERE student_id = ?
    ''', (user_id,))
    user_info = cursor.fetchone()

    if not user_info:
        cursor.execute('''
        SELECT email, '', username, role
        FROM users WHERE id = ?
        ''', (user_id,))
        user_info = cursor.fetchone()

    if not user_info:
        cursor.execute('''
        SELECT email, '', first_name, last_name
        FROM users WHERE username = ?
        ''', (user_id,))
        user_info = cursor.fetchone()

    return user_info


@handle_exception
def send_book_checkout_confirmation(user_id, book_id, book_title, due_date):
    """Send an email confirmation for a book checkout"""
    from education_system.university_system.infrastructure.email.email_service.queue import queue_email

    def _send_checkout_confirmation(cursor):
        user_info = _get_user_info(cursor, user_id)

        if not user_info:
            log_event('error', f"User {user_id} not found")
            return False

        email, title, first_name, last_name = user_info

        subject, body = render_template('library_book_checkout_confirmation', {
            'title': title or '',
            'first_name': first_name,
            'last_name': last_name,
            'book_title': book_title,
            'book_id': book_id,
            'due_date': due_date
        })

        success = queue_email(email, subject, body)

        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            email,
            subject,
            current_time,
            'sent' if success else 'failed',
            f"Book Checkout: {book_title}"
        ))

        return success

    try:
        result = execute_db_operation(_send_checkout_confirmation)

        if result:
            log_event('info', f"Checkout confirmation email sent for book {book_id}")
        else:
            log_event('error', f"Failed to send checkout confirmation email")

        return result

    except Exception as e:
        log_event('error', f"Error sending book checkout confirmation: {e}")
        return False

@handle_exception
def send_book_return_reminder(user_id, book_id, book_title, due_date):
    """Send a reminder email for an upcoming book return date"""
    from education_system.university_system.infrastructure.email.email_service.queue import queue_email

    def _send_return_reminder(cursor):
        user_info = _get_user_info(cursor, user_id)

        if not user_info:
            log_event('error', f"User {user_id} not found")
            return False

        email, title, first_name, last_name = user_info

        subject, body = render_template('library_return_reminder', {
            'title': title or '',
            'first_name': first_name,
            'last_name': last_name,
            'book_title': book_title,
            'book_id': book_id,
            'due_date': due_date
        })

        success = queue_email(email, subject, body)

        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            email,
            subject,
            current_time,
            'sent' if success else 'failed',
            f"Book Return Reminder: {book_title}"
        ))

        return success

    try:
        result = execute_db_operation(_send_return_reminder)

        if result:
            log_event('info', f"Return reminder email sent for book {book_id}")
        else:
            log_event('error', f"Failed to send return reminder email")

        return result

    except Exception as e:
        log_event('error', f"Error sending book return reminder: {e}")
        return False

@handle_exception
def send_overdue_notification(user_id, book_id, book_title, due_date, days_overdue):
    """Send a notification for an overdue book"""
    from education_system.university_system.infrastructure.email.email_service.queue import queue_email

    def _send_overdue_notification(cursor):
        user_info = _get_user_info(cursor, user_id)

        if not user_info:
            log_event('error', f"User {user_id} not found")
            return False

        email, title, first_name, last_name = user_info

        subject, body = render_template('library_overdue_notice', {
            'title': title or '',
            'first_name': first_name,
            'last_name': last_name,
            'book_title': book_title,
            'book_id': book_id,
            'days_overdue': days_overdue,
            'due_date': due_date
        })

        success = queue_email(email, subject, body)

        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            email,
            subject,
            current_time,
            'sent' if success else 'failed',
            f"Overdue Notice: {book_title} ({days_overdue} days)"
        ))

        return success

    try:
        result = execute_db_operation(_send_overdue_notification)

        if result:
            log_event('info', f"Overdue notification email sent for book {book_id}")
        else:
            log_event('error', f"Failed to send overdue notification email")

        return result

    except Exception as e:
        log_event('error', f"Error sending overdue notification: {e}")
        return False
