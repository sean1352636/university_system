"""Email notifications and calendar integration for the Exam Scheduling System."""

import logging
from datetime import datetime
from typing import Tuple, List, Dict, Optional

from .models import Exam

logger = logging.getLogger(__name__)

# Email imports
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    HAS_EMAIL = True
except ImportError:
    HAS_EMAIL = False


def send_exam_notifications(exam: Exam, get_enrolled_students, get_instructor_by_id) -> Tuple[int, int]:
    """Send email notifications about an exam to all enrolled students and instructor.

    Args:
        exam: The exam to notify about.
        get_enrolled_students: Callable that takes module_code and returns list of student dicts.
        get_instructor_by_id: Callable that takes instructor_id and returns instructor dict or None.

    Returns:
        Tuple of (success_count, failure_count)
    """
    if not HAS_EMAIL:
        logger.warning("Email system not available")
        return (0, 0)

    success_count = 0
    failure_count = 0

    # Get enrolled students
    students = get_enrolled_students(exam.module_code)

    # Get instructor
    instructor = get_instructor_by_id(exam.instructor_id) if exam.instructor_id else None

    # Render email template for students
    try:
        from education_system.university_system.infrastructure.email.template_utils import render_template

        subject, body = render_template('academics/exam_scheduled_student', {
            'module_code': exam.module_code,
            'module_name': exam.module_name,
            'exam_date': exam.date,
            'start_time': exam.start_time,
            'end_time': exam.end_time,
            'room': exam.room,
            'instructor_name': exam.instructor_name
        })

        # Fallback if template not found
        if not subject or not body:
            subject = f"Exam Scheduled: {exam.module_code} - {exam.module_name}"
            body = f"Dear Student/Instructor,\n\nAn exam has been scheduled for {exam.module_code} - {exam.module_name} on {exam.date} from {exam.start_time} to {exam.end_time} in {exam.room}.\n\nBest regards,\nUniversity Examination Office"
    except Exception as e:
        logger.error(f"Error rendering email template: {e}")
        subject = f"Exam Scheduled: {exam.module_code} - {exam.module_name}"
        body = f"Dear Student/Instructor,\n\nAn exam has been scheduled for {exam.module_code} - {exam.module_name} on {exam.date} from {exam.start_time} to {exam.end_time} in {exam.room}.\n\nBest regards,\nUniversity Examination Office"

    # Send to students
    for student in students:
        if student.get('email'):
            try:
                send_email(student['email'], subject, body)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to send exam notification to {student['email']}: {e}")
                failure_count += 1

    # Send to instructor
    if instructor and instructor.get('email'):
        try:
            from education_system.university_system.infrastructure.email.template_utils import render_template

            instructor_subject, instructor_body = render_template('academics/exam_scheduled_instructor', {
                'instructor_name': instructor['display_name'],
                'module_code': exam.module_code,
                'module_name': exam.module_name,
                'exam_date': exam.date,
                'start_time': exam.start_time,
                'end_time': exam.end_time,
                'room': exam.room,
                'students_enrolled': exam.students_enrolled
            })

            # Fallback if template not found
            if not instructor_subject or not instructor_body:
                instructor_subject = f"Exam Scheduled (Instructor): {exam.module_code} - {exam.module_name}"
                instructor_body = f"Dear {instructor['display_name']},\n\nYou have been assigned as the instructor for an exam on {exam.date} from {exam.start_time} to {exam.end_time} in {exam.room}.\n\nBest regards,\nUniversity Examination Office"

            send_email(instructor['email'], instructor_subject, instructor_body)
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to send exam notification to instructor {instructor['email']}: {e}")
            failure_count += 1

    return (success_count, failure_count)


