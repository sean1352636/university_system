from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager, ensure_parent_dir
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH, SUBMISSIONS_DIR
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.core.sql_safety import validate_table_name, validate_identifier  # nosec B608
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
import matplotlib.pyplot as plt
import pandas as pd
from collections import defaultdict
import zipfile
import tempfile

from education_system.university_system.modules.domain.academics.services.assignments.core.database import DatabaseMixin
from education_system.university_system.modules.domain.academics.services.assignments.core.permissions import PermissionsMixin
from education_system.university_system.modules.domain.academics.services.assignments.core.utils import UtilsMixin
from education_system.university_system.modules.domain.academics.services.assignments.assignments.crud import AssignmentCrudMixin
from education_system.university_system.modules.domain.academics.services.assignments.assignments.submissions import SubmissionsMixin
from education_system.university_system.modules.domain.academics.services.assignments.grading.grading import GradingMixin
from education_system.university_system.modules.domain.academics.services.assignments.groups.group_management import GroupManagementMixin
from education_system.university_system.modules.domain.academics.services.assignments.peer_review.peer_review import PeerReviewMixin
from education_system.university_system.modules.domain.academics.services.assignments.extensions.extensions import ExtensionsMixin
from education_system.university_system.modules.domain.academics.services.assignments.templates.templates import TemplatesMixin
from education_system.university_system.modules.domain.academics.services.assignments.notifications.messaging import MessagingMixin
from education_system.university_system.modules.domain.academics.services.assignments.analytics.analytics import AnalyticsMixin
from education_system.university_system.modules.domain.academics.services.assignments.maintenance.maintenance import MaintenanceMixin


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
                    ('8', 'Complete Peer Reviews', self.complete_peer_reviews)  # NEW
                ])

            if student_options:
                menu_sections.append(("STUDENT FEATURES", student_options))

            # Instructor/Admin Section - ENHANCED
            instructor_options = []
            if self.auth.check_permission('manage_assignments'):
                instructor_options.extend([
                    ('11', 'Create Assignment', self.create_assignment),
                    ('12', 'Create Group Assignment', self.create_group_assignment),
                    ('13', 'Create Assessment', self.create_assessment),  # NEW
                    ('14', 'Manage Assignments', self.manage_assignments),
                    ('15', 'Manage Assessments', self.manage_assessments),  # NEW
                    ('16', 'Manage Groups', self.manage_groups),
                    ('17', 'Grade Submissions', self.grade_submission),
                    ('18', 'Grade with Rubrics', self.grade_with_rubrics),  # NEW
                    ('19', 'View All Submissions', self.view_all_submissions),
                    ('20', 'Review Extension Requests', self.review_extension_requests),
                    ('21', 'Send Message', self.send_message),
                    ('22', 'Setup Peer Review', self.setup_peer_review),
                    ('23', 'Manage Peer Reviews', self.manage_peer_reviews)  # NEW
                ])

            if instructor_options:
                menu_sections.append(("INSTRUCTOR FEATURES", instructor_options))

            # Analytics Section - ENHANCED
            analytics_options = []
            if self.auth.check_permission('view_all_submissions'):
                analytics_options.extend([
                    ('31', 'Analytics Dashboard', self.generate_analytics_dashboard),
                    ('32', 'Advanced Analytics', self.generate_advanced_analytics),  # NEW
                    ('33', 'Preview Submissions', self.preview_submission_file),
                    ('34', 'Generate Custom Reports', self.generate_custom_reports)  # NEW
                ])

            if analytics_options:
                menu_sections.append(("ANALYTICS & REPORTING", analytics_options))

            # Template & Admin Section - ENHANCED
            admin_options = []
            if self.auth.check_permission('manage_assignments'):
                admin_options.extend([
                    ('41', 'Create Rubric', self.create_rubric),
                    ('42', 'Manage Rubrics', self.manage_rubrics),  # NEW
                    ('43', 'Create Assignment Template', self.create_assignment_template),
                    ('44', 'Use Assignment Template', self.use_assignment_template),
                    ('45', 'System Maintenance', self.system_maintenance),  # NEW
                    ('46', 'Backup System Data', self.backup_system_data),
                    ('47', 'Data Cleanup', self.cleanup_old_data)  # NEW
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
            choice = input(f"\nEnter your choice: ").strip()

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
        from education_system.university_system.infrastructure.auth import UserAuth
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
