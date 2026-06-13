"""Schedule change email notifications."""

from __future__ import annotations

import smtplib

from education_system.university_system.infrastructure.database.db import sqlite3

from education_system.university_system.core.logs import log_event
from education_system.university_system.infrastructure.email.templates import load_template
from education_system.university_system.core.exceptions import (
    EmailDeliveryError,
    TemplateError,
)


def send_schedule_change_notification(schedule_id: int, old_data: dict, new_data: dict) -> bool:
    """
    Send notifications for schedule changes to affected students and staff.

    Args:
        schedule_id: The schedule entry ID
        old_data: Dictionary with old schedule data (module_code, day_of_week, start_time, end_time, room_id, instructor_id, session_type)
        new_data: Dictionary with new schedule data

    Returns:
        True if notifications were sent successfully
    """
    try:
        from education_system.university_system.core.activity_logger import log_activity

        module_code = old_data.get('module_code')
        if not module_code:
            return False

        # Get module information
        module_info = _get_module_info(module_code)
        if not module_info:
            return False

        # Determine what changed
        changes = []
        datetime_changed = False
        instructor_changed = False
        room_changed = False

        if (old_data.get('day_of_week') != new_data.get('day_of_week') or
            old_data.get('start_time') != new_data.get('start_time') or
            old_data.get('end_time') != new_data.get('end_time')):
            datetime_changed = True
            changes.append('date/time')

        if old_data.get('instructor_id') != new_data.get('instructor_id'):
            instructor_changed = True
            changes.append('instructor')

        if old_data.get('room_id') != new_data.get('room_id'):
            room_changed = True
            changes.append('room')

        if not changes:
            return True  # No notification needed

        # Get recipients
        students = _get_enrolled_students(module_code)
        staff = _get_module_staff(module_code)

        # Send appropriate notifications
        success = True

        if datetime_changed:
            success = success and _notify_datetime_change(
                students + staff, module_info, old_data, new_data
            )

        if instructor_changed:
            success = success and _notify_instructor_change(
                students, module_info, old_data, new_data
            )

            # Notify new instructor
            new_instructor_id = new_data.get('instructor_id')
            if new_instructor_id:
                success = success and _notify_new_instructor_assignment(
                    new_instructor_id, module_info, new_data
                )

        if room_changed:
            success = success and _notify_room_change(
                students + staff, module_info, old_data, new_data
            )

        # Log the notification activity
        log_activity(
            'notify',
            'schedule_change',
            details={
                'schedule_id': schedule_id,
                'module_code': module_code,
                'changes': ', '.join(changes),
                'recipients': len(students) + len(staff)
            }
        )

        return success

    except (smtplib.SMTPException, EmailDeliveryError) as e:
        log_event('error', f"Email delivery error sending schedule change notifications: {e}")
        return False
    except sqlite3.Error as e:
        log_event('error', f"Database error sending schedule change notifications: {e}")
        return False

def _get_module_info(module_code: str) -> dict | None:
    """Get module information from database"""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT module_code, module_name, credits
                FROM modules
                WHERE module_code = ?
            ''', (module_code,))
            row = cursor.fetchone()

            if row:
                return {
                    'module_code': row[0],
                    'module_name': row[1] if row[1] else row[0],
                    'credits': row[2] if row[2] else 'N/A'
                }
    except sqlite3.Error as e:
        log_event('error', f"Database error getting module info: {e}")
    return None

def _get_room_location(room_id: int | None) -> str:
    """Get room location string"""
    if not room_id:
        return "TBA"

    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT building, room_number
                FROM rooms
                WHERE id = ?
            ''', (room_id,))
            row = cursor.fetchone()

            if row and row[0] and row[1]:
                return f"{row[0]}-{row[1]}"
    except sqlite3.Error as e:
        log_event('error', f"Database error getting room location: {e}")

    return "TBA"

def _get_instructor_info(instructor_id: int | None) -> dict:
    """Get instructor information"""
    if not instructor_id:
        return {'name': 'TBA', 'email': ''}

    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT first_name, last_name, email
                FROM instructors
                WHERE id = ?
            ''', (instructor_id,))
            row = cursor.fetchone()

            if row:
                return {
                    'name': f"{row[0]} {row[1]}",
                    'email': row[2] if row[2] else ''
                }
    except sqlite3.Error as e:
        log_event('error', f"Database error getting instructor info: {e}")

    return {'name': 'TBA', 'email': ''}

def _get_enrolled_students(module_code: str) -> list:
    """Get list of students enrolled in a module"""
    students = []
    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email_address
                FROM students s
                INNER JOIN student_modules sm ON s.student_id = sm.student_id
                WHERE sm.module_code = ? AND sm.status = 'Enrolled'
            ''', (module_code,))

            for row in cursor.fetchall():
                if row[3]:  # Has email
                    students.append({
                        'student_id': row[0],
                        'name': f"{row[1]} {row[2]}",
                        'email': row[3]
                    })
    except sqlite3.Error as e:
        log_event('error', f"Database error getting enrolled students: {e}")

    return students

