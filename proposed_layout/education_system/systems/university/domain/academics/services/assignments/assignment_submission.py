from education_system.systems.university.infrastructure.database.db import sqlite3, DatabaseManager, ensure_parent_dir
from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH, SUBMISSIONS_DIR
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth
from education_system.systems.university.infrastructure.sql_safety import validate_table_name, validate_identifier  # nosec B608
import os
import shutil
from datetime import datetime, timedelta
import hashlib
from pathlib import Path
import mimetypes
import json
import csv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from collections import defaultdict
import zipfile
import tempfile

from education_system.systems.university.domain.academics.services.assignments.core.database import DatabaseMixin
from education_system.systems.university.domain.academics.services.assignments.core.permissions import PermissionsMixin
from education_system.systems.university.domain.academics.services.assignments.core.utils import UtilsMixin
from education_system.systems.university.domain.academics.services.assignments.assignments.crud import AssignmentCrudMixin
from education_system.systems.university.domain.academics.services.assignments.assignments.submissions import SubmissionsMixin
from education_system.systems.university.domain.academics.services.assignments.grading.grading import GradingMixin
from education_system.systems.university.domain.academics.services.assignments.groups.group_management import GroupManagementMixin
from education_system.systems.university.domain.academics.services.assignments.peer_review.peer_review import PeerReviewMixin
from education_system.systems.university.domain.academics.services.assignments.extensions.extensions import ExtensionsMixin
from education_system.systems.university.domain.academics.services.assignments.templates.templates import TemplatesMixin
from education_system.systems.university.domain.academics.services.assignments.notifications.messaging import MessagingMixin
from education_system.systems.university.domain.academics.services.assignments.analytics.analytics import AnalyticsMixin
from education_system.systems.university.domain.academics.services.assignments.maintenance.maintenance import MaintenanceMixin
from education_system.systems.university.domain.academics.services.assignments.auto_grading.auto_grading import AutoGradingMixin
from education_system.systems.university.domain.academics.services.assignments.exam_integrity.exam_integrity import ExamIntegrityMixin
from education_system.systems.university.domain.academics.services.assignments.student_experience.student_experience import StudentExperienceMixin
from education_system.systems.university.domain.academics.services.assignments.grade_disputes.grade_disputes import GradeDisputeMixin
from education_system.systems.university.domain.academics.services.assignments.late_policy.late_policy import LatePolicyMixin
from education_system.systems.university.domain.academics.services.assignments.annotations.annotations import AnnotationMixin
from education_system.systems.university.domain.academics.services.assignments.multi_stage.multi_stage import MultiStageMixin
from education_system.systems.university.domain.academics.services.assignments.admin_tools.admin_tools import AdminToolsMixin
from education_system.systems.university.domain.academics.services.assignments.ai_assistant.ai_assistant import AIAssistantMixin


