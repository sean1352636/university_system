"""Extracted GradeManager behaviour."""
from . import *
from .scale import GRADE_SYSTEMS, letter_to_gpa, letter_to_percentage, percentage_to_letter

class GradeNotificationMixin:
    def _email_grade_notification(self, student_id, assessment_name, action, score=None,
                                   letter_grade=None, percentage=None, feedback=None):
        """Email a student about a grade change (added/updated/removed)."""
        try:
            from education_system.systems.university.infrastructure.email.email_service import send_email

            cursor = self.get_safe_cursor()
            cursor.execute(
                "SELECT first_name, last_name, email_address FROM students WHERE student_id = ?",
                (student_id,)
            )
            row = cursor.fetchone()
            if not row or not row[2]:
                return

            name = f"{row[0]} {row[1]}"
            email = row[2]

            if action == 'added':
                subject = f"Grade Released: {assessment_name}"
                body = (
                    f"Dear {name},\n\n"
                    f"A grade has been released for the following assessment:\n\n"
                    f"Assessment: {assessment_name}\n"
                    f"Score: {score} ({percentage:.1f}%)\n"
                    f"Letter Grade: {letter_grade}\n"
                )
                if feedback:
                    body += f"\nFeedback:\n{feedback}\n"
                body += "\nPlease log in to view your full results.\n\nBest regards,\nAcademic Administration"

            elif action == 'updated':
                subject = f"Grade Updated: {assessment_name}"
                body = (
                    f"Dear {name},\n\n"
                    f"Your grade has been updated for the following assessment:\n\n"
                    f"Assessment: {assessment_name}\n"
                    f"New Score: {score} ({percentage:.1f}%)\n"
                    f"Letter Grade: {letter_grade}\n"
                )
                if feedback:
                    body += f"\nFeedback:\n{feedback}\n"
                body += "\nPlease log in to view your updated results.\n\nBest regards,\nAcademic Administration"

            elif action == 'deleted':
                subject = f"Grade Removed: {assessment_name}"
                body = (
                    f"Dear {name},\n\n"
                    f"Your grade for the following assessment has been removed:\n\n"
                    f"Assessment: {assessment_name}\n\n"
                    f"If you believe this is an error, please contact your instructor.\n\n"
                    f"Best regards,\nAcademic Administration"
                )
            else:
                return

            send_email(recipient_email=email, subject=subject, body=body)

        except Exception as e:
            print(f"Grade notification email failed: {e}")
