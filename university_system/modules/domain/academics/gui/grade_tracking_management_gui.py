import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sys
import threading
import logging
from datetime import datetime, timedelta

# Import grade tracking modules
try:
    from university_system.modules.domain.academics.gui.grade_tracking import GradeTrackingApp
    GRADE_TRACKING_GUI_AVAILABLE = True
except ImportError as e:
    print(f"Grade Tracking GUI module not available: {e}")
    GradeTrackingApp = None
    GRADE_TRACKING_GUI_AVAILABLE = False

# Import CLI fallback and grade tracking functions
try:
    from university_system.modules.domain.academics.grading.grade_tracking import (
        init_basic_database,
        init_enhanced_grades_db,
        display_enhanced_grade_menu,
        grade_curve_analysis_menu,
        learning_outcome_menu,
        competency_assessment_menu,
        predictive_analytics_menu,
        performance_analysis_menu
    )
    GRADE_TRACKING_CLI_AVAILABLE = True
except ImportError as e:
    print(f"Grade tracking CLI functions not available: {e}")
    GRADE_TRACKING_CLI_AVAILABLE = False

    # Define fallback functions
    def init_basic_database():
        print("Grade tracking database initialization not available")
        return False

    def init_enhanced_grades_db():
        print("Enhanced grades database initialization not available")
        return False

    def display_enhanced_grade_menu():
        print("Grade tracking CLI menu not available")

    def grade_curve_analysis_menu():
        print("Grade curve analysis menu not available")

    def learning_outcome_menu():
        print("Learning outcome menu not available")

    def competency_assessment_menu():
        print("Competency assessment menu not available")

    def predictive_analytics_menu():
        print("Predictive analytics menu not available")

    def performance_analysis_menu():
        print("Performance analysis menu not available")

# Import learning outcomes functions
try:
    from university_system.modules.domain.academics.grading.learning_outcomes import (
        manage_learning_outcomes,
        record_outcome_achievement,
        view_student_outcome_achievement,
        generate_outcome_report,
        generate_student_outcome_report,
        generate_course_outcome_report,
        generate_all_courses_outcome_report,
        generate_module_outcome_report
    )
    LEARNING_OUTCOMES_AVAILABLE = True
except ImportError as e:
    print(f"Learning outcomes functions not available: {e}")
    LEARNING_OUTCOMES_AVAILABLE = False

    # Define fallback functions
    def manage_learning_outcomes():
        print("Manage learning outcomes not available")

    def record_outcome_achievement():
        print("Record outcome achievement not available")

    def view_student_outcome_achievement():
        print("View student outcome achievement not available")

    def generate_outcome_report():
        print("Generate outcome report not available")

    def generate_student_outcome_report(cursor, student_id):
        print("Generate student outcome report not available")

    def generate_course_outcome_report(cursor, course):
        print("Generate course outcome report not available")

    def generate_all_courses_outcome_report(cursor):
        print("Generate all courses outcome report not available")

    def generate_module_outcome_report(cursor, module_code):
        print("Generate module outcome report not available")

# Import performance analytics functions
try:
    from university_system.modules.domain.academics.grading.performance_analytics import (
        _table_exists,
        _cols,
        _first_existing_table,
        _first_existing_column,
        collect_dashboard_data,
        module_performance_summary,
        analyze_module_performance,
        display_module_performance_results,
        calculate_course_statistics,
        generate_performance_dashboard,
        display_performance_dashboard,
        export_module_performance,
        analyze_course_performance_trends,
        forecast_course_performance,
        export_performance_summary,
        performance_prediction_models,
        forecast_overall_performance,
        forecast_single_course,
        build_module_success_model
    )
    PERFORMANCE_ANALYTICS_AVAILABLE = True
except ImportError as e:
    print(f"Performance analytics functions not available: {e}")
    PERFORMANCE_ANALYTICS_AVAILABLE = False

    # Define fallback functions
    def _table_exists(cur, name):
        return False

    def _cols(cur, table):
        return set()

    def _first_existing_table(cur, candidates):
        return None

    def _first_existing_column(cur, table, candidates):
        return None

    def collect_dashboard_data(cursor):
        print("Collect dashboard data not available")
        return {}

    def module_performance_summary():
        print("Module performance summary not available")

    def analyze_module_performance(cursor, module_code, module_name, module_type):
        print("Analyze module performance not available")

    def display_module_performance_results(module_stats):
        print("Display module performance results not available")

    def calculate_course_statistics(cursor, course):
        print("Calculate course statistics not available")

    def generate_performance_dashboard():
        print("Generate performance dashboard not available")

    def display_performance_dashboard(dashboard_data):
        print("Display performance dashboard not available")

    def export_module_performance(module_stats):
        print("Export module performance not available")

    def analyze_course_performance_trends(cursor):
        print("Analyze course performance trends not available")

    def forecast_course_performance(cursor):
        print("Forecast course performance not available")

    def export_performance_summary(summary_data, export_type):
        print("Export performance summary not available")

    def performance_prediction_models():
        print("Performance prediction models not available")

    def forecast_overall_performance(cursor):
        print("Forecast overall performance not available")

    def forecast_single_course(cursor, course_name):
        print("Forecast single course not available")

    def build_module_success_model(cursor):
        print("Build module success model not available")

