"""Email notifications and calendar integration for the Exam Scheduling System."""

import logging
from datetime import datetime
from typing import Tuple, List, Dict, Optional

from education_system.university_system.modules.domain.academics.gui.exam_management.models import Exam

logger = logging.getLogger(__name__)

# Email imports
try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    HAS_EMAIL = True
except ImportError:
    HAS_EMAIL = False

# In-app notifications service (best-effort: tolerate missing module)
try:
    from education_system.university_system.modules.domain.operations.communications.notifications.services.notifications_service import (
        NotificationsService,
    )
    HAS_NOTIFICATIONS = True
except Exception:  # pragma: no cover - depends on optional infra
    HAS_NOTIFICATIONS = False


def _push_in_app_notification(user_id, title: str, message: str,
                              source_id, priority: str = "normal") -> bool:
    """Send a single in-app notification via NotificationsService.

    Returns True on success, False if the service is unavailable or the
    write fails. Best-effort: never raises.
    """
    if not HAS_NOTIFICATIONS or user_id is None:
        return False
    try:
        NotificationsService().create_notification(
            user_id=str(user_id),
            channel="academic",
            priority=priority,
            title=title,
            message=message,
            source_system="exam_management",
            source_id=str(source_id) if source_id is not None else None,
        )
        return True
    except Exception as exc:
        logger.debug("In-app notification failed for user_id=%s: %s",
                     user_id, exc)
        return False


def _push_exam_in_app(exam: 'Exam', students: List[Dict],
                      instructor: Optional[Dict],
                      action: str) -> Tuple[int, int]:
    """Fan an exam event out as in-app notifications.

    *action* is one of "scheduled", "updated", "cancelled" and shapes the
    title and priority. Returns (sent, failed).
    """
    titles = {
        "scheduled": f"Exam scheduled: {exam.module_code}",
        "updated":   f"Exam updated: {exam.module_code}",
        "cancelled": f"Exam cancelled: {exam.module_code}",
    }
    priorities = {"scheduled": "normal", "updated": "high", "cancelled": "high"}
    title = titles.get(action, f"Exam {action}: {exam.module_code}")
    priority = priorities.get(action, "normal")

    if action == "cancelled":
        message = (
            f"The exam for {exam.module_code} - {exam.module_name} "
            f"originally scheduled on {exam.date} {exam.start_time}–{exam.end_time} "
            f"in {exam.room} has been cancelled."
        )
    else:
        message = (
            f"{exam.module_code} - {exam.module_name}: "
            f"{exam.date} {exam.start_time}–{exam.end_time} in {exam.room} "
            f"(instructor {exam.instructor_name})."
        )

    sent = failed = 0
    for student in students:
        sid = student.get("student_id")
        if not sid:
            continue
        if _push_in_app_notification(sid, title, message, exam.id, priority):
            sent += 1
        else:
            failed += 1

    if instructor:
        iid = instructor.get("user_id") or instructor.get("id")
        if iid is not None:
            if _push_in_app_notification(iid, title, message, exam.id, priority):
                sent += 1
            else:
                failed += 1

    return sent, failed


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

    # Mirror as in-app notifications (best-effort)
    _push_exam_in_app(exam, students, instructor, "scheduled")

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

    # Mirror as in-app notifications (best-effort)
    _push_exam_in_app(exam, students, instructor, "updated")

    return (success_count, failure_count)


