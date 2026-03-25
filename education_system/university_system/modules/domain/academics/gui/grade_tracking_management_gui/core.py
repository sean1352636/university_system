import tkinter as tk
from tkinter import messagebox
import threading

from education_system.university_system.modules.shared.utils.i18n import get_text as _

from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui._imports import (
    GradeTrackingApp,
    GRADE_TRACKING_GUI_AVAILABLE,
    GRADE_TRACKING_CLI_AVAILABLE,
    init_basic_database,
    init_enhanced_grades_db,
    display_enhanced_grade_menu,
    grade_curve_analysis_menu,
    learning_outcome_menu,
    competency_assessment_menu,
    predictive_analytics_menu,
    performance_analysis_menu,
)
from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui.learning_outcomes import LearningOutcomesMixin
from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui.performance_analytics import PerformanceAnalyticsMixin
from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui.curve_analysis import CurveAnalysisMixin
from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui.competency import CompetencyMixin
from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui.predictive_analytics import PredictiveAnalyticsMixin
from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui.grade_calculations import GradeCalculationsMixin
from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui.student_management import StudentManagementMixin
from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui.statistics import StatisticsMixin
from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui.trends import TrendsMixin
from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui.predictions import PredictionsMixin


class GradeTrackingManagementGUI(
    LearningOutcomesMixin,
    PerformanceAnalyticsMixin,
    CurveAnalysisMixin,
    CompetencyMixin,
    PredictiveAnalyticsMixin,
    GradeCalculationsMixin,
    StudentManagementMixin,
    StatisticsMixin,
    TrendsMixin,
    PredictionsMixin,
):
    """Grade Tracking management GUI wrapper"""

    def __init__(self, parent_root, auth_manager):
        self.root = parent_root
        self.auth = auth_manager

    def show_grade_tracking_gui(self):
        """Launch the Grade Tracking GUI in a child window"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.messages.login_required"))
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('view_own_grades') or
                self.auth.check_permission('manage_module_grades')):
            messagebox.showerror(_("common.error"), _("grades.messages.no_permission_access"))
            return

        try:
            if GRADE_TRACKING_GUI_AVAILABLE and GradeTrackingApp:
                grade_window = tk.Toplevel(self.root)
                grade_window.title(_("grades.title"))
                grade_window.geometry("1200x800")
                grade_window.minsize(1000, 600)

                # Configure window background
                grade_window.configure(bg='#f0f0f0')

                try:
                    grade_window.transient(self.root)
                except Exception:
                    pass

                # Initialize the Grade Tracking GUI
                grade_gui = GradeTrackingApp(grade_window)

                # Pass auth context if supported
                if hasattr(grade_gui, 'set_auth'):
                    grade_gui.set_auth(self.auth)
                elif hasattr(grade_gui, 'auth'):
                    grade_gui.auth = self.auth

                print("Grade Tracking GUI opened successfully")

            else:
                # Fallback to CLI menu
                messagebox.showinfo(_("grades.title"), _("grades.messages.gui_not_available"))
                try:
                    display_enhanced_grade_menu()
                except ImportError:
                    messagebox.showerror(_("common.error"), _("grades.messages.system_not_available"))

        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.messages.failed_to_open").format(error=str(e)))
            print(f"Grade Tracking error: {e}")

    def show_grades(self):
        """Alias method for compatibility"""
        self.show_grade_tracking_gui()

    # Database initialization methods
    def initialize_basic_database(self):
        """Initialize basic grade tracking database tables"""
        try:
            return init_basic_database()
        except Exception as e:
            messagebox.showerror(_("grades.errors.database_error"), _("grades.messages.failed_init_db").format(error=str(e)))
            print(f"Database initialization error: {e}")
            return False

    def initialize_enhanced_database(self):
        """Initialize enhanced grades database with all required tables"""
        try:
            return init_enhanced_grades_db()
        except Exception as e:
            messagebox.showerror(_("grades.errors.database_error"), _("grades.messages.failed_init_enhanced_db").format(error=str(e)))
            print(f"Enhanced database initialization error: {e}")
            return False

    # Menu access methods
    def show_enhanced_grade_menu(self):
        """Display the enhanced grade and performance tracking menu (CLI fallback)"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.messages.login_required"))
            return

        try:
            if GRADE_TRACKING_CLI_AVAILABLE:
                # Run CLI menu in a separate thread to prevent GUI blocking
                thread = threading.Thread(target=display_enhanced_grade_menu, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.messages.menu_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.messages.failed_open_menu").format(error=str(e)))
            print(f"Grade menu error: {e}")

    def show_curve_analysis_menu(self):
        """Display the grade curve analysis menu"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.messages.login_required_curve"))
            return

        try:
            if GRADE_TRACKING_CLI_AVAILABLE:
                thread = threading.Thread(target=grade_curve_analysis_menu, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.messages.curve_menu_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.messages.failed_open_curve_menu").format(error=str(e)))
            print(f"Curve analysis menu error: {e}")

    def show_learning_outcome_menu(self):
        """Display the learning outcome tracking menu"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.messages.login_required_outcomes"))
            return

        try:
            if GRADE_TRACKING_CLI_AVAILABLE:
                thread = threading.Thread(target=learning_outcome_menu, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.messages.outcome_menu_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.messages.failed_open_outcome_menu").format(error=str(e)))
            print(f"Learning outcome menu error: {e}")

    def show_competency_assessment_menu(self):
        """Display the competency-based assessment menu"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.messages.login_required_competency"))
            return

        try:
            if GRADE_TRACKING_CLI_AVAILABLE:
                thread = threading.Thread(target=competency_assessment_menu, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.messages.competency_menu_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.messages.failed_open_competency_menu").format(error=str(e)))
            print(f"Competency assessment menu error: {e}")

    def show_predictive_analytics_menu(self):
        """Display the predictive analytics menu"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.messages.login_required_analytics"))
            return

        try:
            if GRADE_TRACKING_CLI_AVAILABLE:
                thread = threading.Thread(target=predictive_analytics_menu, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.messages.analytics_menu_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.messages.failed_open_analytics_menu").format(error=str(e)))
            print(f"Predictive analytics menu error: {e}")

    def show_performance_analysis_menu(self):
        """Display the performance analysis menu"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.messages.login_required_performance"))
            return

        try:
            if GRADE_TRACKING_CLI_AVAILABLE:
                thread = threading.Thread(target=performance_analysis_menu, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.messages.performance_menu_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.messages.failed_open_performance_menu").format(error=str(e)))
            print(f"Performance analysis menu error: {e}")
