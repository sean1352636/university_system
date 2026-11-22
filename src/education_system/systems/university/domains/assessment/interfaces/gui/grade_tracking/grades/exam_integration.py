"""Extracted GradeManager behaviour."""

from education_system.systems.university.infrastructure.i18n import get_text as _t
from . import *
from .scale import GRADE_SYSTEMS, letter_to_gpa, letter_to_percentage, percentage_to_letter

class ExamIntegrationMixin:
    def _open_exam_results_for_grade(self, student_grades_id: int):
        """Look up the originating exam for a student_grades row and
        open the exam scheduler's per-exam marks dialog."""
        try:
            cursor = self.get_safe_cursor()
        except Exception:
            return

        # student_grades.assessment_name was written as
        # "{module_code} Exam ({date})" by results.apply_exam_results,
        # so we can recover the exam by matching module_code + date
        # against the exams table.
        try:
            row = cursor.execute(
                "SELECT module_code, assessment_date "
                "FROM student_grades WHERE id = ?",
                (student_grades_id,),
            ).fetchone()
        except sqlite3.Error:
            row = None
        if not row:
            messagebox.showwarning(
                _t('gui.academics.grade_tracking.grades.exam_integration.dialogs.exam_grade', default="Exam grade"),
                _t('gui.academics.grade_tracking.grades.exam_integration.dialogs.couldn_t_locate_the_source_row_in_student_grades', default="Couldn't locate the source row in student_grades."),
            )
            return
        module_code, exam_date = row[0], row[1]

        exam_row = None
        try:
            exam_row = cursor.execute(
                "SELECT id, module_code, module_name, date, start_time, "
                "       end_time, COALESCE(room,''), instructor_id, "
                "       COALESCE(instructor_name,''), "
                "       COALESCE(students_enrolled,0), "
                "       COALESCE(enrolled_student_ids,'[]') "
                "FROM exams "
                "WHERE module_code = ? AND date = ? "
                "ORDER BY id DESC LIMIT 1",
                (module_code, exam_date),
            ).fetchone()
        except sqlite3.Error:
            pass
        if not exam_row:
            messagebox.showinfo(
                _t('gui.academics.grade_tracking.grades.exam_integration.dialogs.exam_grade', default="Exam grade"),
                f"No matching exam found in the scheduler for "
                f"{module_code} on {exam_date}. The exam may have been "
                "deleted; the recorded grade remains visible here.",
            )
            return

        try:
            from education_system.systems.university.domains.assessment.interfaces.gui.exam_management.models import Exam
            from education_system.systems.university.domains.assessment.interfaces.gui.exam_management.data_manager import DataManager
            from education_system.systems.university.domains.assessment.interfaces.gui.exam_management.tabs.results_tab import ResultsEntryDialog
        except Exception as exc:
            messagebox.showerror(
                _t('gui.academics.grade_tracking.grades.exam_integration.dialogs.exam_grade', default="Exam grade"),
                f"Exam scheduler isn't available: {exc}",
            )
            return

        try:
            ids_blob = exam_row[10]
            enrolled_ids = json.loads(ids_blob) if ids_blob else []
        except (TypeError, ValueError):
            enrolled_ids = []

        exam_obj = Exam(
            id=exam_row[0], module_code=exam_row[1], module_name=exam_row[2],
            date=exam_row[3], start_time=exam_row[4], end_time=exam_row[5],
            room=exam_row[6], instructor_id=exam_row[7],
            instructor_name=exam_row[8], students_enrolled=exam_row[9],
            enrolled_student_ids=enrolled_ids,
        )

        # ResultsEntryDialog needs a DataManager so it can read enrolled
        # students and existing grades. Spin up a fresh one — it loads
        # data lazily and shares the same DB.
        data_manager = DataManager()
        ResultsEntryDialog(
            self.content_frame, exam_obj, data_manager,
            on_saved=self.refresh_grades,
        )
