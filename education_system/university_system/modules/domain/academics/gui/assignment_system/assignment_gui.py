"""Main Assignment GUI - coordinates all manager classes"""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH
from education_system.university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()

# Import all manager classes
from education_system.university_system.modules.domain.academics.gui.assignment_system.db_manager import DatabaseManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.layout_manager import LayoutManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.dashboard import DashboardManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.assignment_manager import AssignmentManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.submission_manager import SubmissionManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.template_manager import TemplateManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.extension_manager import ExtensionManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.grading_manager import GradingManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.group_manager import GroupManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.messaging import MessagingManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.notifications import NotificationManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.analytics import AnalyticsManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.file_preview import FilePreviewManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.assessment_manager import AssessmentManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.rubric_manager import RubricManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.peer_review import PeerReviewManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.maintenance import MaintenanceManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.auto_grading_manager import AutoGradingManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.exam_integrity_manager import ExamIntegrityManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.student_experience_manager import StudentExperienceManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.grade_dispute_manager import GradeDisputeManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.late_policy_manager import LatePolicyManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.annotation_manager import AnnotationManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.multi_stage_manager import MultiStageManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.admin_tools_manager import AdminToolsManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.ai_assistant_manager import AIAssistantManager
from education_system.university_system.modules.domain.academics.gui.assignment_system.integrations_manager import IntegrationsManager