# Import curve analysis functions
try:
    from university_system.modules.domain.academics.grading.curve_analysis import (
        apply_grading_curve,
        comparative_performance_analysis,
        performance_trends_analysis,
        analyze_distribution_by_course,
        analyze_distribution_by_module_type,
        analyze_overall_distribution,
        dropout_risk_analysis
    )
    CURVE_ANALYSIS_AVAILABLE = True
except ImportError as e:
    print(f"Curve analysis functions not available: {e}")
    CURVE_ANALYSIS_AVAILABLE = False

    # Define fallback functions
    def apply_grading_curve():
        print("Apply grading curve not available")

    def comparative_performance_analysis():
        print("Comparative performance analysis not available")

    def performance_trends_analysis():
        print("Performance trends analysis not available")

    def analyze_distribution_by_course(cursor):
        print("Analyze distribution by course not available")

    def analyze_distribution_by_module_type(cursor):
        print("Analyze distribution by module type not available")

    def analyze_overall_distribution(cursor):
        print("Analyze overall distribution not available")

    def dropout_risk_analysis():
        print("Dropout risk analysis not available")

# Import competency assessment functions
try:
    from university_system.modules.domain.academics.grading.competency_assessment import (
        add_competency_levels,
        manage_competency_levels,
        view_student_competency_profile,
        generate_competency_report,
        generate_student_competency_report,
        generate_course_competency_report,
        assess_comprehensive_student_risk
    )
    COMPETENCY_ASSESSMENT_AVAILABLE = True
except ImportError as e:
    print(f"Competency assessment functions not available: {e}")
    COMPETENCY_ASSESSMENT_AVAILABLE = False

    # Define fallback functions
    def add_competency_levels(cursor, competency_id, competency_name):
        print("Add competency levels not available")

    def manage_competency_levels():
        print("Manage competency levels not available")

    def view_student_competency_profile():
        print("View student competency profile not available")

    def generate_competency_report():
        print("Generate competency report not available")

    def generate_student_competency_report(cursor, student_id):
        print("Generate student competency report not available")

    def generate_course_competency_report(cursor, course):
        print("Generate course competency report not available")

    def assess_comprehensive_student_risk(cursor, student_id, first_name, last_name, course, email):
        print("Assess comprehensive student risk not available")

# Import predictive analytics functions
try:
    from university_system.modules.domain.academics.grading.predictive_analytics import (
        identify_at_risk_students,
        calculate_risk_factors,
        early_warning_system,
        generate_early_warning_alert,
        export_at_risk_students,
        export_early_warning_alerts,
        export_dropout_risk_list,
        build_at_risk_prediction_model,
        analyze_dropout_risk_factors,
        build_dropout_prediction_model,
        generate_dropout_interventions,
        generate_dropout_intervention_plan,
        identify_high_dropout_risk,
        calculate_dropout_risk_score,
        generate_risk_report,
        collect_comprehensive_risk_data,
        generate_comprehensive_risk_report
    )
    PREDICTIVE_ANALYTICS_AVAILABLE = True
except ImportError as e:
    print(f"Predictive analytics functions not available: {e}")
    PREDICTIVE_ANALYTICS_AVAILABLE = False

    # Define fallback functions
    def identify_at_risk_students():
        print("Identify at-risk students not available")

    def calculate_risk_factors(cursor, student_id):
        print("Calculate risk factors not available")
        return 0, []

    def early_warning_system():
        print("Early warning system not available")

    def generate_early_warning_alert(cursor, student_id, first_name, last_name, course, email, risk_score, risk_level):
        print("Generate early warning alert not available")

    def export_at_risk_students(at_risk_students, threshold):
        print("Export at-risk students not available")

    def export_early_warning_alerts(alerts):
        print("Export early warning alerts not available")

    def export_dropout_risk_list(high_risk_students):
        print("Export dropout risk list not available")

    def build_at_risk_prediction_model(cursor):
        print("Build at-risk prediction model not available")

    def analyze_dropout_risk_factors(cursor):
        print("Analyze dropout risk factors not available")

    def build_dropout_prediction_model(cursor):
        print("Build dropout prediction model not available")

    def generate_dropout_interventions(cursor):
        print("Generate dropout interventions not available")

    def generate_dropout_intervention_plan(cursor, student_id, first_name, last_name, course, email):
        print("Generate dropout intervention plan not available")

    def identify_high_dropout_risk(cursor):
        print("Identify high dropout risk not available")

    def calculate_dropout_risk_score(cursor, student_id):
        print("Calculate dropout risk score not available")
        return 0

    def generate_risk_report():
        print("Generate risk report not available")

    def collect_comprehensive_risk_data(cursor):
        print("Collect comprehensive risk data not available")
        return {}

    def generate_comprehensive_risk_report(risk_data):
        print("Generate comprehensive risk report not available")

