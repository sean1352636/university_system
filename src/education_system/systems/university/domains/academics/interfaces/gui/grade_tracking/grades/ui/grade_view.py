"""Extracted GradeManager behaviour."""

from education_system.systems.university.infrastructure.i18n import get_text as _t
from .. import *
from ..scale import GRADE_SYSTEMS, letter_to_gpa, letter_to_percentage, percentage_to_letter
from education_system.systems.university.domains.academics.interfaces.gui.grade_tracking.utils import attr_alive, widget_alive

def safe_grab_set(dialog):
    """Safely set grab on dialog window, handling TclError exceptions"""
    try:
        # Ensure dialog is visible first
        dialog.update_idletasks()
        dialog.grab_set()
    except tk.TclError:
        # If grab fails, continue without modal behavior
        pass

def safe_combo_update(obj, combo_attr, values):
    """Safely update combobox values, handling widget destruction"""
    try:
        combo = getattr(obj, combo_attr, None)
        if widget_alive(combo):
            combo['values'] = values
            return True
    except (tk.TclError, AttributeError):
        # Widget no longer exists or is invalid
        pass
    return False

class GradeViewMixin:
    def create_grades_content(self):
        """Create grades management content"""
        # Top controls frame
        top_controls = ttk.Frame(self.content_frame)
        top_controls.pack(fill='x', padx=10, pady=5)

        # Left side controls
        left_controls = ttk.Frame(top_controls)
        left_controls.pack(side='left', fill='x', expand=True)

        ttk.Button(left_controls, text=_t('gui.academics.grade_tracking.grades.ui.grade_view.buttons.add_grade', default="Add Grade"),
                  command=self.add_grade_dialog).pack(side='left', padx=5)
        ttk.Button(left_controls, text=_t('gui.academics.grade_tracking.grades.ui.grade_view.buttons.edit_grade', default="Edit Grade"),
                  command=self.edit_grade_dialog).pack(side='left', padx=5)
        ttk.Button(left_controls, text=_t('gui.academics.grade_tracking.grades.ui.grade_view.buttons.delete_grade', default="Delete Grade"),
                  command=self.delete_grade).pack(side='left', padx=5)
        ttk.Button(left_controls, text=_t('gui.academics.grade_tracking.grades.ui.grade_view.buttons.import_grades', default="Import Grades"),
                  command=self.import_grades).pack(side='left', padx=5)
        ttk.Button(left_controls, text=_t('gui.academics.grade_tracking.grades.ui.grade_view.buttons.batch_entry', default="Batch Entry"),
                  command=self.batch_grade_entry).pack(side='left', padx=5)

        # Right side controls
        right_controls = ttk.Frame(top_controls)
        right_controls.pack(side='right')

        ttk.Button(right_controls, text=_t('gui.academics.grade_tracking.grades.ui.grade_view.buttons.calculate_gpas', default="Calculate GPAs"),
                  command=self.calculate_all_gpas).pack(side='left', padx=5)
        ttk.Button(right_controls, text=_t('gui.academics.grade_tracking.grades.ui.grade_view.buttons.grade_statistics', default="Grade Statistics"),
                  command=self.show_grade_statistics).pack(side='left', padx=5)
        ttk.Button(right_controls, text=_t('gui.academics.grade_tracking.grades.ui.grade_view.buttons.refresh', default="Refresh"),
                  command=self.refresh_grades).pack(side='left', padx=5)

        # Filter frame
        filter_frame = ttk.Frame(self.content_frame)
        filter_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(filter_frame, text=_t('gui.academics.grade_tracking.grades.ui.grade_view.labels.student', default="Student:")).pack(side='left', padx=5)
        self.grade_student_filter_var = tk.StringVar()
        self.grade_student_combo = ttk.Combobox(filter_frame,
                                               textvariable=self.grade_student_filter_var,
                                               width=25, state='readonly')
        self.grade_student_combo.pack(side='left', padx=5)
        self.grade_student_combo.bind('<<ComboboxSelected>>', self.filter_grades)

        ttk.Label(filter_frame, text=_t('gui.academics.grade_tracking.grades.ui.grade_view.labels.assessment', default="Assessment:")).pack(side='left', padx=5)
        self.grade_assessment_filter_var = tk.StringVar()
        self.grade_assessment_combo = ttk.Combobox(filter_frame,
                                                  textvariable=self.grade_assessment_filter_var,
                                                  width=25, state='readonly')
        self.grade_assessment_combo.pack(side='left', padx=5)
        self.grade_assessment_combo.bind('<<ComboboxSelected>>', self.filter_grades)

        ttk.Button(filter_frame, text=_t('gui.academics.grade_tracking.grades.ui.grade_view.buttons.clear_filters', default="Clear Filters"),
                  command=self.clear_grade_filters).pack(side='left', padx=20)

        # Grades list
        list_frame = ttk.Frame(self.content_frame)
        list_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('ID', 'Student', 'Assessment', 'Score', 'Max Points', 'Percentage', 'Letter Grade', 'Date')
        self.grades_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=22)

        for col in columns:
            self.grades_tree.heading(col, text=col)
            if col == 'Student' or col == 'Assessment':
                self.grades_tree.column(col, width=150, anchor='w')
            else:
                self.grades_tree.column(col, width=100, anchor='center')

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.grades_tree.yview)
        h_scrollbar = ttk.Scrollbar(list_frame, orient='horizontal', command=self.grades_tree.xview)
        self.grades_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        self.grades_tree.pack(side='left', fill='both', expand=True)
        v_scrollbar.pack(side='right', fill='y')
        h_scrollbar.pack(side='bottom', fill='x')

        # Double-click on an exam-source row ('E' prefix) hands off to
        # the exam scheduler's Results dialog so re-grading goes through
        # the canonical writeback (audit log, student_modules update,
        # accommodations) instead of a generic UPDATE.
        self.grades_tree.bind("<Double-1>", self._on_grade_row_double_click)

        # Load grades data
        self.refresh_grades()

        # Populate filter combos now that they exist
        self.populate_filter_combos()

    def _on_grade_row_double_click(self, _event):
        """Hand exam-source rows off to the exam scheduler's Results
        dialog. Other rows fall through to whatever default editing
        path exists (currently none — leave them no-op rather than
        opening the scheduler for the wrong source).
        """
        sel = self.grades_tree.selection()
        if not sel:
            return
        values = self.grades_tree.item(sel[0]).get("values") or []
        if not values:
            return
        grade_id = str(values[0])
        if not grade_id.startswith("E"):
            return  # non-exam row — let the existing Edit button handle it
        try:
            student_grades_id = int(grade_id[1:])
        except ValueError:
            return
        self._open_exam_results_for_grade(student_grades_id)

    def refresh_grades(self):
        """Refresh the grades list with current filters"""
        # The tree is destroyed whenever the user navigates to another view;
        # a stale reference here is normal, not an error.
        if not attr_alive(self, 'grades_tree'):
            return

        try:
            # Clear existing items
            for item in self.grades_tree.get_children():
                self.grades_tree.delete(item)

            # Get filter values
            student_filter = None
            assessment_filter = None

            if hasattr(self, 'grade_student_filter_var'):
                student_filter = self.grade_student_filter_var.get()
                if student_filter == "All Students":
                    student_filter = None

            if hasattr(self, 'grade_assessment_filter_var'):
                assessment_filter = self.grade_assessment_filter_var.get()
                if assessment_filter == "All Assessments":
                    assessment_filter = None

            # Build UNION query to get grades from both sources
            # Part 1: Grades from grades table (traditional assessments)
            query_part1 = """
                SELECT
                    g.grade_id,
                    s.first_name || ' ' || s.last_name as student_name,
                    a.assessment_name,
                    g.score,
                    a.max_points,
                    ROUND((g.score / a.max_points) * 100, 2) as percentage,
                    g.letter_grade,
                    g.submission_date,
                    'assessment' as source_type
                FROM grades g
                JOIN students s ON g.student_id = s.student_id
                JOIN assessments a ON g.assessment_id = a.assessment_id
                WHERE 1=1
            """

            params1 = []

            # Apply student filter to part 1
            if student_filter:
                student_id = student_filter.split(' - ')[0]
                query_part1 += " AND s.student_id = ?"
                params1.append(student_id)

            # Apply assessment filter to part 1 (only if not an assignment ID)
            if assessment_filter and not assessment_filter.startswith('A'):
                assessment_id = assessment_filter.split(' - ')[0]
                query_part1 += " AND a.assessment_id = ?"
                params1.append(assessment_id)

            # Part 2: Grades from assignment_submissions table (assignment GUI)
            query_part2 = """
                SELECT
                    'S' || sub.id as grade_id,
                    s.first_name || ' ' || s.last_name as student_name,
                    a.title as assessment_name,
                    ROUND((sub.grade * COALESCE(a.max_marks, 100) / 100), 2) as score,
                    COALESCE(a.max_marks, 100) as max_points,
                    ROUND(sub.grade, 2) as percentage,
                    CASE
                        WHEN sub.grade >= 93 THEN 'A+'
                        WHEN sub.grade >= 90 THEN 'A'
                        WHEN sub.grade >= 87 THEN 'A-'
                        WHEN sub.grade >= 83 THEN 'B+'
                        WHEN sub.grade >= 80 THEN 'B'
                        WHEN sub.grade >= 77 THEN 'B-'
                        WHEN sub.grade >= 73 THEN 'C+'
                        WHEN sub.grade >= 70 THEN 'C'
                        WHEN sub.grade >= 67 THEN 'C-'
                        WHEN sub.grade >= 63 THEN 'D+'
                        WHEN sub.grade >= 60 THEN 'D'
                        WHEN sub.grade >= 57 THEN 'D-'
                        ELSE 'F'
                    END as letter_grade,
                    sub.graded_date as submission_date,
                    'assignment' as source_type
                FROM assignment_submissions sub
                JOIN students s ON sub.student_id = s.student_id
                JOIN assignments a ON sub.assignment_id = a.id
                WHERE sub.grade IS NOT NULL
            """

            params2 = []

            # Apply student filter to part 2
            if student_filter:
                student_id = student_filter.split(' - ')[0]
                query_part2 += " AND s.student_id = ?"
                params2.append(student_id)

            # Apply assessment filter to part 2 (only if it's an assignment ID starting with 'A')
            if assessment_filter and assessment_filter.startswith('A'):
                assignment_id = assessment_filter.split(' - ')[0][1:]  # Remove 'A' prefix
                query_part2 += " AND a.id = ?"
                params2.append(assignment_id)

            # Part 3: Exam results from student_grades (written by the
            # exam scheduler's results.apply_exam_results — assessment_type='exam').
            # IDs are prefixed 'E' so they can be told apart from rows in
            # `grades` ('grade_id' as int) and `assignment_submissions` ('S' + id).
            query_part3 = """
                SELECT
                    'E' || sg.id as grade_id,
                    s.first_name || ' ' || s.last_name as student_name,
                    sg.assessment_name as assessment_name,
                    ROUND(sg.percentage, 2) as score,
                    100 as max_points,
                    ROUND(sg.percentage, 2) as percentage,
                    CASE
                        WHEN sg.percentage >= 93 THEN 'A+'
                        WHEN sg.percentage >= 90 THEN 'A'
                        WHEN sg.percentage >= 87 THEN 'A-'
                        WHEN sg.percentage >= 83 THEN 'B+'
                        WHEN sg.percentage >= 80 THEN 'B'
                        WHEN sg.percentage >= 77 THEN 'B-'
                        WHEN sg.percentage >= 73 THEN 'C+'
                        WHEN sg.percentage >= 70 THEN 'C'
                        WHEN sg.percentage >= 67 THEN 'C-'
                        WHEN sg.percentage >= 63 THEN 'D+'
                        WHEN sg.percentage >= 60 THEN 'D'
                        WHEN sg.percentage >= 57 THEN 'D-'
                        ELSE 'F'
                    END as letter_grade,
                    COALESCE(sg.assessment_date, sg.grade_date) as submission_date,
                    'exam' as source_type
                FROM student_grades sg
                JOIN students s ON sg.student_id = s.student_id
                WHERE sg.assessment_type = 'exam'
                  AND sg.percentage IS NOT NULL
            """

            params3 = []
            if student_filter:
                student_id = student_filter.split(' - ')[0]
                query_part3 += " AND s.student_id = ?"
                params3.append(student_id)
            # Assessment filter: exam rows have prefix 'E'
            if assessment_filter and assessment_filter.startswith('E'):
                exam_assessment = assessment_filter.split(' - ', 1)[0][1:]
                query_part3 += " AND sg.assessment_name = ?"
                params3.append(exam_assessment)

            # Combine all three queries
            full_query = (f"{query_part1} UNION ALL {query_part2} "
                          f"UNION ALL {query_part3} "
                          "ORDER BY submission_date DESC, student_name")

            cursor = self.get_safe_cursor()

            # Execute with combined parameters
            all_params = params1 + params2 + params3
            cursor.execute(full_query, all_params)
            grades = cursor.fetchall()

            # Insert into treeview
            for grade in grades:
                self.grades_tree.insert('', 'end', values=(
                    grade[0],  # ID
                    grade[1],  # Student
                    grade[2],  # Assessment
                    grade[3],  # Score
                    grade[4],  # Max Points
                    f"{grade[5]}%",  # Percentage
                    grade[6],  # Letter Grade
                    grade[7] if grade[7] else 'N/A'  # Date
                ))

        except tk.TclError:
            # Widget torn down mid-refresh (view switched / window closed).
            return

        except ConnectionError as e:
            messagebox.showerror(_t('gui.academics.grade_tracking.grades.ui.grade_view.dialogs.database_error', default="Database Error"), str(e))
        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.academics.grade_tracking.grades.ui.grade_view.dialogs.database_error', default="Database Error"), f"Error loading grades: {e}")

    def clear_grade_filters(self):
        """Clear all grade filters"""
        if hasattr(self, 'grade_student_filter_var'):
            self.grade_student_filter_var.set('')
            if hasattr(self, 'grade_student_combo'):
                self.grade_student_combo.set('')

        if hasattr(self, 'grade_assessment_filter_var'):
            self.grade_assessment_filter_var.set('')
            if hasattr(self, 'grade_assessment_combo'):
                self.grade_assessment_combo.set('')

        self.refresh_grades()

    def filter_grades(self, event=None):
        """Apply current filters to grades list"""
        self.refresh_grades()

    def populate_filter_combos(self):
        """Populate filter comboboxes with current data"""
        try:
            cursor = self.get_safe_cursor()

            # Populate student filter — include students with rows in
            # `grades`, `assignment_submissions`, or `student_grades`
            # (the latter is where exam scheduler results land).
            if attr_alive(self, 'grade_student_combo'):
                cursor.execute("""
                    SELECT DISTINCT s.student_id, s.first_name, s.last_name
                    FROM students s
                    WHERE EXISTS (SELECT 1 FROM grades g
                                   WHERE g.student_id = s.student_id)
                       OR EXISTS (SELECT 1 FROM assignment_submissions sub
                                   WHERE sub.student_id = s.student_id)
                       OR EXISTS (SELECT 1 FROM student_grades sg
                                   WHERE sg.student_id = s.student_id)
                    ORDER BY s.last_name, s.first_name
                """)
                students = cursor.fetchall()
                student_list = ["All Students"] + [f"{s[0]} - {s[1]} {s[2]}" for s in students]
                safe_combo_update(self, 'grade_student_combo', student_list)

            # Populate assessment filter (from both assessments and assignments tables)
            if attr_alive(self, 'grade_assessment_combo'):
                # Query assessments table
                cursor.execute("""
                    SELECT DISTINCT a.assessment_id, a.assessment_name, m.module_name
                    FROM assessments a
                    JOIN modules m ON a.module_code = m.module_code
                    JOIN grades g ON a.assessment_id = g.assessment_id
                    ORDER BY m.module_name, a.assessment_name
                """)
                assessments_from_assessments = cursor.fetchall()

                # Query assignments table
                cursor.execute("""
                    SELECT DISTINCT
                        'A' || a.id as assessment_id,
                        a.title as assessment_name,
                        m.module_name
                    FROM assignments a
                    JOIN modules m ON a.module_code = m.module_code
                    WHERE EXISTS (SELECT 1 FROM grades g WHERE CAST(g.assessment_id AS TEXT) = 'A' || CAST(a.id AS TEXT))
                    ORDER BY m.module_name, a.title
                """)
                assessments_from_assignments = cursor.fetchall()

                # Query exam-source assessments from student_grades. The
                # filter id uses an 'E' prefix + the assessment_name so
                # refresh_grades can identify and route the filter.
                cursor.execute("""
                    SELECT DISTINCT sg.assessment_name,
                           COALESCE(m.module_name, sg.module_code) AS module_name
                    FROM student_grades sg
                    LEFT JOIN modules m ON m.module_code = sg.module_code
                    WHERE sg.assessment_type = 'exam'
                      AND sg.assessment_name IS NOT NULL
                    ORDER BY module_name, sg.assessment_name
                """)
                assessments_from_exams = [
                    (f"E{name}", name, mod or "")
                    for name, mod in cursor.fetchall()
                ]

                # Combine all three sources
                all_assessments = (list(assessments_from_assessments)
                                   + list(assessments_from_assignments)
                                   + assessments_from_exams)
                assessment_list = ["All Assessments"] + [f"{a[0]} - {a[1]} ({a[2]})" for a in all_assessments]
                safe_combo_update(self, 'grade_assessment_combo', assessment_list)

        except (ConnectionError, sqlite3.Error):
            # Silently fail - filters just won't be populated
            pass
