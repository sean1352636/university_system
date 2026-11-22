"""Extracted GradeManager behaviour."""

from education_system.systems.university.infrastructure.i18n import get_text as _t
from .. import *
from ..scale import GRADE_SYSTEMS, letter_to_gpa, letter_to_percentage, percentage_to_letter
from .grade_view import safe_combo_update, safe_grab_set
from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking._dialogs import make_toplevel

class BatchGradeDialogMixin:
    def batch_grade_entry(self):
        """Open batch grade entry dialog"""
        dialog = make_toplevel(self.root)
        dialog.title(_t('gui.academics.grade_tracking.grades.ui.batch_dialog.windows.batch_grade_entry', default="Batch Grade Entry"))
        dialog.geometry("900x600")

        # Make dialog modal
        dialog.transient(self.root)
        safe_grab_set(dialog)

        # Assessment selection
        top_frame = ttk.Frame(dialog)
        top_frame.pack(fill='x', padx=10, pady=10)

        ttk.Label(top_frame, text=_t('gui.academics.grade_tracking.grades.ui.batch_dialog.labels.assessment', default="Assessment:")).pack(side='left', padx=5)
        assessment_var = tk.StringVar()
        assessment_combo = ttk.Combobox(top_frame, textvariable=assessment_var, width=40, state='readonly')
        assessment_combo.pack(side='left', padx=5)

        # Load assessments (from both assessments and assignments tables)
        try:
            cursor = self.get_safe_cursor()
            # Query assessments table
            cursor.execute("""
                SELECT a.assessment_id, a.assessment_name, a.max_points, m.module_name
                FROM assessments a
                JOIN modules m ON a.module_code = m.module_code
                ORDER BY m.module_name, a.assessment_name
            """)
            assessments_from_assessments = cursor.fetchall()

            # Query assignments table (which might have been created via assignment GUI)
            cursor.execute("""
                SELECT
                    'A' || a.id as assessment_id,
                    a.title as assessment_name,
                    COALESCE(a.max_marks, 100) as max_points,
                    m.module_name
                FROM assignments a
                JOIN modules m ON a.module_code = m.module_code
                ORDER BY m.module_name, a.title
            """)
            assessments_from_assignments = cursor.fetchall()

            # Combine both sources
            all_assessments = list(assessments_from_assessments) + list(assessments_from_assignments)
            assessments = all_assessments
            assessment_list = [f"{a[0]} - {a[1]} ({a[3]}) - Max: {a[2]}" for a in assessments]
            assessment_combo['values'] = assessment_list
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.academics.grade_tracking.grades.ui.batch_dialog.dialogs.database_error', default="Database Error"), f"Error loading assessments: {e}")
            dialog.destroy()
            return

        # Max points display
        max_points_var = tk.StringVar(value=_t('gui.academics.grade_tracking.grades.ui.batch_dialog.values.select_an_assessment', default="Select an assessment"))
        ttk.Label(top_frame, text=_t('gui.academics.grade_tracking.grades.ui.batch_dialog.labels.max_points', default="Max Points:")).pack(side='left', padx=10)
        ttk.Label(top_frame, textvariable=max_points_var).pack(side='left', padx=5)

        # Student list with score entry
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ('Student ID', 'Name', 'Score', 'Percentage', 'Letter Grade')
        tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=20)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Name':
                tree.column(col, width=200, anchor='w')
            else:
                tree.column(col, width=100, anchor='center')

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=v_scrollbar.set)
        tree.pack(side='left', fill='both', expand=True)
        v_scrollbar.pack(side='right', fill='y')

        # Store scores
        scores_dict = {}

        def load_students():
            """Load enrolled students for selected assessment"""
            tree.delete(*tree.get_children())
            scores_dict.clear()

            selected = assessment_var.get()
            if not selected:
                return

            assessment_id = selected.split(' - ')[0]

            # Get max points
            for a in assessments:
                if str(a[0]) == assessment_id:
                    max_points_var.set(str(a[2]))
                    break

            try:
                # Get students enrolled in the module
                cursor.execute("""
                    SELECT DISTINCT s.student_id, s.first_name, s.last_name, g.score, g.result_code
                    FROM students s
                    JOIN student_modules sm ON s.student_id = sm.student_id
                    JOIN assessments a ON sm.module_code = a.module_code
                    LEFT JOIN grades g ON s.student_id = g.student_id AND g.assessment_id = a.assessment_id
                    WHERE a.assessment_id = ?
                    ORDER BY s.last_name, s.first_name
                """, (assessment_id,))

                students = cursor.fetchall()
                from ..marking_rules import label_for
                from education_system.systems.university.application.exams import (
                    marking as exam_marking,
                )
                anonymous = exam_marking.is_anonymised(cursor.connection, int(assessment_id))

                for student in students:
                    student_id = student[0]
                    name = label_for(cursor.connection, int(assessment_id), student_id,
                                     f"{student[1]} {student[2]}")
                    score = student[4] or (student[3] if student[3] is not None else '')
                    if student[4]:
                        tree.insert('', 'end', iid=str(student_id),
                                    values=('—' if anonymous else student_id, name, score, '', ''))
                        scores_dict[str(student_id)] = score
                        continue

                    # Calculate percentage and letter grade if score exists
                    percentage = ''
                    letter_grade = ''
                    if score:
                        max_pts = float(max_points_var.get())
                        percentage = f"{(score / max_pts) * 100:.2f}%"
                        letter_grade = self.percentage_to_letter((score / max_pts) * 100)

                    # Keyed by iid so the student id need not be shown when marking anonymously.
                    tree.insert('', 'end', iid=str(student_id),
                                values=('—' if anonymous else student_id, name, score, percentage, letter_grade))
                    scores_dict[str(student_id)] = score if score != '' else ''
                if anonymous:
                    max_points_var.set(max_points_var.get() + "   (anonymous marking)")

            except sqlite3.Error as e:
                messagebox.showerror(_t('gui.academics.grade_tracking.grades.ui.batch_dialog.dialogs.database_error', default="Database Error"), f"Error loading students: {e}")

        assessment_combo.bind('<<ComboboxSelected>>', lambda e: load_students())

        # Edit score on double-click
        def edit_score(event):
            selection = tree.selection()
            if not selection:
                return

            item = tree.item(selection[0])
            student_id = selection[0]
            current_score = item['values'][2]

            # Create simple dialog to enter score
            score_dialog = make_toplevel(dialog)
            score_dialog.title(_t('gui.academics.grade_tracking.grades.ui.batch_dialog.windows.enter_score', default="Enter Score"))
            score_dialog.geometry("300x150")
            score_dialog.transient(dialog)
            safe_grab_set(score_dialog)

            ttk.Label(score_dialog, text=f"Student: {item['values'][1]}").pack(pady=10)
            ttk.Label(score_dialog, text=f"Max Points: {max_points_var.get()}").pack(pady=5)

            ttk.Label(score_dialog, text=_t('gui.academics.grade_tracking.grades.ui.batch_dialog.labels.score', default="Score:")).pack(pady=5)
            score_var = tk.StringVar(value=str(current_score) if current_score else '')
            score_entry = ttk.Entry(score_dialog, textvariable=score_var, width=20)
            score_entry.pack(pady=5)
            score_entry.focus()

            def save_score():
                try:
                    score_text = score_var.get().strip()
                    from ..marking_rules import ABSENCE_CODES
                    if score_text.upper() in ABSENCE_CODES:
                        tree.item(selection[0], values=(
                            item['values'][0], item['values'][1], score_text.upper(), '', ''))
                        scores_dict[student_id] = score_text.upper()
                        score_dialog.destroy()
                        return
                    if score_text:
                        score = float(score_text)
                        max_pts = float(max_points_var.get().split()[0])

                        if score < 0 or score > max_pts:
                            messagebox.showerror(_t('gui.academics.grade_tracking.grades.ui.batch_dialog.dialogs.invalid_score', default="Invalid Score"), f"Score must be between 0 and {max_pts}")
                            return

                        percentage = (score / max_pts) * 100
                        letter_grade = self.percentage_to_letter(percentage)

                        # Update tree
                        tree.item(selection[0], values=(
                            item['values'][0], item['values'][1], score,
                            f"{percentage:.2f}%", letter_grade
                        ))
                        scores_dict[student_id] = score
                    else:
                        # Clear score
                        tree.item(selection[0], values=(
                            item['values'][0], item['values'][1], '', '', ''
                        ))
                        scores_dict[student_id] = ''

                    score_dialog.destroy()

                except ValueError:
                    messagebox.showerror(_t('gui.academics.grade_tracking.grades.ui.batch_dialog.dialogs.invalid_input', default="Invalid Input"), _t('gui.academics.grade_tracking.grades.ui.batch_dialog.dialogs.please_enter_a_valid_number', default="Please enter a valid number"))

            ttk.Button(score_dialog, text=_t('gui.academics.grade_tracking.grades.ui.batch_dialog.buttons.save', default="Save"), command=save_score).pack(pady=10)

        tree.bind('<Double-1>', edit_score)

        # Save all button
        def save_all_grades():
            selected = assessment_var.get()
            if not selected:
                messagebox.showwarning(_t('gui.academics.grade_tracking.grades.ui.batch_dialog.dialogs.no_assessment', default="No Assessment"), _t('gui.academics.grade_tracking.grades.ui.batch_dialog.dialogs.please_select_an_assessment', default="Please select an assessment"))
                return

            assessment_id = selected.split(' - ')[0]
            max_pts = float(max_points_var.get().split()[0])

            if not self.require_grade_mutation('import', assessment_id=assessment_id):
                return

            from ..marking_rules import (ABSENCE_CODES, ask_reason, log_change, after_exam_mark,
                                         locked_message)
            from education_system.systems.university.application.exams import (
                marking as exam_marking,
            )
            cursor = self.get_safe_cursor()
            module_code = cursor.execute("SELECT module_code, reassessment_of FROM assessments "
                                         "WHERE assessment_id = ?", (assessment_id,)).fetchone()
            # Students whose ratified result locks this mark are skipped and reported.
            locked = set()
            if module_code and module_code[1] is None:
                locked = {sid for sid in scores_dict if locked_message(cursor, sid, module_code[0])}
            existing_marks = {str(r[0]): (r[1] if r[1] is not None else r[2]) for r in cursor.execute(
                "SELECT student_id, result_code, score FROM grades WHERE assessment_id = ?",
                (assessment_id,))}
            changed = [sid for sid, sc in scores_dict.items()
                       if sid not in locked and sc not in ('', None)
                       and existing_marks.get(sid) not in (None, '')
                       and str(existing_marks[sid]) != str(sc)]
            reason = None
            if changed:
                reason = ask_reason(dialog, f"change {len(changed)} recorded mark(s)")
                if reason is None:
                    return
            user = getattr(self.auth, 'current_user', None) or {}

            saved_count = 0
            saved_grade_ids = []
            try:
                for student_id, score in scores_dict.items():
                    if student_id in locked:
                        continue
                    if student_id in changed:
                        log_change(cursor.connection, source='grades', record_id=None,
                                   student_id=student_id, module_code=module_code[0] if module_code else None,
                                   old_value=existing_marks.get(student_id), new_value=score,
                                   reason=reason, changed_by=user.get('username'))
                    if str(score).upper() in ABSENCE_CODES:
                        exam_marking.record_absence(cursor.connection, int(assessment_id), student_id,
                                                    str(score).upper(), user.get('username'), reason=reason)
                        saved_count += 1
                        continue
                    if score != '' and score is not None:
                        numeric_score = float(score)
                        if not math.isfinite(numeric_score) or not math.isfinite(max_pts):
                            raise ValueError("Score must be finite")
                        percentage = (numeric_score / max_pts) * 100
                        letter_grade = self.percentage_to_letter(percentage)

                        # Check if grade exists
                        cursor.execute("""
                            SELECT grade_id, COALESCE(version, 1) FROM grades
                            WHERE student_id = ? AND assessment_id = ?
                        """, (student_id, assessment_id))

                        existing = cursor.fetchone()
                        if existing:
                            # Update
                            cursor.execute("""
                                UPDATE grades
                                SET score = ?, letter_grade = ?, submission_date = ?,
                                    version = COALESCE(version, 1) + 1, updated_at = datetime('now')
                                WHERE student_id = ? AND assessment_id = ?
                                  AND COALESCE(version, 1) = ?
                            """, (score, letter_grade, datetime.now().strftime('%Y-%m-%d'),
                                 student_id, assessment_id, existing[1]))
                            if cursor.rowcount != 1:
                                raise sqlite3.Error("Grade was changed by another user")
                            saved_grade_ids.append(existing[0])
                        else:
                            # Insert
                            cursor.execute("""
                                INSERT INTO grades (student_id, assessment_id, score, letter_grade, submission_date)
                                VALUES (?, ?, ?, ?, ?)
                            """, (student_id, assessment_id, score, letter_grade,
                                 datetime.now().strftime('%Y-%m-%d')))
                            saved_grade_ids.append(cursor.lastrowid)

                        saved_count += 1

                if saved_count:
                    user_id, session_id = get_gui_context()
                    require_grade_audit(
                        conn=cursor.connection,
                        action=AuditAction.BULK_UPDATE,
                        user_id=user_id,
                        resource_type='grade',
                        session_id=session_id,
                        details={'operation': 'batch_save', 'count': saved_count,
                                 'assessment_id': str(assessment_id)},
                    )
                # Referral caps, moderation, module results — same transaction.
                for grade_id in saved_grade_ids:
                    after_exam_mark(cursor.connection, grade_id)
                self.safe_commit()
                note = (f"\n\n{len(locked)} student(s) skipped: their module result has been "
                        "ratified by an exam board." if locked else "")
                messagebox.showinfo(_t('gui.academics.grade_tracking.grades.ui.batch_dialog.dialogs.success', default="Success"), f"Saved {saved_count} grade(s) successfully!{note}")
                dialog.destroy()
                self.refresh_grades()

            except sqlite3.Error as e:
                self.conn.rollback()
                messagebox.showerror(_t('gui.academics.grade_tracking.grades.ui.batch_dialog.dialogs.database_error', default="Database Error"), f"Error saving grades: {e}")
            except (RuntimeError, ValueError):
                self.conn.rollback()
                messagebox.showerror("Security error", "Grades were not saved because validation or audit failed.")

        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill='x', padx=10, pady=10)
        ttk.Button(button_frame, text=_t('gui.academics.grade_tracking.grades.ui.batch_dialog.buttons.save_all_grades', default="Save All Grades"), command=save_all_grades).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t('gui.academics.grade_tracking.grades.ui.batch_dialog.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side='left', padx=5)
