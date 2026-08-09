
from education_system.systems.university.infrastructure.i18n import get_text as _t
from tkinter import messagebox
import threading

from education_system.systems.university.interfaces.gui.academics.grade_tracking_management_gui._imports import (
    GRADE_CALCULATION_AVAILABLE,
    analyze_overall_grade_trends,
    analyze_by_assessment_type,
    analyze_all_assessments,
    analyze_distribution_by_assessment_type,
    compare_by_grade_threshold,
    analyze_assessment_performance_trends,
)


class TrendsMixin:
    # Grade Trends Analysis
    def analyze_overall_grade_trends_gui(self):
        """Analyze overall grade trends across time"""
        if not self.auth.current_user:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.trends.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.trends.dialogs.you_must_be_logged_in_to_analyze_grade_trends', default="You must be logged in to analyze grade trends."))
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                def analyze():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        analyze_overall_grade_trends(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error analyzing overall grade trends: {e}")

                thread = threading.Thread(target=analyze, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.trends.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.trends.dialogs.analyze_overall_grade_trends_not_available', default="Analyze overall grade trends not available."))
        except Exception as e:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.trends.dialogs.error', default="Error"), f"Failed to analyze overall grade trends: {str(e)}")

    def analyze_by_assessment_type_gui(self):
        """Analyze performance by assessment type"""
        if not self.auth.current_user:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.trends.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.trends.dialogs.you_must_be_logged_in_to_analyze_by_assessment_type', default="You must be logged in to analyze by assessment type."))
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                def analyze():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        analyze_by_assessment_type(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error analyzing by assessment type: {e}")

                thread = threading.Thread(target=analyze, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.trends.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.trends.dialogs.analyze_by_assessment_type_not_available', default="Analyze by assessment type not available."))
        except Exception as e:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.trends.dialogs.error', default="Error"), f"Failed to analyze by assessment type: {str(e)}")

    def analyze_all_assessments_gui(self):
        """Analyze all assessments performance"""
        if not self.auth.current_user:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.trends.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.trends.dialogs.you_must_be_logged_in_to_analyze_all_assessments', default="You must be logged in to analyze all assessments."))
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                def analyze():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        analyze_all_assessments(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error analyzing all assessments: {e}")

                thread = threading.Thread(target=analyze, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.trends.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.trends.dialogs.analyze_all_assessments_not_available', default="Analyze all assessments not available."))
        except Exception as e:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.trends.dialogs.error', default="Error"), f"Failed to analyze all assessments: {str(e)}")

    def analyze_distribution_by_assessment_type_gui(self):
        """Analyze grade distribution by assessment type"""
        if not self.auth.current_user:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.trends.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.trends.dialogs.you_must_be_logged_in_to_analyze_distribution', default="You must be logged in to analyze distribution."))
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                def analyze():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        analyze_distribution_by_assessment_type(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error analyzing distribution by assessment type: {e}")

                thread = threading.Thread(target=analyze, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.trends.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.trends.dialogs.analyze_distribution_by_assessment_type_not_available', default="Analyze distribution by assessment type not available."))
        except Exception as e:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.trends.dialogs.error', default="Error"), f"Failed to analyze distribution: {str(e)}")

    def compare_by_grade_threshold_gui(self):
        """Compare students above and below grade threshold"""
        if not self.auth.current_user:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.trends.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.trends.dialogs.you_must_be_logged_in_to_compare_by_threshold', default="You must be logged in to compare by threshold."))
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                def compare():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        compare_by_grade_threshold(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error comparing by grade threshold: {e}")

                thread = threading.Thread(target=compare, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.trends.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.trends.dialogs.compare_by_grade_threshold_not_available', default="Compare by grade threshold not available."))
        except Exception as e:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.trends.dialogs.error', default="Error"), f"Failed to compare by threshold: {str(e)}")

    def analyze_assessment_performance_trends_gui(self):
        """Analyze performance trends by assessment type over time"""
        if not self.auth.current_user:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.trends.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.trends.dialogs.you_must_be_logged_in_to_analyze_performance_trends', default="You must be logged in to analyze performance trends."))
            return

        try:
            if GRADE_CALCULATION_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                def analyze():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        analyze_assessment_performance_trends(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error analyzing assessment performance trends: {e}")

                thread = threading.Thread(target=analyze, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.trends.dialogs.error', default="Error"), _t('gui.academics.grade_tracking_management_gui.trends.dialogs.analyze_assessment_performance_trends_not_available', default="Analyze assessment performance trends not available."))
        except Exception as e:
            messagebox.showerror(_t('gui.academics.grade_tracking_management_gui.trends.dialogs.error', default="Error"), f"Failed to analyze performance trends: {str(e)}")
