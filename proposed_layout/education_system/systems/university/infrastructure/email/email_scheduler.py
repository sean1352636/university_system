"""
Email Scheduler - Automated periodic email tasks

This module handles scheduled email operations including:
- Daily satisfaction surveys for resolved tickets
- Book return reminders (3 days before due date)
- Overdue book notifications
- SLA breach alerts for support tickets

Usage:
    # Start the scheduler in a separate thread
    from education_system.systems.university.infrastructure.email.email_scheduler import start_scheduler, stop_scheduler

    start_scheduler()
    # ... application runs ...
    stop_scheduler()

    # Or run in foreground (blocking)
    from education_system.systems.university.infrastructure.email.email_scheduler import run_scheduler
    run_scheduler()
"""

import schedule
import time
import threading
import logging
from datetime import datetime, timedelta

from education_system.systems.university.infrastructure.database.db import get_connection, transaction

# i18n support
try:
    from education_system.systems.university.infrastructure.i18n import get_text as _t
except ImportError:
    def _t(key, **kwargs):
        return key
from education_system.systems.university.infrastructure.email.email_service import (
    send_bulk_satisfaction_surveys,
    send_book_return_reminder,
    send_overdue_notification,
)
from education_system.systems.university.infrastructure.email.email_manager import send_sla_alert
from education_system.systems.university.infrastructure.logs import log_event

# Configure logging
logger = logging.getLogger(__name__)

# Scheduler control
scheduler_thread = None
scheduler_running = threading.Event()
scheduler_stop = threading.Event()


def check_book_return_reminders():
    """Check for books due in 3 days and send reminders"""
    try:
        logger.info("Running book return reminder check...")

        with get_connection() as conn:
            cursor = conn.cursor()

            # Find books due in 3 days
            reminder_date = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')

            cursor.execute('''
                SELECT co.checkout_id, co.user_id, co.book_id, co.due_date,
                       b.title
                FROM checkouts co
                JOIN books b ON co.book_id = b.book_id
                WHERE DATE(co.due_date) = ?
                  AND co.returned = 0
                  AND co.checkout_id NOT IN (
                      SELECT DISTINCT CAST(SUBSTR(related_to,
                          INSTR(related_to, 'Book ID: ') + 9
                      ) AS INTEGER)
                      FROM email_log
                      WHERE related_to LIKE 'Book Return Reminder - Book ID: %'
                        AND DATE(sent_at) = DATE('now')
                  )
            ''', (reminder_date,))

            books_to_remind = cursor.fetchall()

            reminder_count = 0
            for checkout_id, user_id, book_id, due_date, title in books_to_remind:
                try:
                    send_book_return_reminder(user_id, book_id, title, due_date)
                    reminder_count += 1
                except Exception as e:
                    logger.error(f"Failed to send reminder for book {book_id}: {e}")

            logger.info(f"Sent {reminder_count} book return reminders")
            log_event('info', f'Email Scheduler: Sent {reminder_count} book return reminders')

    except Exception as e:
        logger.error(f"Error in book return reminder check: {e}")
        log_event('error', f'Email Scheduler: Book return reminder check failed: {e}')


def check_overdue_books():
    """Check for overdue books and send notifications"""
    try:
        logger.info("Running overdue book check...")

        with get_connection() as conn:
            cursor = conn.cursor()

            # Find overdue books
            current_date = datetime.now().strftime('%Y-%m-%d')

            cursor.execute('''
                SELECT co.checkout_id, co.user_id, co.book_id, co.due_date,
                       b.title,
                       JULIANDAY('now') - JULIANDAY(co.due_date) as days_overdue
                FROM checkouts co
                JOIN books b ON co.book_id = b.book_id
                WHERE DATE(co.due_date) < DATE('now')
                  AND co.returned = 0
                  AND co.checkout_id NOT IN (
                      SELECT DISTINCT CAST(SUBSTR(related_to,
                          INSTR(related_to, 'Book ID: ') + 9
                      ) AS INTEGER)
                      FROM email_log
                      WHERE related_to LIKE 'Overdue Notice - Book ID: %'
                        AND DATE(sent_at) = DATE('now')
                  )
            ''')

            overdue_books = cursor.fetchall()

            notification_count = 0
            for checkout_id, user_id, book_id, due_date, title, days_overdue in overdue_books:
                try:
                    send_overdue_notification(user_id, book_id, title, due_date, int(days_overdue))
                    notification_count += 1
                except Exception as e:
                    logger.error(f"Failed to send overdue notice for book {book_id}: {e}")

            logger.info(f"Sent {notification_count} overdue book notifications")
            log_event('info', f'Email Scheduler: Sent {notification_count} overdue book notifications')

    except Exception as e:
        logger.error(f"Error in overdue book check: {e}")
        log_event('error', f'Email Scheduler: Overdue book check failed: {e}')


