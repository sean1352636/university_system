"""Extracted GradeManager behaviour."""

from education_system.systems.university.infrastructure.i18n import get_text as _t
from . import *
from .scale import GRADE_SYSTEMS, letter_to_gpa, letter_to_percentage, percentage_to_letter

class GradeStatisticsMixin:
    def calculate_all_gpas(self):
        """Calculate GPAs for all students.

        Delegates per-student GPA math to
        ``grading.grade_calculation.gpa.calculate_student_gpa`` so the
        formula stays in one place; this method only handles the loop
        and the result-dialog rendering.
        """
        try:
            from education_system.systems.university.domains.assessment.domain.grading.grade_calculation.gpa import (
                calculate_student_gpa,
            )
            from education_system.systems.university.domains.academics.interfaces.gui.grade_tracking.integrations import (
                push_grade_kpi,
                notify_aid_of_gpa,
            )

            cursor = self.get_safe_cursor()
            cursor.execute("SELECT student_id, first_name, last_name FROM students")
            students = cursor.fetchall()

            results = []
            updated_count = 0
            gpa_values: list[float] = []

            for student in students:
                student_id = student[0]
                name = f"{student[1]} {student[2]}"

                gpa, credits, _ = calculate_student_gpa(cursor, student_id)
                if gpa is None:
                    results.append(f"{name}: No grades found")
                    continue

                results.append(f"{name}: GPA = {gpa:.2f} ({credits} module(s))")
                updated_count += 1
                gpa_values.append(gpa)

                # Cross-domain side-effect: tag the student's aid record(s)
                # with the latest GPA so financial_aid reviewers see the
                # number that's gating their scholarship eligibility.
                try:
                    notify_aid_of_gpa(student_id=student_id, gpa=gpa)
                except Exception:
                    pass

            self.safe_commit()

            # Best-effort KPI push — silent when no matching KPI exists
            if gpa_values:
                try:
                    push_grade_kpi(
                        "Average GPA", sum(gpa_values) / len(gpa_values),
                    )
                    pass_rate = (
                        sum(1 for g in gpa_values if g >= 2.0) / len(gpa_values) * 100.0
                    )
                    push_grade_kpi("Pass Rate %", pass_rate)
                except Exception:
                    pass

            # Show results dialog
            result_dialog = tk.Toplevel(self.root)
            result_dialog.title(_t('gui.academics.grade_tracking.grades.statistics.windows.gpa_calculation_results', default="GPA Calculation Results"))
            result_dialog.geometry("500x600")

            ttk.Label(result_dialog, text=f"Calculated GPAs for {updated_count} students",
                     font=('Arial', 12, 'bold')).pack(pady=10)

            # Results text area
            text_frame = ttk.Frame(result_dialog)
            text_frame.pack(fill='both', expand=True, padx=10, pady=10)

            text_widget = scrolledtext.ScrolledText(text_frame, width=60, height=30)
            text_widget.pack(fill='both', expand=True)

            for result in results:
                text_widget.insert('end', result + '\n')

            text_widget.config(state='disabled')

            ttk.Button(result_dialog, text=_t('gui.academics.grade_tracking.grades.statistics.buttons.close', default="Close"), command=result_dialog.destroy).pack(pady=10)

        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.academics.grade_tracking.grades.statistics.dialogs.database_error', default="Database Error"), f"Error calculating GPAs: {e}")
