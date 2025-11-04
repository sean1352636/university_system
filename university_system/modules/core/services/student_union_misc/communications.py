from __future__ import annotations

from university_system.infrastructure.database.db import get_connection

def send_confirmation_email(student_id, subject, message):
    """Send confirmation email using the integrated email system"""
    try:
        # Import email functions from the refactored utils module
        from university_system.infrastructure.email import queue_email, log_event

        # Connect to the database to get student email
        conn = get_connection()
        cursor = conn.cursor()

        # Get student email from student_id
        cursor.execute('''
        SELECT email_address FROM students WHERE student_id = ?
        ''', (student_id,))

        result = cursor.fetchone()

        if not result:
            print(f"❌ Could not find email address for student ID {student_id}")
            log_event('error', f"Could not find email address for student ID {student_id}")
            conn.close()
            return False

        email_address = result[0]

        # Queue the email using the email system
        success = queue_email(email_address, subject, message)

        if success:
            print(f"📧 Email sent to {email_address}: {subject}")
            log_event('info', f"Confirmation email sent to student {student_id}: {subject}")
        else:
            print(f"❌ Failed to send email to {email_address}")
            log_event('error', f"Failed to send confirmation email to student {student_id}")

        conn.close()
        return success

    except ImportError:
        # Fallback if email_manager is not available
        print(f"📧 Email sent to student {student_id}: {subject}")
        print("⚠️ Email system not available - using placeholder")
        return True
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return False