def send_exam_update_notifications(exam: Exam, get_enrolled_students, get_instructor_by_id) -> Tuple[int, int]:
    """Send email notifications about an exam update to all enrolled students and instructor.

    Args:
        exam: The updated exam.
        get_enrolled_students: Callable that takes module_code and returns list of student dicts.
        get_instructor_by_id: Callable that takes instructor_id and returns instructor dict or None.

    Returns:
        Tuple of (success_count, failure_count)
    """
    if not HAS_EMAIL:
        logger.warning("Email system not available")
        return (0, 0)

    success_count = 0
    failure_count = 0

    # Get enrolled students
    students = get_enrolled_students(exam.module_code)

    # Get instructor
    instructor = get_instructor_by_id(exam.instructor_id) if exam.instructor_id else None

    # Render email template for students
    try:
        from education_system.university_system.infrastructure.email.template_utils import render_template

        subject, body = render_template('academics/exam_updated_student', {
            'module_code': exam.module_code,
            'module_name': exam.module_name,
            'exam_date': exam.date,
            'start_time': exam.start_time,
            'end_time': exam.end_time,
            'room': exam.room,
            'instructor_name': exam.instructor_name
        })

        # Fallback if template not found
        if not subject or not body:
            subject = f"Exam Updated: {exam.module_code} - {exam.module_name}"
            body = f"Dear Student/Instructor,\n\nIMPORTANT: The exam for {exam.module_code} - {exam.module_name} has been updated.\n\nNew details: {exam.date}, {exam.start_time} - {exam.end_time}, {exam.room}\n\nBest regards,\nUniversity Examination Office"
    except Exception as e:
        logger.error(f"Error rendering email template: {e}")
        subject = f"Exam Updated: {exam.module_code} - {exam.module_name}"
        body = f"Dear Student/Instructor,\n\nIMPORTANT: The exam for {exam.module_code} - {exam.module_name} has been updated.\n\nNew details: {exam.date}, {exam.start_time} - {exam.end_time}, {exam.room}\n\nBest regards,\nUniversity Examination Office"

    # Send to students
    for student in students:
        if student.get('email'):
            try:
                send_email(student['email'], subject, body)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to send exam update notification to {student['email']}: {e}")
                failure_count += 1

    # Send to instructor
    if instructor and instructor.get('email'):
        try:
            from education_system.university_system.infrastructure.email.template_utils import render_template

            instructor_subject, instructor_body = render_template('academics/exam_updated_instructor', {
                'instructor_name': instructor['display_name'],
                'module_code': exam.module_code,
                'module_name': exam.module_name,
                'exam_date': exam.date,
                'start_time': exam.start_time,
                'end_time': exam.end_time,
                'room': exam.room,
                'students_enrolled': exam.students_enrolled
            })

            # Fallback if template not found
            if not instructor_subject or not instructor_body:
                instructor_subject = f"Exam Updated (Instructor): {exam.module_code} - {exam.module_name}"
                instructor_body = f"Dear {instructor['display_name']},\n\nIMPORTANT: The exam you are supervising has been updated.\n\nNew details: {exam.date}, {exam.start_time} - {exam.end_time}, {exam.room}\n\nBest regards,\nUniversity Examination Office"

            send_email(instructor['email'], instructor_subject, instructor_body)
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to send exam update notification to instructor {instructor['email']}: {e}")
            failure_count += 1

    return (success_count, failure_count)


def add_exam_to_calendar(exam: Exam) -> bool:
    """Add exam as an event to the academic calendar (events table)."""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
    except ImportError:
        logger.warning("Database not available for calendar integration")
        return False

    try:
        import uuid
        event_id = f"EXAM-{exam.module_code}-{uuid.uuid4().hex[:8]}"
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Combine date and time for start/end
        # Note: events table constraint requires EITHER date OR (date_start AND date_end), not both
        start_datetime = f"{exam.date} {exam.start_time}"
        end_datetime = f"{exam.date} {exam.end_time}"

        with get_connection() as conn:
            conn.execute("""
                INSERT INTO academic_calendar_events
                (id, name, date_start, date_end, description, event_type, date_added, last_modified)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id,
                f"Exam: {exam.module_code} - {exam.module_name}",
                start_datetime,
                end_datetime,
                f"Room: {exam.room}\nInstructor: {exam.instructor_name}\nStudents Enrolled: {exam.students_enrolled}\nTime: {exam.start_time} - {exam.end_time}",
                'Exam',
                now,
                now
            ))
            conn.commit()
        logger.info(f"Added exam {exam.module_code} to academic calendar (events table)")
        return True
    except Exception as e:
        logger.error(f"Failed to add exam to calendar: {e}")
        return False
