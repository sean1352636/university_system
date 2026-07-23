"""Academic and student notification emails."""

from __future__ import annotations

from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import sqlite3

from education_system.post_18.university_system.infrastructure.email.email_db_utilities import execute_db_operation
from education_system.post_18.university_system.core.logs import handle_exception, log_event
from education_system.post_18.university_system.infrastructure.email.templates import render_template
from education_system.post_18.university_system.core.exceptions import (
    EmailDeliveryError,
    TemplateError,
)

# Import immutable audit logging for compliance
try:
    from education_system.post_18.university_system.infrastructure.security.audit_helpers import (
        safe_log_security_event,
        mask_sensitive_data,
    )
    from education_system.post_18.university_system.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False
    def mask_sensitive_data(data, fields=None):
        return data


@handle_exception
def send_registration_confirmation(student_id):
    """Send a registration confirmation email to a student"""
    from education_system.post_18.university_system.infrastructure.email.email_service.queue import queue_template_email

    def _send_confirmation(cursor):
        cursor.execute('''
        SELECT email_address, title, first_name, middle_name, last_name, course
        FROM students WHERE student_id = ?
        ''', (student_id,))

        student = cursor.fetchone()

        if not student:
            log_event('error', f"Student not found: {student_id}")
            return False

        email_address, title, first_name, middle_name, last_name, course = student

        cursor.execute('''
        SELECT m.module_type, sm.module_code, m.module_name
        FROM student_modules sm
        JOIN modules m ON sm.module_code = m.module_code
        WHERE sm.student_id = ?
        ORDER BY m.module_type
        ''', (student_id,))

        modules = cursor.fetchall()

        modules_list = ""
        for module in modules:
            modules_list += f"- {module[0]}: {module[1]} - {module[2]}\n"

        template_vars = {
            'student_id': student_id,
            'email_address': email_address,
            'title': title,
            'first_name': first_name,
            'middle_name': middle_name or '',
            'last_name': last_name,
            'course': course,
            'modules_list': modules_list
        }

        return template_vars, email_address

    try:
        result = execute_db_operation(_send_confirmation)
        if result:
            template_vars, email_address = result
            return queue_template_email('user_management/registration_confirmation', email_address, template_vars)
        return False
    except sqlite3.Error as e:
        log_event('error', f"Database error sending registration confirmation: {e}")
        return False
    except (TemplateError, Exception) as e:
        log_event('error', f"Email error sending registration confirmation: {e}")
        return False

@handle_exception
def send_update_confirmation(student_email, updated_fields):
    """Send update confirmation email to student"""
    from education_system.post_18.university_system.infrastructure.email.email_service.core import send_template_email

    try:
        if isinstance(updated_fields, dict):
            updated_fields_str = '\n'.join(
                [f"- {field}: {value}" for field, value in updated_fields.items()]
            )
        else:
            updated_fields_str = '\n'.join([f"- {field}" for field in updated_fields])

        template_vars = {
            'updated_fields': updated_fields_str
        }

        return send_template_email('update_confirmation', student_email, template_vars)
    except (TemplateError, EmailDeliveryError) as e:
        log_event('error', f"Email error sending update confirmation: {e}")
        return False
    except (TypeError, AttributeError) as e:
        log_event('error', f"Data error sending update confirmation: {e}")
        return False

@handle_exception
def send_grade_notification(student_email, assignment_title, module_code, grade, feedback=None):
    """Send grade notification email"""
    from education_system.post_18.university_system.infrastructure.email.email_service.core import send_template_email

    template_vars = {
        'student_name': "Student",
        'assignment_title': assignment_title,
        'module_code': module_code,
        'grade': grade,
        'feedback': feedback or "No additional feedback provided"
    }

    return send_template_email('assignment_grade_released', student_email, template_vars)

