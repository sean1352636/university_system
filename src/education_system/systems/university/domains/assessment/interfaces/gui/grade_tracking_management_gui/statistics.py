
from education_system.systems.university.infrastructure.i18n import get_text as _t
from tkinter import messagebox
import threading

from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking_management_gui._imports import (
    GRADE_CALCULATION_AVAILABLE,
    calculate_assessment_statistics,
    normalize_assessment_grades,
    view_grade_distribution,
    map_assessments_to_outcomes,
    map_assessments_to_competencies,
    assessment_performance_summary,
    grade_distribution_analysis,
    student_risk_assessment,
)


class StatisticsMixin:
    # Statistics & Analysis
    def calculate_assessment_statistics_gui(self):
        """Calculate statistical measures for assessment"""
        if not self.auth.current_user:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.statistics.dialogs.you_must_be_logged_in_to_calculate_statistics', default="You must be logged in to calculate statistics."))
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                thread = threading.Thread(target=calculate_assessment_statistics, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.statistics.dialogs.calculate_assessment_statistics_not_available', default="Calculate assessment statistics not available."))
        except Exception as e:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), f"Failed to calculate statistics: {str(e)}")

    def normalize_assessment_grades_gui(self):
        """Normalize grades for assessment using z-scores"""
        if not self.auth.current_user:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.statistics.dialogs.you_must_be_logged_in_to_normalize_grades', default="You must be logged in to normalize grades."))
            return

        if not self.auth.check_permission('manage_grades'):
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.statistics.dialogs.you_don_t_have_permission_to_normalize_grades', default="You don't have permission to normalize grades."))
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                thread = threading.Thread(target=normalize_assessment_grades, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.statistics.dialogs.normalize_assessment_grades_not_available', default="Normalize assessment grades not available."))
        except Exception as e:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), f"Failed to normalize grades: {str(e)}")

    def view_grade_distribution_gui(self):
        """Visualize grade distribution for assessment/module"""
        if not self.auth.current_user:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.statistics.dialogs.you_must_be_logged_in_to_view_grade_distribution', default="You must be logged in to view grade distribution."))
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                thread = threading.Thread(target=view_grade_distribution, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.statistics.dialogs.view_grade_distribution_not_available', default="View grade distribution not available."))
        except Exception as e:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), f"Failed to view grade distribution: {str(e)}")

    # Assessment Mapping & Reporting
    def map_assessments_to_outcomes_gui(self):
        """Map assessments to learning outcomes with weights"""
        if not self.auth.current_user:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.statistics.dialogs.you_must_be_logged_in_to_map_assessments', default="You must be logged in to map assessments."))
            return

        if not self.auth.check_permission('manage_grades'):
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.statistics.dialogs.you_don_t_have_permission_to_map_assessments', default="You don't have permission to map assessments."))
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                thread = threading.Thread(target=map_assessments_to_outcomes, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.statistics.dialogs.map_assessments_to_outcomes_not_available', default="Map assessments to outcomes not available."))
        except Exception as e:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), f"Failed to map assessments to outcomes: {str(e)}")

    def map_assessments_to_competencies_gui(self):
        """Map assessments to competencies with weights"""
        if not self.auth.current_user:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.statistics.dialogs.you_must_be_logged_in_to_map_assessments', default="You must be logged in to map assessments."))
            return

        if not self.auth.check_permission('manage_grades'):
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.statistics.dialogs.you_don_t_have_permission_to_map_assessments', default="You don't have permission to map assessments."))
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                thread = threading.Thread(target=map_assessments_to_competencies, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.statistics.dialogs.map_assessments_to_competencies_not_available', default="Map assessments to competencies not available."))
        except Exception as e:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), f"Failed to map assessments to competencies: {str(e)}")

    def assessment_performance_summary_gui(self):
        """Generate assessment performance summary"""
        if not self.auth.current_user:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.statistics.dialogs.you_must_be_logged_in_to_view_performance_summary', default="You must be logged in to view performance summary."))
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                thread = threading.Thread(target=assessment_performance_summary, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.statistics.dialogs.assessment_performance_summary_not_available', default="Assessment performance summary not available."))
        except Exception as e:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), f"Failed to generate performance summary: {str(e)}")

    def grade_distribution_analysis_gui(self):
        """Analyze grade distributions across dimensions"""
        if not self.auth.current_user:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.statistics.dialogs.you_must_be_logged_in_to_analyze_grade_distribution', default="You must be logged in to analyze grade distribution."))
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                thread = threading.Thread(target=grade_distribution_analysis, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.statistics.dialogs.grade_distribution_analysis_not_available', default="Grade distribution analysis not available."))
        except Exception as e:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), f"Failed to analyze grade distribution: {str(e)}")

    def student_risk_assessment_gui(self):
        """Assess risk levels for all students"""
        if not self.auth.current_user:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.statistics.dialogs.you_must_be_logged_in_to_assess_student_risk', default="You must be logged in to assess student risk."))
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('predictive_analytics')):
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.statistics.dialogs.you_don_t_have_permission_to_assess_student_risk', default="You don't have permission to assess student risk."))
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                thread = threading.Thread(target=student_risk_assessment, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.statistics.dialogs.student_risk_assessment_not_available', default="Student risk assessment not available."))
        except Exception as e:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.statistics.dialogs.error', default="Error"), f"Failed to assess student risk: {str(e)}")
