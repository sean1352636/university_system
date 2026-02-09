# Auto-generated module for Student Success & Engagement GUIs
import tkinter as tk
from tkinter import ttk, messagebox
import logging

# Import GUI launchers
from university_system.modules.shared.gui.main.imports.gui_imports import (
    launch_advanced_attendance_gui,
    launch_mental_health_gui,
    launch_early_warning_gui,
    launch_career_services_gui,
)

# Alias for translation function
from university_system.modules.shared.utils.i18n import get_text as _t

logger = logging.getLogger(__name__)

def show_academic_progress_gui(self):
    """Launch Academic Progress Dashboard GUI"""
    try:
        from university_system.modules.domain.academic_progress.gui.progress_gui import AcademicProgressGUI
        # AcademicProgressGUI creates its own window
        gui = AcademicProgressGUI(parent=self.root)
    except ImportError as e:
        logger.error(f"Failed to import Academic Progress GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Academic Progress", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Academic Progress GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Academic Progress", error=str(e)))

def show_ai_study_gui(self):
    """Launch AI Study Companion GUI"""
    try:
        from university_system.modules.domain.ai_study.gui.ai_study_gui import AIStudyGUI
        # AIStudyGUI creates its own window
        gui = AIStudyGUI(parent=self.root)
    except ImportError as e:
        logger.error(f"Failed to import AI Study GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="AI Study", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching AI Study GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="AI Study", error=str(e)))

def show_budget_tracker_gui(self):
    """Launch Budget Tracker GUI"""
    try:
        from university_system.modules.domain.budget.gui.budget_gui import BudgetTrackerGUI
        from university_system.infrastructure.shared_context import get_auth
        auth = get_auth()
        gui = BudgetTrackerGUI(parent=self.root, auth=auth)
    except ImportError as e:
        logger.error(f"Failed to import Budget Tracker GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Budget Tracker", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Budget Tracker GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Budget Tracker", error=str(e)))

def show_student_jobs_gui(self):
    """Launch Student Job Board GUI"""
    try:
        from university_system.modules.domain.student_jobs.gui.jobs_gui import StudentJobsGUI
        from university_system.infrastructure.shared_context import get_auth
        auth = get_auth()
        gui = StudentJobsGUI(parent=self.root, auth=auth)
    except ImportError as e:
        logger.error(f"Failed to import Student Jobs GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Student Jobs", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Student Jobs GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Student Jobs", error=str(e)))

def show_scholarship_finder_gui(self):
    """Launch Scholarship Finder GUI"""
    try:
        from university_system.modules.domain.scholarship_finder.gui.scholarship_gui import ScholarshipFinderGUI
        gui = ScholarshipFinderGUI(parent=self.root)
    except ImportError as e:
        logger.error(f"Failed to import Scholarship Finder GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Scholarship Finder", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Scholarship Finder GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Scholarship Finder", error=str(e)))

def show_study_matching_gui(self):
    """Launch Peer Study Matching GUI"""
    try:
        from university_system.modules.domain.study_matching.gui.study_matching_gui import StudyMatchingGUI
        gui = StudyMatchingGUI(parent=self.root)
    except ImportError as e:
        logger.error(f"Failed to import Study Matching GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Study Matching", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Study Matching GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Study Matching", error=str(e)))

def show_course_planning_gui(self):
    """Launch Course Planning Assistant GUI"""
    try:
        from university_system.modules.domain.course_planning.gui.course_planning_gui import CoursePlanningGUI
        from university_system.infrastructure.shared_context import get_auth
        auth = get_auth()
        # CoursePlanningGUI creates its own Toplevel window
        gui = CoursePlanningGUI(root=self.root, auth=auth)
    except ImportError as e:
        logger.error(f"Failed to import Course Planning GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Course Planning", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Course Planning GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Course Planning", error=str(e)))

def show_roommate_finder_gui(self):
    """Launch Roommate Finder GUI"""
    try:
        from university_system.modules.domain.roommate_finder.gui.roommate_gui import RoommateFinderGUI
        gui = RoommateFinderGUI(parent=self.root)
    except ImportError as e:
        logger.error(f"Failed to import Roommate Finder GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Roommate Finder", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Roommate Finder GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Roommate Finder", error=str(e)))

def show_campus_navigation_gui(self):
    """Launch Campus Navigation GUI"""
    try:
        import tkinter as tk
        from university_system.modules.domain.campus_navigation.gui.navigation_gui import NavigationGUI
        # Create a new Toplevel window
        window = tk.Toplevel(self.root)
        window.title(_t("student_success.windows.campus_navigation"))
        window.geometry("1200x800")
        gui = NavigationGUI(parent=window)
    except ImportError as e:
        logger.error(f"Failed to import Campus Navigation GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Campus Navigation", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Campus Navigation GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Campus Navigation", error=str(e)))

def show_lost_found_gui(self):
    """Launch Lost & Found GUI"""
    try:
        from university_system.modules.domain.lost_found.gui.lost_found_gui import LostFoundGUI
        gui = LostFoundGUI(parent=self.root)
    except ImportError as e:
        logger.error(f"Failed to import Lost & Found GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Lost & Found", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Lost & Found GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Lost & Found", error=str(e)))

def show_marketplace_gui(self):
    """Launch Student Marketplace GUI"""
    try:
        from university_system.modules.domain.marketplace.gui.marketplace_gui import MarketplaceGUI
        gui = MarketplaceGUI(parent=self.root)
    except ImportError as e:
        logger.error(f"Failed to import Student Marketplace GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Student Marketplace", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Student Marketplace GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Student Marketplace", error=str(e)))

def show_wellness_hub_gui(self):
    """Launch Wellness Hub GUI"""
    try:
        from university_system.modules.domain.wellness.gui.wellness_gui import WellnessGUI
        gui = WellnessGUI(parent=self.root)
    except ImportError as e:
        logger.error(f"Failed to import Wellness Hub GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Wellness Hub", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Wellness Hub GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Wellness Hub", error=str(e)))

def show_accessibility_portal_gui(self):
    """Launch Accessibility Portal GUI"""
    try:
        from university_system.modules.domain.accessibility.gui.accessibility_gui import AccessibilityGUI
        gui = AccessibilityGUI(parent=self.root)
    except ImportError as e:
        logger.error(f"Failed to import Accessibility Portal GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Accessibility Portal", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Accessibility Portal GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Accessibility Portal", error=str(e)))

def show_events_discovery_gui(self):
    """Launch Events Discovery GUI"""
    try:
        import tkinter as tk
        from university_system.modules.domain.events.gui.events_gui import EventsGUI
        # Create a new Toplevel window
        window = tk.Toplevel(self.root)
        window.title(_t("student_success.windows.event_discovery"))
        window.geometry("1400x800")
        gui = EventsGUI(parent=window)
    except ImportError as e:
        logger.error(f"Failed to import Events Discovery GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Events Discovery", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Events Discovery GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Events Discovery", error=str(e)))

def show_social_matching_gui(self):
    """Launch Social Matching GUI"""
    try:
        from university_system.modules.domain.social_matching.gui.social_matching_gui import SocialMatchingGUI
        gui = SocialMatchingGUI(parent=self.root)
    except ImportError as e:
        logger.error(f"Failed to import Social Matching GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Social Matching", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Social Matching GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Social Matching", error=str(e)))

def show_portfolio_system_gui(self):
    """Launch Portfolio System GUI"""
    try:
        from university_system.modules.domain.portfolio.gui.portfolio_gui import PortfolioGUI
        gui = PortfolioGUI(parent=self.root)
    except ImportError as e:
        logger.error(f"Failed to import Portfolio System GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Portfolio System", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Portfolio System GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Portfolio System", error=str(e)))

def show_notifications_hub_gui(self):
    """Launch Email Manager with Notifications tab focused"""
    try:
        # Import email manager GUI
        from university_system.modules.shared.gui.email.email_gui.email_manager_main import EmailManagerGUI
        import tkinter as tk

        # Create new window for email manager
        email_window = tk.Toplevel(self.root)
        email_window.title(_t("student_success.windows.communication_center"))
        email_window.geometry("1200x800")

        # Create email manager GUI
        email_gui = EmailManagerGUI(email_window, auth=self.auth)

        # Switch to notifications tab after window is created
        if hasattr(email_gui, 'show_notifications_tab'):
            email_window.after(100, email_gui.show_notifications_tab)

        logger.info("Opened Email Manager with Notifications tab")
    except ImportError as e:
        logger.error(f"Failed to import Email Manager GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Email Manager", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Email Manager: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Email Manager", error=str(e)))

def show_feedback_system_gui(self):
    """Launch Feedback System GUI"""
    try:
        from university_system.modules.domain.feedback.gui.feedback_gui import FeedbackGUI
        gui = FeedbackGUI(parent=self.root)
    except ImportError as e:
        logger.error(f"Failed to import Feedback System GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Feedback System", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Feedback System GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Feedback System", error=str(e)))
