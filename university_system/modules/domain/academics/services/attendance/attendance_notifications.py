"""
Attendance Notification System

Monitors student attendance rates and sends automated notifications to students
and parents when attendance falls below acceptable thresholds.

Author: University System
Date: 2025-11-12
"""

import datetime
from typing import List, Dict, Tuple, Optional
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.infrastructure.email.email_service import send_email
from university_system.infrastructure.email.template_utils import load_template, render_template
from university_system.modules.shared.utils.activity_logger import log_activity


class AttendanceNotificationService:
    """Service for managing attendance notifications to students and parents"""

    def __init__(self, attendance_threshold: float = 90.0):
        """
        Initialize the notification service.

        Args:
            attendance_threshold: Minimum acceptable attendance percentage (default: 90%)
        """
        self.attendance_threshold = attendance_threshold

    def check_and_notify_low_attendance(self, module_code: Optional[str] = None,
                                       send_to_students: bool = True,
                                       send_to_parents: bool = True) -> Dict[str, int]:
        """
        Check all students' attendance and send notifications for those below threshold.

        Args:
            module_code: Optional specific module to check. If None, checks all modules.
            send_to_students: Whether to send notifications to students
            send_to_parents: Whether to send notifications to parents

        Returns:
            Dictionary with counts: {
                'students_checked': int,
                'students_notified': int,
                'parents_notified': int,
                'emails_sent': int,
                'errors': int
            }
        """
        results = {
            'students_checked': 0,
            'students_notified': 0,
            'parents_notified': 0,
            'emails_sent': 0,
            'errors': 0
        }

        try:
            # Get students with low attendance
            low_attendance_students = self.get_low_attendance_students(module_code)
            results['students_checked'] = len(low_attendance_students)

            for student_data in low_attendance_students:
                student_id = student_data['student_id']
                module = student_data['module_code']
                attendance_rate = student_data['attendance_percentage']

                # Send to student
                if send_to_students:
                    if self.notify_student_low_attendance(student_data):
                        results['students_notified'] += 1
                        results['emails_sent'] += 1
                    else:
                        results['errors'] += 1

                # Send to parents
                if send_to_parents:
                    parent_count = self.notify_parents_low_attendance(student_data)
                    results['parents_notified'] += parent_count
                    results['emails_sent'] += parent_count

                # Log activity
                log_activity('notification', 'low_attendance_alert',
                           student_id=student_id,
                           details={
                               'module': module,
                               'attendance_rate': attendance_rate,
                               'threshold': self.attendance_threshold,
                               'student_notified': send_to_students,
                               'parents_notified': send_to_parents
                           })

            return results

        except Exception as e:
            print(f"Error in check_and_notify_low_attendance: {e}")
            import traceback
            traceback.print_exc()
            results['errors'] += 1
            return results

    def get_low_attendance_students(self, module_code: Optional[str] = None) -> List[Dict]:
        """
        Query database for students with attendance below threshold.

        Args:
            module_code: Optional specific module to check

        Returns:
            List of dictionaries with student attendance data
        """
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Build query
                if module_code:
                    query = '''
                    SELECT
                        s.student_id,
                        s.first_name,
                        s.last_name,
                        s.email,
                        sm.module_code,
                        m.module_name,
                        COUNT(DISTINCT ar.date) as sessions_attended,
                        COUNT(DISTINCT
                            CASE WHEN ar.status IN ('Present', 'Late', 'present', 'late')
                            THEN ar.date END
                        ) as sessions_present,
                        ROUND(
                            CAST(COUNT(DISTINCT
                                CASE WHEN ar.status IN ('Present', 'Late', 'present', 'late')
                                THEN ar.date END
                            ) AS REAL) * 100.0 /
                            NULLIF(COUNT(DISTINCT ar.date), 0),
                            2
                        ) as attendance_percentage
                    FROM students s
                    JOIN student_modules sm ON s.student_id = sm.student_id
                    JOIN modules m ON sm.module_code = m.module_code
                    LEFT JOIN attendance_records ar ON s.student_id = ar.student_id
                        AND ar.module_code = sm.module_code
                    WHERE sm.module_code = ?
                    GROUP BY s.student_id, sm.module_code
                    HAVING attendance_percentage < ? OR attendance_percentage IS NULL
                    '''
                    params = (module_code, self.attendance_threshold)
                else:
                    query = '''
                    SELECT
                        s.student_id,
                        s.first_name,
                        s.last_name,
                        s.email,
                        sm.module_code,
                        m.module_name,
                        COUNT(DISTINCT ar.date) as sessions_attended,
                        COUNT(DISTINCT
                            CASE WHEN ar.status IN ('Present', 'Late', 'present', 'late')
                            THEN ar.date END
                        ) as sessions_present,
                        ROUND(
                            CAST(COUNT(DISTINCT
                                CASE WHEN ar.status IN ('Present', 'Late', 'present', 'late')
                                THEN ar.date END
                            ) AS REAL) * 100.0 /
                            NULLIF(COUNT(DISTINCT ar.date), 0),
                            2
                        ) as attendance_percentage
                    FROM students s
                    JOIN student_modules sm ON s.student_id = sm.student_id
                    JOIN modules m ON sm.module_code = m.module_code
                    LEFT JOIN attendance_records ar ON s.student_id = ar.student_id
                        AND ar.module_code = sm.module_code
                    GROUP BY s.student_id, sm.module_code
                    HAVING attendance_percentage < ? OR attendance_percentage IS NULL
                    '''
                    params = (self.attendance_threshold,)

                cursor.execute(query, params)
                results = cursor.fetchall()

                # Convert to list of dictionaries
                students = []
                for row in results:
                    students.append({
                        'student_id': row[0],
                        'first_name': row[1],
                        'last_name': row[2],
                        'email': row[3],
                        'module_code': row[4],
                        'module_name': row[5],
                        'total_sessions': row[6] if row[6] else 0,
                        'attended_sessions': row[7] if row[7] else 0,
                        'attendance_percentage': row[8] if row[8] else 0.0
                    })

                return students

        except Exception as e:
            print(f"Error getting low attendance students: {e}")
            import traceback
            traceback.print_exc()
            return []

    def notify_student_low_attendance(self, student_data: Dict) -> bool:
        """
        Send low attendance notification to student.

        Args:
            student_data: Dictionary containing student and attendance information

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Load template
            template = load_template('academics/low_attendance_alert')
            if not template:
                print("Error: low_attendance_alert template not found")
                return False

            # Prepare template variables
            attendance_summary = self._build_attendance_summary(student_data)

            template_vars = {
                'student_name': f"{student_data['first_name']} {student_data['last_name']}",
                'student_id': student_data['student_id'],
                'module_name': student_data['module_name'],
                'module_code': student_data['module_code'],
                'attendance_percentage': f"{student_data['attendance_percentage']:.1f}",
                'total_sessions': student_data['total_sessions'],
                'attended_sessions': student_data['attended_sessions'],
                'attendance_summary': attendance_summary,
                'signature': 'Academic Affairs Office\nUniversity Management System'
            }

            # Render template
            subject, body = render_template('low_attendance_alert', template_vars)

            if not subject or not body:
                print("Error rendering template")
                return False

            # Send email
            success = send_email(
                recipient_email=student_data['email'],
                subject=subject,
                body=body
            )

            if success:
                # Log notification in database
                self._log_notification(
                    student_id=student_data['student_id'],
                    notification_type='low_attendance_student',
                    module_code=student_data['module_code'],
                    recipient_email=student_data['email']
                )

            return success

        except Exception as e:
            print(f"Error sending student notification: {e}")
            import traceback
            traceback.print_exc()
            return False

    def notify_parents_low_attendance(self, student_data: Dict) -> int:
        """
        Send low attendance notification to all registered parents of the student.

        Args:
            student_data: Dictionary containing student and attendance information

        Returns:
            Number of parents successfully notified
        """
        try:
            # Get parents for this student
            parents = self._get_student_parents(student_data['student_id'])

            if not parents:
                return 0

            # Load template
            template = load_template('academics/parent_low_attendance_alert')
            if not template:
                print("Error: parent_low_attendance_alert template not found")
                return 0

            notifications_sent = 0

            for parent in parents:
                try:
                    # Prepare template variables
                    attendance_summary = self._build_attendance_summary(student_data)

                    # Get instructor email from module data
                    instructor_email = self._get_module_instructor_email(student_data['module_code'])

                    template_vars = {
                        'parent_name': f"{parent['first_name']} {parent['last_name']}",
                        'student_name': f"{student_data['first_name']} {student_data['last_name']}",
                        'student_id': student_data['student_id'],
                        'module_name': student_data['module_name'],
                        'module_code': student_data['module_code'],
                        'attendance_percentage': f"{student_data['attendance_percentage']:.1f}",
                        'total_sessions': student_data['total_sessions'],
                        'attended_sessions': student_data['attended_sessions'],
                        'absent_sessions': student_data['total_sessions'] - student_data['attended_sessions'],
                        'attendance_summary': attendance_summary,
                        'instructor_email': instructor_email,
                        'signature': 'Academic Affairs Office\nUniversity Management System'
                    }

                    # Render template
                    subject, body = render_template('parent_low_attendance_alert', template_vars)

                    if not subject or not body:
                        continue

                    # Send email
                    success = send_email(
                        recipient_email=parent['email'],
                        subject=subject,
                        body=body
                    )

                    if success:
                        notifications_sent += 1

                        # Log parent notification
                        self._log_parent_notification(
                            parent_id=parent['parent_id'],
                            student_id=student_data['student_id'],
                            notification_type='low_attendance_alert',
                            module_code=student_data['module_code']
                        )

                except Exception as e:
                    print(f"Error sending notification to parent {parent.get('parent_id', 'unknown')}: {e}")
                    continue

            return notifications_sent

        except Exception as e:
            print(f"Error in notify_parents_low_attendance: {e}")
            import traceback
            traceback.print_exc()
            return 0

    def _get_student_parents(self, student_id: str) -> List[Dict]:
        """Get all registered parents for a student"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT DISTINCT
                        pa.parent_id,
                        pa.first_name,
                        pa.last_name,
                        pa.email,
                        pa.phone
                    FROM parent_accounts pa
                    JOIN parent_student_relationships psr ON pa.parent_id = psr.parent_id
                    WHERE psr.student_id = ? AND pa.email IS NOT NULL AND pa.email != ''
                ''', (student_id,))

                results = cursor.fetchall()

                parents = []
                for row in results:
                    parents.append({
                        'parent_id': row[0],
                        'first_name': row[1],
                        'last_name': row[2],
                        'email': row[3],
                        'phone': row[4]
                    })

                return parents

        except Exception as e:
            print(f"Error getting student parents: {e}")
            return []

    def _build_attendance_summary(self, student_data: Dict) -> str:
        """Build a formatted attendance summary for email"""
        absent = student_data['total_sessions'] - student_data['attended_sessions']

        summary = f"""
Total Sessions: {student_data['total_sessions']}
Sessions Attended: {student_data['attended_sessions']}
Sessions Absent: {absent}
Current Attendance Rate: {student_data['attendance_percentage']:.1f}%
Required Minimum: {self.attendance_threshold}%
Shortfall: {self.attendance_threshold - student_data['attendance_percentage']:.1f}%
"""
        return summary.strip()

    def _log_notification(self, student_id: str, notification_type: str,
                         module_code: str, recipient_email: str):
        """Log notification in database"""
        try:
            with transaction() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO attendance_notifications
                    (student_id, notification_type, module_code, recipient_email, sent_at, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (student_id, notification_type, module_code, recipient_email,
                      datetime.datetime.now().isoformat(), 'sent'))

        except Exception as e:
            print(f"Error logging notification: {e}")

    def _log_parent_notification(self, parent_id: str, student_id: str,
                                 notification_type: str, module_code: str):
        """Log parent notification in database"""
        try:
            with transaction() as conn:
                cursor = conn.cursor()

                # Check if parent_notifications table exists
                cursor.execute('''
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='parent_notifications'
                ''')

                if cursor.fetchone():
                    cursor.execute('''
                        INSERT INTO parent_notifications
                        (parent_id, student_id, notification_type, message, sent_at)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (parent_id, student_id, notification_type,
                          f"Low attendance alert for module {module_code}",
                          datetime.datetime.now().isoformat()))

        except Exception as e:
            print(f"Error logging parent notification: {e}")

    def _get_module_instructor_email(self, module_code: str) -> str:
        """
        Get the instructor email for a given module.

        Checks multiple tables in order of preference:
        1. module_schedule (linked to instructors table)
        2. lms_courses (instructor_id field)
        3. courses table (instructor_id field)

        Args:
            module_code: The module code to look up

        Returns:
            str: Instructor email if found, otherwise fallback to default
        """
        default_email = 'academic-affairs@university.edu'

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Try 1: Get instructor from module_schedule -> instructors table
                cursor.execute('''
                    SELECT DISTINCT i.email
                    FROM module_schedule ms
                    JOIN instructors i ON ms.instructor_id = i.id
                    WHERE ms.module_code = ? AND i.email IS NOT NULL AND i.email != ''
                    LIMIT 1
                ''', (module_code,))
                result = cursor.fetchone()
                if result and result[0]:
                    return result[0]

                # Try 2: Get instructor from lms_courses -> instructors table
                cursor.execute('''
                    SELECT DISTINCT i.email
                    FROM lms_courses lc
                    JOIN instructors i ON lc.instructor_id = i.id OR lc.instructor_id = CAST(i.id AS TEXT)
                    WHERE lc.module_code = ? AND i.email IS NOT NULL AND i.email != ''
                    LIMIT 1
                ''', (module_code,))
                result = cursor.fetchone()
                if result and result[0]:
                    return result[0]

                # Try 3: Get instructor directly from courses table if instructor_id looks like an email
                cursor.execute('''
                    SELECT instructor_id
                    FROM courses
                    WHERE code = ? OR course_code = ?
                    LIMIT 1
                ''', (module_code, module_code))
                result = cursor.fetchone()
                if result and result[0] and '@' in str(result[0]):
                    return result[0]

                # Try 4: If instructor_id is a numeric ID, look up in instructors table
                if result and result[0]:
                    cursor.execute('''
                        SELECT email
                        FROM instructors
                        WHERE id = ? OR id = CAST(? AS INTEGER)
                        LIMIT 1
                    ''', (result[0], result[0]))
                    instructor_result = cursor.fetchone()
                    if instructor_result and instructor_result[0]:
                        return instructor_result[0]

                # Try 5: Get any instructor associated with this module via course_instructor_assignments
                cursor.execute('''
                    SELECT i.email
                    FROM instructors i
                    JOIN course_instructor_assignments cia ON i.id = cia.instructor_id
                    JOIN courses c ON cia.course_id = c.id
                    WHERE c.code = ? OR c.course_code = ?
                    LIMIT 1
                ''', (module_code, module_code))
                result = cursor.fetchone()
                if result and result[0]:
                    return result[0]

        except Exception as e:
            print(f"Error getting instructor email for module {module_code}: {e}")

        return default_email

    def get_notification_history(self, student_id: Optional[str] = None,
                                days: int = 30) -> List[Dict]:
        """
        Get notification history.

        Args:
            student_id: Optional student ID to filter by
            days: Number of days to look back (default: 30)

        Returns:
            List of notification records
        """
        try:
            cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()

            with get_connection() as conn:
                cursor = conn.cursor()

                # Check if table exists
                cursor.execute('''
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='attendance_notifications'
                ''')

                if not cursor.fetchone():
                    # Create table if it doesn't exist
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS attendance_notifications (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT,
                            notification_type TEXT,
                            module_code TEXT,
                            recipient_email TEXT,
                            sent_at TEXT,
                            status TEXT DEFAULT 'sent'
                        )
                    ''')
                    conn.commit()
                    return []

                if student_id:
                    cursor.execute('''
                        SELECT id, student_id, notification_type, module_code,
                               recipient_email, sent_at, status
                        FROM attendance_notifications
                        WHERE student_id = ? AND sent_at >= ?
                        ORDER BY sent_at DESC
                    ''', (student_id, cutoff_date))
                else:
                    cursor.execute('''
                        SELECT id, student_id, notification_type, module_code,
                               recipient_email, sent_at, status
                        FROM attendance_notifications
                        WHERE sent_at >= ?
                        ORDER BY sent_at DESC
                    ''', (cutoff_date,))

                results = cursor.fetchall()

                notifications = []
                for row in results:
                    notifications.append({
                        'id': row[0],
                        'student_id': row[1],
                        'notification_type': row[2],
                        'module_code': row[3],
                        'recipient_email': row[4],
                        'sent_at': row[5],
                        'status': row[6]
                    })

                return notifications

        except Exception as e:
            print(f"Error getting notification history: {e}")
            return []


# Convenience function for easy import
def check_and_notify_low_attendance(module_code: Optional[str] = None,
                                    threshold: float = 90.0,
                                    send_to_students: bool = True,
                                    send_to_parents: bool = True) -> Dict[str, int]:
    """
    Convenience function to check and notify low attendance.

    Args:
        module_code: Optional specific module to check
        threshold: Minimum acceptable attendance percentage (default: 90%)
        send_to_students: Whether to send notifications to students
        send_to_parents: Whether to send notifications to parents

    Returns:
        Dictionary with notification results
    """
    service = AttendanceNotificationService(attendance_threshold=threshold)
    return service.check_and_notify_low_attendance(
        module_code=module_code,
        send_to_students=send_to_students,
        send_to_parents=send_to_parents
    )
