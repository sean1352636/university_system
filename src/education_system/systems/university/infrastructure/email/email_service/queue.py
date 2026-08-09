"""Email queue and worker thread management."""

from __future__ import annotations

import queue
import smtplib
import threading
import time

from education_system.systems.university.infrastructure.database.db import sqlite3

from education_system.systems.university.infrastructure.email.config import config
from education_system.systems.university.infrastructure.logs import handle_exception, log_event
from education_system.systems.university.infrastructure.exceptions import (
    EmailDeliveryError,
    TemplateError,
    AttachmentError,
)

# Global queue and worker state
email_queue = queue.Queue()

worker_threads = []
worker_threads_lock = threading.Lock()  # Protect worker_threads list

# Use threading.Event for thread-safe signaling (replaces stop_workers boolean)
stop_workers_event = threading.Event()


@handle_exception
def email_worker():
    """Simplified worker function with better database handling"""
    from education_system.systems.university.infrastructure.email.email_service.core import send_email, send_template_email

    # Single worker thread with proper serialization
    worker_id = threading.current_thread().ident
    log_event('info', f"Email worker {worker_id} started")

    while not stop_workers_event.is_set():
        try:
            # Get an email task from the queue with a timeout
            task = email_queue.get(timeout=5.0)

            # Process the email task with proper delay
            success = False

            try:
                if task.get('type') == 'template':
                    success = send_template_email(
                        task['template_name'],
                        task['recipient'],
                        task['template_vars'],
                        task.get('cc'),
                        task.get('bcc'),
                        task.get('attachments')
                    )
                else:
                    success = send_email(
                        task['recipient'],
                        task['subject'],
                        task['body'],
                        task.get('cc'),
                        task.get('bcc'),
                        task.get('attachments')
                    )

            except (smtplib.SMTPException, EmailDeliveryError) as e:
                log_event('error', f"Worker email delivery error: {e}")
                success = False
            except (TemplateError, AttachmentError) as e:
                log_event('error', f"Worker template/attachment error: {e}")
                success = False
            except sqlite3.Error as e:
                log_event('error', f"Worker database error: {e}")
                success = False

            # Handle success/failure
            if success:
                log_event('info', f"Email processed for {task['recipient']}")
            else:
                log_event('error', f"Failed to process email for {task['recipient']}")

            # Mark the task as done
            email_queue.task_done()

            # Longer delay between operations to reduce contention
            time.sleep(config.get('send_delay', 2.0))

        except queue.Empty:
            # No email in queue, continue waiting
            continue
        except (KeyError, TypeError) as e:
            log_event('error', f"Invalid task format in email worker: {e}")
            time.sleep(1.0)
        except RuntimeError as e:
            log_event('error', f"Runtime error in email worker: {e}")
            time.sleep(2.0)

    log_event('info', f"Email worker {worker_id} stopped")

@handle_exception
def start_email_workers():
    """Start worker threads for processing the email queue - SINGLE THREAD ONLY"""
    # Only start workers if not in database-only mode
    if config.get('database_only_mode', True):
        log_event('info', "Database-only mode enabled - email workers not started")
        return True

    # Stop any existing workers
    stop_email_workers()

    # Reset event and create new workers - FORCE SINGLE THREAD
    stop_workers_event.clear()  # Thread-safe signal to start workers

    with worker_threads_lock:
        # Create and start ONLY ONE worker thread
        t = threading.Thread(target=email_worker, daemon=True)
        t.start()
        worker_threads.append(t)

        log_event('info', f"Started {len(worker_threads)} email worker thread")

    return True

@handle_exception
def stop_email_workers():
    """Stop all email worker threads"""
    with worker_threads_lock:
        if worker_threads:
            log_event('info', "Stopping email worker threads...")
            stop_workers_event.set()  # Thread-safe signal to stop workers

            # Wait for all threads to complete
            for thread in worker_threads:
                if thread.is_alive():
                    thread.join(timeout=5.0)

            worker_threads.clear()
            log_event('info', "Email workers stopped")
    return True

@handle_exception
def queue_email(recipient, subject, body, cc=None, bcc=None, attachments=None, scheduled_id=None):
    """Queue an email to be sent asynchronously"""
    # In database-only mode, process immediately instead of queuing
    if config.get('database_only_mode', True):
        from education_system.systems.university.infrastructure.email.email_service.core import send_email
        return send_email(recipient, subject, body, cc, bcc, attachments)

    # Ensure worker threads are running
    if not worker_threads:
        start_email_workers()

    # Create the email task
    task = {
        'recipient': recipient,
        'subject': subject,
        'body': body,
        'cc': cc,
        'bcc': bcc,
        'attachments': attachments
    }

    if scheduled_id:
        task['scheduled_id'] = scheduled_id

    # Add to the queue
    email_queue.put(task)

    return True

@handle_exception
def queue_template_email(template_name, recipient, template_vars, cc=None, bcc=None, attachments=None, scheduled_id=None):
    """Queue a template email to be sent asynchronously with enhanced logging"""
    # In database-only mode, process immediately instead of queuing
    if config.get('database_only_mode', True):
        from education_system.systems.university.infrastructure.email.email_service.core import send_template_email
        from education_system.systems.university.infrastructure.email.email_service.scheduling import update_scheduled_email_status
        log_event('info', f"Processing template email immediately: {template_name} to {recipient}")
        success = send_template_email(template_name, recipient, template_vars, cc, bcc, attachments)
        if scheduled_id and success:
            update_scheduled_email_status(scheduled_id, 'sent')
            log_event('info', f"Scheduled email {scheduled_id} marked as sent")
        elif scheduled_id:
            update_scheduled_email_status(scheduled_id, 'failed')
            log_event('error', f"Scheduled email {scheduled_id} marked as failed")
        return success

    # Ensure worker threads are running
    if not worker_threads:
        start_email_workers()

    # Create the email task
    task = {
        'type': 'template',
        'template_name': template_name,
        'recipient': recipient,
        'template_vars': template_vars,
        'cc': cc,
        'bcc': bcc,
        'attachments': attachments
    }

    if scheduled_id:
        task['scheduled_id'] = scheduled_id

    # Add to the queue
    email_queue.put(task)
    log_event('info', f"Template email queued: {template_name} for {recipient}")

    return True

@handle_exception
def wait_for_email_queue():
    """Wait for all queued emails to be sent"""
    if config.get('database_only_mode', True):
        log_event('info', "Database-only mode - no queue to wait for")
        return True

    queue_size = email_queue.qsize()
    log_event('info', f"Waiting for {queue_size} emails to be sent...")
    email_queue.join()
    log_event('info', "All emails have been sent")
    return True
