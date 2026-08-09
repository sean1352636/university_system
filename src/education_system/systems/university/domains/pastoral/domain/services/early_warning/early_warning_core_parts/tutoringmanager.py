"""Extracted class implementation."""

from .. import early_warning_core_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class TutoringManager:
    """Manages tutoring recommendations"""

    @staticmethod
    def create_tutoring_recommendation(
        student_id: str,
        module_code: str,
        recommended_by: str,
        recommendation_type: str,
        priority: str = "medium"
    ) -> int:
        """Create a tutoring recommendation"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO early_warning_tutoring_recommendations (
                    student_id, module_code, recommended_by, recommendation_type, priority
                )
                VALUES (?, ?, ?, ?, ?)
            ''', (student_id, module_code, recommended_by, recommendation_type, priority))

            recommendation_id = cursor.lastrowid
            conn.commit()

            # Notify student
            TutoringManager._notify_recommendation(recommendation_id)

            return recommendation_id

        except Exception as e:
            conn.rollback()
            raise Exception(f"Error creating tutoring recommendation: {e}")
        finally:
            conn.close()

    @staticmethod
    def _notify_recommendation(recommendation_id: int) -> None:
        """Notify student of tutoring recommendation"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT tr.*, s.first_name, s.email_address
                FROM early_warning_tutoring_recommendations tr
                JOIN students s ON tr.student_id = s.student_id
                WHERE tr.recommendation_id = ?
            ''', (recommendation_id,))

            rec = cursor.fetchone()
            if not rec:
                return

            subject, body = render_template('tutoring_recommended', {
                'first_name': rec['first_name'],
                'module_code': rec['module_code'],
                'recommendation_type': rec['recommendation_type'],
                'priority': rec['priority']
            })

            send_email(rec['email_address'], subject, body)

        finally:
            conn.close()

    @staticmethod
    def assign_tutor(recommendation_id: int, tutor_assigned: str) -> bool:
        """Assign a tutor to a recommendation"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE early_warning_tutoring_recommendations
                SET tutor_assigned = ?, status = 'assigned'
                WHERE recommendation_id = ?
            ''', (tutor_assigned, recommendation_id))

            conn.commit()
            return True

        finally:
            conn.close()