@handle_exception
def send_password_reset(student_id, reset_code):
    """Send a password reset email to a student"""
    from education_system.post_18.university_system.infrastructure.email.email_service.queue import queue_template_email

    def _send_password_reset(cursor):
        cursor.execute('''
        SELECT email_address, title, first_name, middle_name, last_name
        FROM students WHERE student_id = ?
        ''', (student_id,))

        student = cursor.fetchone()

        if not student:
            log_event('error', f"Student not found: {student_id}")
            return False

        email_address, title, first_name, middle_name, last_name = student

        template_vars = {
            'student_id': student_id,
            'email_address': email_address,
            'title': title,
            'first_name': first_name,
            'middle_name': middle_name or '',
            'last_name': last_name,
            'reset_code': reset_code
        }

        return template_vars, email_address

    try:
        result = execute_db_operation(_send_password_reset)
        if result:
            template_vars, email_address = result
            email_sent = queue_template_email('password_reset', email_address, template_vars)

            if IMMUTABLE_AUDIT_AVAILABLE and email_sent:
                safe_log_security_event(
                    action=AuditAction.PASSWORD_RESET,
                    user_id=student_id,
                    resource_type='password_reset_email',
                    details={
                        'recipient_masked': mask_sensitive_data({'email': email_address}, ['email']),
                        'student_id': student_id
                    }
                )

            return email_sent
        return False
    except Exception as e:
        log_event('error', f"Error sending password reset: {e}")
        return False

@handle_exception
def send_assignment_notification(assignment_id, assignment_title, module_code, due_date, description=None):
    """Send assignment notification using the centralized email system"""
    from education_system.post_18.university_system.infrastructure.email.email_service.core import send_email, send_template_email

    def _send_notifications(cursor):
        cursor.execute('''
        SELECT s.email_address, s.first_name, s.last_name, s.student_id
        FROM students s
        JOIN student_modules sm ON s.student_id = sm.student_id
        WHERE sm.module_code = ? AND s.email_address IS NOT NULL AND s.email_address != ''
        ''', (module_code,))

        students = cursor.fetchall()
        success_count = 0

        for email, first_name, last_name, student_id in students:
            template_vars = {
                'student_name': f"{first_name} {last_name}".strip() or "Student",
                'assignment_title': assignment_title,
                'module_code': module_code,
                'due_date': due_date,
                'assignment_description': description or "No description provided"
            }

            try:
                if send_template_email('assignment_notification', email, template_vars):
                    success_count += 1
                    continue
            except Exception:
                pass

            try:
                subject = f"New Assignment: {assignment_title}"
                body = f"""Dear {first_name},

A new assignment has been published for {module_code}.

Assignment: {assignment_title}
Due Date: {due_date}

{description or ''}

Please login to the Assignment System to view details and submit your work.

Best regards,
Academic Administration Team
"""
                if send_email(email, subject, body):
                    success_count += 1
            except Exception as e:
                print(f"Failed to send email to {student_id}: {e}")

        return success_count

    try:
        count = execute_db_operation(_send_notifications)
        log_event('info', f"Assignment notification sent to {count} students")
        return count > 0
    except Exception as e:
        log_event('error', f"Error sending assignment notifications: {e}")
        return False

@handle_exception
def send_extension_notification(student_email, assignment_title, module_code, new_due_date, extension_days):
    """Send extension approval notification"""
    from education_system.post_18.university_system.infrastructure.email.email_service.core import send_template_email

    template_vars = {
        'student_name': "Student",
        'assignment_title': assignment_title,
        'module_code': module_code,
        'new_due_date': new_due_date,
        'extension_days': extension_days
    }

    return send_template_email('assignment_extension_approved', student_email, template_vars)

@handle_exception
def send_confirmation_email(self, student_id, subject, message):
    """Send a confirmation email to a student using centralized email system"""
    from education_system.post_18.university_system.infrastructure.email.email_service.queue import queue_email

    def _send_confirmation_email(cursor):
        cursor.execute('''
        SELECT email_address FROM students WHERE student_id = ?
        ''', (student_id,))

        result = cursor.fetchone()

        if not result:
            log_event('error', f"Could not find email address for student ID {student_id}")
            return False

        email_address = result[0]
        return queue_email(email_address, subject, message)

    try:
        return execute_db_operation(_send_confirmation_email)
    except Exception as e:
        log_event('error', f"Error sending confirmation email: {e}")
        return False
