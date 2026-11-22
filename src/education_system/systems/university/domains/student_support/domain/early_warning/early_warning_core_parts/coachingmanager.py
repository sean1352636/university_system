"""Extracted class implementation."""

from .. import early_warning_core_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class CoachingManager:
    """Manages success coaches and student assignments"""

    @staticmethod
    def register_coach(
        user_id: str,
        name: str,
        specialization: str = "",
        max_students: int = 30
    ) -> int:
        """Register a success coach"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO early_warning_coaches (
                    user_id, name, specialization, max_students
                )
                VALUES (?, ?, ?, ?)
            ''', (user_id, name, specialization, max_students))

            coach_id = cursor.lastrowid
            conn.commit()

            return coach_id

        except Exception as e:
            conn.rollback()
            raise Exception(f"Error registering coach: {e}")
        finally:
            conn.close()

    @staticmethod
    def assign_student_to_coach(
        student_id: str,
        coach_id: int,
        reason: str,
        meeting_frequency: str = "weekly"
    ) -> int:
        """Assign a student to a success coach"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Check coach capacity
            cursor.execute('''
                SELECT COUNT(*) as current_students, c.max_students
                FROM early_warning_coaching_assignments ca
                JOIN early_warning_coaches c ON ca.coach_id = c.coach_id
                WHERE ca.coach_id = ? AND ca.status = 'active'
                GROUP BY c.coach_id, c.max_students
            ''', (coach_id,))

            capacity = cursor.fetchone()
            if capacity and capacity['current_students'] >= capacity['max_students']:
                raise Exception("Coach has reached maximum student capacity")

            cursor.execute('''
                INSERT INTO early_warning_coaching_assignments (
                    student_id, coach_id, reason, meeting_frequency
                )
                VALUES (?, ?, ?, ?)
            ''', (student_id, coach_id, reason, meeting_frequency))

            assignment_id = cursor.lastrowid
            conn.commit()

            # Send notification
            CoachingManager._notify_assignment(assignment_id)

            return assignment_id

        except Exception as e:
            conn.rollback()
            raise Exception(f"Error assigning student to coach: {e}")
        finally:
            conn.close()

    @staticmethod
    def _notify_assignment(assignment_id: int) -> None:
        """Notify student and coach of assignment"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT ca.*, s.first_name, s.last_name, s.email_address, c.name as coach_name
                FROM early_warning_coaching_assignments ca
                JOIN students s ON ca.student_id = s.student_id
                JOIN early_warning_coaches c ON ca.coach_id = c.coach_id
                WHERE ca.assignment_id = ?
            ''', (assignment_id,))

            assignment = cursor.fetchone()
            if not assignment:
                return

            # Notify student using template
            subject, body = render_template('success_coach_assigned', {
                'first_name': assignment['first_name'],
                'coach_name': assignment['coach_name'],
                'meeting_frequency': assignment['meeting_frequency']
            })

            send_email(assignment['email_address'], subject, body)

        finally:
            conn.close()

    @staticmethod
    def record_progress(
        student_id: str,
        coach_id: int,
        academic_progress: str,
        attendance_progress: str,
        engagement_progress: str,
        goals_achieved: str,
        concerns: str,
        next_steps: str
    ) -> int:
        """Record progress monitoring"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO early_warning_progress_monitoring (
                    student_id, coach_id, academic_progress, attendance_progress,
                    engagement_progress, goals_achieved, concerns, next_steps
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, coach_id, academic_progress, attendance_progress,
                  engagement_progress, goals_achieved, concerns, next_steps))

            monitoring_id = cursor.lastrowid

            # Update assignment with last meeting date
            cursor.execute('''
                UPDATE early_warning_coaching_assignments
                SET last_meeting_date = ?
                WHERE student_id = ? AND coach_id = ? AND status = 'active'
            ''', (date.today().isoformat(), student_id, coach_id))

            conn.commit()

            return monitoring_id

        except Exception as e:
            conn.rollback()
            raise Exception(f"Error recording progress: {e}")
        finally:
            conn.close()
