"""Bulk send and scheduled email operations."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime

try:
    import schedule
except ImportError:  # pragma: no cover - optional dependency
    schedule = None

from education_system.systems.university.infrastructure.database.db import sqlite3

from education_system.systems.university.infrastructure.email.config import config
from education_system.systems.university.infrastructure.email.email_db_utilities import execute_db_operation
from education_system.systems.university.infrastructure.logs import handle_exception, log_event
from education_system.systems.university.infrastructure.exceptions import (
    EmailDeliveryError,
    TemplateError,
    ValidationError,
)

# Scheduling state
scheduled_jobs = {}
scheduled_jobs_lock = threading.Lock()  # Protect scheduled_jobs dict


@handle_exception
def send_bulk(recipients, template_name, template_vars_list=None, rate_limit=None):
    """Send emails to multiple recipients with optional rate limiting"""
    from education_system.systems.university.infrastructure.email.email_service.core import send_template_email
    from education_system.systems.university.infrastructure.email.email_service.queue import (
        queue_template_email, start_email_workers, worker_threads,
    )

    if not recipients:
        log_event('error', "No recipients specified for bulk send")
        return False

    if not template_name:
        log_event('error', "No template specified for bulk send")
        return False

    # Set rate limit if provided (emails per second) - only applies to SMTP mode
    if rate_limit and not config.get('database_only_mode', True):
        original_delay = config['send_delay']
        config['send_delay'] = 1.0 / rate_limit

    success_count = 0
    failure_count = 0

    # In database-only mode, process immediately
    if config.get('database_only_mode', True):
        for i, recipient in enumerate(recipients):
            try:
                # Skip empty/blank recipients up front so send_template_email
                # doesn't raise "Recipient email is required" for each one.
                if not (recipient and str(recipient).strip()):
                    log_event('warning', "Bulk send: skipping recipient with no email address")
                    failure_count += 1
                    continue

                # Get template variables for this recipient
                vars_dict = template_vars_list[i] if template_vars_list and i < len(template_vars_list) else {}

                # Send the email directly
                if send_template_email(template_name, recipient, vars_dict):
                    success_count += 1
                else:
                    failure_count += 1
            except (TemplateError, EmailDeliveryError) as e:
                log_event('error', f"Email error processing for {recipient}: {e}")
                failure_count += 1
            except (KeyError, IndexError) as e:
                log_event('error', f"Template variable error for {recipient}: {e}")
                failure_count += 1
    else:
        # Ensure email workers are running
        if not worker_threads:
            start_email_workers()

        # Send to each recipient
        for i, recipient in enumerate(recipients):
            try:
                # Get template variables for this recipient
                vars_dict = template_vars_list[i] if template_vars_list and i < len(template_vars_list) else {}

                # Queue the email
                queue_template_email(template_name, recipient, vars_dict)
                success_count += 1
            except (TemplateError, ValidationError) as e:
                log_event('error', f"Error queueing email for {recipient}: {e}")
                failure_count += 1
            except (KeyError, IndexError) as e:
                log_event('error', f"Template variable error queueing for {recipient}: {e}")
                failure_count += 1

    # Restore original delay if changed
    if rate_limit and not config.get('database_only_mode', True):
        config['send_delay'] = original_delay

    log_event('info', f"Bulk send processed: {success_count} successes, {failure_count} failures")

    return {
        'total': len(recipients),
        'success': success_count,
        'failure': failure_count
    }

@handle_exception
def schedule_send(datetime_obj, recipients, template_name, template_vars_list=None):
    """Schedule emails to be sent at a specific time"""
    if not recipients:
        log_event('error', "No recipients specified for scheduled send")
        return False

    if not template_name:
        log_event('error', "No template specified for scheduled send")
        return False

    if not datetime_obj or datetime_obj <= datetime.now():
        log_event('error', "Scheduled datetime must be in the future")
        return False

    def _schedule_emails(cursor):
        success_count = 0
        failure_count = 0
        scheduled_ids = []

        # Schedule each email
        for i, recipient in enumerate(recipients):
            try:
                # Get template variables for this recipient
                vars_dict = template_vars_list[i] if template_vars_list and i < len(template_vars_list) else {}

                # Convert template vars to JSON
                vars_json = json.dumps(vars_dict)

                # Insert into scheduled_emails table
                cursor.execute('''
                INSERT INTO scheduled_emails
                (template_name, recipient_email, template_vars, scheduled_date, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    template_name,
                    recipient,
                    vars_json,
                    datetime_obj.strftime('%Y-%m-%d %H:%M:%S'),
                    'pending',
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))

                scheduled_id = cursor.lastrowid
                scheduled_ids.append(scheduled_id)
                success_count += 1
            except sqlite3.Error as e:
                log_event('error', f"Database error scheduling email for {recipient}: {e}")
                failure_count += 1
            except (json.JSONDecodeError, TypeError) as e:
                log_event('error', f"JSON serialization error for {recipient}: {e}")
                failure_count += 1

        return {
            'total': len(recipients),
            'success': success_count,
            'failure': failure_count,
            'scheduled_ids': scheduled_ids
        }

    try:
        result = execute_db_operation(_schedule_emails)

        # Start the scheduler if needed and not in database-only mode
        if result['success'] > 0 and not config.get('database_only_mode', True):
            ensure_scheduler_running()

        log_event('info', f"Scheduled send: {result['success']} successes, {result['failure']} failures for {datetime_obj}")
        return result

    except sqlite3.Error as e:
        log_event('error', f"Database error scheduling emails: {e}")
        return {
            'total': len(recipients),
            'success': 0,
            'failure': len(recipients),
            'scheduled_ids': []
        }

@handle_exception
def process_scheduled_emails():
    """Process due scheduled emails"""
    from education_system.systems.university.infrastructure.email.email_service.core import send_template_email
    from education_system.systems.university.infrastructure.email.email_service.queue import queue_template_email

    def _process_emails(cursor):
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Find due emails with pending status
        cursor.execute('''
        SELECT id, template_name, recipient_email, template_vars
        FROM scheduled_emails
        WHERE scheduled_date <= ? AND status = 'pending'
        ''', (current_time,))

        scheduled_emails = cursor.fetchall()
        return scheduled_emails

    try:
        scheduled_emails = execute_db_operation(_process_emails)

        if not scheduled_emails:
            return 0

        # Process each due email
        processed_count = 0

        for email in scheduled_emails:
            scheduled_id, template_name, recipient, vars_json = email

            try:
                # Parse template vars
                template_vars = json.loads(vars_json) if vars_json else {}

                # Queue or send the email depending on mode
                if config.get('database_only_mode', True):
                    # Send directly in database mode
                    success = send_template_email(template_name, recipient, template_vars)
                    if success:
                        update_scheduled_email_status(scheduled_id, 'sent')
                    else:
                        update_scheduled_email_status(scheduled_id, 'failed')
                else:
                    # Queue the email
                    queue_template_email(template_name, recipient, template_vars, scheduled_id=scheduled_id)
                    # Update status to 'processing'
                    update_scheduled_email_status(scheduled_id, 'processing')

                processed_count += 1
            except (TemplateError, EmailDeliveryError) as e:
                log_event('error', f"Email error processing scheduled email {scheduled_id}: {e}")
                update_scheduled_email_status(scheduled_id, 'failed')
            except sqlite3.Error as e:
                log_event('error', f"Database error processing scheduled email {scheduled_id}: {e}")
                update_scheduled_email_status(scheduled_id, 'failed')

        log_event('info', f"Processed {processed_count} scheduled emails")
        return processed_count

    except sqlite3.Error as e:
        log_event('error', f"Database error processing scheduled emails: {e}")
        return 0

@handle_exception
def ensure_scheduler_running():
    """Ensure the scheduler is running"""
    global scheduled_jobs

    # Skip scheduler in database-only mode
    if config.get('database_only_mode', True):
        log_event('info', "Database-only mode - scheduler not needed")
        return True
    if schedule is None:
        log_event('warning', "Scheduling library not available; skipping scheduler startup")
        return False

    # Check if scheduler is already running
    if 'process_emails' in scheduled_jobs:
        return True

    # Schedule job to run every minute
    scheduled_jobs['process_emails'] = schedule.every(1).minutes.do(process_scheduled_emails)

    # Start scheduler in a separate thread if not already running
    scheduler_thread = getattr(ensure_scheduler_running, 'scheduler_thread', None)
    if not scheduler_thread or not scheduler_thread.is_alive():
        ensure_scheduler_running.scheduler_thread = threading.Thread(target=run_scheduler)
        ensure_scheduler_running.scheduler_thread.daemon = True
        ensure_scheduler_running.scheduler_thread.start()

    log_event('info', "Email scheduler started")
    return True

def run_scheduler():
    """Run the scheduler in a loop"""
    if schedule is None:
        log_event('warning', "Scheduling library not available; scheduler loop not started")
        return
    while True:
        try:
            schedule.run_pending()
            time.sleep(10)  # Check every 10 seconds
        except (RuntimeError, OSError) as e:
            log_event('error', f"Scheduler runtime error: {e}")
            time.sleep(30)  # Longer delay on error

@handle_exception
def update_scheduled_email_status(scheduled_id, status):
    """Update the status of a scheduled email"""
    def _update_status(cursor):
        cursor.execute('''
        UPDATE scheduled_emails
        SET status = ?
        WHERE id = ?
        ''', (status, scheduled_id))
        return True

    try:
        return execute_db_operation(_update_status)
    except sqlite3.Error as e:
        log_event('error', f"Database error updating scheduled email status: {e}")
        return False
