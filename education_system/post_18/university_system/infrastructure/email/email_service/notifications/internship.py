"""Internship notification emails."""

from __future__ import annotations

from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import sqlite3

from education_system.post_18.university_system.infrastructure.email.email_db_utilities import execute_db_operation
from education_system.post_18.university_system.core.logs import handle_exception, log_event
from education_system.post_18.university_system.infrastructure.email.templates import render_template


@handle_exception
def send_internship_notification(student_id, internship_id, status, feedback=None):
    """Send a notification about an internship application status update"""
    from education_system.post_18.university_system.infrastructure.email.email_service.queue import queue_email

    def _send_internship_notification(cursor):
        cursor.execute('''
        SELECT s.email_address, s.first_name, s.last_name, i.title, i.company
        FROM students s
        JOIN internships i ON i.internship_id = ?
        WHERE s.student_id = ?
        ''', (internship_id, student_id))

        result = cursor.fetchone()

        if not result:
            log_event('error', "Could not find student or internship details")
            return False

        email_address, first_name, last_name, internship_title, company = result

        if status == 'approved':
            template_name="internships/internship_application_approved"
        elif status == 'rejected':
            template_name="internships/internship_application_rejected"
        else:
            template_name="internships/internship_application_status_update"

        subject, message = render_template(template_name, {
            "first_name": first_name,
            "last_name": last_name,
            "internship_title": internship_title,
            "company": company,
            "status": status
        })

        if feedback and message:
            message += f"\n\nFeedback: {feedback}"

        success = queue_email(email_address, subject, message)

        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to, student_id)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            email_address,
            subject,
            current_time,
            'sent' if success else 'failed',
            f"Internship Update ({status})",
            student_id
        ))

        return success

    try:
        result = execute_db_operation(_send_internship_notification)

        if result:
            log_event('info', f"Internship notification email sent to student {student_id}")
        else:
            log_event('error', "Failed to send internship notification email")

        return result

    except Exception as e:
        log_event('error', f"Error sending internship notification: {e}")
        return False

@handle_exception
def send_application_confirmation(student_id, internship_id):
    """Send a confirmation email when a student applies for an internship"""
    from education_system.post_18.university_system.infrastructure.email.email_service.queue import queue_email

    def _send_application_confirmation(cursor):
        cursor.execute('''
        SELECT s.email_address, s.first_name, s.last_name, i.title, i.company, i.deadline_date
        FROM students s
        JOIN internships i ON i.internship_id = ?
        WHERE s.student_id = ?
        ''', (internship_id, student_id))

        result = cursor.fetchone()

        if not result:
            log_event('error', "Could not find student or internship details")
            return False

        email_address, first_name, last_name, internship_title, company, deadline = result

        subject, message = render_template('internship_application_confirmed', {
            'first_name': first_name,
            'last_name': last_name,
            'internship_title': internship_title,
            'company': company,
            'deadline': deadline
        })

        success = queue_email(email_address, subject, message)

        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to, student_id)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            email_address,
            subject,
            current_time,
            'sent' if success else 'failed',
            "Internship Application",
            student_id
        ))

        return success

    try:
        result = execute_db_operation(_send_application_confirmation)

        if result:
            log_event('info', f"Internship application confirmation email sent to student {student_id}")
        else:
            log_event('error', "Failed to send internship application confirmation email")

        return result

    except Exception as e:
        log_event('error', f"Error sending application confirmation: {e}")
        return False
