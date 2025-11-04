"""Main Assignment GUI - coordinates all manager classes"""

import tkinter as tk
from tkinter import ttk, messagebox
from university_system.infrastructure.database.db import DEFAULT_DB_PATH

# Import all manager classes
from university_system.modules.domain.academics.gui.assignment_system.db_manager import DatabaseManager
from university_system.modules.domain.academics.gui.assignment_system.layout_manager import LayoutManager
from university_system.modules.domain.academics.gui.assignment_system.dashboard import DashboardManager
from university_system.modules.domain.academics.gui.assignment_system.assignment_manager import AssignmentManager
from university_system.modules.domain.academics.gui.assignment_system.submission_manager import SubmissionManager
from university_system.modules.domain.academics.gui.assignment_system.template_manager import TemplateManager
from university_system.modules.domain.academics.gui.assignment_system.extension_manager import ExtensionManager
from university_system.modules.domain.academics.gui.assignment_system.grading_manager import GradingManager
from university_system.modules.domain.academics.gui.assignment_system.group_manager import GroupManager
from university_system.modules.domain.academics.gui.assignment_system.messaging import MessagingManager
from university_system.modules.domain.academics.gui.assignment_system.notifications import NotificationManager
from university_system.modules.domain.academics.gui.assignment_system.analytics import AnalyticsManager
from university_system.modules.domain.academics.gui.assignment_system.file_preview import FilePreviewManager
from university_system.modules.domain.academics.gui.assignment_system.assessment_manager import AssessmentManager
from university_system.modules.domain.academics.gui.assignment_system.rubric_manager import RubricManager
from university_system.modules.domain.academics.gui.assignment_system.peer_review import PeerReviewManager
from university_system.modules.domain.academics.gui.assignment_system.maintenance import MaintenanceManager


class AssignmentGUI:
    """Main GUI class that coordinates all managers"""

    def __init__(self, assignment_system, auth, parent=None):
        self.assignment_system = assignment_system
        self.auth = auth

        # Add missing methods to assignment system if needed
        self._ensure_assignment_system_methods()

        if parent is not None:
            self.root = parent
            self.is_standalone = False
        else:
            self.root = tk.Tk()
            self.is_standalone = True

        self.root.title("Assignment & Assessment Management System")
        self.root.geometry("1200x800")
        self.root.configure(bg='#f0f0f0')

        # Style configuration
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Initialize variables
        self.current_frame = None
        self.notification_count = 0

        # Initialize all manager classes
        self.db = DatabaseManager(self)
        self.layout = LayoutManager(self)
        self.dashboard = DashboardManager(self)
        self.assignments = AssignmentManager(self)
        self.submissions = SubmissionManager(self)
        self.templates = TemplateManager(self)
        self.extensions = ExtensionManager(self)
        self.grading = GradingManager(self)
        self.groups = GroupManager(self)
        self.messaging = MessagingManager(self)
        self.notifications_mgr = NotificationManager(self)
        self.analytics = AnalyticsManager(self)
        self.file_preview = FilePreviewManager(self)
        self.assessments = AssessmentManager(self)
        self.rubrics = RubricManager(self)
        self.peer_review = PeerReviewManager(self)
        self.maintenance = MaintenanceManager(self)

        # Initialize database and interface
        self.db.ensure_database_exists()
        self.layout.configure_styles()
        self.layout.create_main_interface()
        self.notifications_mgr.update_notifications()

    def _ensure_assignment_system_methods(self):
        """Ensure assignment system has required methods"""
        # These will be set after managers are initialized
        pass

    def _check_permission(self, permission):
        """Check if user has permission"""
        try:
            return self.auth.check_permission(permission)
        except:
            return self.auth.user_role in ['Admin', 'Faculty']

    def _launch_gui_feature(self, callback, feature_name):
        """Launch a GUI feature with error handling"""
        try:
            callback()
        except Exception as e:
            messagebox.showerror("Error", f"Error launching {feature_name}: {str(e)}")

    def logout(self):
        """Logout and return to main menu"""
        if self.is_standalone:
            self.root.destroy()
        else:
            self.root.destroy()

    def run(self):
        """Start the GUI mainloop"""
        if self.is_standalone:
            self.root.mainloop()

    # Delegate method calls to appropriate managers
    def display_main_menu(self, *args, **kwargs):
        return self.layout.create_main_interface(*args, **kwargs)

    def set_auth(self, auth):
        self.auth = auth

    # Backward compatibility methods - delegate to managers
    def show_dashboard(self):
        return self.dashboard.show_dashboard()

    def show_my_assignments(self):
        return self.assignments.show_my_assignments()

    def show_submit_assignment(self):
        return self.submissions.show_submit_assignment()

    def show_my_submissions(self):
        return self.submissions.show_my_submissions()

    def show_create_assignment(self):
        return self.assignments.show_create_assignment()

    def show_manage_assignments(self):
        return self.assignments.show_manage_assignments()

    def show_grade_submissions(self):
        return self.grading.show_grade_submissions()

    def show_analytics(self):
        return self.analytics.show_analytics()

    def show_notifications(self):
        return self.notifications_mgr.show_notifications()

    def show_extension_request(self):
        return self.extensions.show_extension_request()

    def show_review_extensions(self):
        return self.extensions.show_review_extensions()

    def show_send_messages(self):
        return self.messaging.show_send_messages()

    def view_messages(self):
        return self.messaging.view_messages()

    def show_manage_groups(self):
        return self.groups.show_manage_groups()

    def show_create_group_assignment(self):
        return self.groups.show_create_group_assignment()

    def show_templates(self):
        return self.templates.show_templates()

    def show_file_preview(self):
        return self.file_preview.show_file_preview()

    def show_calendar(self):
        return self.file_preview.show_calendar()

    def manage_assessments(self):
        return self.assessments.manage_assessments()

    def manage_rubrics(self):
        return self.rubrics.manage_rubrics()

    def manage_peer_reviews(self):
        return self.peer_review.manage_peer_reviews()

    def system_maintenance(self):
        return self.maintenance.system_maintenance()

    def show_system_backup(self):
        return self.maintenance.show_system_backup()

    def cleanup_old_data(self):
        return self.maintenance.cleanup_old_data()

    def show_peer_review_dashboard(self):
        return self.peer_review.show_peer_review_dashboard()

    def complete_peer_reviews(self):
        return self.peer_review.complete_peer_reviews()

    def generate_advanced_analytics(self):
        return self.analytics.generate_advanced_analytics()

    def generate_custom_reports(self):
        return self.analytics.generate_custom_reports()

    def grade_with_rubrics(self):
        return self.grading.grade_with_rubrics()

    def manage_notifications(self):
        return self.notifications_mgr.manage_notifications()

    def show_admin_all_assignments(self):
        return self.assignments.show_admin_all_assignments()

    def show_create_assessment(self):
        return self.assessments.show_create_assessment()

    def show_manage_assessments(self):
        return self.assessments.show_manage_assessments()

    def show_create_rubric(self):
        return self.rubrics.show_create_rubric()

    def view_all_submissions(self):
        return self.submissions.view_all_submissions()


def launch_gui(assignment_system, auth):
    """Launch the assignment GUI"""
    gui = AssignmentGUI(assignment_system, auth)
    gui.run()


def display_assignment_menu_gui(auth):
    """Display assignment menu in GUI mode"""
    from university_system.modules.academics.services.assignment_submission import AssignmentSubmission
    assignment_system = AssignmentSubmission()
    launch_gui(assignment_system, auth)


def display_assignment_menu(auth):
    """Wrapper for backward compatibility"""
    display_assignment_menu_gui(auth)
