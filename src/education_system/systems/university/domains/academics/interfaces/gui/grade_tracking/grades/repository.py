"""Extracted GradeManager behaviour."""

from education_system.systems.university.infrastructure.i18n import get_text as _t
from . import *
from .scale import GRADE_SYSTEMS, letter_to_gpa, letter_to_percentage, percentage_to_letter

class GradeRepositoryMixin:
    def delete_grade(self):
        """Delete selected grade (supports both grades and assignment_submissions)"""
        selection = self.grades_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.academics.grade_tracking.grades.repository.dialogs.no_selection', default="No Selection"), _t('gui.academics.grade_tracking.grades.repository.dialogs.please_select_a_grade_to_delete', default="Please select a grade to delete"))
            return

        item = self.grades_tree.item(selection[0])
        raw_id = str(item['values'][0])
        student_name = item['values'][1]
        assessment_name = item['values'][2]
        is_submission = raw_id.startswith('S')

        if is_submission:
            cursor = self.get_safe_cursor()
            cursor.execute("SELECT assignment_id FROM assignment_submissions WHERE id=?", (int(raw_id[1:]),))
            resolved = cursor.fetchone()
            if not resolved or not self.require_grade_mutation('delete', assignment_id=resolved[0]):
                return
        elif not self.require_grade_mutation('delete', grade_id=raw_id):
            return

        if not messagebox.askyesno(_t('gui.academics.grade_tracking.grades.repository.dialogs.confirm_deletion', default="Confirm Deletion"),
                                   f"Are you sure you want to delete the grade for:\n\n"
                                   f"Student: {student_name}\n"
                                   f"Assessment: {assessment_name}\n\n"
                                   f"This action cannot be undone."):
            return

        try:
            cursor = self.get_safe_cursor()
            student_id_for_email = None

            if is_submission:
                real_id = int(raw_id[1:])
                cursor.execute("SELECT student_id FROM assignment_submissions WHERE id = ?", (real_id,))
                row = cursor.fetchone()
                student_id_for_email = row[0] if row else None
                # Clear the grade but keep the submission record
                cursor.execute("""
                    UPDATE assignment_submissions
                    SET grade = NULL, feedback = NULL, graded_date = NULL,
                        graded_by = NULL, status = 'submitted'
                    WHERE id = ?
                """, (real_id,))
            else:
                cursor.execute("SELECT student_id FROM grades WHERE grade_id = ?", (raw_id,))
                row = cursor.fetchone()
                student_id_for_email = row[0] if row else None
                cursor.execute("DELETE FROM grades WHERE grade_id = ?", (raw_id,))

            # Immutable audit log for grade deletion (FERPA compliance)
            if IMMUTABLE_AUDIT_AVAILABLE:
                user_id, session_id = get_gui_context()
                require_grade_audit(
                    action=AuditAction.RECORD_DELETE,
                    user_id=user_id,
                    resource_type='grade',
                    resource_id=raw_id,
                    session_id=session_id,
                    details={
                        'student_id': student_id_for_email,
                        'student_name': student_name,
                        'assessment_name': assessment_name
                    }
                )
            else:
                raise RuntimeError("Grade audit service unavailable")
            self.safe_commit()

            messagebox.showinfo(_t('gui.academics.grade_tracking.grades.repository.dialogs.success', default="Success"), _t('gui.academics.grade_tracking.grades.repository.dialogs.grade_deleted_successfully', default="Grade deleted successfully!"))
            self.refresh_grades()

            # Email student about removed grade
            if student_id_for_email:
                self._email_grade_notification(student_id_for_email, assessment_name, 'deleted')

        except sqlite3.Error as e:
            logger.exception("Grade deletion failed")
            messagebox.showerror(_t('gui.academics.grade_tracking.grades.repository.dialogs.database_error', default="Database Error"), "The grade could not be deleted.")
        except RuntimeError:
            self.conn.rollback()
            messagebox.showerror("Security error", "The grade was not deleted because its audit record could not be written.")