def send_exam_cancellation_notifications(exam: Exam, get_enrolled_students,
                                         get_instructor_by_id) -> Tuple[int, int]:
    """Notify enrolled students and the instructor that an exam was cancelled.

    Sends an email to each recipient with an inline subject/body (no
    template needed) and pushes a high-priority in-app notification.
    Returns (success_count, failure_count) covering email sends only;
    in-app delivery is best-effort and not counted here.
    """
    students = get_enrolled_students(exam.module_code) or []
    instructor = get_instructor_by_id(exam.instructor_id) if exam.instructor_id else None

    if not HAS_EMAIL:
        # Still push in-app notifications so users see something.
        _push_exam_in_app(exam, students, instructor, "cancelled")
        return (0, 0)

    success_count = failure_count = 0
    subject = f"Exam Cancelled: {exam.module_code} - {exam.module_name}"
    body = (
        f"The exam for {exam.module_code} - {exam.module_name} originally "
        f"scheduled on {exam.date} from {exam.start_time} to {exam.end_time} "
        f"in {exam.room} has been cancelled.\n\n"
        f"If you have questions, contact the instructor "
        f"({exam.instructor_name}) or the Examination Office.\n\n"
        f"— University Examination Office"
    )

    for student in students:
        if student.get('email'):
            try:
                send_email(student['email'], subject, body)
                success_count += 1
            except Exception as e:
                logger.error("Failed to send cancellation to %s: %s",
                             student['email'], e)
                failure_count += 1

    if instructor and instructor.get('email'):
        try:
            instructor_body = (
                f"Dear {instructor.get('display_name') or exam.instructor_name},\n\n"
                + body
            )
            send_email(instructor['email'], subject, instructor_body)
            success_count += 1
        except Exception as e:
            logger.error("Failed to send cancellation to instructor %s: %s",
                         instructor['email'], e)
            failure_count += 1

    _push_exam_in_app(exam, students, instructor, "cancelled")

    return (success_count, failure_count)


def _calendar_event_id(exam_id) -> str:
    """Deterministic event id for an exam so add/update/delete address the
    same row in academic_calendar_events."""
    return f"EXAM-{exam_id}"


def add_exam_to_calendar(exam: Exam) -> bool:
    """Upsert an exam into the academic calendar.

    Uses a deterministic event id so calling this on an existing exam
    overwrites the previous calendar entry (idempotent for updates).
    """
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
    except ImportError:
        logger.warning("Database not available for calendar integration")
        return False

    try:
        event_id = _calendar_event_id(exam.id)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        start_datetime = f"{exam.date} {exam.start_time}"
        end_datetime = f"{exam.date} {exam.end_time}"
        name = f"Exam: {exam.module_code} - {exam.module_name}"
        description = (
            f"Room: {exam.room}\n"
            f"Instructor: {exam.instructor_name}\n"
            f"Students Enrolled: {exam.students_enrolled}\n"
            f"Time: {exam.start_time} - {exam.end_time}"
        )

        with get_connection() as conn:
            existing = conn.execute(
                "SELECT 1 FROM academic_calendar_events WHERE id = ?",
                (event_id,),
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE academic_calendar_events
                       SET name = ?, date_start = ?, date_end = ?,
                           description = ?, event_type = ?, last_modified = ?
                       WHERE id = ?""",
                    (name, start_datetime, end_datetime, description,
                     'Exam', now, event_id),
                )
            else:
                conn.execute(
                    """INSERT INTO academic_calendar_events
                       (id, name, date_start, date_end, description,
                        event_type, date_added, last_modified)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (event_id, name, start_datetime, end_datetime,
                     description, 'Exam', now, now),
                )
            conn.commit()
        logger.info("Synced exam %s to academic calendar (event %s)",
                    exam.module_code, event_id)
        return True
    except Exception as e:
        logger.error("Failed to sync exam to calendar: %s", e)
        return False


def remove_exam_from_calendar(exam_id) -> bool:
    """Remove the calendar event corresponding to an exam, if present."""
    try:
        from education_system.university_system.infrastructure.database.db import get_connection
    except ImportError:
        return False
    try:
        event_id = _calendar_event_id(exam_id)
        with get_connection() as conn:
            conn.execute(
                "DELETE FROM academic_calendar_events WHERE id = ?",
                (event_id,),
            )
            conn.commit()
        logger.info("Removed exam %s from academic calendar", event_id)
        return True
    except Exception as e:
        logger.error("Failed to remove exam from calendar: %s", e)
        return False
