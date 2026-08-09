from tkinter import messagebox
import threading

from education_system.systems.university.infrastructure.i18n import get_text as _

from education_system.systems.university.interfaces.gui.academics.grade_tracking_management_gui._imports import (
    CURVE_ANALYSIS_AVAILABLE,
    apply_grading_curve,
    comparative_performance_analysis,
    performance_trends_analysis,
    analyze_distribution_by_course,
    analyze_distribution_by_module_type,
    analyze_overall_distribution,
    dropout_risk_analysis,
)


class CurveAnalysisMixin:
    # Curve Analysis Functions
    def apply_grading_curve_gui(self):
        """Apply grading curve to assessment"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.curve.login_required_apply"))
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('apply_curve')):
            messagebox.showerror(_("common.error"), _("grades.curve.no_permission_apply"))
            return

        try:
            if CURVE_ANALYSIS_AVAILABLE:
                thread = threading.Thread(target=apply_grading_curve, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.curve.apply_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.curve.failed_apply").format(error=str(e)))
            print(f"Grading curve error: {e}")

    def comparative_performance_analysis_gui(self):
        """Compare performance across different groups"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.curve.login_required_comparative"))
            return

        try:
            if CURVE_ANALYSIS_AVAILABLE:
                thread = threading.Thread(target=comparative_performance_analysis, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.curve.comparative_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.curve.failed_comparative").format(error=str(e)))
            print(f"Comparative analysis error: {e}")

    def performance_trends_analysis_gui(self):
        """Analyze performance trends over time"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.curve.login_required_trends"))
            return

        try:
            if CURVE_ANALYSIS_AVAILABLE:
                thread = threading.Thread(target=performance_trends_analysis, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.curve.trends_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.curve.failed_trends").format(error=str(e)))
            print(f"Performance trends error: {e}")

    def analyze_distribution_by_course_gui(self):
        """Analyze grade distribution by course"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.distribution.login_required"))
            return

        try:
            if CURVE_ANALYSIS_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                def analyze():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        analyze_distribution_by_course(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error analyzing distribution by course: {e}")

                thread = threading.Thread(target=analyze, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.distribution.by_course_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.distribution.failed_by_course").format(error=str(e)))
            print(f"Distribution by course error: {e}")

    def analyze_distribution_by_module_type_gui(self):
        """Analyze grade distribution by module type"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.distribution.login_required"))
            return

        try:
            if CURVE_ANALYSIS_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                def analyze():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        analyze_distribution_by_module_type(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error analyzing distribution by module type: {e}")

                thread = threading.Thread(target=analyze, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.distribution.by_module_type_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.distribution.failed_by_module_type").format(error=str(e)))
            print(f"Distribution by module type error: {e}")

    def analyze_overall_distribution_gui(self):
        """Analyze overall grade distribution"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.distribution.login_required_overall"))
            return

        try:
            if CURVE_ANALYSIS_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                def analyze():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        analyze_overall_distribution(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error analyzing overall distribution: {e}")

                thread = threading.Thread(target=analyze, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.distribution.overall_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.distribution.failed_overall").format(error=str(e)))
            print(f"Overall distribution error: {e}")

    def dropout_risk_analysis_gui(self):
        """Analyze dropout risk factors"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.risk.login_required_dropout"))
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('view_risk_analysis')):
            messagebox.showerror(_("common.error"), _("grades.risk.no_permission_dropout"))
            return

        try:
            if CURVE_ANALYSIS_AVAILABLE:
                thread = threading.Thread(target=dropout_risk_analysis, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.risk.dropout_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.risk.failed_dropout").format(error=str(e)))
            print(f"Dropout risk analysis error: {e}")
