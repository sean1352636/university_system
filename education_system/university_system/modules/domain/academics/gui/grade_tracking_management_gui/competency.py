from tkinter import messagebox, simpledialog
import threading

from education_system.university_system.modules.shared.utils.i18n import get_text as _

from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui._imports import (
    COMPETENCY_ASSESSMENT_AVAILABLE,
    add_competency_levels,
    manage_competency_levels,
    view_student_competency_profile,
    generate_competency_report,
    generate_student_competency_report,
    generate_course_competency_report,
    assess_comprehensive_student_risk,
)


class CompetencyMixin:
    # Competency Assessment Functions
    def manage_competency_levels_gui(self):
        """Manage competency levels - view, add, edit, delete"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.competency.login_required_manage"))
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('manage_competencies')):
            messagebox.showerror(_("common.error"), _("grades.competency.no_permission_manage"))
            return

        try:
            if COMPETENCY_ASSESSMENT_AVAILABLE:
                thread = threading.Thread(target=manage_competency_levels, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.competency.management_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.competency.failed_manage").format(error=str(e)))
            print(f"Competency levels management error: {e}")

    def add_competency_levels_gui(self, competency_id=None, competency_name=None):
        """Add proficiency levels for a competency"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.competency.login_required_add"))
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('manage_competencies')):
            messagebox.showerror(_("common.error"), _("grades.competency.no_permission_add"))
            return

        try:
            if COMPETENCY_ASSESSMENT_AVAILABLE:
                from education_system.university_system.infrastructure.database.db import get_connection

                # If parameters not provided, prompt for them
                if not competency_id:
                    competency_id = simpledialog.askinteger(
                        _("grades.dialogs.competency_id_title"),
                        _("grades.dialogs.enter_competency_id"),
                        parent=self.root
                    )

                    if not competency_id:
                        return

                if not competency_name:
                    competency_name = simpledialog.askstring(
                        _("grades.dialogs.competency_name_title"),
                        _("grades.dialogs.enter_competency_name"),
                        parent=self.root
                    )

                    if not competency_name:
                        return

                def add_levels():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        add_competency_levels(cursor, competency_id, competency_name)
                        conn.close()
                    except Exception as e:
                        print(f"Error adding competency levels: {e}")

                thread = threading.Thread(target=add_levels, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.competency.add_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.competency.failed_add").format(error=str(e)))
            print(f"Add competency levels error: {e}")

    def view_student_competency_profile_gui(self):
        """View a student's competency profile"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.competency.login_required_view"))
            return

        try:
            if COMPETENCY_ASSESSMENT_AVAILABLE:
                thread = threading.Thread(target=view_student_competency_profile, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.competency.view_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.competency.failed_view").format(error=str(e)))
            print(f"View competency profile error: {e}")

    def generate_competency_report_gui(self):
        """Generate comprehensive competency report menu"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.competency.login_required_report"))
            return

        try:
            if COMPETENCY_ASSESSMENT_AVAILABLE:
                thread = threading.Thread(target=generate_competency_report, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.competency.report_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.competency.failed_report").format(error=str(e)))
            print(f"Generate competency report error: {e}")

    def generate_student_competency_report_gui(self, student_id=None):
        """Generate detailed competency report for a student"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.competency.login_required_student_report"))
            return

        try:
            if COMPETENCY_ASSESSMENT_AVAILABLE:
                from education_system.university_system.infrastructure.database.db import get_connection

                # If no student_id provided, prompt for one
                if not student_id:
                    student_id = simpledialog.askstring(
                        _("grades.dialogs.student_id_title"),
                        _("grades.dialogs.enter_student_id"),
                        parent=self.root
                    )

                    if not student_id:
                        return

                def generate_report():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        generate_student_competency_report(cursor, student_id)
                        conn.close()
                    except Exception as e:
                        print(f"Error generating student competency report: {e}")

                thread = threading.Thread(target=generate_report, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.competency.student_report_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.competency.failed_student_report").format(error=str(e)))
            print(f"Generate student competency report error: {e}")

    def generate_course_competency_report_gui(self, course=None):
        """Generate competency report for a course"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.competency.login_required_course_report"))
            return

        try:
            if COMPETENCY_ASSESSMENT_AVAILABLE:
                from education_system.university_system.infrastructure.database.db import get_connection

                # If no course provided, prompt for one
                if not course:
                    course = simpledialog.askstring(
                        _("grades.dialogs.course_title"),
                        _("grades.dialogs.enter_course_name"),
                        parent=self.root
                    )

                    if not course:
                        return

                def generate_report():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        generate_course_competency_report(cursor, course)
                        conn.close()
                    except Exception as e:
                        print(f"Error generating course competency report: {e}")

                thread = threading.Thread(target=generate_report, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.competency.course_report_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.competency.failed_course_report").format(error=str(e)))
            print(f"Generate course competency report error: {e}")

    def assess_comprehensive_student_risk_gui(self, student_id=None):
        """Assess comprehensive risk for a student"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.risk.login_required_assess"))
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('view_risk_analysis')):
            messagebox.showerror(_("common.error"), _("grades.risk.no_permission_assess"))
            return

        try:
            if COMPETENCY_ASSESSMENT_AVAILABLE:
                from education_system.university_system.infrastructure.database.db import get_connection

                # If no student_id provided, prompt for one
                if not student_id:
                    student_id = simpledialog.askstring(
                        _("grades.dialogs.student_id_title"),
                        _("grades.dialogs.enter_student_id"),
                        parent=self.root
                    )

                    if not student_id:
                        return

                def assess_risk():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()

                        # Fetch student details
                        cursor.execute(
                            "SELECT first_name, last_name, course, email_address FROM students WHERE student_id = ?",
                            (student_id,)
                        )
                        result = cursor.fetchone()

                        if not result:
                            print(f"Student {student_id} not found in database")
                            conn.close()
                            return

                        first_name, last_name, course, email = result
                        assess_comprehensive_student_risk(cursor, student_id, first_name, last_name, course, email)
                        conn.close()
                    except Exception as e:
                        print(f"Error assessing student risk: {e}")

                thread = threading.Thread(target=assess_risk, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.risk.comprehensive_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.risk.failed_assess").format(error=str(e)))
            print(f"Assess student risk error: {e}")
