"""Health portal notification emails."""

from __future__ import annotations

from datetime import datetime

from education_system.systems.university.infrastructure.database.db import sqlite3

from education_system.systems.university.infrastructure.email.email_db_utilities import execute_db_operation
from education_system.systems.university.infrastructure.logs import handle_exception, log_event
from education_system.systems.university.infrastructure.email.templates import render_template


@handle_exception
def send_appointment_confirmation(student_id, appointment_id, appointment_date, appointment_time, provider, appointment_type):
    """Send an email confirmation for a scheduled health appointment"""
    from education_system.systems.university.infrastructure.email.email_service.queue import queue_email

    def _send_appointment_confirmation(cursor):
        cursor.execute('SELECT email_address, first_name, last_name FROM students WHERE student_id = ?', (student_id,))
        result = cursor.fetchone()

        if not result:
            log_event('error', "Could not find student email address")
            return False

        email_address, first_name, last_name = result

        subject, body = render_template('health_appointment_confirmation', {
            'first_name': first_name,
            'last_name': last_name,
            'appointment_id': appointment_id,
            'appointment_type': appointment_type,
            'appointment_date': appointment_date,
            'appointment_time': appointment_time,
            'provider': provider
        })

        success = queue_email(email_address, subject, body)

        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to, student_id)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            email_address,
            subject,
            current_time,
            'sent' if success else 'failed',
            f"Health Appointment (ID: {appointment_id})",
            student_id
        ))

        return success

    try:
        result = execute_db_operation(_send_appointment_confirmation)

        if result:
            log_event('info', f"Appointment confirmation email sent for appointment {appointment_id}")
        else:
            log_event('error', "Failed to send appointment confirmation email")

        return result

    except Exception as e:
        log_event('error', f"Error sending appointment confirmation email: {e}")
        return False

@handle_exception
def send_health_notification(student_id, advisory_title, advisory_description, severity):
    """Send a health advisory notification to a student"""
    from education_system.systems.university.infrastructure.email.email_service.queue import queue_email

    def _send_health_notification(cursor):
        cursor.execute('SELECT email_address, first_name, last_name FROM students WHERE student_id = ?', (student_id,))
        result = cursor.fetchone()

        if not result:
            log_event('error', f"Could not find student with ID {student_id}")
            return False

        email_address, first_name, last_name = result

        subject, body = render_template('health_advisory', {
            'first_name': first_name,
            'last_name': last_name,
            'advisory_title': advisory_title,
            'severity': severity,
            'advisory_description': advisory_description
        })

        success = queue_email(email_address, subject, body)

        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to, student_id)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            email_address,
            subject,
            current_time,
            'sent' if success else 'failed',
            f"Health Advisory ({severity})",
            student_id
        ))

        return success

    try:
        result = execute_db_operation(_send_health_notification)

        if result:
            log_event('info', f"Health notification email sent to student {student_id}")
        else:
            log_event('error', "Failed to send health notification email")

        return result

    except Exception as e:
        log_event('error', f"Error sending health notification email: {e}")
        return False