from university_system.infrastructure.auth.user_authentication import UserAuth

class GradeTrackingManagementGUI:
    """Grade Tracking management GUI wrapper"""

    def __init__(self, parent_root, auth_manager):
        self.root = parent_root
        self.auth = auth_manager

        # Initialize theme manager for dark mode support
        try:
            from university_system.modules.shared.gui.theme_config import get_theme_manager
            self.theme_manager = get_theme_manager()
            self.theme_manager.register_observer(self.on_theme_changed)
        except Exception as e:
            print(f"Warning: Could not initialize theme manager: {e}")
            self.theme_manager = None

    def on_theme_changed(self):
        """Handle theme changes"""
        if self.theme_manager:
            pass

    def show_grade_tracking_gui(self):
        """Launch the Grade Tracking GUI in a child window"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to access grade tracking.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('view_own_grades') or
                self.auth.check_permission('manage_module_grades')):
            messagebox.showerror("Error", "You don't have permission to access grade tracking.")
            return

        try:
            if GRADE_TRACKING_GUI_AVAILABLE and GradeTrackingApp:
                grade_window = tk.Toplevel(self.root)
                grade_window.title("Grade & Performance Tracking System")
                grade_window.geometry("1200x800")
                grade_window.minsize(1000, 600)

                # Apply theme to window
                if self.theme_manager:
                    self.theme_manager.apply_theme_to_window(grade_window)

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
                messagebox.showinfo("Grade Tracking", "Grade Tracking GUI not available. Using CLI menu.")
                try:
                    display_enhanced_grade_menu()
                except ImportError:
                    messagebox.showerror("Error", "Grade tracking system not available.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open Grade Tracking: {str(e)}")
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
            messagebox.showerror("Database Error", f"Failed to initialize database: {str(e)}")
            print(f"Database initialization error: {e}")
            return False

    def initialize_enhanced_database(self):
        """Initialize enhanced grades database with all required tables"""
        try:
            return init_enhanced_grades_db()
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to initialize enhanced database: {str(e)}")
            print(f"Enhanced database initialization error: {e}")
            return False

    # Menu access methods
    def show_enhanced_grade_menu(self):
        """Display the enhanced grade and performance tracking menu (CLI fallback)"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to access grade tracking.")
            return

        try:
            if GRADE_TRACKING_CLI_AVAILABLE:
                # Run CLI menu in a separate thread to prevent GUI blocking
                thread = threading.Thread(target=display_enhanced_grade_menu, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Grade tracking menu not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open grade menu: {str(e)}")
            print(f"Grade menu error: {e}")

    def show_curve_analysis_menu(self):
        """Display the grade curve analysis menu"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to access grade curve analysis.")
            return

        try:
            if GRADE_TRACKING_CLI_AVAILABLE:
                thread = threading.Thread(target=grade_curve_analysis_menu, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Grade curve analysis menu not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open curve analysis menu: {str(e)}")
            print(f"Curve analysis menu error: {e}")

    def show_learning_outcome_menu(self):
        """Display the learning outcome tracking menu"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to access learning outcomes.")
            return

        try:
            if GRADE_TRACKING_CLI_AVAILABLE:
                thread = threading.Thread(target=learning_outcome_menu, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Learning outcome menu not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open learning outcome menu: {str(e)}")
            print(f"Learning outcome menu error: {e}")

    def show_competency_assessment_menu(self):
        """Display the competency-based assessment menu"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to access competency assessment.")
            return

        try:
            if GRADE_TRACKING_CLI_AVAILABLE:
                thread = threading.Thread(target=competency_assessment_menu, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Competency assessment menu not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open competency assessment menu: {str(e)}")
            print(f"Competency assessment menu error: {e}")

    def show_predictive_analytics_menu(self):
        """Display the predictive analytics menu"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to access predictive analytics.")
            return

        try:
            if GRADE_TRACKING_CLI_AVAILABLE:
                thread = threading.Thread(target=predictive_analytics_menu, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Predictive analytics menu not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open predictive analytics menu: {str(e)}")
            print(f"Predictive analytics menu error: {e}")

    def show_performance_analysis_menu(self):
        """Display the performance analysis menu"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to access performance analysis.")
            return

        try:
            if GRADE_TRACKING_CLI_AVAILABLE:
                thread = threading.Thread(target=performance_analysis_menu, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Performance analysis menu not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open performance analysis menu: {str(e)}")
            print(f"Performance analysis menu error: {e}")

    # Learning Outcomes Functions
    def manage_learning_outcomes_gui(self):
        """Manage learning outcomes - add, edit, delete"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to manage learning outcomes.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('manage_learning_outcomes')):
            messagebox.showerror("Error", "You don't have permission to manage learning outcomes.")
            return

        try:
            if LEARNING_OUTCOMES_AVAILABLE:
                thread = threading.Thread(target=manage_learning_outcomes, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Learning outcomes management not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open learning outcomes management: {str(e)}")
            print(f"Learning outcomes management error: {e}")

    def record_outcome_achievement_gui(self):
        """Record student outcome achievement"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to record outcome achievement.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('record_outcomes')):
            messagebox.showerror("Error", "You don't have permission to record outcome achievements.")
            return

        try:
            if LEARNING_OUTCOMES_AVAILABLE:
                thread = threading.Thread(target=record_outcome_achievement, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Record outcome achievement not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to record outcome achievement: {str(e)}")
            print(f"Record outcome achievement error: {e}")

    def view_student_outcome_achievement_gui(self):
        """View student outcome achievements"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to view outcome achievements.")
            return

        try:
            if LEARNING_OUTCOMES_AVAILABLE:
                thread = threading.Thread(target=view_student_outcome_achievement, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "View student outcome achievement not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to view student outcome achievement: {str(e)}")
            print(f"View student outcome achievement error: {e}")

    def generate_outcome_report_gui(self):
        """Generate learning outcome reports menu"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to generate outcome reports.")
            return

        try:
            if LEARNING_OUTCOMES_AVAILABLE:
                thread = threading.Thread(target=generate_outcome_report, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Generate outcome report not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate outcome report: {str(e)}")
            print(f"Generate outcome report error: {e}")

    def generate_student_outcome_report_gui(self, student_id=None):
        """Generate student outcome report"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to generate student outcome reports.")
            return

        try:
            if LEARNING_OUTCOMES_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

                # If no student_id provided, prompt for one
                if not student_id:
                    student_id = tk.simpledialog.askstring(
                        "Student ID",
                        "Enter Student ID:",
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
                messagebox.showerror("Error", "Generate student outcome report not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate student outcome report: {str(e)}")
            print(f"Generate student outcome report error: {e}")

    def generate_course_outcome_report_gui(self, course=None):
        """Generate course outcome report"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to generate course outcome reports.")
            return

        try:
            if LEARNING_OUTCOMES_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

                # If no course provided, prompt for one
                if not course:
                    course = tk.simpledialog.askstring(
                        "Course",
                        "Enter Course Name:",
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
                messagebox.showerror("Error", "Generate course outcome report not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate course outcome report: {str(e)}")
            print(f"Generate course outcome report error: {e}")

    def generate_all_courses_outcome_report_gui(self):
        """Generate outcomes for all courses"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to generate all courses outcome report.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('view_reports')):
            messagebox.showerror("Error", "You don't have permission to generate institution-wide reports.")
            return

        try:
            if LEARNING_OUTCOMES_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

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
                messagebox.showerror("Error", "Generate all courses outcome report not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate all courses outcome report: {str(e)}")
            print(f"Generate all courses outcome report error: {e}")

    def generate_module_outcome_report_gui(self, module_code=None):
        """Generate module outcome report"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to generate module outcome reports.")
            return

        try:
            if LEARNING_OUTCOMES_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

                # If no module_code provided, prompt for one
                if not module_code:
                    module_code = tk.simpledialog.askstring(
                        "Module Code",
                        "Enter Module Code:",
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
                messagebox.showerror("Error", "Generate module outcome report not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate module outcome report: {str(e)}")
            print(f"Generate module outcome report error: {e}")

    # Performance Analytics Functions
    def module_performance_summary_gui(self):
        """Generate module performance summary"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to view module performance.")
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                thread = threading.Thread(target=module_performance_summary, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Module performance summary not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate module performance summary: {str(e)}")
            print(f"Module performance summary error: {e}")

    def generate_performance_dashboard_gui(self):
        """Generate comprehensive performance dashboard"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to generate performance dashboard.")
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                thread = threading.Thread(target=generate_performance_dashboard, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Performance dashboard not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate performance dashboard: {str(e)}")
            print(f"Performance dashboard error: {e}")

    def analyze_course_performance_trends_gui(self):
        """Analyze course performance trends"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to analyze course performance trends.")
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

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
                messagebox.showerror("Error", "Course performance trends analysis not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to analyze course performance trends: {str(e)}")
            print(f"Course performance trends error: {e}")

    def forecast_course_performance_gui(self):
        """Forecast future course performance"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to forecast course performance.")
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

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
                messagebox.showerror("Error", "Course performance forecasting not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to forecast course performance: {str(e)}")
            print(f"Course performance forecasting error: {e}")

    def performance_prediction_models_gui(self):
        """Build and use performance prediction models"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to use prediction models.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('use_ml_models')):
            messagebox.showerror("Error", "You don't have permission to use prediction models.")
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                thread = threading.Thread(target=performance_prediction_models, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Performance prediction models not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to run prediction models: {str(e)}")
            print(f"Prediction models error: {e}")

    def forecast_overall_performance_gui(self):
        """Forecast overall institution performance"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to forecast overall performance.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('view_reports')):
            messagebox.showerror("Error", "You don't have permission to forecast overall performance.")
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

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
                messagebox.showerror("Error", "Overall performance forecasting not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to forecast overall performance: {str(e)}")
            print(f"Overall performance forecasting error: {e}")

    def forecast_single_course_gui(self, course_name=None):
        """Forecast single course performance"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to forecast course performance.")
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

                # If no course_name provided, prompt for one
                if not course_name:
                    course_name = simpledialog.askstring(
                        "Course Name",
                        "Enter Course Name:",
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
                messagebox.showerror("Error", "Course forecasting not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to forecast course: {str(e)}")
            print(f"Course forecasting error: {e}")

    def build_module_success_model_gui(self):
        """Build ML model for module success prediction"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to build success models.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('use_ml_models')):
            messagebox.showerror("Error", "You don't have permission to build ML models.")
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

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
                messagebox.showerror("Error", "Module success model building not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to build module success model: {str(e)}")
            print(f"Module success model error: {e}")

    def analyze_module_performance_gui(self, module_code=None):
        """Analyze performance for specific module"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to analyze module performance.")
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

                # If no module_code provided, prompt for one
                if not module_code:
                    module_code = simpledialog.askstring(
                        "Module Code",
                        "Enter Module Code:",
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
                messagebox.showerror("Error", "Module performance analysis not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to analyze module performance: {str(e)}")
            print(f"Module performance analysis error: {e}")

    def calculate_course_statistics_gui(self, course=None):
        """Calculate comprehensive statistics for a course"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to calculate course statistics.")
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

                # If no course provided, prompt for one
                if not course:
                    course = simpledialog.askstring(
                        "Course",
                        "Enter Course Name:",
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
                messagebox.showerror("Error", "Course statistics calculation not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to calculate course statistics: {str(e)}")
            print(f"Course statistics error: {e}")

    def export_module_performance_gui(self, module_stats=None):
        """Export module performance data to CSV"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to export module performance.")
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                if module_stats:
                    export_module_performance(module_stats)
                else:
                    messagebox.showinfo("Info", "Please generate module performance summary first.")
            else:
                messagebox.showerror("Error", "Module performance export not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export module performance: {str(e)}")
            print(f"Module performance export error: {e}")

    def export_performance_summary_gui(self, summary_data=None, export_type="csv"):
        """Export performance summary data"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to export performance summary.")
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                if summary_data:
                    export_performance_summary(summary_data, export_type)
                    messagebox.showinfo("Success", f"Performance summary exported as {export_type}")
                else:
                    messagebox.showinfo("Info", "Please generate performance summary first.")
            else:
                messagebox.showerror("Error", "Performance summary export not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export performance summary: {str(e)}")
            print(f"Performance summary export error: {e}")

    def collect_dashboard_data_gui(self):
        """Collect data for performance dashboard"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to collect dashboard data.")
            return None

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

                conn = get_connection()
                cursor = conn.cursor()
                data = collect_dashboard_data(cursor)
                conn.close()
                return data
            else:
                messagebox.showerror("Error", "Dashboard data collection not available.")
                return None
        except Exception as e:
            messagebox.showerror("Error", f"Failed to collect dashboard data: {str(e)}")
            print(f"Dashboard data collection error: {e}")
            return None

    def display_performance_dashboard_gui(self, dashboard_data=None):
        """Display performance dashboard"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to view performance dashboard.")
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
                messagebox.showerror("Error", "Performance dashboard display not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to display performance dashboard: {str(e)}")
            print(f"Performance dashboard display error: {e}")

    def display_module_performance_results_gui(self, module_stats=None):
        """Display module performance results"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to view module performance results.")
            return

        try:
            if PERFORMANCE_ANALYTICS_AVAILABLE and module_stats:
                def display():
                    display_module_performance_results(module_stats)

                thread = threading.Thread(target=display, daemon=True)
                thread.start()
            else:
                messagebox.showinfo("Info", "Module performance statistics not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to display module performance results: {str(e)}")
            print(f"Module performance results error: {e}")

    # Curve Analysis Functions
    def apply_grading_curve_gui(self):
        """Apply grading curve to assessment"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to apply grading curves.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('apply_curve')):
            messagebox.showerror("Error", "You don't have permission to apply grading curves.")
            return

        try:
            if CURVE_ANALYSIS_AVAILABLE:
                thread = threading.Thread(target=apply_grading_curve, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Grading curve application not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply grading curve: {str(e)}")
            print(f"Grading curve error: {e}")

    def comparative_performance_analysis_gui(self):
        """Compare performance across different groups"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to perform comparative analysis.")
            return

        try:
            if CURVE_ANALYSIS_AVAILABLE:
                thread = threading.Thread(target=comparative_performance_analysis, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Comparative performance analysis not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to perform comparative analysis: {str(e)}")
            print(f"Comparative analysis error: {e}")

    def performance_trends_analysis_gui(self):
        """Analyze performance trends over time"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to analyze performance trends.")
            return

        try:
            if CURVE_ANALYSIS_AVAILABLE:
                thread = threading.Thread(target=performance_trends_analysis, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Performance trends analysis not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to analyze performance trends: {str(e)}")
            print(f"Performance trends error: {e}")

    def analyze_distribution_by_course_gui(self):
        """Analyze grade distribution by course"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to analyze grade distribution.")
            return

        try:
            if CURVE_ANALYSIS_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

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
                messagebox.showerror("Error", "Distribution analysis by course not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to analyze distribution by course: {str(e)}")
            print(f"Distribution by course error: {e}")

    def analyze_distribution_by_module_type_gui(self):
        """Analyze grade distribution by module type"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to analyze grade distribution.")
            return

        try:
            if CURVE_ANALYSIS_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

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
                messagebox.showerror("Error", "Distribution analysis by module type not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to analyze distribution by module type: {str(e)}")
            print(f"Distribution by module type error: {e}")

    def analyze_overall_distribution_gui(self):
        """Analyze overall grade distribution"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to analyze overall distribution.")
            return

        try:
            if CURVE_ANALYSIS_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

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
                messagebox.showerror("Error", "Overall distribution analysis not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to analyze overall distribution: {str(e)}")
            print(f"Overall distribution error: {e}")

    def dropout_risk_analysis_gui(self):
        """Analyze dropout risk factors"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to analyze dropout risk.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('view_risk_analysis')):
            messagebox.showerror("Error", "You don't have permission to view dropout risk analysis.")
            return

        try:
            if CURVE_ANALYSIS_AVAILABLE:
                thread = threading.Thread(target=dropout_risk_analysis, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Dropout risk analysis not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to analyze dropout risk: {str(e)}")
            print(f"Dropout risk analysis error: {e}")

    # Competency Assessment Functions
    def manage_competency_levels_gui(self):
        """Manage competency levels - view, add, edit, delete"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to manage competency levels.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('manage_competencies')):
            messagebox.showerror("Error", "You don't have permission to manage competency levels.")
            return

        try:
            if COMPETENCY_ASSESSMENT_AVAILABLE:
                thread = threading.Thread(target=manage_competency_levels, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Competency levels management not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to manage competency levels: {str(e)}")
            print(f"Competency levels management error: {e}")

    def add_competency_levels_gui(self, competency_id=None, competency_name=None):
        """Add proficiency levels for a competency"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to add competency levels.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('manage_competencies')):
            messagebox.showerror("Error", "You don't have permission to add competency levels.")
            return

        try:
            if COMPETENCY_ASSESSMENT_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

                # If parameters not provided, prompt for them
                if not competency_id:
                    competency_id = simpledialog.askinteger(
                        "Competency ID",
                        "Enter Competency ID:",
                        parent=self.root
                    )

                    if not competency_id:
                        return

                if not competency_name:
                    competency_name = simpledialog.askstring(
                        "Competency Name",
                        "Enter Competency Name:",
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
                messagebox.showerror("Error", "Add competency levels not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add competency levels: {str(e)}")
            print(f"Add competency levels error: {e}")

    def view_student_competency_profile_gui(self):
        """View a student's competency profile"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to view competency profiles.")
            return

        try:
            if COMPETENCY_ASSESSMENT_AVAILABLE:
                thread = threading.Thread(target=view_student_competency_profile, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "View student competency profile not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to view competency profile: {str(e)}")
            print(f"View competency profile error: {e}")

    def generate_competency_report_gui(self):
        """Generate comprehensive competency report menu"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to generate competency reports.")
            return

        try:
            if COMPETENCY_ASSESSMENT_AVAILABLE:
                thread = threading.Thread(target=generate_competency_report, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Generate competency report not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate competency report: {str(e)}")
            print(f"Generate competency report error: {e}")

    def generate_student_competency_report_gui(self, student_id=None):
        """Generate detailed competency report for a student"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to generate student competency reports.")
            return

        try:
            if COMPETENCY_ASSESSMENT_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

                # If no student_id provided, prompt for one
                if not student_id:
                    student_id = simpledialog.askstring(
                        "Student ID",
                        "Enter Student ID:",
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
                messagebox.showerror("Error", "Generate student competency report not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate student competency report: {str(e)}")
            print(f"Generate student competency report error: {e}")

    def generate_course_competency_report_gui(self, course=None):
        """Generate competency report for a course"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to generate course competency reports.")
            return

        try:
            if COMPETENCY_ASSESSMENT_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

                # If no course provided, prompt for one
                if not course:
                    course = simpledialog.askstring(
                        "Course",
                        "Enter Course Name:",
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
                messagebox.showerror("Error", "Generate course competency report not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate course competency report: {str(e)}")
            print(f"Generate course competency report error: {e}")

    def assess_comprehensive_student_risk_gui(self, student_id=None):
        """Assess comprehensive risk for a student"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to assess student risk.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('view_risk_analysis')):
            messagebox.showerror("Error", "You don't have permission to assess student risk.")
            return

        try:
            if COMPETENCY_ASSESSMENT_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

                # If no student_id provided, prompt for one
                if not student_id:
                    student_id = simpledialog.askstring(
                        "Student ID",
                        "Enter Student ID:",
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
                messagebox.showerror("Error", "Comprehensive student risk assessment not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to assess student risk: {str(e)}")
            print(f"Assess student risk error: {e}")

    # Predictive Analytics Functions
    def identify_at_risk_students_gui(self):
        """Identify students at risk of academic failure"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to identify at-risk students.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('view_risk_analysis')):
            messagebox.showerror("Error", "You don't have permission to identify at-risk students.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                thread = threading.Thread(target=identify_at_risk_students, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Identify at-risk students not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to identify at-risk students: {str(e)}")
            print(f"Identify at-risk students error: {e}")

    def calculate_risk_factors_gui(self, student_id=None):
        """Calculate risk factors for a student"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to calculate risk factors.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

                # If no student_id provided, prompt for one
                if not student_id:
                    student_id = simpledialog.askstring(
                        "Student ID",
                        "Enter Student ID:",
                        parent=self.root
                    )

                    if not student_id:
                        return

                def calculate():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        risk_score, risk_factors = calculate_risk_factors(cursor, student_id)
                        print(f"Risk Score: {risk_score}")
                        print(f"Risk Factors: {risk_factors}")
                        conn.close()
                    except Exception as e:
                        print(f"Error calculating risk factors: {e}")

                thread = threading.Thread(target=calculate, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Calculate risk factors not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to calculate risk factors: {str(e)}")
            print(f"Calculate risk factors error: {e}")

    def early_warning_system_gui(self):
        """Implement early warning system for at-risk students"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to use early warning system.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('view_risk_analysis')):
            messagebox.showerror("Error", "You don't have permission to use early warning system.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                thread = threading.Thread(target=early_warning_system, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Early warning system not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to run early warning system: {str(e)}")
            print(f"Early warning system error: {e}")

    def generate_early_warning_alert_gui(self, student_id=None):
        """Generate early warning alert for a student"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to generate early warning alerts.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('generate_alerts')):
            messagebox.showerror("Error", "You don't have permission to generate alerts.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

                # If no student_id provided, prompt for one
                if not student_id:
                    student_id = simpledialog.askstring(
                        "Student ID",
                        "Enter Student ID:",
                        parent=self.root
                    )

                    if not student_id:
                        return

                def generate_alert():
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

                        # Calculate risk
                        risk_score, _ = calculate_risk_factors(cursor, student_id)

                        # Determine risk level
                        if risk_score >= 70:
                            risk_level = "High"
                        elif risk_score >= 40:
                            risk_level = "Medium"
                        else:
                            risk_level = "Low"

                        generate_early_warning_alert(cursor, student_id, first_name, last_name, course, email, risk_score, risk_level)
                        conn.close()
                    except Exception as e:
                        print(f"Error generating early warning alert: {e}")

                thread = threading.Thread(target=generate_alert, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Generate early warning alert not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate early warning alert: {str(e)}")
            print(f"Generate early warning alert error: {e}")

    def export_at_risk_students_gui(self, at_risk_students=None, threshold=None):
        """Export at-risk students list to file"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to export at-risk students.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                if at_risk_students and threshold is not None:
                    export_at_risk_students(at_risk_students, threshold)
                    messagebox.showinfo("Success", "At-risk students list exported successfully")
                else:
                    messagebox.showinfo("Info", "Please identify at-risk students first.")
            else:
                messagebox.showerror("Error", "Export at-risk students not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export at-risk students: {str(e)}")
            print(f"Export at-risk students error: {e}")

    def export_early_warning_alerts_gui(self, alerts=None):
        """Export early warning alerts to file"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to export alerts.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                if alerts:
                    export_early_warning_alerts(alerts)
                    messagebox.showinfo("Success", "Early warning alerts exported successfully")
                else:
                    messagebox.showinfo("Info", "Please generate early warning alerts first.")
            else:
                messagebox.showerror("Error", "Export early warning alerts not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export alerts: {str(e)}")
            print(f"Export alerts error: {e}")

    def export_dropout_risk_list_gui(self, high_risk_students=None):
        """Export dropout risk list to file"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to export dropout risk list.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                if high_risk_students:
                    export_dropout_risk_list(high_risk_students)
                    messagebox.showinfo("Success", "Dropout risk list exported successfully")
                else:
                    messagebox.showinfo("Info", "Please identify high dropout risk students first.")
            else:
                messagebox.showerror("Error", "Export dropout risk list not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export dropout risk list: {str(e)}")
            print(f"Export dropout risk list error: {e}")

    def build_at_risk_prediction_model_gui(self):
        """Build ML model to predict at-risk students"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to build prediction models.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('use_ml_models')):
            messagebox.showerror("Error", "You don't have permission to build ML models.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

                def build_model():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        build_at_risk_prediction_model(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error building at-risk prediction model: {e}")

                thread = threading.Thread(target=build_model, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Build at-risk prediction model not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to build prediction model: {str(e)}")
            print(f"Build prediction model error: {e}")

    def analyze_dropout_risk_factors_gui(self):
        """Analyze common dropout risk factors"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to analyze dropout risk factors.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('view_risk_analysis')):
            messagebox.showerror("Error", "You don't have permission to analyze dropout risk factors.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

                def analyze():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        analyze_dropout_risk_factors(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error analyzing dropout risk factors: {e}")

                thread = threading.Thread(target=analyze, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Analyze dropout risk factors not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to analyze dropout risk factors: {str(e)}")
            print(f"Analyze dropout risk factors error: {e}")

    def build_dropout_prediction_model_gui(self):
        """Build predictive model for dropout risk"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to build dropout prediction model.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('use_ml_models')):
            messagebox.showerror("Error", "You don't have permission to build ML models.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

                def build_model():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        build_dropout_prediction_model(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error building dropout prediction model: {e}")

                thread = threading.Thread(target=build_model, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Build dropout prediction model not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to build dropout prediction model: {str(e)}")
            print(f"Build dropout prediction model error: {e}")

    def generate_dropout_interventions_gui(self):
        """Generate dropout prevention interventions"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to generate interventions.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('generate_interventions')):
            messagebox.showerror("Error", "You don't have permission to generate interventions.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

                def generate():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        generate_dropout_interventions(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error generating dropout interventions: {e}")

                thread = threading.Thread(target=generate, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Generate dropout interventions not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate interventions: {str(e)}")
            print(f"Generate interventions error: {e}")

    def generate_dropout_intervention_plan_gui(self, student_id=None):
        """Generate individual dropout intervention plan"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to generate intervention plans.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('generate_interventions')):
            messagebox.showerror("Error", "You don't have permission to generate intervention plans.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

                # If no student_id provided, prompt for one
                if not student_id:
                    student_id = simpledialog.askstring(
                        "Student ID",
                        "Enter Student ID:",
                        parent=self.root
                    )

                    if not student_id:
                        return

                def generate_plan():
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
                        generate_dropout_intervention_plan(cursor, student_id, first_name, last_name, course, email)
                        conn.close()
                    except Exception as e:
                        print(f"Error generating intervention plan: {e}")

                thread = threading.Thread(target=generate_plan, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Generate dropout intervention plan not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate intervention plan: {str(e)}")
            print(f"Generate intervention plan error: {e}")

    def identify_high_dropout_risk_gui(self):
        """Identify students at high risk of dropping out"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to identify high dropout risk students.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('view_risk_analysis')):
            messagebox.showerror("Error", "You don't have permission to identify high dropout risk students.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

                def identify():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        identify_high_dropout_risk(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error identifying high dropout risk students: {e}")

                thread = threading.Thread(target=identify, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Identify high dropout risk not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to identify high dropout risk students: {str(e)}")
            print(f"Identify high dropout risk error: {e}")

    def calculate_dropout_risk_score_gui(self, student_id=None):
        """Calculate dropout risk score for a student"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to calculate dropout risk score.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

                # If no student_id provided, prompt for one
                if not student_id:
                    student_id = simpledialog.askstring(
                        "Student ID",
                        "Enter Student ID:",
                        parent=self.root
                    )

                    if not student_id:
                        return

                def calculate():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        risk_score = calculate_dropout_risk_score(cursor, student_id)
                        print(f"Dropout Risk Score for {student_id}: {risk_score}")
                        conn.close()
                    except Exception as e:
                        print(f"Error calculating dropout risk score: {e}")

                thread = threading.Thread(target=calculate, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Calculate dropout risk score not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to calculate dropout risk score: {str(e)}")
            print(f"Calculate dropout risk score error: {e}")

    def generate_risk_report_gui(self):
        """Generate comprehensive risk assessment report"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to generate risk reports.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('view_reports')):
            messagebox.showerror("Error", "You don't have permission to generate risk reports.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                thread = threading.Thread(target=generate_risk_report, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Generate risk report not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate risk report: {str(e)}")
            print(f"Generate risk report error: {e}")

    def collect_comprehensive_risk_data_gui(self):
        """Collect comprehensive risk assessment data"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to collect risk data.")
            return None

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                from university_system.infrastructure.database.db import get_connection

                conn = get_connection()
                cursor = conn.cursor()
                risk_data = collect_comprehensive_risk_data(cursor)
                conn.close()
                return risk_data
            else:
                messagebox.showerror("Error", "Collect risk data not available.")
                return None
        except Exception as e:
            messagebox.showerror("Error", f"Failed to collect risk data: {str(e)}")
            print(f"Collect risk data error: {e}")
            return None

    def generate_comprehensive_risk_report_gui(self, risk_data=None):
        """Generate comprehensive risk assessment report"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to generate comprehensive risk reports.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('view_reports')):
            messagebox.showerror("Error", "You don't have permission to generate comprehensive risk reports.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                if not risk_data:
                    risk_data = self.collect_comprehensive_risk_data_gui()

                if risk_data:
                    def generate():
                        generate_comprehensive_risk_report(risk_data)

                    thread = threading.Thread(target=generate, daemon=True)
                    thread.start()
            else:
                messagebox.showerror("Error", "Generate comprehensive risk report not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate comprehensive risk report: {str(e)}")
            print(f"Generate comprehensive risk report error: {e}")