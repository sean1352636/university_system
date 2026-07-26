from tkinter import messagebox, simpledialog
import threading

from education_system.systems.university.infrastructure.i18n import get_text as _

from education_system.systems.university.interfaces.gui.academics.grade_tracking_management_gui._imports import (
    PERFORMANCE_ANALYTICS_AVAILABLE,
    module_performance_summary,
    generate_performance_dashboard,
    analyze_course_performance_trends,
    forecast_course_performance,
    performance_prediction_models,
    forecast_overall_performance,
    forecast_single_course,
    build_module_success_model,
    analyze_module_performance,
    calculate_course_statistics,
    export_module_performance,
    export_performance_summary,
    collect_dashboard_data,
    display_performance_dashboard,
    display_module_performance_results,
)


class PerformanceAnalyticsMixin:
    # Performance Analytics Functions
    def module_performance_summary_gui(self):
        """Generate module performance summary"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.performance.login_required_module"))
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                thread = threading.Thread(target=module_performance_summary, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.performance.module_summary_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.performance.failed_module_summary").format(error=str(e)))
            print(f"Module performance summary error: {e}")

    def generate_performance_dashboard_gui(self):
        """Generate comprehensive performance dashboard"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.performance.login_required_dashboard"))
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                thread = threading.Thread(target=generate_performance_dashboard, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.performance.dashboard_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.performance.failed_dashboard").format(error=str(e)))
            print(f"Performance dashboard error: {e}")

    def analyze_course_performance_trends_gui(self):
        """Analyze course performance trends"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.performance.login_required_trends"))
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                def analyze_trends():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        analyze_course_performance_trends(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error analyzing course performance trends: {e}")

                thread = threading.Thread(target=analyze_trends, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.performance.trends_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.performance.failed_trends").format(error=str(e)))
            print(f"Course performance trends error: {e}")

    def forecast_course_performance_gui(self):
        """Forecast future course performance"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.performance.login_required_forecast"))
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                def forecast():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        forecast_course_performance(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error forecasting course performance: {e}")

                thread = threading.Thread(target=forecast, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.performance.forecast_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.performance.failed_forecast").format(error=str(e)))
            print(f"Course performance forecasting error: {e}")

    def performance_prediction_models_gui(self):
        """Build and use performance prediction models"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.performance.login_required_prediction"))
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('use_ml_models')):
            messagebox.showerror(_("common.error"), _("grades.performance.no_permission_prediction"))
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                thread = threading.Thread(target=performance_prediction_models, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.performance.prediction_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.performance.failed_prediction").format(error=str(e)))
            print(f"Prediction models error: {e}")

    def forecast_overall_performance_gui(self):
        """Forecast overall institution performance"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.performance.login_required_overall"))
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('view_reports')):
            messagebox.showerror(_("common.error"), _("grades.performance.no_permission_overall"))
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                def forecast():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        forecast_overall_performance(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error forecasting overall performance: {e}")

                thread = threading.Thread(target=forecast, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.performance.overall_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.performance.failed_overall").format(error=str(e)))
            print(f"Overall performance forecasting error: {e}")

    def forecast_single_course_gui(self, course_name=None):
        """Forecast single course performance"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.performance.login_required_single_course"))
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                # If no course_name provided, prompt for one
                if not course_name:
                    course_name = simpledialog.askstring(
                        _("grades.dialogs.course_name_title"),
                        _("grades.dialogs.enter_course_name"),
                        parent=self.root
                    )

                    if not course_name:
                        return

                def forecast():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        forecast_single_course(cursor, course_name)
                        conn.close()
                    except Exception as e:
                        print(f"Error forecasting course performance: {e}")

                thread = threading.Thread(target=forecast, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.performance.single_course_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.performance.failed_single_course").format(error=str(e)))
            print(f"Course forecasting error: {e}")

    def build_module_success_model_gui(self):
        """Build ML model for module success prediction"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.performance.login_required_ml"))
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('use_ml_models')):
            messagebox.showerror(_("common.error"), _("grades.performance.no_permission_ml"))
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                def build_model():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        build_module_success_model(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error building module success model: {e}")

                thread = threading.Thread(target=build_model, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.performance.ml_model_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.performance.failed_ml_model").format(error=str(e)))
            print(f"Module success model error: {e}")

    def analyze_module_performance_gui(self, module_code=None):
        """Analyze performance for specific module"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.performance.login_required_analyze_module"))
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                # If no module_code provided, prompt for one
                if not module_code:
                    module_code = simpledialog.askstring(
                        _("grades.dialogs.module_code_title"),
                        _("grades.dialogs.enter_module_code"),
                        parent=self.root
                    )

                    if not module_code:
                        return

                # Get module name and type from database
                def analyze():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()

                        # Fetch module details
                        cursor.execute("SELECT module_name, module_type FROM modules WHERE module_code = ?", (module_code,))
                        result = cursor.fetchone()

                        if not result:
                            print(f"Module {module_code} not found in database")
                            conn.close()
                            return

                        module_name, module_type = result
                        analyze_module_performance(cursor, module_code, module_name, module_type)
                        conn.close()
                    except Exception as e:
                        print(f"Error analyzing module performance: {e}")

                thread = threading.Thread(target=analyze, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.performance.module_analysis_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.performance.failed_module_analysis").format(error=str(e)))
            print(f"Module performance analysis error: {e}")

    def calculate_course_statistics_gui(self, course=None):
        """Calculate comprehensive statistics for a course"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.statistics.login_required"))
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                # If no course provided, prompt for one
                if not course:
                    course = simpledialog.askstring(
                        _("grades.dialogs.course_title"),
                        _("grades.dialogs.enter_course_name"),
                        parent=self.root
                    )

                    if not course:
                        return

                def calculate():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        calculate_course_statistics(cursor, course)
                        conn.close()
                    except Exception as e:
                        print(f"Error calculating course statistics: {e}")

                thread = threading.Thread(target=calculate, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.statistics.not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.statistics.failed").format(error=str(e)))
            print(f"Course statistics error: {e}")

    def export_module_performance_gui(self, module_stats=None):
        """Export module performance data to CSV"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.export.login_required_module"))
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                if module_stats:
                    export_module_performance(module_stats)
                else:
                    messagebox.showinfo(_("common.info"), _("grades.export.generate_summary_first"))
            else:
                messagebox.showerror(_("common.error"), _("grades.export.module_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.export.failed_module").format(error=str(e)))
            print(f"Module performance export error: {e}")

    def export_performance_summary_gui(self, summary_data=None, export_type="csv"):
        """Export performance summary data"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.export.login_required_summary"))
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                if summary_data:
                    export_performance_summary(summary_data, export_type)
                    messagebox.showinfo(_("common.success"), _("grades.export.summary_exported").format(type=export_type))
                else:
                    messagebox.showinfo(_("common.info"), _("grades.export.generate_performance_first"))
            else:
                messagebox.showerror(_("common.error"), _("grades.export.summary_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.export.failed_summary").format(error=str(e)))
            print(f"Performance summary export error: {e}")

    def collect_dashboard_data_gui(self):
        """Collect data for performance dashboard"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.dashboard.login_required_collect"))
            return None

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                conn = get_connection()
                cursor = conn.cursor()
                data = collect_dashboard_data(cursor)
                conn.close()
                return data
            else:
                messagebox.showerror(_("common.error"), _("grades.dashboard.collection_not_available"))
                return None
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.dashboard.failed_collect").format(error=str(e)))
            print(f"Dashboard data collection error: {e}")
            return None

    def display_performance_dashboard_gui(self, dashboard_data=None):
        """Display performance dashboard"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.dashboard.login_required_view"))
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                if not dashboard_data:
                    dashboard_data = self.collect_dashboard_data_gui()

                if dashboard_data:
                    def display():
                        display_performance_dashboard(dashboard_data)

                    thread = threading.Thread(target=display, daemon=True)
                    thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.dashboard.display_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.dashboard.failed_display").format(error=str(e)))
            print(f"Performance dashboard display error: {e}")

    def display_module_performance_results_gui(self, module_stats=None):
        """Display module performance results"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.dashboard.login_required_module_results"))
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE and module_stats:
                def display():
                    display_module_performance_results(module_stats)

                thread = threading.Thread(target=display, daemon=True)
                thread.start()
            else:
                messagebox.showinfo(_("common.info"), _("grades.dashboard.module_stats_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.dashboard.failed_module_results").format(error=str(e)))
            print(f"Module performance results error: {e}")
