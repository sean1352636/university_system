"""Alumni notification emails."""

from __future__ import annotations

from datetime import datetime

from education_system.systems.university.infrastructure.database.db import sqlite3

from education_system.systems.university.infrastructure.email.email_db_utilities import execute_db_operation
from education_system.systems.university.infrastructure.logs import handle_exception, log_event
from education_system.systems.university.infrastructure.email.templates import render_template


@handle_exception
def send_alumni_welcome_email(alumni_id, email_address, full_name):
    """Send a welcome email to a newly registered alumni"""
    from education_system.systems.university.infrastructure.email.email_service.queue import queue_email

    subject, message = render_template("alumni_welcome", {
        "full_name": full_name
    })

    success = queue_email(email_address, subject, message)

    def _log_alumni_email(cursor):
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            email_address,
            subject,
            current_time,
            'sent' if success else 'failed',
            f"Alumni Welcome (ID: {alumni_id})"
        ))
        return True

    try:
        execute_db_operation(_log_alumni_email)

        if success:
            log_event('info', f"Alumni welcome email sent to {email_address}")
        else:
            log_event('error', f"Failed to send alumni welcome email to {email_address}")

        return success

    except Exception as e:
        log_event('error', f"Error sending alumni welcome email: {e}")
        return False

def send_mentorship_notification(mentor_email, mentee_email, mentor_name, mentee_name, focus_area, start_date, end_date=None):
    from education_system.systems.university.infrastructure.email.email_service.core import send_email

    end_text = f" until {end_date}" if end_date else ""
    subject, body = render_template("mentorship_notification", {
        "mentor_name": mentor_name,
        "mentee_name": mentee_name,
        "focus_area": focus_area,
        "start_date": start_date,
        "end_text": end_text
    })

    send_email(mentor_email, subject, body)
    send_email(mentee_email, subject, body)

@handle_exception
def send_event_invitation(alumni_id, event_id=None, email_address=None, event_name=None, event_date=None, event_location=None):
    """Send an invitation to an alumni event"""
    from education_system.systems.university.infrastructure.email.email_service.queue import queue_email

    def _send_event_invitation(cursor):
        nonlocal email_address, event_name, event_date, event_location

        if email_address is None or event_name is None or event_date is None or event_location is None:
            if email_address is None:
                cursor.execute('SELECT email FROM alumni_profiles WHERE alumni_id = ?', (alumni_id,))
                result = cursor.fetchone()
                if not result:
                    log_event('error', f"Could not find email for alumni ID {alumni_id}")
                    return False
                email_address = result[0]

            if event_name is None or event_date is None or event_location is None:
                cursor.execute('''
                SELECT title as event_name, start_datetime as event_date, location
                FROM unified_events
                WHERE source_type = 'alumni' AND event_id = ?
                ''', (event_id,))

                result = cursor.fetchone()
                if not result:
                    log_event('error', f"Could not find event details for event ID {event_id}")
                    return False

                event_name, event_date, event_location = result

        subject, message = render_template("alumni_event_invitation", {
            "event_name": event_name,
            "event_date": event_date,
            "event_location": event_location
        })

        success = queue_email(email_address, subject, message)

        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            email_address,
            subject,
            current_time,
            'sent' if success else 'failed',
            f"Event Invitation: {event_name}"
        ))

        return success

    try:
        result = execute_db_operation(_send_event_invitation)

        if result:
            log_event('info', f"Event invitation sent to {email_address} for event: {event_name}")
        else:
            log_event('error', f"Failed to send event invitation to {email_address}")

        return result

    except Exception as e:
        log_event('error', f"Error sending event invitation: {e}")
        return False

@handle_exception
def send_donation_receipt(alumni_id, donation_id=None, email_address=None, amount=None, donation_date=None, purpose=None):
    """Send a receipt for an alumni donation"""
    from education_system.systems.university.infrastructure.email.email_service.queue import queue_email

    def _send_donation_receipt(cursor):
        nonlocal email_address, amount, donation_date, purpose

        if email_address is None or amount is None or donation_date is None:
            if email_address is None:
                cursor.execute('SELECT email FROM alumni_profiles WHERE alumni_id = ?', (alumni_id,))
                result = cursor.fetchone()
                if not result:
                    log_event('error', f"Could not find email for alumni ID {alumni_id}")
                    return False
                email_address = result[0]

            if amount is None or donation_date is None:
                cursor.execute('''
                SELECT amount, donation_date, purpose
                FROM alumni_donations
                WHERE donation_id = ?
                ''', (donation_id,))

                result = cursor.fetchone()
                if not result:
                    log_event('error', f"Could not find donation details for donation ID {donation_id}")
                    return False

                amount, donation_date, purpose = result

        purpose_text = f"\nDonation Purpose: {purpose}" if purpose else ""

        subject, message = render_template("donation_receipt", {
            "amount": f"{amount:.2f}",
            "donation_date": donation_date,
            "purpose_text": purpose_text
        })

        success = queue_email(email_address, subject, message)

        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO email_log (recipient, subject, sent_date, status, related_to)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            email_address,
            subject,
            current_time,
            'sent' if success else 'failed',
            f"Donation Receipt: \u00a3{amount:.2f}"
        ))

        return success

    try:
        result = execute_db_operation(_send_donation_receipt)

        if result:
            log_event('info', f"Donation receipt sent to {email_address} for amount: \u00a3{amount:.2f}")
        else:
            log_event('error', f"Failed to send donation receipt to {email_address}")

        return result

    except Exception as e:
        log_event('error', f"Error sending donation receipt: {e}")
        return False
