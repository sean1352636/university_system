"""Academic and student notification emails."""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

from datetime import datetime

from education_system.systems.university.infrastructure.database.db import sqlite3

from education_system.systems.university.infrastructure.email.email_db_utilities import execute_db_operation
from education_system.systems.university.infrastructure.logs import handle_exception, log_event
from education_system.systems.university.infrastructure.email.templates import render_template
from education_system.systems.university.infrastructure.exceptions import (
    EmailDeliveryError,
    TemplateError,
)

# Import immutable audit logging for compliance
try:
    from education_system.systems.university.infrastructure.security.audit_helpers import (
        safe_log_security_event,
        mask_sensitive_data,
    )
    from education_system.systems.university.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False
    def mask_sensitive_data(data, fields=None):
        return data


@handle_exception
def send_registration_confirmation(student_id):
    """Send a registration confirmation email to a student"""
    from education_system.systems.university.infrastructure.email.email_service.queue import queue_template_email

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
    from education_system.systems.university.infrastructure.email.email_service.core import send_template_email

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
    from education_system.systems.university.infrastructure.email.email_service.core import send_template_email

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
    from education_system.systems.university.infrastructure.email.email_service.queue import queue_template_email

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
    from education_system.systems.university.infrastructure.email.email_service.core import send_email, send_template_email

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
                logger.debug("Suppressed exception", exc_info=True)

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
    from education_system.systems.university.infrastructure.email.email_service.core import send_template_email

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
    from education_system.systems.university.infrastructure.email.email_service.queue import queue_email

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


# ---------------------------------------------------------------------------
# Online sessions (virtual classrooms)
#
# A class that exists only in the database helps nobody: the lecturer and
# the students on the module need the date, the join link and the access
# code, and they need telling again when it moves or is called off.
# ---------------------------------------------------------------------------

#: Full path from the templates root. ``load_template`` resolves a bare
#: name only one level deep, so the old "virtual_classroom/..." prefix
#: matched nothing and every one of these emails was silently dropped.
_ONLINE_CLASS_TEMPLATE_DIR = "academics/research_and_events/virtual_classroom"

_ONLINE_CLASS_TEMPLATES = {
    "created": "class_created",
    "updated": "class_updated",
    "cancelled": "class_cancelled",
    "scheduled": "session_scheduled",
}

_ACTIVE_ENROLMENT = ("active", "enrolled", "registered", "in_progress")


def get_online_class_audience(classroom_id):
    """Who should hear about an online class.

    Returns ``{lecturer, students, module_code, module_name, reason}``.
    Students come from ``module_enrolments`` when the classroom names a
    module, falling back to ``programme_registrations`` and then
    ``students.course`` when it only names a course. A classroom tied to
    neither has no audience, and *reason* says so rather than the caller
    reporting a silent success.
    """
    from education_system.systems.university.infrastructure.database.db import get_connection

    out = {"lecturer": None, "students": [], "module_code": None,
           "module_name": "", "course_id": None, "reason": None}
    try:
        with get_connection() as conn:
            classroom = conn.execute(
                "SELECT * FROM virtual_classrooms WHERE classroom_id = ?",
                (classroom_id,)).fetchone()
            if classroom is None:
                out["reason"] = "classroom not found"
                return out

            keys = classroom.keys() if hasattr(classroom, "keys") else []
            module_code = classroom["module_code"] if "module_code" in keys else None
            course_id = classroom["course_id"] if "course_id" in keys else None
            out["module_code"], out["course_id"] = module_code, course_id

            instructor_id = classroom["instructor_id"] if "instructor_id" in keys else None
            if instructor_id:
                row = conn.execute(
                    "SELECT first_name, last_name, email FROM instructors WHERE id = ?",
                    (instructor_id,)).fetchone()
                if row and row["email"]:
                    name = " ".join(p for p in (row["first_name"], row["last_name"]) if p)
                    out["lecturer"] = {"name": name or f"Instructor {instructor_id}",
                                       "email": row["email"]}

            if module_code:
                row = conn.execute(
                    "SELECT module_name FROM modules WHERE module_code = ?",
                    (module_code,)).fetchone()
                out["module_name"] = (row["module_name"] if row else "") or str(module_code)

            placeholders = ",".join("?" * len(_ACTIVE_ENROLMENT))
            rows = []
            if module_code:
                rows = conn.execute(
                    "SELECT s.student_id, s.first_name, s.last_name, s.email_address "
                    "FROM module_enrolments me "
                    "JOIN students s ON s.student_id = me.student_id "
                    "WHERE me.module_code = ? "
                    f"  AND LOWER(COALESCE(me.status,'active')) IN ({placeholders}) "
                    "  AND COALESCE(s.is_active, 1) = 1",
                    (module_code, *_ACTIVE_ENROLMENT)).fetchall()
            if not rows and course_id:
                rows = conn.execute(
                    "SELECT s.student_id, s.first_name, s.last_name, s.email_address "
                    "FROM programme_registrations pr "
                    "JOIN students s ON s.student_id = pr.student_id "
                    "WHERE pr.programme_code = ? AND COALESCE(s.is_active, 1) = 1",
                    (str(course_id),)).fetchall()
            if not rows and course_id:
                rows = conn.execute(
                    "SELECT student_id, first_name, last_name, email_address "
                    "FROM students WHERE course = ? AND COALESCE(is_active, 1) = 1",
                    (str(course_id),)).fetchall()

            seen = set()
            for r in rows:
                email = (r["email_address"] or "").strip()
                if not email or email.lower() in seen:
                    continue
                seen.add(email.lower())
                name = " ".join(p for p in (r["first_name"], r["last_name"]) if p)
                out["students"].append({"name": name or str(r["student_id"]),
                                        "email": email})

        if not out["students"] and not out["lecturer"]:
            out["reason"] = ("no recipients — the class has no module or course "
                             "set, or nobody on it has an email address")
        return out
    except sqlite3.Error as e:
        log_event('error', f"Database error building online class audience: {e}")
        out["reason"] = str(e)
        return out


