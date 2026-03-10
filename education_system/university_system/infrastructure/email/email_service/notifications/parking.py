"""Parking notification emails."""

from __future__ import annotations

from datetime import datetime

from education_system.university_system.infrastructure.database.db import sqlite3

from education_system.university_system.infrastructure.email.email_db_utilities import execute_db_operation
from education_system.university_system.core.logs import handle_exception, log_event
from education_system.university_system.infrastructure.email.templates import render_template


@handle_exception
def send_permit_confirmation(permit_id, email, zone, permit_type, start_date, end_date):
    """Send a parking permit confirmation email"""
    from education_system.university_system.infrastructure.email.email_service.queue import queue_email

    subject, body = render_template('parking_permit_confirmation', {
        'permit_id': permit_id,
        'zone': zone,
        'zone_description': '',
        'permit_type': permit_type,
        'start_date': start_date,
        'end_date': end_date,
        'vehicle_info': '',
        'status': 'Active',
        'student_name': 'Permit Holder'
    })

    success = queue_email(email, subject, body)

    def _log_permit_email(cursor):
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            email,
            subject,
            current_time,
            'sent' if success else 'failed',
            f"Parking Permit Confirmation (ID: {permit_id})"
        ))
        return True

    try:
        execute_db_operation(_log_permit_email)

        if success:
            log_event('info', f"Permit confirmation email sent to {email}")
        else:
            log_event('error', f"Failed to send permit confirmation email to {email}")

        return success

    except Exception as e:
        log_event('error', f"Error sending permit confirmation: {e}")
        return False

@handle_exception
def send_permit_update_confirmation(permit_id, email, updated_fields):
    """Send a parking permit update confirmation email"""
    from education_system.university_system.infrastructure.email.email_service.queue import queue_email

    field_updates = "\n".join([f"- {field}: {value}" for field, value in updated_fields.items()])

    subject, body = render_template('parking_permit_updated', {
        'permit_id': permit_id,
        'updates': field_updates
    })

    success = queue_email(email, subject, body)

    def _log_permit_update_email(cursor):
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            email,
            subject,
            current_time,
            'sent' if success else 'failed',
            f"Parking Permit Update (ID: {permit_id})"
        ))
        return True

    try:
        execute_db_operation(_log_permit_update_email)

        if success:
            log_event('info', f"Permit update confirmation email sent to {email}")
        else:
            log_event('error', f"Failed to send permit update confirmation email to {email}")

        return success

    except Exception as e:
        log_event('error', f"Error sending permit update confirmation: {e}")
        return False