def check_sla_breaches():
    """Check for SLA breaches on support tickets and send alerts"""
    try:
        logger.info("Running SLA breach check...")

        with get_connection() as conn:
            cursor = conn.cursor()

            # Find tickets that are overdue
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                SELECT ticket_id, due_date, status, priority
                FROM support_tickets
                WHERE due_date IS NOT NULL
                  AND due_date < ?
                  AND status NOT IN ('resolved', 'closed')
                  AND ticket_id NOT IN (
                      SELECT DISTINCT CAST(SUBSTR(related_to,
                          INSTR(related_to, 'Ticket #') + 8
                      ) AS INTEGER)
                      FROM email_log
                      WHERE related_to LIKE 'SLA Alert - Ticket #%'
                        AND sent_at >= datetime('now', '-1 hour')
                  )
            ''', (current_time,))

            breached_tickets = cursor.fetchall()

            alert_count = 0
            for ticket_id, due_date, status, priority in breached_tickets:
                try:
                    send_sla_alert(ticket_id, alert_type='overdue')
                    alert_count += 1
                except Exception as e:
                    logger.error(f"Failed to send SLA alert for ticket {ticket_id}: {e}")

            logger.info(f"Sent {alert_count} SLA breach alerts")
            log_event('info', f'Email Scheduler: Sent {alert_count} SLA breach alerts')

    except Exception as e:
        logger.error(f"Error in SLA breach check: {e}")
        log_event('error', f'Email Scheduler: SLA breach check failed: {e}')


def send_daily_satisfaction_surveys():
    """Send satisfaction surveys for tickets resolved in the last day"""
    try:
        logger.info("Running satisfaction survey batch...")

        success_count, total = send_bulk_satisfaction_surveys(days_old=1)

        logger.info(f"Sent {success_count}/{total} satisfaction surveys")
        log_event('info', f'Email Scheduler: Sent {success_count}/{total} satisfaction surveys')

    except Exception as e:
        logger.error(f"Error sending satisfaction surveys: {e}")
        log_event('error', f'Email Scheduler: Satisfaction survey batch failed: {e}')


def check_visa_expiry_alerts():
    """Send sponsor-duty visa-expiry warnings for any international student
    whose visa or BRP is now inside a configured alert bucket
    (90 / 60 / 30 / 14 / 7 days). Deduped per (student, threshold) by
    ``visa_expiry_alert_log`` so re-running this every day is safe."""
    try:
        from education_system.systems.university.domain.governance.compliance.international_compliance.services import visa_service as _vs
        sent = _vs.run_scheduled_visa_expiry_alerts()
        logger.info(f"Visa-expiry alerts: sent {sent} email(s)")
        log_event('info', f'Email Scheduler: Sent {sent} visa-expiry alert(s)')
    except Exception as e:
        logger.error(f"Error running visa-expiry alerts: {e}")
        log_event('error', f'Email Scheduler: Visa-expiry alert run failed: {e}')


def refresh_external_qa_kpis():
    """Recompute and write the external-QA KPIs (OfS / TEF / REF) into
    ``kpi_metrics`` so the analytics dashboard always shows current
    institutional-reporting numbers."""
    try:
        from education_system.systems.university.domain.operations.reporting.external_qa_kpis import (
            record_external_qa_kpis,
        )
        n = record_external_qa_kpis()
        logger.info(f"External-QA KPIs: recorded {n} metric(s)")
        log_event('info', f'Email Scheduler: Recorded {n} external-QA KPI(s)')
    except Exception as e:
        logger.error(f"Error refreshing external-QA KPIs: {e}")
        log_event('error', f'Email Scheduler: External-QA KPI refresh failed: {e}')


def refresh_sponsor_compliance_kpis():
    """Recompute and write the four sponsor-compliance KPIs into
    ``kpi_metrics`` so the analytics dashboard tells the truth without
    waiting for someone to open the visa GUI."""
    try:
        from education_system.systems.university.domain.governance.compliance.international_compliance.services import visa_service as _vs
        n = _vs.record_sponsor_compliance_kpis()
        logger.info(f"Sponsor-compliance KPIs: recorded {n} metric(s)")
        log_event('info', f'Email Scheduler: Recorded {n} sponsor-compliance KPI(s)')
    except Exception as e:
        logger.error(f"Error refreshing sponsor-compliance KPIs: {e}")
        log_event('error', f'Email Scheduler: KPI refresh failed: {e}')


def setup_schedules():
    """Configure all scheduled tasks"""

    # Daily tasks at specific times
    schedule.every().day.at("09:00").do(send_daily_satisfaction_surveys)
    schedule.every().day.at("08:00").do(check_book_return_reminders)
    schedule.every().day.at("10:00").do(check_overdue_books)
    schedule.every().day.at("07:00").do(check_visa_expiry_alerts)
    schedule.every().day.at("06:30").do(refresh_sponsor_compliance_kpis)
    schedule.every().day.at("06:35").do(refresh_external_qa_kpis)

    # Periodic tasks
    schedule.every(30).minutes.do(check_sla_breaches)

    logger.info("Email scheduler configured:")
    logger.info("  - Satisfaction surveys: Daily at 09:00")
    logger.info("  - Book return reminders: Daily at 08:00")
    logger.info("  - Overdue book notices: Daily at 10:00")
    logger.info("  - Visa-expiry alerts: Daily at 07:00")
    logger.info("  - Sponsor-compliance KPI refresh: Daily at 06:30")
    logger.info("  - External-QA KPI refresh: Daily at 06:35")
    logger.info("  - SLA breach alerts: Every 30 minutes")


def _run_scheduler_loop():
    """Internal function to run the scheduler loop"""
    scheduler_running.set()
    logger.info("Email scheduler started")
    log_event('info', 'Email Scheduler: Started')

    try:
        while not scheduler_stop.is_set():
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except Exception as e:
        logger.error(f"Scheduler loop error: {e}")
        log_event('error', f'Email Scheduler: Loop error: {e}')
    finally:
        scheduler_running.clear()
        logger.info("Email scheduler stopped")
        log_event('info', 'Email Scheduler: Stopped')


def start_scheduler():
    """Start the email scheduler in a background thread"""
    global scheduler_thread

    if scheduler_thread and scheduler_thread.is_alive():
        logger.warning("Email scheduler is already running")
        return False

    scheduler_stop.clear()
    setup_schedules()

    scheduler_thread = threading.Thread(target=_run_scheduler_loop, daemon=True, name="EmailScheduler")
    scheduler_thread.start()

    # Wait a moment to ensure thread started
    time.sleep(0.5)

    return scheduler_running.is_set()


def stop_scheduler(timeout=10):
    """Stop the email scheduler"""
    global scheduler_thread

    if not scheduler_thread or not scheduler_thread.is_alive():
        logger.warning("Email scheduler is not running")
        return True

    logger.info("Stopping email scheduler...")
    scheduler_stop.set()

    scheduler_thread.join(timeout=timeout)

    if scheduler_thread.is_alive():
        logger.error(f"Email scheduler did not stop within {timeout} seconds")
        return False

    scheduler_thread = None
    schedule.clear()

    return True


def is_scheduler_running():
    """Check if the scheduler is currently running"""
    return scheduler_running.is_set()


def get_scheduled_jobs():
    """Get list of currently scheduled jobs"""
    return schedule.get_jobs()


def run_scheduler():
    """Run the scheduler in the foreground (blocking)"""
    setup_schedules()

    logger.info("Email scheduler running (foreground mode)")
    log_event('info', 'Email Scheduler: Started in foreground mode')

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("Email scheduler stopped by user")
        log_event('info', 'Email Scheduler: Stopped by user')
    except Exception as e:
        logger.error(f"Scheduler error: {e}")
        log_event('error', f'Email Scheduler: Error: {e}')
    finally:
        schedule.clear()


if __name__ == '__main__':
    # When run directly, start in foreground mode
    import sys

    # Set up logging to console
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print(_t("email.scheduler.starting"))
    print(_t("email.scheduler.press_ctrl_c"))
    print("-" * 50)

    run_scheduler()
