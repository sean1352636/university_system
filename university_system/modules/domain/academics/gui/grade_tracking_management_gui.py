import tkinter as tk
from tkinter import ttk, messagebox
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