class AssignmentGUI:
    """Main GUI class that coordinates all managers"""

    def __init__(self, assignment_system, auth, parent=None):
        self.assignment_system = assignment_system
        self.auth = auth

        if parent is not None:
            self.root = parent
            self.is_standalone = False
        else:
            self.root = tk.Tk()
            self.is_standalone = True

        self.root.title(_("assignment.title"))
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
        self.auto_grading = AutoGradingManager(self)
        self.exam_integrity = ExamIntegrityManager(self)
        self.student_experience = StudentExperienceManager(self)
        self.grade_disputes = GradeDisputeManager(self)
        self.late_policies = LatePolicyManager(self)
        self.annotations = AnnotationManager(self)
        self.multi_stage = MultiStageManager(self)
        self.admin_tools = AdminToolsManager(self)
        self.ai_assistant = AIAssistantManager(self)
        self.integrations = IntegrationsManager(self)

        # Initialize database and interface
        self.db.ensure_database_exists()
        self.layout.configure_styles()
        self.layout.create_main_interface()
        self.notifications_mgr.update_notifications()

    def _ensure_assignment_system_methods(self):
        """
        Ensure assignment system has required methods

        Validates that all manager classes are properly initialized and
        sets up any required cross-references between managers.
        This is called after all managers are initialized in __init__.
        """
        # Verify all managers are initialized
        required_managers = [
            'db', 'layout', 'dashboard', 'assignments', 'submissions',
            'templates', 'extensions', 'grading', 'groups', 'messaging',
            'notifications_mgr', 'analytics', 'file_preview', 'assessments',
            'rubrics', 'peer_review', 'maintenance', 'auto_grading',
            'exam_integrity', 'student_experience', 'grade_disputes',
            'late_policies', 'annotations', 'multi_stage', 'admin_tools',
            'ai_assistant', 'integrations'
        ]

        for manager_name in required_managers:
            if not hasattr(self, manager_name):
                print(_("assignment.warnings.manager_not_initialized").format(manager_name=manager_name))

        # Set up cross-references if needed
        # (Managers can now reference each other through self.app)
        # All managers already have self.app reference from their initialization

        # Validate database connectivity
        try:
            self.db.ensure_database_exists()
        except Exception as e:
            print(_("assignment.warnings.database_validation_failed").format(error=str(e)))

    def _check_permission(self, permission):
        """Check if user has permission"""
        try:
            return self.auth.check_permission(permission)
        except (AttributeError, Exception):
            return self.auth.user_role in ['Admin', 'Faculty']

    def get_user_role(self):
        """Get the current user's role from authentication system"""
        try:
            if hasattr(self.auth, 'current_user') and self.auth.current_user:
                role = self.auth.current_user.get('role', '').lower()
                return role
            elif hasattr(self.auth, 'user_role'):
                return self.auth.user_role.lower()
            return None
        except Exception as e:
            print(_("assignment.errors.get_user_role").format(error=str(e)))
            return None

    def is_admin(self):
        """Check if current user is admin"""
        role = self.get_user_role()
        return role == 'admin'

    def is_staff(self):
        """Check if current user is staff/instructor/faculty"""
        role = self.get_user_role()
        return role in ['staff', 'instructor', 'faculty']

    def is_student(self):
        """Check if current user is student"""
        role = self.get_user_role()
        return role == 'student'

    def show_plagiarism_checker(self):
        """Launch the Plagiarism Checker GUI"""
        try:
            from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui import PlagiarismCheckerGUI
            import tkinter as _tk
            plagiarism_window = _tk.Toplevel(self.root)
            plagiarism_window.title(_("ai_features.window_titles.plagiarism_detection"))
            plagiarism_window.geometry("1200x800")
            PlagiarismCheckerGUI(plagiarism_window, self.auth)
        except Exception as e:
            messagebox.showerror(_("common.error"), _("ai_features.messages.plagiarism_launch_error").format(error=str(e)))

    def show_ai_detector(self):
        """Launch the AI Content Detector GUI"""
        try:
            from education_system.university_system.modules.domain.academics.gui.ai_detector import AIDetectorGUI
            import tkinter as _tk
            ai_window = _tk.Toplevel(self.root)
            ai_window.title(_("ai_features.window_titles.ai_content_detector"))
            ai_window.geometry("1000x700")
            AIDetectorGUI(ai_window, self.auth)
        except Exception as e:
            messagebox.showerror(_("common.error"), _("ai_features.messages.ai_detector_launch_error").format(error=str(e)))

    def show_academic_misconduct(self):
        """Launch the Academic Misconduct Panel GUI"""
        try:
            from education_system.shared.academic_misconduct.academic_misconduct_gui import AcademicMisconductPanel
            import tkinter as _tk
            window = _tk.Toplevel(self.root)
            window.title("Academic Misconduct")
            window.geometry("1200x800")
            AcademicMisconductPanel(window, system_key='university')
        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to open Academic Misconduct: {e}")

    def show_external_examiners(self):
        """Launch the External Examiner GUI"""
        try:
            from education_system.university_system.modules.domain.academics.external_examiners.gui.external_examiner_gui import ExternalExaminerGUI
            ExternalExaminerGUI(parent=self.root)
        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to open External Examiners: {e}")

    def _launch_gui_feature(self, callback, feature_name):
        """Launch a GUI feature with error handling"""
        try:
            callback()
        except Exception as e:
            messagebox.showerror(_("common.error"), _("assignment.errors.launch_feature").format(feature_name=feature_name, error=str(e)))

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

    def create_assignment(self, *args, **kwargs):
        """Create new assignment (wrapper for GUI)"""
        return self.assignments.show_create_assignment()

    def submit_assignment(self, *args, **kwargs):
        """Submit assignment (student wrapper for GUI)"""
        return self.submissions.show_student_submissions()

    def add_assignment_permissions(self):
        """Add assignment permissions to roles"""
        try:
            from education_system.university_system.infrastructure.auth.authorization import add_permission

            # Define assignment-related permissions
            permissions = [
                ('view_assignments', 'View assignments'),
                ('create_assignments', 'Create new assignments'),
                ('edit_assignments', 'Edit assignments'),
                ('delete_assignments', 'Delete assignments'),
                ('manage_assignments', 'Manage all assignments'),
                ('grade_assignments', 'Grade assignments'),
                ('view_all_submissions', 'View all submissions'),
                ('manage_groups', 'Manage assignment groups'),
                ('manage_peer_reviews', 'Manage peer reviews'),
                ('export_analytics', 'Export assignment analytics'),
            ]

            # Add permissions to database
            from education_system.university_system.infrastructure.database.db import sqlite3
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                for perm_code, perm_desc in permissions:
                    cursor.execute('''
                    INSERT OR IGNORE INTO permissions (code, description)
                    VALUES (?, ?)
                    ''', (perm_code, perm_desc))

                # Assign permissions to roles
                role_permissions = {
                    'Admin': ['manage_assignments', 'view_all_submissions', 'delete_assignments',
                             'manage_groups', 'manage_peer_reviews', 'export_analytics'],
                    'Faculty': ['view_assignments', 'create_assignments', 'edit_assignments',
                               'grade_assignments', 'view_all_submissions', 'manage_groups',
                               'manage_peer_reviews', 'export_analytics'],
                    'Student': ['view_assignments'],
                    'Staff': ['view_assignments', 'view_all_submissions']
                }

                for role, perms in role_permissions.items():
                    for perm_code in perms:
                        cursor.execute('''
                        INSERT OR IGNORE INTO role_permissions (role_name, permission_code)
                        VALUES (?, ?)
                        ''', (role, perm_code))

                conn.commit()
            finally:
                conn.close()

            messagebox.showinfo(_("common.success"), _("assignment.messages.permissions_configured"))

        except Exception as e:
            messagebox.showerror(_("common.error"), _("assignment.errors.add_permissions").format(error=str(e)))

    # ── Auto-Grading delegates ──

    def show_auto_grading(self):
        return self.auto_grading.show_auto_grading()

    def manage_question_banks(self):
        return self.auto_grading.manage_question_banks()

    def show_question_bank_stats(self):
        return self.auto_grading.show_question_bank_stats()

    # ── Exam Integrity delegates ──

    def show_exam_integrity_settings(self):
        return self.exam_integrity.show_exam_integrity_settings()

    def show_proctoring_dashboard(self):
        return self.exam_integrity.show_proctoring_dashboard()

    def view_integrity_logs(self):
        return self.exam_integrity.view_integrity_logs()

    # ── Student Experience delegates ��─

    def show_draft_manager(self):
        return self.student_experience.show_draft_manager()

    def show_progress_tracker(self):
        return self.student_experience.show_progress_tracker()

    def show_accessibility_settings(self):
        return self.student_experience.show_accessibility_settings()

    def show_countdown_timer(self):
        return self.student_experience.show_countdown_timer(None)

    # ── Grade Dispute delegates ──

    def show_dispute_form(self):
        return self.grade_disputes.show_dispute_form()

    def show_my_disputes(self):
        return self.grade_disputes.show_my_disputes()

    def show_regrade_queue(self):
        return self.grade_disputes.show_regrade_queue()

    def show_dispute_history(self):
        return self.grade_disputes.show_dispute_history()

    # ── Late Policy delegates ──

    def show_late_policies(self):
        return self.late_policies.show_late_policies()

    def show_late_submission_report(self):
        return self.late_policies.show_late_submission_report()

    # ── Annotation delegates ──

    def show_annotation_interface(self):
        return self.annotations.show_annotation_interface(None)

    def show_annotation_templates(self):
        return self.annotations.show_annotation_templates()

    def show_annotation_summary(self):
        return self.annotations.show_annotation_summary()

    # ── Multi-Stage delegates ──

    def show_multi_stage_assignments(self):
        return self.multi_stage.show_multi_stage_assignments()

    def create_multi_stage_assignment(self):
        return self.multi_stage.create_multi_stage_assignment()

    def show_external_submissions(self):
        return self.multi_stage.show_external_submissions()

    # ── Admin Tools delegates ──

    def show_sis_sync(self):
        return self.admin_tools.show_sis_sync()

    def show_integrity_cases(self):
        return self.admin_tools.show_integrity_cases()

    def show_grade_audit_log(self):
        return self.admin_tools.show_grade_audit_log()

    def show_accommodations(self):
        return self.admin_tools.show_accommodations()

    def show_ta_management(self):
        return self.admin_tools.show_ta_management()

    # ── AI Assistant delegates ──

    def show_ai_dashboard(self):
        return self.ai_assistant.show_ai_dashboard()

    def show_draft_feedback(self):
        return self.ai_assistant.show_draft_feedback()

    def show_practice_generator(self):
        return self.ai_assistant.show_practice_generator()

    def show_collusion_detector(self):
        return self.ai_assistant.show_collusion_detector()

    def show_late_pass_advisor(self):
        return self.ai_assistant.show_late_pass_advisor()

    # ── Integration delegates (parent_portal / library / attendance) ──

    def show_module_resources(self, module_code, student_id=None):
        return self.integrations.show_module_resources(module_code, student_id=student_id)

    def show_student_attendance(self, student_id, module_code):
        return self.integrations.show_student_attendance(student_id, module_code)

    def attendance_warning(self, student_id, module_code):
        return self.integrations.attendance_warning(student_id, module_code)

    def show_parent_assignments_view(self):
        return self.integrations.show_parent_assignments_view()

    def show_integrations_activity(self):
        return self.integrations.show_integrations_activity()

    def open_grade_management(self):
        """Launch the Grade Tracking / Management GUI alongside this one."""
        try:
            from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui.core import (
                GradeTrackingManagementGUI,
            )
            wrapper = GradeTrackingManagementGUI(self.root, self.auth)
            wrapper.show_grade_tracking_gui()
        except Exception as e:
            messagebox.showerror(
                _("common.error"),
                f"Failed to open Grade Management: {e}",
            )

    # Internal/Helper Functions

    def _init_directories(self):
        """Initialize submission directories"""
        try:
            from pathlib import Path
            from education_system.university_system.modules.shared.constants import paths

            # Create main directories
            directories = [
                paths.DATA_DIR / 'assignments',
                paths.SUBMISSIONS_DIR,
                paths.DATA_DIR / 'backups' / 'assignments',
                paths.DATA_DIR / 'temp' / 'assignments',
            ]

            for directory in directories:
                directory.mkdir(parents=True, exist_ok=True)

            return True

        except Exception as e:
            print(_("assignment.errors.init_directories").format(error=str(e)))
            return False

    def _init_db(self):
        """Initialize database connection"""
        return self.db.ensure_database_exists()

    def _update_existing_tables(self):
        """Update existing database tables"""
        try:
            from education_system.university_system.infrastructure.database.db import sqlite3
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Migrate notifications table
            self.db.migrate_notifications_table(cursor)

            # Migrate messages table
            self.db.migrate_messages_table(cursor)

            # Migrate peer review tables
            self.db.migrate_peer_review_tables(cursor)

            conn.commit()
            conn.close()

            return True

        except Exception as e:
            print(_("assignment.errors.update_tables").format(error=str(e)))
            return False

    def _get_student_id(self):
        """Get current student ID"""
        try:
            if self.auth and self.auth.current_user:
                user_role = self.auth.current_user.get('role', '')
                if user_role == 'Student':
                    return self.auth.current_user.get('id')
            return None
        except (AttributeError, Exception):
            return None

    def _get_student_modules(self, student_id):
        """Get modules for student"""
        try:
            from education_system.university_system.infrastructure.database.db import sqlite3
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT module_code, module_name
            FROM student_modules sm
            JOIN modules m ON sm.module_code = m.code
            WHERE sm.student_id = ?
            ORDER BY module_name
            ''', (student_id,))

            modules = cursor.fetchall()
            conn.close()

            return modules

        except Exception as e:
            print(_("assignment.errors.get_student_modules").format(error=str(e)))
            return []

    def _calculate_file_hash(self, file_path):
        """Calculate file hash for integrity checking"""
        try:
            import hashlib

            hash_md5 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)

            return hash_md5.hexdigest()

        except Exception as e:
            print(_("assignment.errors.calculate_file_hash").format(error=str(e)))
            return None

    def _validate_file(self, file_path, allowed_types=None, max_size_mb=None):
        """Validate uploaded file"""
        try:
            import os

            # Check if file exists
            if not os.path.exists(file_path):
                return False, _("assignment.validation.file_not_exists")

            # Check file size
            if max_size_mb:
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                if file_size_mb > max_size_mb:
                    return False, _("assignment.validation.file_size_exceeds").format(file_size=f"{file_size_mb:.1f}", max_size=max_size_mb)

            # Check file type
            if allowed_types:
                file_ext = os.path.splitext(file_path)[1].lower()
                if file_ext not in allowed_types:
                    return False, _("assignment.validation.file_type_not_allowed").format(file_ext=file_ext, allowed_types=', '.join(allowed_types))

            # Check for malicious content (basic check)
            file_name = os.path.basename(file_path)
            dangerous_patterns = ['../', '.exe', '.bat', '.sh', '.cmd']
            for pattern in dangerous_patterns:
                if pattern in file_name.lower():
                    return False, _("assignment.validation.dangerous_pattern").format(pattern=pattern)

            return True, _("assignment.validation.file_valid")

        except Exception as e:
            return False, _("assignment.errors.validate_file").format(error=str(e))

    def _log_action(self, action, details=None):
        """Log user action"""
        try:
            from education_system.university_system.modules.shared.utils.activity_logger import log_activity

            user_id = self.auth.current_user.get('id') if self.auth and self.auth.current_user else None

            log_activity(
                action_type=action,
                resource_type='assignment',
                resource_id=details.get('resource_id') if details else None,
                details=details,
                user_id=user_id
            )

            return True

        except Exception as e:
            print(_("assignment.errors.log_action").format(error=str(e)))
            return False

    def _send_notification(self, user_id, notification_type, title, message, related_id=None):
        """Send notification to user"""
        try:
            from education_system.university_system.infrastructure.database.db import sqlite3
            from datetime import datetime

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO notifications (user_id, type, title, message, related_id, is_read, created_at)
                VALUES (?, ?, ?, ?, ?, 0, ?)
                ''', (user_id, notification_type, title, message, related_id, timestamp))

                conn.commit()
            finally:
                conn.close()

            return True

        except Exception as e:
            print(_("assignment.errors.send_notification").format(error=str(e)))
            return False

    def _check_and_send_email(self, user_id, email_type, subject, body):
        """Check preferences and send email"""
        try:
            from education_system.university_system.infrastructure.database.db import sqlite3
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Check if user has email notifications enabled
            cursor.execute('''
            SELECT email_enabled FROM notification_preferences
            WHERE user_id = ? AND notification_type = ?
            ''', (user_id, email_type))

            pref = cursor.fetchone()
            conn.close()

            # Send email if enabled (or no preference set, default to enabled)
            if not pref or pref[0]:
                return self._send_email(user_id, subject, body)

            return True

        except Exception as e:
            print(_("assignment.errors.check_email_preferences").format(error=str(e)))
            return False

    def _send_email(self, user_id, subject, body):
        """Send email message"""
        try:
            from education_system.university_system.infrastructure.database.db import sqlite3
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT email FROM users WHERE id = ?', (user_id,))
            user = cursor.fetchone()
            conn.close()

            if not user:
                return False

            email_address = user[0]

            # Send email using email service
            from education_system.university_system.infrastructure.email.email_service import send_email

            send_email(
                recipient_email=email_address,
                subject=subject,
                body=body
            )

            return True

        except Exception as e:
            print(_("assignment.errors.send_email").format(error=str(e)))
            return False

def launch_gui(assignment_system, auth):
    """Launch the assignment GUI"""
    gui = AssignmentGUI(assignment_system, auth)
    gui.run()

def display_assignment_menu_gui(auth):
    """Display assignment menu in GUI mode"""
    from education_system.university_system.modules.domain.academics.services.assignments.assignment_submission import AssignmentSubmission
    assignment_system = AssignmentSubmission()
    launch_gui(assignment_system, auth)

def display_assignment_menu(auth):
    """Wrapper for backward compatibility"""
    display_assignment_menu_gui(auth)