class AssignmentSubmission(
    DatabaseMixin,
    PermissionsMixin,
    UtilsMixin,
    AssignmentCrudMixin,
    SubmissionsMixin,
    GradingMixin,
    GroupManagementMixin,
    PeerReviewMixin,
    ExtensionsMixin,
    TemplatesMixin,
    MessagingMixin,
    AnalyticsMixin,
    MaintenanceMixin,
    AutoGradingMixin,
    ExamIntegrityMixin,
    StudentExperienceMixin,
    GradeDisputeMixin,
    LatePolicyMixin,
    AnnotationMixin,
    MultiStageMixin,
    AdminToolsMixin,
    AIAssistantMixin,
):
    def __init__(self, db_path=None, submission_dir=None, auth=None):
        self.db_path = str(db_path) if db_path else str(DEFAULT_DB_PATH)
        ensure_parent_dir(self.db_path)
        self.submission_dir = str(submission_dir) if submission_dir else str(SUBMISSIONS_DIR)
        # Use provided auth or create a new UserAuth instance
        self.auth = auth if auth is not None else UserAuth(db_path=self.db_path)
        self._init_db()
        self._init_directories()

    def set_auth(self, auth):
        """Set the authentication object"""
        self.auth = auth

    def display_main_menu(self):
        """Display comprehensive menu based on user permissions - UPDATED"""
        while True:
            print(f"\n{'='*60}")
            print("ASSIGNMENT & ASSESSMENT MANAGEMENT SYSTEM")
            print(f"{'='*60}")
            print(f"Logged in as: {self.auth.current_user['username']} ({self.auth.current_user['role']})")

            menu_sections = []

            # Student Section - ENHANCED
            student_options = []
            if self.auth.check_permission('view_assignments'):
                student_options.extend([
                    ('1', 'View My Assignments', self.view_assignments),
                    ('2', 'Submit Assignment', self.submit_assignment),
                    ('3', 'View My Submissions', self.view_submissions),
                    ('4', 'Request Extension', self.request_extension),
                    ('5', 'View Assignment Calendar', self.view_assignment_calendar),
                    ('6', 'View Messages', self.view_messages),
                    ('7', 'Manage Notifications', self.manage_notifications),
                    ('8', 'Complete Peer Reviews', self.complete_peer_reviews),
                    ('9', 'Manage My Drafts', self.manage_drafts),
                    ('10', 'Submit Grade Dispute', self.submit_grade_dispute),
                    ('51', 'View My Disputes', self.view_my_disputes),
                    ('53', 'Submit External Link', self.submit_external_link),
                    ('54', 'Submit Assignment Stage', self.submit_stage),
                    ('55', 'Accessibility Settings', self.manage_accessibility_settings),
                    ('56', 'AI Draft Feedback', self.get_draft_feedback),
                    ('57', 'Practice Questions', self.view_practice_questions),
                ])

            if student_options:
                menu_sections.append(("STUDENT FEATURES", student_options))

            # Instructor/Admin Section - ENHANCED
            instructor_options = []
            if self.auth.check_permission('manage_assignments'):
                instructor_options.extend([
                    ('11', 'Create Assignment', self.create_assignment),
                    ('12', 'Create Group Assignment', self.create_group_assignment),
                    ('13', 'Create Assessment', self.create_assessment),
                    ('14', 'Create Multi-Stage Assignment', self.create_multi_stage_assignment),
                    ('15', 'Manage Assignments', self.manage_assignments),
                    ('16', 'Manage Assessments', self.manage_assessments),
                    ('17', 'Manage Groups', self.manage_groups),
                    ('18', 'Grade Submissions', self.grade_submission),
                    ('19', 'Grade with Rubrics', self.grade_with_rubrics),
                    ('20', 'Auto-Grade Submissions', self.auto_grade_submissions),
                    ('21', 'Annotate Submission', self.annotate_submission),
                    ('22', 'View All Submissions', self.view_all_submissions),
                    ('23', 'Review Extension Requests', self.review_extension_requests),
                    ('24', 'Regrade Queue', self.view_regrade_queue),
                    ('25', 'Review Grade Dispute', self.review_grade_dispute),
                    ('26', 'Late Policies', self.manage_late_policies),
                    ('27', 'Send Message', self.send_message),
                    ('28', 'Setup Peer Review', self.setup_peer_review),
                    ('29', 'Manage Peer Reviews', self.manage_peer_reviews),
                    ('30', 'Multi-Stage Assignments', self.manage_multi_stage_assignments),
                    ('58', 'Review Assignment Stage', self.review_stage),
                    ('59', 'View External Submissions', self.view_external_submissions),
                    ('60', 'Manage Annotation Templates', self.manage_annotation_templates),
                ])

            if instructor_options:
                menu_sections.append(("INSTRUCTOR FEATURES", instructor_options))

            # Exam Integrity Section
            integrity_options = []
            if self.auth.check_permission('manage_assignments'):
                integrity_options.extend([
                    ('61', 'Exam Integrity Settings', self.manage_exam_integrity),
                    ('62', 'View Integrity Logs', self.view_integrity_logs),
                    ('63', 'View Flagged Students', self.view_flagged_students),
                    ('64', 'Proctoring Status', self.view_proctoring_status),
                    ('65', 'Collusion Analysis', self.run_collusion_analysis),
                    ('66', 'View Collusion Reports', self.view_collusion_reports),
                    ('67', 'Late Pass Recommendations', self.get_late_pass_recommendation),
                ])

            if integrity_options:
                menu_sections.append(("EXAM INTEGRITY & AI", integrity_options))

            # Analytics Section - ENHANCED
            analytics_options = []
            if self.auth.check_permission('view_all_submissions'):
                analytics_options.extend([
                    ('31', 'Analytics Dashboard', self.generate_analytics_dashboard),
                    ('32', 'Advanced Analytics', self.generate_advanced_analytics),
                    ('33', 'Preview Submissions', self.preview_submission_file),
                    ('34', 'Generate Custom Reports', self.generate_custom_reports),
                    ('35', 'Question Bank Stats', self.view_question_bank_stats),
                    ('36', 'Late Submission Report', self.late_submission_report),
                    ('37', 'Dispute Analytics', self.dispute_analytics),
                    ('38', 'Annotation Summary', self.annotation_summary),
                    ('39', 'Grade Audit Log', self.view_grade_audit_log),
                ])

            if analytics_options:
                menu_sections.append(("ANALYTICS & REPORTING", analytics_options))

            # Template & Admin Section - ENHANCED
            admin_options = []
            if self.auth.check_permission('manage_assignments'):
                admin_options.extend([
                    ('41', 'Create Rubric', self.create_rubric),
                    ('42', 'Manage Rubrics', self.manage_rubrics),
                    ('43', 'Manage Question Banks', self.manage_question_banks),
                    ('44', 'Create Assignment Template', self.create_assignment_template),
                    ('45', 'Use Assignment Template', self.use_assignment_template),
                    ('46', 'Generate Practice Questions', self.generate_practice_questions),
                    ('47', 'SIS Roster Sync', self.sis_roster_sync),
                    ('48', 'Integrity Cases', self.manage_integrity_cases),
                    ('49', 'Manage Accommodations', self.manage_accommodations),
                    ('50', 'Manage TA Assignments', self.manage_ta_assignments),
                    ('71', 'Manage Late Passes', self.manage_late_passes),
                    ('72', 'Apply Late Penalties (Batch)', self.apply_late_penalties_batch),
                    ('73', 'Dispute History', self.view_dispute_history),
                    ('74', 'System Maintenance', self.system_maintenance),
                    ('75', 'Backup System Data', self.backup_system_data),
                    ('76', 'Data Cleanup', self.cleanup_old_data)
                ])

            if admin_options:
                menu_sections.append(("TEMPLATES & ADMINISTRATION", admin_options))

            # Display menu sections
            for section_name, options in menu_sections:
                print(f"\n{section_name}:")
                print("-" * 30)
                for option_num, description, _ in options:
                    print(f"{option_num}. {description}")

            # Always show exit option
            print(f"\n{'SYSTEM'}:")
            print("-" * 30)
            print("0. Exit System")

            # Get user choice
            choice = input("\nEnter your choice: ").strip()

            if choice == '0':
                print("Thank you for using the Assignment Management System!")
                break

            # Find and execute the chosen option
            option_found = False
            for section_name, options in menu_sections:
                for option_num, description, function in options:
                    if choice == option_num:
                        try:
                            print(f"\n{'-'*60}")
                            function()
                            print(f"{'-'*60}")
                            input("\nPress Enter to continue...")
                            option_found = True
                            break
                        except Exception as e:
                            print(f"Error executing {description}: {e}")
                            input("\nPress Enter to continue...")
                            option_found = True
                            break
                if option_found:
                    break

            if not option_found:
                print("Invalid choice. Please try again.")