def _get_module_staff(module_code: str) -> list:
    """Get staff associated with a module (via schedules)"""
    staff = []
    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT i.id, i.first_name, i.last_name, i.email
                FROM instructors i
                INNER JOIN module_schedule ms ON i.id = ms.instructor_id
                WHERE ms.module_code = ?
            ''', (module_code,))

            for row in cursor.fetchall():
                if row[3]:  # Has email
                    staff.append({
                        'instructor_id': row[0],
                        'name': f"{row[1]} {row[2]}",
                        'email': row[3]
                    })
    except sqlite3.Error as e:
        log_event('error', f"Database error getting module staff: {e}")

    return staff

def _notify_datetime_change(recipients: list, module_info: dict, old_data: dict, new_data: dict) -> bool:
    """Send date/time change notifications"""
    from education_system.university_system.infrastructure.email.email_service.core import send_email

    old_room = _get_room_location(old_data.get('room_id'))

    for recipient in recipients:
        try:
            variables = {
                'recipient_name': recipient['name'],
                'module_code': module_info['module_code'],
                'module_name': module_info['module_name'],
                'old_day': old_data.get('day_of_week', 'TBA'),
                'old_start_time': old_data.get('start_time', 'TBA'),
                'old_end_time': old_data.get('end_time', 'TBA'),
                'new_day': new_data.get('day_of_week', 'TBA'),
                'new_start_time': new_data.get('start_time', 'TBA'),
                'new_end_time': new_data.get('end_time', 'TBA'),
                'room_location': old_room,
                'session_type': old_data.get('session_type', 'Session'),
                'instructor_name': _get_instructor_info(old_data.get('instructor_id'))['name'],
                'coordinator_email': 'coordinator@university.edu',
                'signature': '\n\nBest regards,\nAcademic Office\nUniversity Management System'
            }

            # Load and render template
            template = load_template('academics/schedule_change_datetime')
            if template:
                subject = template.get('subject', 'Schedule Change Notification')
                body = template.get('body', 'A schedule change has occurred.')

                # Replace variables
                for key, value in variables.items():
                    subject = subject.replace(f'£{key}', str(value))
                    body = body.replace(f'£{key}', str(value))
            else:
                subject = f"Schedule Change - {module_info['module_code']}: Date/Time Updated"
                body = f"Dear {recipient['name']},\n\nThe schedule for {module_info['module_code']} has changed.\n\nOld: {old_data.get('day_of_week')} at {old_data.get('start_time')}\nNew: {new_data.get('day_of_week')} at {new_data.get('start_time')}"

            send_email(recipient['email'], subject, body)

        except (smtplib.SMTPException, EmailDeliveryError) as e:
            log_event('error', f"Email error sending datetime change to {recipient['email']}: {e}")
            return False
        except (TemplateError, KeyError) as e:
            log_event('error', f"Template error sending datetime change to {recipient['email']}: {e}")
            return False

    return True

def _notify_instructor_change(recipients: list, module_info: dict, old_data: dict, new_data: dict) -> bool:
    """Send instructor change notifications"""
    from education_system.university_system.infrastructure.email.email_service.core import send_email

    old_instructor = _get_instructor_info(old_data.get('instructor_id'))
    new_instructor = _get_instructor_info(new_data.get('instructor_id'))
    room_location = _get_room_location(new_data.get('room_id'))

    for recipient in recipients:
        try:
            variables = {
                'recipient_name': recipient['name'],
                'module_code': module_info['module_code'],
                'module_name': module_info['module_name'],
                'day_of_week': new_data.get('day_of_week', 'TBA'),
                'start_time': new_data.get('start_time', 'TBA'),
                'end_time': new_data.get('end_time', 'TBA'),
                'room_location': room_location,
                'session_type': new_data.get('session_type', 'Session'),
                'old_instructor_name': old_instructor['name'],
                'new_instructor_name': new_instructor['name'],
                'new_instructor_email': new_instructor['email'] or 'TBA',
                'coordinator_email': 'coordinator@university.edu',
                'signature': '\n\nBest regards,\nAcademic Office\nUniversity Management System'
            }

            template = load_template('academics/schedule_change_instructor')
            if template:
                subject = template.get('subject', 'Schedule Change Notification')
                body = template.get('body', 'An instructor change has occurred.')

                for key, value in variables.items():
                    subject = subject.replace(f'£{key}', str(value))
                    body = body.replace(f'£{key}', str(value))
            else:
                subject = f"Schedule Change - {module_info['module_code']}: Instructor Updated"
                body = f"Dear {recipient['name']},\n\nThe instructor for {module_info['module_code']} has changed.\n\nOld: {old_instructor['name']}\nNew: {new_instructor['name']}"

            send_email(recipient['email'], subject, body)

        except Exception as e:
            log_event('error', f"Error sending instructor change email to {recipient['email']}: {e}")
            return False

    return True

def _notify_room_change(recipients: list, module_info: dict, old_data: dict, new_data: dict) -> bool:
    """Send room change notifications"""
    from education_system.university_system.infrastructure.email.email_service.core import send_email

    old_room = _get_room_location(old_data.get('room_id'))
    new_room = _get_room_location(new_data.get('room_id'))
    instructor_info = _get_instructor_info(new_data.get('instructor_id'))

    for recipient in recipients:
        try:
            variables = {
                'recipient_name': recipient['name'],
                'module_code': module_info['module_code'],
                'module_name': module_info['module_name'],
                'day_of_week': new_data.get('day_of_week', 'TBA'),
                'start_time': new_data.get('start_time', 'TBA'),
                'end_time': new_data.get('end_time', 'TBA'),
                'session_type': new_data.get('session_type', 'Session'),
                'instructor_name': instructor_info['name'],
                'old_room_location': old_room,
                'new_room_location': new_room,
                'coordinator_email': 'coordinator@university.edu',
                'signature': '\n\nBest regards,\nAcademic Office\nUniversity Management System'
            }

            template = load_template('academics/schedule_change_room')
            if template:
                subject = template.get('subject', 'Schedule Change Notification')
                body = template.get('body', 'A room change has occurred.')

                for key, value in variables.items():
                    subject = subject.replace(f'£{key}', str(value))
                    body = body.replace(f'£{key}', str(value))
            else:
                subject = f"Schedule Change - {module_info['module_code']}: Room Updated"
                body = f"Dear {recipient['name']},\n\nThe room for {module_info['module_code']} has changed.\n\nOld: {old_room}\nNew: {new_room}"

            send_email(recipient['email'], subject, body)

        except Exception as e:
            log_event('error', f"Error sending room change email to {recipient['email']}: {e}")
            return False

    return True

def _notify_new_instructor_assignment(instructor_id: int, module_info: dict, schedule_data: dict) -> bool:
    """Notify a newly assigned instructor"""
    from education_system.university_system.infrastructure.email.email_service.core import send_email

    instructor_info = _get_instructor_info(instructor_id)
    if not instructor_info['email']:
        return True  # No email to send to

    room_location = _get_room_location(schedule_data.get('room_id'))

    # Get student count
    student_count = 0
    try:
        from education_system.university_system.infrastructure.database.db import get_connection

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM enrollments
                WHERE module_code = ? AND status = 'enrolled'
            ''', (module_info['module_code'],))
            row = cursor.fetchone()
            if row:
                student_count = row[0]
    except Exception:
        pass

    try:
        variables = {
            'instructor_name': instructor_info['name'],
            'module_code': module_info['module_code'],
            'module_name': module_info['module_name'],
            'session_type': schedule_data.get('session_type', 'Session'),
            'day_of_week': schedule_data.get('day_of_week', 'TBA'),
            'start_time': schedule_data.get('start_time', 'TBA'),
            'end_time': schedule_data.get('end_time', 'TBA'),
            'room_location': room_location,
            'student_count': str(student_count),
            'hod_email': 'hod@university.edu',
            'signature': '\n\nBest regards,\nAcademic Office\nUniversity Management System'
        }

        template = load_template('academics/instructor_assignment_notification')
        if template:
            subject = template.get('subject', 'New Module Assignment')
            body = template.get('body', 'You have been assigned to teach a module.')

            for key, value in variables.items():
                subject = subject.replace(f'£{key}', str(value))
                body = body.replace(f'£{key}', str(value))
        else:
            subject = f"New Module Assignment - {module_info['module_code']}"
            body = f"Dear {instructor_info['name']},\n\nYou have been assigned to teach {module_info['module_code']} on {schedule_data.get('day_of_week')} at {schedule_data.get('start_time')}."

        send_email(instructor_info['email'], subject, body)
        return True

    except Exception as e:
        log_event('error', f"Error sending instructor assignment email: {e}")
        return False
