"""Extracted GradeManager behaviour."""

from education_system.systems.university.infrastructure.i18n import get_text as _t
from .. import *
from ..scale import GRADE_SYSTEMS, letter_to_gpa, letter_to_percentage, percentage_to_letter
from .grade_view import safe_combo_update, safe_grab_set

class EditGradeDialogMixin:
    def edit_grade_dialog(self):
        """Open dialog to edit selected grade (supports both grades and assignment_submissions)"""
        selection = self.grades_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.academics.grade_tracking.grades.ui.edit_dialog.dialogs.no_selection', default="No Selection"), _t('gui.academics.grade_tracking.grades.ui.edit_dialog.dialogs.please_select_a_grade_to_edit', default="Please select a grade to edit"))
            return

        item = self.grades_tree.item(selection[0])
        grade_id = str(item['values'][0])
        is_submission = grade_id.startswith('S')

        scope = ({'assignment_id': int(grade_id[1:])} if is_submission
                 else {'grade_id': grade_id})
        if is_submission:
            # The S-prefixed value is a submission id; resolve its assignment.
            cursor = self.get_safe_cursor()
            cursor.execute("SELECT assignment_id FROM assignment_submissions WHERE id=?", (int(grade_id[1:]),))
            resolved = cursor.fetchone()
            if not resolved or not self.require_grade_mutation('update', assignment_id=resolved[0]):
                return
        elif not self.require_grade_mutation('update', **scope):
            return

        # Fetch grade details from the correct source
        try:
            cursor = self.get_safe_cursor()

            if is_submission:
                real_id = int(grade_id[1:])
                cursor.execute("""
                    SELECT sub.id, sub.student_id, a.id, sub.grade,
                           sub.graded_date, sub.feedback,
                           s.first_name, s.last_name, a.title,
                           COALESCE(a.max_marks, 100), a.module_code
                    FROM assignment_submissions sub
                    JOIN students s ON sub.student_id = s.student_id
                    JOIN assignments a ON sub.assignment_id = a.id
                    WHERE sub.id = ?
                """, (real_id,))
            else:
                cursor.execute("""
                    SELECT g.grade_id, g.student_id, g.assessment_id, g.score,
                           g.submission_date, g.comments,
                           s.first_name, s.last_name, a.assessment_name,
                           a.max_points, m.module_name
                    FROM grades g
                    JOIN students s ON g.student_id = s.student_id
                    JOIN assessments a ON g.assessment_id = a.assessment_id
                    JOIN modules m ON a.module_code = m.module_code
                    WHERE g.grade_id = ?
                """, (grade_id,))

            grade_data = cursor.fetchone()

            if not grade_data:
                messagebox.showerror(_t('gui.academics.grade_tracking.grades.ui.edit_dialog.dialogs.error', default="Error"), _t('gui.academics.grade_tracking.grades.ui.edit_dialog.dialogs.grade_not_found', default="Grade not found"))
                return

        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.academics.grade_tracking.grades.ui.edit_dialog.dialogs.database_error', default="Database Error"), f"Error loading grade: {e}")
            return

        # For submissions, grade_data[3] is a percentage; for grades, it's a raw score
        if is_submission:
            current_score = grade_data[3] if grade_data[3] is not None else 0
            max_points = grade_data[9]
            # Convert percentage back to score for display
            display_score = round((current_score * max_points) / 100, 2) if current_score else 0
        else:
            display_score = grade_data[3]
            max_points = grade_data[9]

        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.academics.grade_tracking.grades.ui.edit_dialog.windows.edit_grade', default="Edit Grade"))
        dialog.geometry("500x550")
        dialog.transient(self.root)
        safe_grab_set(dialog)

        ttk.Label(dialog, text=_t('gui.academics.grade_tracking.grades.ui.edit_dialog.labels.student', default="Student:")).grid(row=0, column=0, padx=10, pady=10, sticky='w')
        ttk.Label(dialog, text=f"{grade_data[1]} - {grade_data[6]} {grade_data[7]}").grid(
            row=0, column=1, padx=10, pady=10, sticky='w')

        ttk.Label(dialog, text=_t('gui.academics.grade_tracking.grades.ui.edit_dialog.labels.assessment', default="Assessment:")).grid(row=1, column=0, padx=10, pady=10, sticky='w')
        ttk.Label(dialog, text=f"{grade_data[8]} ({grade_data[10]})").grid(
            row=1, column=1, padx=10, pady=10, sticky='w')

        ttk.Label(dialog, text=_t('gui.academics.grade_tracking.grades.ui.edit_dialog.labels.max_points', default="Max Points:")).grid(row=2, column=0, padx=10, pady=10, sticky='w')
        ttk.Label(dialog, text=str(max_points)).grid(row=2, column=1, padx=10, pady=10, sticky='w')

        ttk.Label(dialog, text=_t('gui.academics.grade_tracking.grades.ui.edit_dialog.labels.score', default="Score:")).grid(row=3, column=0, padx=10, pady=10, sticky='w')
        score_var = tk.StringVar(value=str(display_score))
        ttk.Entry(dialog, textvariable=score_var, width=37).grid(row=3, column=1, padx=10, pady=10)

        ttk.Label(dialog, text=_t('gui.academics.grade_tracking.grades.ui.edit_dialog.labels.date', default="Date:")).grid(row=4, column=0, padx=10, pady=10, sticky='w')
        date_var = tk.StringVar(value=grade_data[4] if grade_data[4] else datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(dialog, textvariable=date_var, width=37).grid(row=4, column=1, padx=10, pady=10)

        ttk.Label(dialog, text=_t('gui.academics.grade_tracking.grades.ui.edit_dialog.labels.comments', default="Comments:")).grid(row=5, column=0, padx=10, pady=10, sticky='nw')
        comments_text = tk.Text(dialog, width=35, height=8)
        comments_text.grid(row=5, column=1, padx=10, pady=10)
        if grade_data[5]:
            comments_text.insert('1.0', grade_data[5])

        def update_grade():
            score = score_var.get()
            date = date_var.get()
            comments = comments_text.get('1.0', 'end-1c')

            if not score:
                messagebox.showerror(_t('gui.academics.grade_tracking.grades.ui.edit_dialog.dialogs.validation_error', default="Validation Error"), _t('gui.academics.grade_tracking.grades.ui.edit_dialog.dialogs.please_enter_a_score', default="Please enter a score"), parent=dialog)
                return

            try:
                score_float = float(score)
                max_pts = float(max_points)
                datetime.strptime(date, '%Y-%m-%d')
                if len(comments) > MAX_FIELD_LENGTH:
                    raise ValueError("Comments exceed maximum length")

                if (not math.isfinite(score_float) or not math.isfinite(max_pts)
                        or score_float < 0 or score_float > max_pts):
                    messagebox.showerror(_t('gui.academics.grade_tracking.grades.ui.edit_dialog.dialogs.validation_error', default="Validation Error"),
                                        f"Score must be between 0 and {max_pts}", parent=dialog)
                    return

                percentage = (score_float / max_pts) * 100
                letter_grade = self.percentage_to_letter(percentage)
                old_score = grade_data[3]

                cursor = self.get_safe_cursor()

                if is_submission:
                    cursor.execute("""
                        UPDATE assignment_submissions
                        SET grade = ?, feedback = ?, graded_date = ?, status = 'graded'
                        WHERE id = ?
                    """, (percentage, comments, date, int(grade_id[1:])))
                else:
                    cursor.execute("SELECT COALESCE(version, 1) FROM grades WHERE grade_id = ?", (grade_id,))
                    version_row = cursor.fetchone()
                    if not version_row:
                        raise sqlite3.Error("Grade no longer exists")
                    cursor.execute("""
                        UPDATE grades
                        SET score = ?, letter_grade = ?, submission_date = ?, comments = ?,
                            version = COALESCE(version, 1) + 1, updated_at = datetime('now')
                        WHERE grade_id = ? AND COALESCE(version, 1) = ?
                    """, (score_float, letter_grade, date, comments, grade_id, version_row[0]))
                    if cursor.rowcount != 1:
                        raise sqlite3.Error("Grade was changed by another user")

                # Immutable audit log for grade update (FERPA compliance)
                if IMMUTABLE_AUDIT_AVAILABLE:
                    user_id, session_id = get_gui_context()
                    require_grade_audit(
                        action=AuditAction.RECORD_UPDATE,
                        user_id=user_id,
                        resource_type='grade',
                        resource_id=str(grade_id),
                        session_id=session_id,
                        details={
                            'student_id': str(grade_data[1]),
                            'assessment_id': str(grade_data[2]),
                            'old_score': old_score,
                            'new_score': score_float,
                            'new_letter_grade': letter_grade
                        }
                    )
                else:
                    raise RuntimeError("Grade audit service unavailable")
                self.safe_commit()

                messagebox.showinfo(_t('gui.academics.grade_tracking.grades.ui.edit_dialog.dialogs.success', default="Success"), _t('gui.academics.grade_tracking.grades.ui.edit_dialog.dialogs.grade_updated_successfully', default="Grade updated successfully!"))
                dialog.destroy()
                self.refresh_grades()

                # Email student about updated grade
                self._email_grade_notification(
                    str(grade_data[1]), str(grade_data[8]), 'updated',
                    score=score_float, letter_grade=letter_grade,
                    percentage=percentage, feedback=comments
                )

            except ValueError:
                messagebox.showerror(_t('gui.academics.grade_tracking.grades.ui.edit_dialog.dialogs.validation_error', default="Validation Error"), _t('gui.academics.grade_tracking.grades.ui.edit_dialog.dialogs.score_must_be_a_valid_number', default="Score must be a valid number"))
            except sqlite3.Error as e:
                logger.exception("Grade update failed")
                messagebox.showerror(_t('gui.academics.grade_tracking.grades.ui.edit_dialog.dialogs.database_error', default="Database Error"), "The grade could not be updated.")
            except RuntimeError:
                self.conn.rollback()
                messagebox.showerror("Security error", "The grade was not saved because its audit record could not be written.", parent=dialog)

        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)
        ttk.Button(button_frame, text=_t('gui.academics.grade_tracking.grades.ui.edit_dialog.buttons.update', default="Update"), command=update_grade).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t('gui.academics.grade_tracking.grades.ui.edit_dialog.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side='left', padx=5)