def display_assignment_menu(auth):
    """Display the enhanced assignment submission menu"""
    assignment_system = AssignmentSubmission()
    assignment_system.set_auth(auth)
    assignment_system.display_main_menu()


def add_assignment_permissions(auth=None):
    """Add assignment-related permissions to the database"""
    # Try to get centralized auth first if not provided
    if auth is None:
        auth = get_auth()
    if auth is None:
        from education_system.systems.university.infrastructure.auth import UserAuth
        auth = UserAuth()

    assignment_permissions = [
        ('view_assignments', 'View assignments for enrolled modules'),
        ('submit_assignment', 'Submit assignments'),
        ('view_own_submissions', 'View own assignment submissions'),
        ('manage_assignments', 'Create and manage assignments'),
        ('view_all_submissions', 'View all assignment submissions'),
        ('delete_assignments', 'Delete assignments'),
        ('export_submission_data', 'Export submission data'),
        ('grade_submissions', 'Grade student submissions'),
        ('manage_groups', 'Manage assignment groups'),
        ('setup_peer_review', 'Setup peer review systems'),
        ('send_notifications', 'Send system notifications'),
        ('manage_extensions', 'Manage extension requests'),
        ('create_templates', 'Create assignment templates'),
        ('backup_system', 'Backup system data'),
        ('view_analytics', 'View system analytics')
    ]

    try:
        conn = sqlite3.connect(auth.db_path)
        cursor = conn.cursor()

        for perm_name, perm_desc in assignment_permissions:
            # Check if permission already exists
            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
            if not cursor.fetchone():
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                    (perm_name, perm_desc, timestamp)
                )

        conn.commit()

        # Now add permissions to roles
        role_permissions = {
            'student': [
                'view_assignments', 'submit_assignment', 'view_own_submissions'
            ],
            'instructor': [
                'view_assignments', 'manage_assignments', 'view_all_submissions',
                'export_submission_data', 'grade_submissions', 'manage_groups',
                'setup_peer_review', 'send_notifications', 'manage_extensions',
                'create_templates', 'view_analytics'
            ],
            'staff': [
                'view_assignments', 'manage_assignments', 'view_all_submissions',
                'export_submission_data', 'grade_submissions', 'view_analytics'
            ],
            'admin': [
                'view_assignments', 'submit_assignment', 'view_own_submissions',
                'manage_assignments', 'view_all_submissions', 'delete_assignments',
                'export_submission_data', 'grade_submissions', 'manage_groups',
                'setup_peer_review', 'send_notifications', 'manage_extensions',
                'create_templates', 'backup_system', 'view_analytics'
            ]
        }

        for role_name, permissions in role_permissions.items():
            # Get role ID
            cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role_name,))
            role_result = cursor.fetchone()
            if role_result:
                role_id = role_result[0]

                for perm in permissions:
                    # Get permission ID
                    cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm,))
                    perm_result = cursor.fetchone()
                    if perm_result:
                        perm_id = perm_result[0]

                        # Check if association already exists
                        cursor.execute(
                            'SELECT COUNT(*) FROM role_permissions WHERE role_id = ? AND permission_id = ?',
                            (role_id, perm_id)
                        )
                        if cursor.fetchone()[0] == 0:
                            cursor.execute(
                                'INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                                (role_id, perm_id)
                            )

        conn.commit()
        conn.close()

        print("Enhanced assignment permissions added successfully!")

    except sqlite3.Error as e:
        print(f"Error adding assignment permissions: {e}")


def init_assignment_system():
    """Initialize the enhanced assignment submission system"""
    try:
        # Create assignment system instance
        assignment_system = AssignmentSubmission()

        # Add permissions
        add_assignment_permissions()

        print("Enhanced Assignment submission system initialized successfully!")
        print("\nNew Features Added:")
        print("Grading and feedback system with rubrics")
        print("Group assignment support")
        print("Peer review system")
        print("Email notifications and messaging")
        print("Extension request management")
        print("Assignment templates")
        print("Analytics and reporting")
        print("File preview and version control")
        print("Calendar integration")
        print("Backup and recovery")
        print("Enhanced security and audit logging")

        return True

    except Exception as e:
        print(f"Error initializing enhanced assignment system: {e}")
        return False


# Export the enhanced functions
__all__ = [
    'display_assignment_menu',
    'init_assignment_system',
    'AssignmentSubmission',
    'add_assignment_permissions'
]
