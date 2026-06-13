from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH, get_connection, transaction  # injected
from education_system.university_system.core.exceptions import (
    CourseNotFoundError,
    ValidationError,
)

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.core.i18n import (
        get_text as _t,
        get_current_language,
        get_current_language_name,
        set_language,
        get_available_language_list,
        init_i18n,
    )
    from education_system.university_system.modules.shared.utils.gui_language_selector import (
        show_gui_language_selector,
    )
    I18N_AVAILABLE = True
    GUI_LANG_SELECTOR_AVAILABLE = True
    # Initialize i18n if not already done
    init_i18n()
except ImportError:
    I18N_AVAILABLE = False
    GUI_LANG_SELECTOR_AVAILABLE = False
    _t = lambda key, **kwargs: key  # Fallback: return key as-is
    get_current_language = lambda: "en"
    get_current_language_name = lambda: "English"
    set_language = lambda lang, save=True: False
    get_available_language_list = lambda: [("en", "English")]
    show_gui_language_selector = lambda parent=None: "en"

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.font import Font
import os
import sys
from datetime import datetime, timedelta
import threading
import subprocess
import webbrowser
from pathlib import Path

# This ensures full backward compatibility
try:
    from education_system.university_system.modules.domain.academics.services.module_scheduling import (
        ModuleScheduler, DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES,
        display_enhanced_scheduling_menu  # Keep CLI available
    )
except ImportError:
    # If the original module isn't available, we'll define basic constants
    DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
    SESSION_TYPES = ['Lecture', 'Lab', 'Tutorial', 'Seminar', 'Workshop']
    ROOM_TYPES = ['Lecture Hall', 'Lab', 'Tutorial Room', 'Seminar Room', 'Workshop Room', 'Computer Lab', 'Other']

    # Import the ModuleScheduler class from the document
    try:
        from education_system.university_system.modules.domain.academics.services.module_scheduling import (ModuleScheduler, DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES, display_enhanced_scheduling_menu)
    except Exception:
        class ModuleScheduler: pass

from education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui import ModuleSchedulingGUI

def _send_room_change_notifications(self, module_code, day, start_time, end_time, old_room, new_room):
    """Send email notifications to students and lecturers about room change"""
    try:
        from education_system.university_system.infrastructure.database.db import sqlite3

        # Import email service
        try:
            from education_system.university_system.infrastructure.email.email_service import send_email
        except ImportError:
            # Email service not available, skip notification
            return

        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()

            # Get students enrolled in this module
            cursor.execute('''
                SELECT DISTINCT s.email, s.first_name, s.last_name
                FROM students s
                INNER JOIN enrollments e ON s.id = e.student_id
                INNER JOIN modules m ON e.module_id = m.id
                WHERE m.module_code = ?
                AND s.email IS NOT NULL
            ''', (module_code,))

            students = cursor.fetchall()

            # Get lecturers for this module
            cursor.execute('''
                SELECT DISTINCT i.email, i.first_name, i.last_name
                FROM instructors i
                INNER JOIN module_schedule ms ON i.id = ms.instructor_id
                WHERE ms.module_code = ?
                AND i.email IS NOT NULL
            ''', (module_code,))

            lecturers = cursor.fetchall()

            # Send emails to students
            from education_system.university_system.infrastructure.email.template_utils import render_template
            for email, first_name, last_name in students:
                if email:
                    try:
                        subject, body = render_template("room_change_notice", {
                            "student_name": f"{first_name} {last_name}",
                            "module_code": module_code,
                            "day": day,
                            "start_time": start_time,
                            "end_time": end_time,
                            "old_room": old_room,
                            "new_room": new_room
                        })
                        if subject and body:
                            send_email(email, subject, body)
                    except Exception:
                        pass  # Continue even if individual email fails

            # Send emails to lecturers
            for email, first_name, last_name in lecturers:
                if email:
                    personalized_body = body.replace("Dear Recipient", f"Dear {first_name} {last_name}")
                    try:
                        send_email(email, subject, personalized_body)
                    except Exception:
                        pass

    except Exception as e:
        # Don't fail the entire operation if email fails
        self.update_activity_log(f"Failed to send email notifications: {str(e)}")

