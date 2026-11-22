"""Extracted GradeManager behaviour."""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t
from .. import *
from ..scale import GRADE_SYSTEMS, letter_to_gpa, letter_to_percentage, percentage_to_letter
from .grade_view import safe_combo_update, safe_grab_set
from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking._dialogs import make_toplevel

class AddGradeDialogMixin:
    def add_grade_dialog(self, prefill_student_id=None,
                         prefill_module_code=None, prefill_comments=None):
        """Open dialog to add a new grade — shows student's submitted assignments.

        Optional kwargs let callers (e.g. the absence tracker's grade-penalty
        workflow) jump straight to the right student/module with a pre-filled
        comment. Pass None for any to leave it blank.
        """
        dialog = make_toplevel(self.root)
        dialog.title(_t('gui.academics.grade_tracking.grades.ui.add_dialog.windows.add_grade', default="Add Grade"))
        dialog.geometry("550x650")
        dialog.transient(self.root)
        safe_grab_set(dialog)

        # Shared state for assessment data lookup
        assessments = []

        # Student selection
        ttk.Label(dialog, text=_t('gui.academics.grade_tracking.grades.ui.add_dialog.labels.student', default="Student:")).grid(row=0, column=0, padx=10, pady=10, sticky='w')
        student_var = tk.StringVar()
        student_combo = ttk.Combobox(dialog, textvariable=student_var, width=40, state='readonly')
        student_combo.grid(row=0, column=1, padx=10, pady=10)

        # Load students
        try:
            cursor = self.get_safe_cursor()
            cursor.execute("SELECT student_id, first_name, last_name FROM students ORDER BY last_name")
            students = cursor.fetchall()
            student_combo['values'] = [f"{s[0]} - {s[1]} {s[2]}" for s in students]
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.academics.grade_tracking.grades.ui.add_dialog.dialogs.database_error', default="Database Error"), f"Error loading students: {e}", parent=dialog)
            dialog.destroy()
            return

        # Assessment selection (populated when student is selected)
        ttk.Label(dialog, text=_t('gui.academics.grade_tracking.grades.ui.add_dialog.labels.assessment', default="Assessment:")).grid(row=1, column=0, padx=10, pady=10, sticky='w')
        assessment_var = tk.StringVar()
        assessment_combo = ttk.Combobox(dialog, textvariable=assessment_var, width=40, state='readonly')
        assessment_combo.grid(row=1, column=1, padx=10, pady=10)

        # Status label to show what's loaded
        status_var = tk.StringVar(value=_t('gui.academics.grade_tracking.grades.ui.add_dialog.values.select_a_student_to_see_their_submissions', default="Select a student to see their submissions"))
        ttk.Label(dialog, textvariable=status_var, foreground='#1565c0').grid(
            row=2, column=0, columnspan=2, padx=10, sticky='w')

        def on_student_selected(event=None):
            """When a student is selected, load their submitted assignments"""
            nonlocal assessments
            assessments = []
            assessment_combo.set('')
            assessment_combo['values'] = []
            max_points_var.set("Select an assessment")

            selected = student_var.get()
            if not selected:
                return

            student_id = selected.split(' - ')[0]

            try:
                cursor = self.get_safe_cursor()

                # Get assignments this student has submitted (from assignment_submissions)
                cursor.execute("""
                    SELECT
                        'A' || a.id as assessment_id,
                        a.title as name,
                        COALESCE(a.max_marks, 100) as max_points,
                        a.module_code,
                        sub.submission_date,
                        CASE WHEN sub.grade IS NOT NULL THEN 'Graded' ELSE 'Submitted' END as status
                    FROM assignment_submissions sub
                    JOIN assignments a ON sub.assignment_id = a.id
                    WHERE sub.student_id = ?
                    ORDER BY sub.submission_date DESC
                """, (student_id,))
                submitted_assignments = cursor.fetchall()

                # Also get assessments from assessments table for this student's modules
                cursor.execute("""
                    SELECT a.assessment_id, a.assessment_name, a.max_points, a.module_code,
                           a.due_date, 'Assessment' as status
                    FROM assessments a
                    JOIN student_modules sm ON a.module_code = sm.module_code
                    WHERE sm.student_id = ?
                    ORDER BY a.due_date DESC
                """, (student_id,))
                module_assessments = cursor.fetchall()

                all_items = list(submitted_assignments) + list(module_assessments)
                assessments = all_items

                if not all_items:
                    status_var.set("No submissions or assessments found for this student")
                    return

                # Format: "A438 - Assignment Title (CIS0001) [Submitted]"
                display_list = []
                for a in all_items:
                    aid, name, max_pts, module, date_val, st = a
                    display_list.append(f"{aid} - {name} ({module}) [{st}] - Max: {max_pts}")

                assessment_combo['values'] = display_list
                submitted_count = len(submitted_assignments)
                assessment_count = len(module_assessments)
                status_var.set(
                    f"Found {submitted_count} submission(s), {assessment_count} assessment(s)")

            except sqlite3.Error as e:
                status_var.set(f"Error loading: {e}")

        student_combo.bind('<<ComboboxSelected>>', on_student_selected)

        # Score entry
        ttk.Label(dialog, text=_t('gui.academics.grade_tracking.grades.ui.add_dialog.labels.score', default="Score:")).grid(row=3, column=0, padx=10, pady=10, sticky='w')
        score_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=score_var, width=42).grid(row=3, column=1, padx=10, pady=10)

        # Max points display
        max_points_var = tk.StringVar(value=_t('gui.academics.grade_tracking.grades.ui.add_dialog.values.select_an_assessment', default="Select an assessment"))
        ttk.Label(dialog, text=_t('gui.academics.grade_tracking.grades.ui.add_dialog.labels.max_points', default="Max Points:")).grid(row=4, column=0, padx=10, pady=10, sticky='w')
        ttk.Label(dialog, textvariable=max_points_var).grid(row=4, column=1, padx=10, pady=10, sticky='w')

        def update_max_points(event=None):
            selected = assessment_var.get()
            if selected:
                aid = selected.split(' - ')[0]
                for a in assessments:
                    if str(a[0]) == aid:
                        max_points_var.set(str(a[2]))
                        break

        assessment_combo.bind('<<ComboboxSelected>>', update_max_points)

        # Date
        ttk.Label(dialog, text=_t('gui.academics.grade_tracking.grades.ui.add_dialog.labels.date', default="Date:")).grid(row=5, column=0, padx=10, pady=10, sticky='w')
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(dialog, textvariable=date_var, width=42).grid(row=5, column=1, padx=10, pady=10)

        # Comments
        ttk.Label(dialog, text=_t('gui.academics.grade_tracking.grades.ui.add_dialog.labels.comments', default="Comments:")).grid(row=6, column=0, padx=10, pady=10, sticky='nw')
        comments_text = tk.Text(dialog, width=40, height=8)
        comments_text.grid(row=6, column=1, padx=10, pady=10)

        def save_grade():
            student_id = student_var.get().split(' - ')[0] if student_var.get() else None
            assessment_id = assessment_var.get().split(' - ')[0] if assessment_var.get() else None
            score = score_var.get()
            date = date_var.get()
            comments = comments_text.get('1.0', 'end-1c')

            if not student_id:
                messagebox.showerror(_t('gui.academics.grade_tracking.grades.ui.add_dialog.dialogs.validation_error', default="Validation Error"), _t('gui.academics.grade_tracking.grades.ui.add_dialog.dialogs.please_select_a_student', default="Please select a student"), parent=dialog)
                return
            if not assessment_id:
                messagebox.showerror(_t('gui.academics.grade_tracking.grades.ui.add_dialog.dialogs.validation_error', default="Validation Error"), _t('gui.academics.grade_tracking.grades.ui.add_dialog.dialogs.please_select_an_assessment', default="Please select an assessment"), parent=dialog)
                return
            if not score:
                messagebox.showerror(_t('gui.academics.grade_tracking.grades.ui.add_dialog.dialogs.validation_error', default="Validation Error"), _t('gui.academics.grade_tracking.grades.ui.add_dialog.dialogs.please_enter_a_score', default="Please enter a score"), parent=dialog)
                return

            is_assignment = str(assessment_id).startswith('A')
            scope = ({'assignment_id': int(assessment_id[1:])} if is_assignment
                     else {'assessment_id': assessment_id})
            # Pass the student so enrolment is rechecked: no grade may be
            # created for a student not enrolled in the module.
            if not self.require_grade_mutation('create', student_id=student_id, **scope):
                return

            # Submission-window gate (#5). Block grade entries outside the
            # active submission_window unless the user has an explicit
            # override permission. Soft-fails open if the calendar has
            # no submission_window defined (no period configured = no
            # restriction yet).
            try:
                from education_system.systems.university.domains.teaching.interfaces.gui._cross_services import (
                    current_period,
                )
                window_today = current_period("submission_window")
                if window_today is None:
                    # If a window exists for this term but today isn't in it,
                    # we can still detect that by querying with the entry date.
                    window_for_entry = current_period("submission_window", on_date=date)
                    if window_for_entry is None:
                        # Need to know whether *any* submission_window is on
                        # the calendar: if not, soft-fail open.
                        from education_system.systems.university.infrastructure.database.db import get_connection
                        with get_connection() as conn:
                            row = conn.execute(
                                "SELECT 1 FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar') "
                                "WHERE LOWER(event_type) = 'submission_window' "
                                "LIMIT 1"
                            ).fetchone()
                        if row:
                            override = False
                            try:
                                if (hasattr(self.app, 'auth') and self.app.auth
                                        and self.app.auth.current_user
                                        and self.app.auth.check_permission(
                                            'manage_extensions')):
                                    override = True
                            except Exception:
                                logger.debug("Suppressed exception", exc_info=True)
                            if not override:
                                messagebox.showerror(
                                    _t('gui.academics.grade_tracking.grades.ui.add_dialog.dialogs.submission_window_closed', default="Submission window closed"),
                                    _t('gui.academics.grade_tracking.grades.ui.add_dialog.dialogs.grade_entries_are_only_allowed_during_the_active_submission_wind', default="Grade entries are only allowed during "
                                    "the active submission window. Update "
                                    "the calendar or request an override."),
                                    parent=dialog,
                                )
                                return
            except Exception:
                # Never block grading on a calendar-gate failure.
                logger.debug("Suppressed exception", exc_info=True)

            # An absence code instead of a score (exams/tests only).
            from ..marking_rules import ABSENCE_CODES, after_exam_mark, is_lock_error
            if score.strip().upper() in ABSENCE_CODES:
                if is_assignment:
                    messagebox.showerror("Absence codes", "Absence codes apply to exams and tests. "
                                         "For a missing assignment record a non-submission in the "
                                         "Assignment system's Assessment QA.", parent=dialog)
                    return
                try:
                    from education_system.systems.university.application.exams import (
                        marking as exam_marking,
                    )
                    user = getattr(self.auth, 'current_user', None) or {}
                    exam_marking.record_absence(self.conn, int(assessment_id), student_id,
                                                score.strip().upper(), user.get('username'),
                                                reason=comments or None)
                    self.safe_commit()
                except Exception as e:
                    self.conn.rollback()
                    messagebox.showerror("Absence not recorded", str(e), parent=dialog)
                    return
                messagebox.showinfo("Absence recorded",
                                    f"{ABSENCE_CODES[score.strip().upper()]} recorded.", parent=dialog)
                dialog.destroy()
                self.refresh_grades()
                return

            try:
                score_float = float(score)
                max_points = float(max_points_var.get())
                datetime.strptime(date, '%Y-%m-%d')
                if len(comments) > MAX_FIELD_LENGTH:
                    raise ValueError("Comments exceed maximum length")
                if not math.isfinite(score_float) or not math.isfinite(max_points):
                    raise ValueError("Score must be finite")

                if score_float < 0:
                    messagebox.showerror(_t('gui.academics.grade_tracking.grades.ui.add_dialog.dialogs.validation_error', default="Validation Error"), _t('gui.academics.grade_tracking.grades.ui.add_dialog.dialogs.score_cannot_be_negative', default="Score cannot be negative"), parent=dialog)
                    return
                if score_float > max_points:
                    messagebox.showerror(_t('gui.academics.grade_tracking.grades.ui.add_dialog.dialogs.validation_error', default="Validation Error"),
                                        f"Score cannot exceed max points ({max_points})", parent=dialog)
                    return

                percentage = (score_float / max_points) * 100
                letter_grade = self.percentage_to_letter(percentage)

                cursor = self.get_safe_cursor()
                if is_assignment:
                    real_id = int(assessment_id[1:])

                    # Check for existing submission
                    cursor.execute(
                        "SELECT id FROM assignment_submissions WHERE assignment_id = ? AND student_id = ?",
                        (real_id, student_id))
                    existing = cursor.fetchone()

                    grader_id = None
                    if hasattr(self.app, 'auth') and self.app.auth and self.app.auth.current_user:
                        grader_id = self.app.auth.current_user.get('id')

                    if existing:
                        cursor.execute("""
                            UPDATE assignment_submissions
                            SET grade = ?, feedback = ?, graded_date = ?,
                                graded_by = ?, status = 'graded'
                            WHERE id = ?
                        """, (percentage, comments, date, grader_id, existing[0]))
                        qa_submission_id = existing[0]
                    else:
                        cursor.execute("""
                            INSERT INTO assignment_submissions
                            (assignment_id, student_id, grade, feedback, graded_date, status,
                             submission_date, file_name, file_path)
                            VALUES (?, ?, ?, ?, ?, 'graded', ?, 'grade_entry', '')
                        """, (real_id, student_id, percentage, comments, date, date))
                        qa_submission_id = cursor.lastrowid
                else:
                    cursor.execute("""
                        INSERT INTO grades (student_id, assessment_id, score, letter_grade,
                                           submission_date, comments)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (student_id, assessment_id, score_float, letter_grade, date, comments))
                    qa_grade_id = cursor.lastrowid

                if IMMUTABLE_AUDIT_AVAILABLE:
                    user_id, session_id = get_gui_context()
                    require_grade_audit(
                        conn=cursor.connection,
                        action=AuditAction.RECORD_CREATE,
                        user_id=user_id,
                        resource_type='grade',
                        resource_id=str(student_id),
                        session_id=session_id,
                        details={
                            'student_id': student_id,
                            'assessment_id': assessment_id,
                            'score': score_float,
                            'letter_grade': letter_grade
                        }
                    )
                else:
                    raise RuntimeError("Grade audit service unavailable")
                self.safe_commit()

                visible = True
                if not is_assignment:
                    # Referral cap, moderation, release control, module result.
                    visible = after_exam_mark(self.conn, qa_grade_id)["released"]
                    self.safe_commit()
                elif qa_submission_id:
                    # Word limit, referral cap, release control, module result.
                    from education_system.systems.university.domains.assessment.domain.assignments.assessment_qa import apply_mark_rules
                    visible = apply_mark_rules(qa_submission_id, percentage,
                                               feedback=comments)["released"]

                # Get assessment name for email
                sel_text = assessment_var.get()
                a_name = sel_text.split(' - ')[1].split(' (')[0] if ' - ' in sel_text else sel_text

                # Broadcast to sibling GUIs.
                try:
                    from education_system.systems.university.infrastructure.event_bus import (
                        publish, EVENT_GRADE_CHANGED,
                    )
                    publish(EVENT_GRADE_CHANGED,
                            student_id=student_id, assessment_id=assessment_id,
                            action="create")
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)

                messagebox.showinfo(_t('gui.academics.grade_tracking.grades.ui.add_dialog.dialogs.success', default="Success"), _t('gui.academics.grade_tracking.grades.ui.add_dialog.dialogs.grade_added_successfully', default="Grade added successfully!"), parent=dialog)
                dialog.destroy()
                self.refresh_grades()

                # Email student about released grade — not while it is still held back
                if visible:
                    self._email_grade_notification(
                        student_id, a_name, 'added',
                        score=score_float, letter_grade=letter_grade,
                        percentage=percentage, feedback=comments
                    )

            except ValueError:
                messagebox.showerror(_t('gui.academics.grade_tracking.grades.ui.add_dialog.dialogs.validation_error', default="Validation Error"), _t('gui.academics.grade_tracking.grades.ui.add_dialog.dialogs.score_must_be_a_valid_number', default="Score must be a valid number"), parent=dialog)
            except sqlite3.Error as e:
                logger.exception("Grade creation failed")
                self.conn.rollback()
                if is_lock_error(e):
                    messagebox.showerror("Marks locked", str(e), parent=dialog)
                else:
                    messagebox.showerror(_t('gui.academics.grade_tracking.grades.ui.add_dialog.dialogs.database_error', default="Database Error"), "The grade could not be saved.", parent=dialog)
            except RuntimeError:
                self.conn.rollback()
                messagebox.showerror("Security error", "The grade was not saved because its audit record could not be written.", parent=dialog)

        ttk.Button(dialog, text=_t('gui.academics.grade_tracking.grades.ui.add_dialog.buttons.save_grade', default="Save Grade"), command=save_grade).grid(row=7, column=0, columnspan=2, pady=15)

        # Prefill: pick student, load their assessments, optionally filter
        # by module, and seed the comments field. Done last so all combos
        # and bound handlers exist.
        if prefill_student_id:
            try:
                match = next(
                    (v for v in student_combo['values']
                     if v.startswith(f"{prefill_student_id} - ")),
                    None)
                if match:
                    student_var.set(match)
                    on_student_selected()
                    if prefill_module_code and assessments:
                        filtered = [
                            f"{a[0]} - {a[1]} ({a[3]}) [{a[5]}] - Max: {a[2]}"
                            for a in assessments
                            if str(a[3]) == str(prefill_module_code)
                        ]
                        if filtered:
                            assessment_combo['values'] = filtered
                            assessment_combo.set(filtered[0])
                            update_max_points()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
        if prefill_comments:
            try:
                comments_text.delete('1.0', 'end')
                comments_text.insert('1.0', prefill_comments)
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
