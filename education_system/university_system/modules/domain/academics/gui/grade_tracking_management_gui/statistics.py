from tkinter import messagebox
import threading

from ._imports import (
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
            messagebox.showerror("Error", "You must be logged in to calculate statistics.")
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                thread = threading.Thread(target=calculate_assessment_statistics, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Calculate assessment statistics not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to calculate statistics: {str(e)}")

    def normalize_assessment_grades_gui(self):
        """Normalize grades for assessment using z-scores"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to normalize grades.")
            return

        if not self.auth.check_permission('manage_grades'):
            messagebox.showerror("Error", "You don't have permission to normalize grades.")
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                thread = threading.Thread(target=normalize_assessment_grades, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Normalize assessment grades not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to normalize grades: {str(e)}")

    def view_grade_distribution_gui(self):
        """Visualize grade distribution for assessment/module"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to view grade distribution.")
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                thread = threading.Thread(target=view_grade_distribution, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "View grade distribution not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to view grade distribution: {str(e)}")

    # Assessment Mapping & Reporting
    def map_assessments_to_outcomes_gui(self):
        """Map assessments to learning outcomes with weights"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to map assessments.")
            return

        if not self.auth.check_permission('manage_grades'):
            messagebox.showerror("Error", "You don't have permission to map assessments.")
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                thread = threading.Thread(target=map_assessments_to_outcomes, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Map assessments to outcomes not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to map assessments to outcomes: {str(e)}")

    def map_assessments_to_competencies_gui(self):
        """Map assessments to competencies with weights"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to map assessments.")
            return

        if not self.auth.check_permission('manage_grades'):
            messagebox.showerror("Error", "You don't have permission to map assessments.")
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                thread = threading.Thread(target=map_assessments_to_competencies, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Map assessments to competencies not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to map assessments to competencies: {str(e)}")

    def assessment_performance_summary_gui(self):
        """Generate assessment performance summary"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to view performance summary.")
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                thread = threading.Thread(target=assessment_performance_summary, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Assessment performance summary not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate performance summary: {str(e)}")

    def grade_distribution_analysis_gui(self):
        """Analyze grade distributions across dimensions"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to analyze grade distribution.")
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                thread = threading.Thread(target=grade_distribution_analysis, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Grade distribution analysis not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to analyze grade distribution: {str(e)}")

    def student_risk_assessment_gui(self):
        """Assess risk levels for all students"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to assess student risk.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('view_risk_analysis')):
            messagebox.showerror("Error", "You don't have permission to assess student risk.")
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                thread = threading.Thread(target=student_risk_assessment, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Student risk assessment not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to assess student risk: {str(e)}")