def describe_online_class_changes(before, after):
    """A 'what changed' block for the update email.

    Only fields a recipient can act on are compared — a changed link or
    access code is what actually stops someone joining.
    """
    labels = [
        ("session_name", "Class name"), ("module_code", "Module"),
        ("platform", "Platform"), ("meeting_link", "Join link"),
        ("meeting_id", "Meeting ID"), ("passcode", "Access code"),
        ("instructor_id", "Lecturer"), ("is_active", "Status"),
    ]
    lines = []
    for key, label in labels:
        if key not in after or before.get(key) == after.get(key):
            continue
        old, new = before.get(key), after.get(key)
        if key == "passcode":
            lines.append("  • Access code has changed — use the new one below.")
        elif key == "is_active":
            lines.append("  • Status: " + ("now active" if new else "no longer active"))
        else:
            lines.append(f"  • {label}: "
                         f"{'(not set)' if old in (None, '') else old} → "
                         f"{'(not set)' if new in (None, '') else new}")
    return "\n".join(lines) if lines else "  • Minor details were updated."


def send_online_class_notification(classroom_id, event, extra=None,
                                   include_lecturer=True):
    """Email everyone on an online class about *event*.

    *event* is ``created`` / ``updated`` / ``cancelled`` / ``scheduled``.
    Sending is best-effort per recipient — one bad address must not stop
    the rest of a cohort being told — so the return value counts both:
    ``{sent, failed, recipients, reason}``.
    """
    from education_system.systems.university.infrastructure.email.email_service.core import (
        send_template_email,
    )
    from education_system.systems.university.infrastructure.database.db import get_connection

    result = {"sent": 0, "failed": 0, "recipients": 0, "reason": None}
    template = _ONLINE_CLASS_TEMPLATES.get(event)
    if template is None:
        result["reason"] = f"unknown event {event!r}"
        return result

    audience = get_online_class_audience(classroom_id)
    if audience.get("reason"):
        result["reason"] = audience["reason"]
        return result

    try:
        with get_connection() as conn:
            classroom = conn.execute(
                "SELECT * FROM virtual_classrooms WHERE classroom_id = ?",
                (classroom_id,)).fetchone()
    except sqlite3.Error as e:
        result["reason"] = str(e)
        return result
    keys = classroom.keys() if classroom is not None else []

    def col(name, default=""):
        return (classroom[name] if name in keys and classroom[name] is not None
                else default)

    base = {
        "class_name": col("session_name", f"Class {classroom_id}"),
        "module_code": audience.get("module_code") or col("course_id", "—"),
        "module_name": audience.get("module_name") or col("session_name", ""),
        "platform": str(col("platform", "")).title(),
        "join_url": col("meeting_link", "(to be confirmed)"),
        "meeting_id": col("meeting_id", "—"),
        "passcode": col("passcode", "(none)"),
        "host_name": (audience.get("lecturer") or {}).get("name", "Your lecturer"),
        "sender_name": "Online Sessions",
        "session_date": "(to be confirmed)", "start_time": "—", "end_time": "—",
        "duration_minutes": "—", "session_type": "—", "session_notes": "",
        "changes": "", "cancellation_reason": "",
    }
    base.update(extra or {})

    people = list(audience["students"])
    if include_lecturer and audience["lecturer"]:
        people.append(audience["lecturer"])
    result["recipients"] = len(people)

    for person in people:
        template_vars = dict(base, participant_name=person["name"])
        try:
            ok = send_template_email(
                f"{_ONLINE_CLASS_TEMPLATE_DIR}/{template}",
                person["email"], template_vars)
        except Exception:
            logger.debug("online class email failed for %s", person["email"],
                         exc_info=True)
            ok = False
        result["sent" if ok else "failed"] += 1

    log_event('info', f"Online class {classroom_id} {event}: "
                      f"{result['sent']}/{result['recipients']} emails sent")
    return result
