"""Stored email CRUD operations."""

from __future__ import annotations

from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta

from education_system.university_system.infrastructure.email.email_db_utilities import execute_db_operation
from education_system.university_system.core.logs import handle_exception, log_event


@handle_exception
def get_stored_emails(limit=50, offset=0, recipient_filter=None, date_filter=None, sender_filter=None):
    """Simplified get stored emails function

    Args:
        limit: Maximum number of emails to return
        offset: Number of emails to skip
        recipient_filter: Filter by recipient email (partial match)
        date_filter: Filter by date
        sender_filter: Filter by sender email (exact match) - used for non-admin users
    """

    def _get_emails(cursor):
        query = '''
        SELECT id, recipient_email, subject, body, sender_email, sender_name,
               cc_recipients, bcc_recipients, attachment_paths, created_date,
               template_name, template_vars, related_to, student_id
        FROM stored_emails
        '''
        params = []

        # Add filters
        conditions = []
        if recipient_filter:
            conditions.append("recipient_email LIKE ?")
            params.append(f"%{recipient_filter}%")

        if date_filter:
            conditions.append("DATE(created_date) = ?")
            params.append(date_filter)

        if sender_filter:
            conditions.append("sender_email = ?")
            params.append(sender_filter)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_date DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        emails = cursor.fetchall()

        # Get total count
        count_query = "SELECT COUNT(*) FROM stored_emails"
        if conditions:
            count_query += " WHERE " + " AND ".join(conditions)
            cursor.execute(count_query, params[:-2])
        else:
            cursor.execute(count_query)

        total_count = cursor.fetchone()[0]

        return {
            'emails': [
                {
                    'id': email[0], 'recipient_email': email[1], 'subject': email[2],
                    'body': email[3], 'sender_email': email[4], 'sender_name': email[5],
                    'cc_recipients': email[6], 'bcc_recipients': email[7],
                    'attachment_paths': email[8], 'created_date': email[9],
                    'template_name': email[10], 'template_vars': email[11],
                    'related_to': email[12], 'student_id': email[13]
                } for email in emails
            ],
            'total_count': total_count,
            'limit': limit,
            'offset': offset
        }

    try:
        return execute_db_operation(_get_emails)
    except sqlite3.Error as e:
        log_event('error', f"Database error retrieving stored emails: {e}")
        return {'emails': [], 'total_count': 0, 'limit': limit, 'offset': offset}

@handle_exception
def delete_stored_email(email_id):
    """Delete a stored email by ID"""
    def _delete_email(cursor):
        cursor.execute('DELETE FROM stored_emails WHERE id = ?', (email_id,))
        deleted_count = cursor.rowcount

        if deleted_count > 0:
            log_event('info', f"Deleted stored email ID: {email_id}")
            return True
        else:
            log_event('warning', f"No stored email found with ID: {email_id}")
            return False

    try:
        return execute_db_operation(_delete_email)
    except sqlite3.Error as e:
        log_event('error', f"Database error deleting stored email: {e}")
        return False

@handle_exception
def clear_stored_emails(older_than_days=None):
    """Clear stored emails, optionally only those older than specified days"""
    def _clear_emails(cursor):
        if older_than_days:
            cutoff_date = (datetime.now() - timedelta(days=older_than_days)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('DELETE FROM stored_emails WHERE created_date < ?', (cutoff_date,))
            log_event('info', f"Deleted {cursor.rowcount} stored emails older than {older_than_days} days")
        else:
            cursor.execute('DELETE FROM stored_emails')
            log_event('info', f"Deleted all {cursor.rowcount} stored emails")

        return cursor.rowcount

    try:
        return execute_db_operation(_clear_emails)
    except sqlite3.Error as e:
        log_event('error', f"Database error clearing stored emails: {e}")
        return 0