ModuleSchedulingGUI._send_room_change_notifications = _send_room_change_notifications

def create_notification(self, recipient_type, recipient_id, message, notification_type="info"):
    """Create a notification by sending an email using the proper email service"""
    try:
        # Import email service
        from education_system.university_system.infrastructure.email.email_service import send_email

        with get_connection() as conn:
            cursor = conn.cursor()

            # Get recipient email based on type
            email_address = None
            recipient_name = "User"

            if recipient_type == 'instructor':
                cursor.execute('SELECT email, first_name, last_name FROM instructors WHERE id = ?', (recipient_id,))
                result = cursor.fetchone()
                if result:
                    email_address, first_name, last_name = result
                    recipient_name = f"{first_name or ''} {last_name or ''}".strip()
            elif recipient_type == 'student':
                cursor.execute('SELECT email, first_name, last_name FROM students WHERE student_id = ?', (recipient_id,))
                result = cursor.fetchone()
                if result:
                    email_address, first_name, last_name = result
                    recipient_name = f"{first_name or ''} {last_name or ''}".strip()

            # Send email if we have a valid address
            if email_address:
                # Render email from template
                from education_system.university_system.infrastructure.email.template_utils import render_template

                subject, body = render_template('academics/module_scheduling_notification', {
                    'notification_type': notification_type.replace('_', ' ').title(),
                    'recipient_name': recipient_name,
                    'message': message
                })

                # Fallback if template not found
                if not subject or not body:
                    subject = f"Module Scheduling Notification - {notification_type.replace('_', ' ').title()}"
                    body = f"Dear {recipient_name},\n\n{message}\n\nBest regards,\nUniversity Module Scheduling System"

                send_email(email_address, subject, body)

    except Exception as e:
        print(f"Error creating notification: {e}")

ModuleSchedulingGUI.create_notification = create_notification

def send_schedule_change_notifications(self, schedule_id, change_description):
    """Send notifications when schedules change"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Get schedule details
        cursor.execute('''
        SELECT ms.module_code, ms.day_of_week, ms.start_time, ms.instructor_id,
               r.building, r.room_number
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        WHERE ms.id = ?
        ''', (schedule_id,))

        schedule = cursor.fetchone()
        if not schedule:
            return

        module_code, day, start_time, instructor_id, building, room = schedule

        # Notify instructor
        message = _t("scheduling.notifications.schedule_change_message", module_code=module_code, description=change_description)
        if instructor_id:
            self.create_notification('instructor', str(instructor_id), message, 'schedule_change')

        # Notify students enrolled in the module
        cursor.execute('SELECT student_id FROM student_modules WHERE module_code = ?', (module_code,))
        students = cursor.fetchall()

        for student in students:
            if student[0]:
                self.create_notification('student', student[0], message, 'schedule_change')

    try:
        messagebox.showinfo(_t("scheduling.notifications.notifications_sent_title"), _t("scheduling.notifications.notifications_sent_message", description=change_description), parent=self.root)
    except Exception:
        messagebox.showinfo("Notifications Sent", f"Notifications sent for schedule change: {change_description}", parent=self.root)

ModuleSchedulingGUI.send_schedule_change_notifications = send_schedule_change_notifications

def get_notifications(self, recipient_type, recipient_id, unread_only=True):
    """Get notifications for a user by checking their emails"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Get user email based on type
        email_address = None
        if recipient_type == 'instructor':
            cursor.execute('SELECT email FROM instructors WHERE id = ?', (recipient_id,))
            result = cursor.fetchone()
            if result:
                email_address = result[0]
        elif recipient_type == 'student':
            cursor.execute('SELECT email FROM students WHERE student_id = ?', (recipient_id,))
            result = cursor.fetchone()
            if result:
                email_address = result[0]

        if not email_address:
            return []

        # Get emails from stored_emails table
        query = '''
        SELECT id, subject, body, created_date
        FROM stored_emails
        WHERE recipient_email = ?
        AND subject LIKE '%Module Scheduling%'
        ORDER BY created_date DESC
        '''

        cursor.execute(query, (email_address,))
        notifications = cursor.fetchall()

    return notifications

