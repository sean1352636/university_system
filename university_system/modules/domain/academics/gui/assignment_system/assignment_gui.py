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
            from university_system.infrastructure.auth.authorization import add_permission

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
            import sqlite3
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
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
            conn.close()

            messagebox.showinfo("Success", "Assignment permissions configured successfully")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to add permissions: {e}")

    # Internal/Helper Functions

    def _init_directories(self):
        """Initialize submission directories"""
        try:
            from pathlib import Path
            from university_system.modules.shared.constants import paths

            # Create main directories
            directories = [
                paths.UPLOAD_DIR / 'assignments',
                paths.UPLOAD_DIR / 'submissions',
                paths.DATA_DIR / 'backups' / 'assignments',
                paths.DATA_DIR / 'temp' / 'assignments',
            ]

            for directory in directories:
                directory.mkdir(parents=True, exist_ok=True)

            return True

        except Exception as e:
            print(f"Error initializing directories: {e}")
            return False

    def _init_db(self):
        """Initialize database connection"""
        return self.db.ensure_database_exists()

    def _update_existing_tables(self):
        """Update existing database tables"""
        try:
            import sqlite3
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
            print(f"Error updating tables: {e}")
            return False

    def _get_student_id(self):
        """Get current student ID"""
        try:
            if self.auth and self.auth.current_user:
                user_role = self.auth.current_user.get('role', '')
                if user_role == 'Student':
                    return self.auth.current_user.get('id')
            return None
        except:
            return None

    def _get_student_modules(self, student_id):
        """Get modules for student"""
        try:
            import sqlite3
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
            print(f"Error getting student modules: {e}")
            return []

    def _calculate_file_hash(self, file_path):
        """Calculate file hash for integrity checking"""
        try:
            import hashlib

            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)

            return hash_md5.hexdigest()

        except Exception as e:
            print(f"Error calculating file hash: {e}")
            return None

    def _validate_file(self, file_path, allowed_types=None, max_size_mb=None):
        """Validate uploaded file"""
        try:
            import os

            # Check if file exists
            if not os.path.exists(file_path):
                return False, "File does not exist"

            # Check file size
            if max_size_mb:
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                if file_size_mb > max_size_mb:
                    return False, f"File size ({file_size_mb:.1f} MB) exceeds maximum ({max_size_mb} MB)"

            # Check file type
            if allowed_types:
                file_ext = os.path.splitext(file_path)[1].lower()
                if file_ext not in allowed_types:
                    return False, f"File type {file_ext} not allowed. Allowed types: {', '.join(allowed_types)}"

            # Check for malicious content (basic check)
            file_name = os.path.basename(file_path)
            dangerous_patterns = ['../', '.exe', '.bat', '.sh', '.cmd']
            for pattern in dangerous_patterns:
                if pattern in file_name.lower():
                    return False, f"File name contains dangerous pattern: {pattern}"

            return True, "File is valid"

        except Exception as e:
            return False, f"Error validating file: {e}"

    def _log_action(self, action, details=None):
        """Log user action"""
        try:
            from university_system.modules.shared.utils.activity_logger import log_activity

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
            print(f"Error logging action: {e}")
            return False

    def _send_notification(self, user_id, notification_type, title, message, related_id=None):
        """Send notification to user"""
        try:
            import sqlite3
            from datetime import datetime

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            INSERT INTO notifications (user_id, type, title, message, related_id, is_read, created_at)
            VALUES (?, ?, ?, ?, ?, 0, ?)
            ''', (user_id, notification_type, title, message, related_id, timestamp))

            conn.commit()
            conn.close()

            return True

        except Exception as e:
            print(f"Error sending notification: {e}")
            return False

    def _check_and_send_email(self, user_id, email_type, subject, body):
        """Check preferences and send email"""
        try:
            import sqlite3

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
            print(f"Error checking email preferences: {e}")
            return False

    def _send_email(self, user_id, subject, body):
        """Send email message"""
        try:
            import sqlite3

            # Get user email
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT email FROM users WHERE id = ?', (user_id,))
            user = cursor.fetchone()
            conn.close()

            if not user:
                return False

            email_address = user[0]

            # Send email using email service
            from university_system.infrastructure.email.email_service import send_email

            send_email(
                to_email=email_address,
                subject=subject,
                body=body
            )

            return True

        except Exception as e:
            print(f"Error sending email: {e}")
            return False


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
