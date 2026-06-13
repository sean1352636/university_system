from __future__ import annotations

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.core.i18n import get_text as _

def send_confirmation_email(student_id, subject, message):
    """Send confirmation email using the integrated email system"""
    try:
        # Import email functions from the refactored utils module
        from education_system.university_system.infrastructure.email import queue_email, log_event

        # Connect to the database to get student email
        conn = get_connection()
        cursor = conn.cursor()

        # Get student email from student_id
        cursor.execute('''
        SELECT email_address FROM students WHERE student_id = ?
        ''', (student_id,))

        result = cursor.fetchone()

        if not result:
            print(_("communication.email_not_found", student_id=student_id))
            log_event('error', f"Could not find email address for student ID {student_id}")
            conn.close()
            return False

        email_address = result[0]

        # Queue the email using the email system
        success = queue_email(email_address, subject, message)

        if success:
            print(_("communication.email_sent", email=email_address, subject=subject))
            log_event('info', f"Confirmation email sent to student {student_id}: {subject}")
        else:
            print(_("communication.email_failed", email=email_address))
            log_event('error', f"Failed to send confirmation email to student {student_id}")

        conn.close()
        return success

    except ImportError:
        # Fallback if email_manager is not available
        print(_("communication.email_sent_placeholder", student_id=student_id, subject=subject))
        print(_("communication.email_system_unavailable"))
        return True
    except Exception as e:
        print(_("communication.email_error", error=str(e)))
        return False