ModuleSchedulingGUI.get_notifications = get_notifications

def mark_notification_read(self, notification_id):
    """Mark a notification as read - no-op for email-based notifications"""
    # Email-based notifications don't use read/unread status in the same way
    # This is kept for backward compatibility but does nothing
    pass

ModuleSchedulingGUI.mark_notification_read = mark_notification_read

def email_all_students_on_module(self, module_code, subject, message, include_instructor=True):
    """
    Email all students enrolled in a module, and optionally the instructor.

    Args:
        module_code: The module code to send emails for
        subject: Email subject line
        message: Email body message
        include_instructor: Whether to also email the instructor (default: True)

    Returns:
        dict: Summary of emails sent (students_emailed, instructor_emailed, errors)
    """
    from education_system.university_system.infrastructure.email.email_service import send_email

    summary = {
        'students_emailed': 0,
        'instructor_emailed': False,
        'errors': []
    }

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Get module name for better messaging
            cursor.execute('SELECT module_name FROM modules WHERE module_code = ?', (module_code,))
            module_result = cursor.fetchone()
            module_name = module_result[0] if module_result else module_code

            # Email all students enrolled in the module
            cursor.execute('''
                SELECT DISTINCT s.student_id, s.email, s.first_name, s.last_name
                FROM students s
                INNER JOIN student_modules sm ON s.student_id = sm.student_id
                WHERE sm.module_code = ?
                AND s.email IS NOT NULL
                AND s.email != ''
            ''', (module_code,))

            students = cursor.fetchall()

            for student_id, email, first_name, last_name in students:
                try:
                    student_name = f"{first_name or ''} {last_name or ''}".strip() or "Student"

                    # Render email from template
                    from education_system.university_system.infrastructure.email.template_utils import render_template

                    template_subject, personalized_message = render_template('academics/module_student_notification', {
                        'custom_subject': subject,
                        'student_name': student_name,
                        'message': message,
                        'module_name': module_name,
                        'module_code': module_code
                    })

                    # Fallback if template not found
                    if not template_subject or not personalized_message:
                        personalized_message = f"Dear {student_name},\n\n{message}\n\nModule: {module_name} ({module_code})\n\nBest regards,\nUniversity Module Scheduling System"

                    send_email(email, subject, personalized_message)
                    summary['students_emailed'] += 1
                except Exception as e:
                    summary['errors'].append(f"Failed to email {email}: {str(e)}")

            # Email instructor if requested
            if include_instructor:
                cursor.execute('''
                    SELECT DISTINCT i.email, i.first_name, i.last_name
                    FROM instructors i
                    INNER JOIN module_schedule ms ON i.id = ms.instructor_id
                    WHERE ms.module_code = ?
                    AND i.email IS NOT NULL
                    AND i.email != ''
                    LIMIT 1
                ''', (module_code,))

                instructor = cursor.fetchone()
                if instructor:
                    email, first_name, last_name = instructor
                    try:
                        instructor_name = f"{first_name or ''} {last_name or ''}".strip() or "Instructor"
                        personalized_message = f"Dear {instructor_name},\n\n{message}\n\nModule: {module_name} ({module_code})\n\nBest regards,\nUniversity Module Scheduling System"

                        send_email(email, subject, personalized_message)
                        summary['instructor_emailed'] = True
                    except Exception as e:
                        summary['errors'].append(f"Failed to email instructor {email}: {str(e)}")

    except Exception as e:
        summary['errors'].append(f"Database error: {str(e)}")

    return summary

ModuleSchedulingGUI.email_all_students_on_module = email_all_students_on_module

def _log_system_action(self, action_type, description, details=None):
    """Log system action to database for audit trail"""
    try:
        with transaction() as conn:
            cursor = conn.cursor()

            # Ensure system_logs table exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_type TEXT,
                    description TEXT,
                    details TEXT,
                    created_date TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            import json
            details_json = json.dumps(details) if details else None

            cursor.execute('''
            INSERT INTO system_logs (action_type, description, details, created_date)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (action_type, description, details_json))

    except Exception as e:
        print(f"Error logging system action: {e}")

ModuleSchedulingGUI._log_system_action = _log_system_action

