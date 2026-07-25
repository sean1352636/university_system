import logging
from datetime import datetime, timedelta

from education_system.systems.university.domain.operations.campus.housing.services.accommodation._common import (
    sqlite3, DB_PATH, NOTIFICATION_THRESHOLD_DAYS, email_manager, get_auth, get_text,
)
from education_system.systems.university.domain.operations.campus.housing.services.accommodation.db import init_accommodation_db
from education_system.systems.university.domain.operations.campus.housing.services.accommodation.audit import log_action


def notify_student(student_id, subject, message):
    """Send an email notification to the student with improved handling."""
    try:
        # Skip if email manager is not available
        if not email_manager:
            logging.info(f"Notification to {student_id}: {subject} -- {message}")
            print(get_text("housing.accommodation.message.email_would_be_sent", "Email would be sent to student {student_id}: {subject}").format(student_id=student_id, subject=subject))
            return

        # Get student email
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT email_address FROM students WHERE student_id = ?', (student_id,))
            row = cursor.fetchone()

        if not row:
            logging.warning(f"Cannot notify student {student_id}: Student not found")
            print(get_text("housing.accommodation.warning.student_not_found", "Warning: Student {student_id} not found").format(student_id=student_id))
            return

        email_address = row[0] if row else None
        if not email_address:
            logging.warning(f"Cannot notify student {student_id}: No email address found")
            print(get_text("housing.accommodation.warning.cannot_send_email_no_address", "Warning: Cannot send email to student {student_id}: No email address found").format(student_id=student_id))
            return

        # Send email - catch any exceptions from the email service
        try:
            email_manager.send_email(email_address, subject, message)
            logging.info(f"Email sent to {student_id} ({email_address}): {subject}")
            print(get_text("housing.accommodation.message.email_sent", "Email sent to student {student_id}").format(student_id=student_id))
        except AttributeError as e:
            # Handle case where email_manager doesn't have send_email method
            logging.error(f"Email manager misconfigured: {e}")
            print(get_text("housing.accommodation.error.email_service_error", "Error: Email service not properly configured"))
        except (KeyError, TypeError) as e:
            # Handle case where email configuration or parameters are incorrect
            logging.error(f"Email configuration error for {student_id}: {e}")
            print(get_text("housing.accommodation.error.email_config_error", "Error: Email configuration problem: {error}").format(error=e))

    except sqlite3.Error as e:
        logging.error(f"Database error while notifying student {student_id}: {e}")
        print(get_text("housing.accommodation.error.database_error_notification", "Database error while sending notification: {error}").format(error=e))
    except Exception as e:
        logging.error(f"Error notifying student {student_id}: {e}")
        print(get_text("housing.accommodation.error.sending_notification", "Error sending notification to student {student_id}: {error}").format(student_id=student_id, error=e))


def check_expiry_notifications(days=NOTIFICATION_THRESHOLD_DAYS):
    """Alert for accommodations nearing expiry with improved error handling."""
    auth = get_auth()

    # Check for permission if called interactively
    if auth is not None:
        if not auth.current_user:
            print(get_text("housing.accommodation.auth.must_be_logged_in_check_expiry", "You must be logged in to check expirations."))
            return

        if not auth.check_permission('manage_accommodations'):
            print(get_text("housing.accommodation.auth.no_permission_check_expiry", "You don't have permission to check expirations."))
            return

    init_accommodation_db()
    try:
        # Calculate threshold date for expirations
        threshold = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
        today = datetime.now().strftime('%Y-%m-%d')

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Find active accommodations expiring on the threshold date
            cursor.execute('''
                SELECT a.id, a.student_id, a.accommodation_type, a.end_date,
                       s.first_name, s.last_name, s.email_address
                FROM accommodations a
                JOIN students s ON a.student_id = s.student_id
                WHERE a.end_date = ? AND a.status = 'active'
            ''', (threshold,))

            expiring_soon = cursor.fetchall()

            # Find accommodations that expired today but still have active status
            cursor.execute('''
                SELECT a.id, a.student_id, a.accommodation_type, a.end_date,
                       s.first_name, s.last_name, s.email_address
                FROM accommodations a
                JOIN students s ON a.student_id = s.student_id
                WHERE a.end_date = ? AND a.status = 'active'
            ''', (today,))

            expired_today = cursor.fetchall()

        # Process accommodations expiring soon
        if expiring_soon:
            print("\n" + get_text("housing.accommodation.message.found_expiring_in_days", "Found {count} accommodation(s) expiring in {days} days:").format(count=len(expiring_soon), days=days))

            for acc in expiring_soon:
                student_id = acc['student_id']
                name = f"{acc['first_name'] or ''} {acc['last_name'] or ''}".strip() or get_text("housing.accommodation.label.na", "N/A")

                print(get_text("housing.accommodation.message.expiry_record", "ID: {id} - Student: {student_id} ({name}) - Type: {type}").format(
                    id=acc['id'], student_id=student_id, name=name, type=acc['accommodation_type']))

                try:
                    # Send notification
                    msg = f"Your accommodation '{acc['accommodation_type']}' will expire on {acc['end_date']}. Please contact the accommodations office if you need to renew it."
                    notify_student(student_id, 'Accommodation Expiry Warning', msg)

                    # Log the notification
                    log_action('expiry_notification', acc['id'], f"Expiry notification for {acc['accommodation_type']}")

                except Exception as notify_e:
                    logging.error(f"Expiry notification error for {acc['id']}: {notify_e}")
                    print(get_text("housing.accommodation.error.sending_notification_for", "Error sending notification for accommodation {id}: {error}").format(id=acc['id'], error=notify_e))
        else:
            print(get_text("housing.accommodation.message.no_expiring_in_days", "No accommodations found expiring in {days} days.").format(days=days))

        # Process accommodations expired today
        if expired_today:
            print("\n" + get_text("housing.accommodation.message.found_expired_today", "Found {count} accommodation(s) expired today:").format(count=len(expired_today)))

            for acc in expired_today:
                student_id = acc['student_id']
                name = f"{acc['first_name'] or ''} {acc['last_name'] or ''}".strip() or get_text("housing.accommodation.label.na", "N/A")

                print(get_text("housing.accommodation.message.expiry_record", "ID: {id} - Student: {student_id} ({name}) - Type: {type}").format(
                    id=acc['id'], student_id=student_id, name=name, type=acc['accommodation_type']))

                try:
                    # Send notification
                    msg = f"Your accommodation '{acc['accommodation_type']}' has expired today ({acc['end_date']}). Please contact the accommodations office if you need to extend it."
                    notify_student(student_id, 'Accommodation Expired', msg)

                    # Update status to expired
                    with sqlite3.connect(DB_PATH) as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE accommodations
                            SET status = 'expired', updated_at = ?
                            WHERE id = ?
                        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), acc['id']))
                        conn.commit()

                    # Log the expiration
                    log_action('expired', acc['id'], f"Accommodation {acc['accommodation_type']} expired")

                except Exception as expire_e:
                    logging.error(f"Expiration processing error for {acc['id']}: {expire_e}")
                    print(get_text("housing.accommodation.error.processing_expiration", "Error processing expiration for accommodation {id}: {error}").format(id=acc['id'], error=expire_e))
        else:
            print(get_text("housing.accommodation.message.no_expired_today", "No accommodations expired today."))

    except Exception as e:
        logging.error(f"Error checking expiry notifications: {e}")
        print(get_text("housing.accommodation.error.checking_expiry", "Error checking expiry notifications: {error}").format(error=e))
