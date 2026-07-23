"""
Staff HR CLI - Main Menu and Integration Functions

Provides:
- init_staff_hr_db() - Database initialization
- setup_staff_hr_permissions() - Permission setup
- display_staff_hr_menu() - Main menu function
- set_auth() - Auth instance assignment
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from education_system.post_18.university_system.infrastructure.database.db import get_connection

try:
    from education_system.post_18.university_system.infrastructure.shared_context import get_auth, set_auth as set_shared_auth
except ImportError:
    get_auth = lambda: None
    set_shared_auth = lambda x: None

try:
    from education_system.post_18.university_system.core.i18n import get_text as _t
except ImportError:
    def _t(key: str, default: str = '') -> str:
        return default or key

logger = logging.getLogger(__name__)

# Global auth instance
auth = None


def set_auth(auth_instance: Any) -> None:
    """Set the global auth instance for the module."""
    global auth
    auth = auth_instance
    try:
        set_shared_auth(auth_instance)
    except Exception as e:
        logger.warning(f"Failed to set auth in shared context: {e}")


def init_staff_hr_db() -> bool:
    """Initialize Staff HR database tables.

    This function should be called during application startup
    to ensure all Staff HR tables exist.
    """
    try:
        from education_system.post_18.university_system.infrastructure.database.schemas.staff_hr_schemas_all import (
            init_staff_hr_schemas
        )

        init_staff_hr_schemas()

        logger.info("Staff HR database initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Error initializing Staff HR database: {e}")
        return False


def setup_staff_hr_permissions(auth_instance: Any = None) -> None:
    """Setup permissions for Staff HR features.

    This function should be called after authentication is set up
    to register all Staff HR permissions with the auth system.
    """
    if auth_instance is None:
        auth_instance = auth or get_auth()

    if auth_instance is None:
        logger.warning("No auth instance available for permission setup")
        return

    permissions = [
        # General access
        'view_staff_hr',
        'manage_staff_hr',
        # Leave management
        'view_own_leave',
        'submit_leave_request',
        'manage_leave',
        'approve_leave',
        # Time & attendance
        'view_own_time',
        'clock_in_out',
        'manage_time',
        'approve_timesheets',
        # Training
        'view_training',
        'enroll_training',
        'manage_training',
        # Performance
        'view_appraisals',
        'submit_self_review',
        'manage_appraisals',
        # Assets
        'view_assets',
        'request_assets',
        'manage_assets',
        'assign_assets',
        # Recruitment
        'view_recruitment',
        'manage_recruitment',
        # Communication
        'view_announcements',
        'manage_announcements',
        # Admin
        'manage_staff_profiles',
        'manage_onboarding',
        'manage_visitors',
    ]

    try:
        if hasattr(auth_instance, 'add_permission_to_role'):
            # Add all permissions to admin
            for perm in permissions:
                auth_instance.add_permission_to_role('admin', perm)

            # Add staff permissions
            staff_permissions = [
                'view_staff_hr', 'view_own_leave', 'submit_leave_request',
                'view_own_time', 'clock_in_out', 'view_training', 'enroll_training',
                'view_appraisals', 'submit_self_review', 'view_assets',
                'request_assets', 'view_announcements',
            ]
            for perm in staff_permissions:
                auth_instance.add_permission_to_role('staff', perm)
                auth_instance.add_permission_to_role('instructor', perm)

            logger.info("Staff HR permissions setup complete")

    except Exception as e:
        logger.warning(f"Could not setup Staff HR permissions: {e}")


def display_staff_hr_menu() -> None:
    """Display the main Staff HR menu."""
    global auth

    if not auth:
        auth = get_auth()

    if not auth or not getattr(auth, 'current_user', None):
        print("\n" + "=" * 60)
        print(_t('staff_hr.error.login_required', default='You must be logged in to access Staff HR features.'))
        print("=" * 60)
        input("Press Enter to continue...")
        return

    current_user = auth.current_user
    user_id = current_user.get('id') or current_user.get('username')
    user_role = current_user.get('role', 'staff')
    is_admin = user_role in ('admin', 'Admin', 'administrator')
    is_manager = 'manager' in user_role.lower() if user_role else False

    # Import menu handlers
    from education_system.post_18.university_system.modules.domain.operations.staff_hr.cli.menus import (
        display_profile_menu,
        display_leave_menu,
        display_time_menu,
        display_training_menu,
        display_appraisal_menu,
        display_asset_menu,
        display_academic_menu,
        display_communication_menu,
        display_admin_menu,
    )

    while True:
        print("\n" + "=" * 70)
        print(_t('staff_hr.menu.title', default='STAFF HR MANAGEMENT SYSTEM'))
        print("=" * 70)

        options = []
        option_num = 1

        def add_option(label: str, key: str) -> None:
            nonlocal option_num
            print(f"  {option_num}. {label}")
            options.append(key)
            option_num += 1

        # Basic options for all staff
        print("\n--- My HR ---")
        add_option("My Profile", "profile")
        add_option("Leave Management", "leave")
        add_option("Time & Attendance", "time")
        add_option("Training & Certifications", "training")
        add_option("Performance & Goals", "appraisal")
        add_option("My Assets", "my_assets")

        # Academic staff options
        print("\n--- Academic ---")
        add_option("Academic Staff Tools", "academic")

        # Communication
        print("\n--- Communication ---")
        add_option("Announcements & Notices", "communication")

        # HR Services
        print("\n--- HR Services ---")
        add_option("My Contract", "contract")
        add_option("Expense Claims", "expense")
        add_option("Grievances", "grievance")
        add_option("My Schedule", "schedule")
        add_option("My Documents", "documents")
        add_option("Workload Overview", "workload")

        # Manager/Admin options
        if is_admin or is_manager:
            print("\n--- Management ---")
            add_option("Staff Directory", "directory")
            add_option("Asset Management", "assets")
            add_option("Leave Approvals", "leave_approvals")
            add_option("Timesheet Approvals", "time_approvals")

        if is_admin:
            print("\n--- Administration ---")
            add_option("Recruitment", "recruitment")
            add_option("Onboarding", "onboarding")
            add_option("Exit Management", "exit")
            add_option("Admin Tools", "admin_tools")
            add_option("Reports & Analytics", "reports")

        # Academic Operations (Grant Budget / Travel / Cover / Curriculum / Schedule)
        print("\n--- Academic Operations ---")
        add_option("Grant Budget", "grant_budget")
        add_option("Travel & Conferences", "travel")
        add_option("Cover / Substitute Teaching", "cover")
        add_option("Curriculum Design", "curriculum")
        add_option("Faculty Schedule", "faculty_schedule")

        # Staff Development & IP (Payroll / Mentoring / Sabbatical / Peer Review / IP)
        print("\n--- Staff Development & IP ---")
        add_option("Payroll", "payroll")
        add_option("Mentoring", "mentoring")
        add_option("Sabbatical / Study Leave", "sabbatical")
        add_option("Peer Review", "peer_review")
        add_option("IP / Patents", "ip")

        print(f"\n  {option_num}. Return to Main Menu")
        print("=" * 70)

        choice = input("\nEnter your choice: ").strip()

        try:
            choice_num = int(choice)
            if choice_num == option_num:
                break  # Return to main menu
            elif 1 <= choice_num < option_num:
                selected = options[choice_num - 1]
                _handle_menu_selection(selected, user_id, is_admin, is_manager)
            else:
                print("\nInvalid choice. Please try again.")
        except ValueError:
            print("\nPlease enter a valid number.")
        except KeyboardInterrupt:
            print("\n\nExiting Staff HR menu...")
            break
        except Exception as e:
            logger.error(f"Error in Staff HR menu: {e}")
            print(f"\nAn error occurred: {e}")
            input("Press Enter to continue...")


def _handle_menu_selection(selected: str, user_id: str,
                           is_admin: bool, is_manager: bool) -> None:
    """Handle menu selection."""
    from education_system.post_18.university_system.modules.domain.operations.staff_hr.cli.menus import (
        display_profile_menu,
        display_leave_menu,
        display_time_menu,
        display_training_menu,
        display_appraisal_menu,
        display_asset_menu,
        display_academic_menu,
        display_communication_menu,
        display_admin_menu,
        display_directory_menu,
        display_recruitment_menu,
        display_onboarding_menu,
        display_reports_menu,
        display_contract_menu,
        display_expense_menu,
        display_grievance_menu,
        display_exit_menu,
    )

    try:
        if selected == 'profile':
            display_profile_menu(user_id)
        elif selected == 'leave':
            display_leave_menu(user_id, is_admin or is_manager)
        elif selected == 'time':
            display_time_menu(user_id, is_admin or is_manager)
        elif selected == 'training':
            display_training_menu(user_id, is_admin)
        elif selected == 'appraisal':
            display_appraisal_menu(user_id, is_admin or is_manager)
        elif selected == 'my_assets':
            display_asset_menu(user_id, admin_mode=False)
        elif selected == 'academic':
            display_academic_menu(user_id)
        elif selected == 'communication':
            display_communication_menu(user_id, is_admin)
        elif selected == 'directory':
            display_directory_menu()
        elif selected == 'assets':
            display_asset_menu(user_id, admin_mode=True)
        elif selected == 'leave_approvals':
            display_leave_menu(user_id, approval_mode=True)
        elif selected == 'time_approvals':
            display_time_menu(user_id, approval_mode=True)
        elif selected == 'recruitment':
            display_recruitment_menu(user_id)
        elif selected == 'onboarding':
            display_onboarding_menu(user_id)
        elif selected == 'admin_tools':
            display_admin_menu(user_id)
        elif selected == 'reports':
            display_reports_menu(user_id)
        elif selected == 'contract':
            display_contract_menu(user_id, is_admin)
        elif selected == 'expense':
            display_expense_menu(user_id, is_admin)
        elif selected == 'grievance':
            display_grievance_menu(user_id, is_admin)
        elif selected == 'exit':
            display_exit_menu(user_id, is_admin)
        elif selected == 'schedule':
            _display_schedule_view(user_id)
        elif selected == 'documents':
            _display_documents_view(user_id)
        elif selected == 'workload':
            _display_workload_view(user_id)
        elif selected in ('grant_budget', 'travel', 'cover',
                          'curriculum', 'faculty_schedule'):
            _handle_academic_operations(selected, user_id, is_admin, is_manager)
        elif selected in ('payroll', 'mentoring', 'sabbatical',
                          'peer_review', 'ip'):
            _handle_staff_development(selected, user_id, is_admin, is_manager)
        else:
            print(f"\nFeature '{selected}' is not available.")
            input("Press Enter to continue...")

    except Exception as e:
        logger.error(f"Error handling menu selection '{selected}': {e}")
        print(f"\nError: {e}")
        input("Press Enter to continue...")


def _handle_academic_operations(selected: str, user_id: str,
                                is_admin: bool, is_manager: bool) -> None:
    """Dispatch to the academic operations submenus (Grant Budget,
    Travel, Cover, Curriculum, Faculty Schedule)."""
    from education_system.post_18.university_system.modules.domain.operations.staff_hr.cli.menus import (
        display_grant_budget_menu,
        display_travel_menu,
        display_cover_menu,
        display_curriculum_menu,
        display_faculty_schedule_menu,
    )

    if selected == 'grant_budget':
        display_grant_budget_menu(user_id, is_admin)
    elif selected == 'travel':
        display_travel_menu(user_id, is_admin or is_manager)
    elif selected == 'cover':
        display_cover_menu(user_id, is_admin or is_manager)
    elif selected == 'curriculum':
        display_curriculum_menu(user_id, is_admin)
    elif selected == 'faculty_schedule':
        display_faculty_schedule_menu(user_id)


def _handle_staff_development(selected: str, user_id: str,
                             is_admin: bool, is_manager: bool) -> None:
    """Dispatch to the staff development & IP submenus (Payroll,
    Mentoring, Sabbatical, Peer Review, IP / Patents)."""
    from education_system.post_18.university_system.modules.domain.operations.staff_hr.cli.menus import (
        display_payroll_menu,
        display_mentoring_menu,
        display_sabbatical_menu,
        display_peer_review_menu,
        display_ip_menu,
    )

    if selected == 'payroll':
        display_payroll_menu(user_id, is_admin)
    elif selected == 'mentoring':
        display_mentoring_menu(user_id, is_admin)
    elif selected == 'sabbatical':
        display_sabbatical_menu(user_id, is_admin)
    elif selected == 'peer_review':
        display_peer_review_menu(user_id, is_admin)
    elif selected == 'ip':
        display_ip_menu(user_id, is_admin)


def _display_schedule_view(user_id) -> None:
    """Display staff schedule from staff_schedules table."""
    day_names = {0: 'Sunday', 1: 'Monday', 2: 'Tuesday', 3: 'Wednesday',
                 4: 'Thursday', 5: 'Friday', 6: 'Saturday'}

    print("\n" + "=" * 60)
    print(_t('staff_hr.schedule.title', default='MY SCHEDULE'))
    print("=" * 60)

    try:
        with get_connection() as conn:
            schedules = conn.execute('''
                SELECT day_of_week, start_time, end_time, location,
                       schedule_type, notes
                FROM staff_schedules
                WHERE user_id = ?
                  AND is_recurring = 1
                  AND (effective_to IS NULL OR effective_to >= date('now'))
                ORDER BY day_of_week, start_time
            ''', (str(user_id),)).fetchall()

            if schedules:
                for s in schedules:
                    d = dict(s)
                    day = day_names.get(d.get('day_of_week'), f"Day {d.get('day_of_week', '?')}")
                    stype = (d.get('schedule_type') or 'general').replace('_', ' ').title()
                    print(f"\n  {day} - {stype}")
                    print(f"    Time: {d.get('start_time', 'N/A')} - {d.get('end_time', 'N/A')}")
                    if d.get('location'):
                        print(f"    Location: {d['location']}")
                    if d.get('notes'):
                        print(f"    Notes: {d['notes']}")
            else:
                print("\n  No schedule entries found.")
    except Exception as e:
        logger.error(f"Error loading schedule: {e}")
        print(f"\n  Could not load schedule data: {e}")

    input("\nPress Enter to continue...")


def _display_documents_view(user_id) -> None:
    """Display staff documents from unified documents table."""
    print("\n" + "=" * 60)
    print(_t('staff_hr.documents.title', default='MY DOCUMENTS'))
    print("=" * 60)

    try:
        with get_connection() as conn:
            docs = conn.execute('''
                SELECT document_name, document_type, status,
                       issue_date, expiry_date, notes
                FROM documents
                WHERE source_type = 'staff' AND owner_id = ? AND owner_type = 'staff'
                ORDER BY upload_date DESC
            ''', (str(user_id),)).fetchall()

            if docs:
                for d in docs:
                    dd = dict(d)
                    status_str = f" [{dd['status']}]" if dd.get('status') else ""
                    expiry_str = f"  (Expires: {dd['expiry_date']})" if dd.get('expiry_date') else ""
                    print(f"\n  {dd.get('document_name', 'Untitled')}{status_str}")
                    print(f"    Type: {dd.get('document_type', 'N/A')}")
                    if dd.get('issue_date'):
                        print(f"    Issued: {dd['issue_date']}{expiry_str}")
                    elif expiry_str:
                        print(f"   {expiry_str.strip()}")
                    if dd.get('notes'):
                        print(f"    Notes: {dd['notes']}")
            else:
                print("\n  No documents on file.")
    except Exception as e:
        logger.error(f"Error loading documents: {e}")
        print(f"\n  Could not load document data: {e}")

    input("\nPress Enter to continue...")


def _display_workload_view(user_id) -> None:
    """Display workload allocation from staff_workload table."""
    print("\n" + "=" * 60)
    print(_t('staff_hr.workload.title', default='WORKLOAD OVERVIEW'))
    print("=" * 60)

    try:
        with get_connection() as conn:
            workload = conn.execute('''
                SELECT academic_year, semester,
                       teaching_hours, research_hours,
                       admin_hours, service_hours, total_fte, notes
                FROM staff_workload
                WHERE user_id = ?
                ORDER BY academic_year DESC, semester DESC
                LIMIT 6
            ''', (str(user_id),)).fetchall()

            if workload:
                for w in workload:
                    wd = dict(w)
                    semester = wd.get('semester') or 'Full Year'
                    print(f"\n  {wd.get('academic_year', 'N/A')} - {semester}")
                    print(f"    Teaching: {wd.get('teaching_hours', 0)}h  |  "
                          f"Research: {wd.get('research_hours', 0)}h  |  "
                          f"Admin: {wd.get('admin_hours', 0)}h  |  "
                          f"Service: {wd.get('service_hours', 0)}h")
                    print(f"    FTE: {wd.get('total_fte', 0)}")
                    if wd.get('notes'):
                        print(f"    Notes: {wd['notes']}")
            else:
                print("\n  No workload data found.")
    except Exception as e:
        logger.error(f"Error loading workload: {e}")
        print(f"\n  Could not load workload data: {e}")

    input("\nPress Enter to continue...")
