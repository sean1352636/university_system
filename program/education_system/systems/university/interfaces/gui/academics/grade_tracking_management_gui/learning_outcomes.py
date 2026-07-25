import tkinter as tk
from tkinter import messagebox, simpledialog
import threading

from education_system.systems.university.infrastructure.i18n import get_text as _

from education_system.systems.university.interfaces.gui.academics.grade_tracking_management_gui._imports import (
    LEARNING_OUTCOMES_AVAILABLE,
    manage_learning_outcomes,
    record_outcome_achievement,
    view_student_outcome_achievement,
    generate_outcome_report,
    generate_student_outcome_report,
    generate_course_outcome_report,
    generate_all_courses_outcome_report,
    generate_module_outcome_report,
)


class LearningOutcomesMixin:
    # Learning Outcomes Functions
    def manage_learning_outcomes_gui(self):
        """Manage learning outcomes - add, edit, delete"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.outcomes.login_required_manage"))
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('manage_learning_outcomes')):
            messagebox.showerror(_("common.error"), _("grades.outcomes.no_permission_manage"))
            return

        try:
            if LEARNING_OUTCOMES_AVAILABLE:
                thread = threading.Thread(target=manage_learning_outcomes, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.outcomes.management_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.outcomes.failed_open_management").format(error=str(e)))
            print(f"Learning outcomes management error: {e}")

    def record_outcome_achievement_gui(self):
        """Record student outcome achievement"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.outcomes.login_required_record"))
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('record_outcomes')):
            messagebox.showerror(_("common.error"), _("grades.outcomes.no_permission_record"))
            return

        try:
            if LEARNING_OUTCOMES_AVAILABLE:
                thread = threading.Thread(target=record_outcome_achievement, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.outcomes.record_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.outcomes.failed_record").format(error=str(e)))
            print(f"Record outcome achievement error: {e}")

    def view_student_outcome_achievement_gui(self):
        """View student outcome achievements"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.outcomes.login_required_view"))
            return

        try:
            if LEARNING_OUTCOMES_AVAILABLE:
                thread = threading.Thread(target=view_student_outcome_achievement, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.outcomes.view_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.outcomes.failed_view").format(error=str(e)))
            print(f"View student outcome achievement error: {e}")

    def generate_outcome_report_gui(self):
        """Generate learning outcome reports menu"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.outcomes.login_required_generate"))
            return

        try:
            if LEARNING_OUTCOMES_AVAILABLE:
                thread = threading.Thread(target=generate_outcome_report, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.outcomes.generate_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.outcomes.failed_generate").format(error=str(e)))
            print(f"Generate outcome report error: {e}")

    def generate_student_outcome_report_gui(self, student_id=None):
        """Generate student outcome report"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.outcomes.login_required_student_report"))
            return

        try:
            if LEARNING_OUTCOMES_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                # If no student_id provided, prompt for one
                if not student_id:
                    student_id = tk.simpledialog.askstring(
                        _("grades.dialogs.student_id_title"),
                        _("grades.dialogs.enter_student_id"),
                        parent=self.root
                    )

                    if not student_id:
                        return

                # Generate report in background thread
                def generate_report():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        generate_student_outcome_report(cursor, student_id)
                        conn.close()
                    except Exception as e:
                        print(f"Error generating student outcome report: {e}")

                thread = threading.Thread(target=generate_report, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.outcomes.student_report_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.outcomes.failed_student_report").format(error=str(e)))
            print(f"Generate student outcome report error: {e}")

    def generate_course_outcome_report_gui(self, course=None):
        """Generate course outcome report"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.outcomes.login_required_course_report"))
            return

        try:
            if LEARNING_OUTCOMES_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                # If no course provided, prompt for one
                if not course:
                    course = tk.simpledialog.askstring(
                        _("grades.dialogs.course_title"),
                        _("grades.dialogs.enter_course_name"),
                        parent=self.root
                    )

                    if not course:
                        return

                # Generate report in background thread
                def generate_report():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        generate_course_outcome_report(cursor, course)
                        conn.close()
                    except Exception as e:
                        print(f"Error generating course outcome report: {e}")

                thread = threading.Thread(target=generate_report, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.outcomes.course_report_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.outcomes.failed_course_report").format(error=str(e)))
            print(f"Generate course outcome report error: {e}")

    def generate_all_courses_outcome_report_gui(self):
        """Generate outcomes for all courses"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.outcomes.login_required_all_courses"))
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('view_reports')):
            messagebox.showerror(_("common.error"), _("grades.outcomes.no_permission_institution_reports"))
            return

        try:
            if LEARNING_OUTCOMES_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                # Generate report in background thread
                def generate_report():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        generate_all_courses_outcome_report(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error generating all courses outcome report: {e}")

                thread = threading.Thread(target=generate_report, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.outcomes.all_courses_report_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.outcomes.failed_all_courses_report").format(error=str(e)))
            print(f"Generate all courses outcome report error: {e}")

    def generate_module_outcome_report_gui(self, module_code=None):
        """Generate module outcome report"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.outcomes.login_required_module_report"))
            return

        try:
            if LEARNING_OUTCOMES_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                # If no module_code provided, prompt for one
                if not module_code:
                    module_code = tk.simpledialog.askstring(
                        _("grades.dialogs.module_code_title"),
                        _("grades.dialogs.enter_module_code"),
                        parent=self.root
                    )

                    if not module_code:
                        return

                # Generate report in background thread
                def generate_report():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        generate_module_outcome_report(cursor, module_code)
                        conn.close()
                    except Exception as e:
                        print(f"Error generating module outcome report: {e}")

                thread = threading.Thread(target=generate_report, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.outcomes.module_report_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.outcomes.failed_module_report").format(error=str(e)))
            print(f"Generate module outcome report error: {e}")
