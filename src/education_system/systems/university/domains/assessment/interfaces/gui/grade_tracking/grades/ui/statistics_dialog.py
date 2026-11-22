"""Extracted GradeManager behaviour."""
import re

from education_system.systems.university.infrastructure.i18n import get_text as _t
from .. import *
from ..scale import GRADE_SYSTEMS, letter_to_gpa, letter_to_percentage, percentage_to_letter
from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking._dialogs import make_toplevel

class StatisticsDialogMixin:
    def show_grade_statistics(self):
        """Show comprehensive grade statistics from both grades and assignment_submissions"""
        try:
            cursor = self.get_safe_cursor()

            # A student sees only their own marks, and only once released.
            # (This screen is a student's one grades entry, and it used to
            # list every student's name and mark.)
            user = getattr(self.auth, 'current_user', None) or {}
            exam_scope = sub_scope = ""
            if str(user.get('role', '')).lower() == 'student':
                # The CTE is reused by several queries without parameters, so the
                # id is reduced to the characters a student number can contain.
                me = re.sub(r'[^A-Za-z0-9_-]', '', str(user.get('student_id') or user.get('username') or ''))
                exam_scope = (f" WHERE g.student_id = '{me}' "
                              "AND (a.marks_released_at IS NOT NULL OR g.released_at IS NOT NULL)")
                sub_scope = (f" AND sub.student_id = '{me}' "
                             "AND (sub.status = 'grade_released' OR a.grades_released_at IS NOT NULL)")

            # Combined view: grades table + assignment_submissions with grades
            all_grades_cte = """
                WITH all_grades AS (
                    SELECT g.score as score,
                           ROUND((g.score / a.max_points) * 100, 2) as percentage,
                           g.letter_grade,
                           s.student_id, s.first_name, s.last_name,
                           a.assessment_name as assessment_name,
                           a.max_points as max_points
                    FROM grades g
                    JOIN students s ON g.student_id = s.student_id
                    JOIN assessments a ON g.assessment_id = a.assessment_id
                    """ + exam_scope + """
                    UNION ALL
                    SELECT ROUND((sub.grade * COALESCE(a.max_marks, 100) / 100), 2) as score,
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
                           s.student_id, s.first_name, s.last_name,
                           a.title as assessment_name,
                           COALESCE(a.max_marks, 100) as max_points
                    FROM assignment_submissions sub
                    JOIN students s ON sub.student_id = s.student_id
                    JOIN assignments a ON sub.assignment_id = a.id
                    WHERE sub.grade IS NOT NULL""" + sub_scope + """
                )
            """

            # Get overall statistics
            # db-audit: ignore[DBW001] - string literal
            cursor.execute(f"""
                {all_grades_cte}
                SELECT COUNT(*) as total_grades,
                       AVG(percentage) as avg_pct,
                       MIN(percentage) as min_pct,
                       MAX(percentage) as max_pct
                FROM all_grades
            """)
            overall_stats = cursor.fetchone()

            if not overall_stats or overall_stats[0] == 0:
                messagebox.showinfo(_t('gui.academics.grade_tracking.grades.ui.statistics_dialog.dialogs.no_data', default="No Data"), _t('gui.academics.grade_tracking.grades.ui.statistics_dialog.dialogs.no_grades_available_for_statistics', default="No grades available for statistics"))
                return

            # Create statistics dialog
            stats_dialog = make_toplevel(self.root)
            stats_dialog.title(_t('gui.academics.grade_tracking.grades.ui.statistics_dialog.windows.grade_statistics', default="Grade Statistics"))
            stats_dialog.geometry("800x700")

            notebook = ttk.Notebook(stats_dialog)
            notebook.pack(fill='both', expand=True, padx=10, pady=10)

            # Overall Statistics Tab
            overall_frame = ttk.Frame(notebook)
            notebook.add(overall_frame, text=_t('gui.academics.grade_tracking.grades.ui.statistics_dialog.tabs.overall_statistics', default="Overall Statistics"))

            stats_text = scrolledtext.ScrolledText(overall_frame, width=80, height=35)
            stats_text.pack(fill='both', expand=True, padx=10, pady=10)

            stats_text.insert('end', "=== OVERALL GRADE STATISTICS ===\n\n")
            stats_text.insert('end', f"Total Grades: {overall_stats[0]}\n")
            stats_text.insert('end', f"Average Percentage: {overall_stats[1]:.2f}%\n")
            stats_text.insert('end', f"Minimum Percentage: {overall_stats[2]:.2f}%\n")
            stats_text.insert('end', f"Maximum Percentage: {overall_stats[3]:.2f}%\n\n")

            # Grade distribution
            # db-audit: ignore[DBW001] - string literal
            cursor.execute(f"""
                {all_grades_cte}
                SELECT letter_grade, COUNT(*) as count
                FROM all_grades
                GROUP BY letter_grade
                ORDER BY letter_grade
            """)
            grade_dist = cursor.fetchall()

            stats_text.insert('end', "=== GRADE DISTRIBUTION ===\n\n")
            for grade, count in grade_dist:
                pct = (count / overall_stats[0]) * 100
                bar = '#' * int(pct / 2)
                stats_text.insert('end', f"{grade:>3s}: {count:3d} ({pct:5.1f}%)  {bar}\n")

            # Per-Assessment Statistics Tab
            assessment_frame = ttk.Frame(notebook)
            notebook.add(assessment_frame, text=_t('gui.academics.grade_tracking.grades.ui.statistics_dialog.tabs.by_assessment', default="By Assessment"))

            assessment_text = scrolledtext.ScrolledText(assessment_frame, width=80, height=35)
            assessment_text.pack(fill='both', expand=True, padx=10, pady=10)

            # db-audit: ignore[DBW001] - string literal
            cursor.execute(f"""
                {all_grades_cte}
                SELECT assessment_name, max_points,
                       COUNT(*) as num_grades,
                       AVG(score) as avg_score,
                       MIN(score) as min_score,
                       MAX(score) as max_score,
                       AVG(percentage) as avg_pct
                FROM all_grades
                GROUP BY assessment_name
                ORDER BY assessment_name
            """)
            assessment_stats = cursor.fetchall()

            assessment_text.insert('end', "=== STATISTICS BY ASSESSMENT ===\n\n")
            for stat in assessment_stats:
                name, max_pts, num, avg_s, min_s, max_s, avg_p = stat
                assessment_text.insert('end', f"Assessment: {name}\n")
                assessment_text.insert('end', f"Number of Grades: {num}\n")
                assessment_text.insert('end', f"Average Score: {avg_s:.2f} / {max_pts}\n")
                assessment_text.insert('end', f"Average Percentage: {avg_p:.2f}%\n")
                assessment_text.insert('end', f"Score Range: {min_s:.2f} - {max_s:.2f}\n")
                assessment_text.insert('end', f"{'-'*60}\n\n")

            # Per-Student Statistics Tab
            student_frame = ttk.Frame(notebook)
            notebook.add(student_frame, text=_t('gui.academics.grade_tracking.grades.ui.statistics_dialog.tabs.by_student', default="By Student"))

            student_text = scrolledtext.ScrolledText(student_frame, width=80, height=35)
            student_text.pack(fill='both', expand=True, padx=10, pady=10)

            # db-audit: ignore[DBW001] - string literal
            cursor.execute(f"""
                {all_grades_cte}
                SELECT student_id, first_name, last_name,
                       COUNT(*) as num_grades,
                       AVG(percentage) as avg_pct,
                       MIN(percentage) as min_pct,
                       MAX(percentage) as max_pct
                FROM all_grades
                GROUP BY student_id
                ORDER BY last_name, first_name
            """)
            student_stats = cursor.fetchall()

            student_text.insert('end', "=== STATISTICS BY STUDENT ===\n\n")
            for stat in student_stats:
                sid, fname, lname, num, avg_p, min_p, max_p = stat
                student_text.insert('end', f"Student: {fname} {lname} ({sid})\n")
                student_text.insert('end', f"Number of Grades: {num}\n")
                student_text.insert('end', f"Average: {avg_p:.2f}%\n")
                student_text.insert('end', f"Range: {min_p:.2f}% - {max_p:.2f}%\n")

                # Letter grade for average
                letter = self.percentage_to_letter(avg_p)
                gpa = self.letter_to_gpa(letter)
                student_text.insert('end', f"Overall Grade: {letter} (GPA: {gpa:.2f})\n")
                student_text.insert('end', f"{'-'*60}\n\n")

            # Disable editing
            stats_text.config(state='disabled')
            assessment_text.config(state='disabled')
            student_text.config(state='disabled')

            ttk.Button(stats_dialog, text=_t('gui.academics.grade_tracking.grades.ui.statistics_dialog.buttons.close', default="Close"), command=stats_dialog.destroy).pack(pady=10)

        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.academics.grade_tracking.grades.ui.statistics_dialog.dialogs.database_error', default="Database Error"), f"Error calculating statistics: {e}")
