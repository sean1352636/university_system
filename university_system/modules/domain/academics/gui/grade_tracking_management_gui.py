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