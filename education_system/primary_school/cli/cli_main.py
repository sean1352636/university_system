"""Main CLI entry point for the Primary School Management System."""

import getpass
import sys
import logging

from education_system.primary_school.infrastructure.auth.core import UserAuth
from education_system.primary_school.infrastructure.auth.role_manager import RoleManager
from education_system.primary_school.infrastructure.database.schema import initialise_database, seed_default_users, seed_default_staff
from education_system.primary_school.infrastructure.database.db import get_db_path
from education_system.primary_school.core.paths import ensure_directories
from education_system.primary_school.core.logs import setup_logging

_role_mgr = RoleManager()
from education_system.shared.cli.cli_helpers import (
    print_header, print_menu, get_choice, run_submenu as _run_submenu, login_prompt,
)

logger = logging.getLogger(__name__)


def change_password_prompt(auth: UserAuth):
    """Prompt user to change their password."""
    print_header("Change Password")
    old_pw = getpass.getpass("Current password: ")
    new_pw = getpass.getpass("New password: ")
    confirm = getpass.getpass("Confirm new password: ")

    if new_pw != confirm:
        print("\n  Passwords do not match.")
        return

    try:
        auth.change_password(auth.current_user["user_id"], old_pw, new_pw)
        print("\n  Password changed successfully.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ================================================================
# Sub-menus
# ================================================================

def _academics(auth):
    from education_system.primary_school.cli.menus.pupil_cli import pupils_menu
    from education_system.primary_school.cli.menus.subject_cli import subjects_menu
    from education_system.primary_school.cli.menus.class_cli import classes_menu
    from education_system.primary_school.cli.menus.assessment_cli import assessment_menu
    from education_system.primary_school.cli.menus.attendance_cli import attendance_menu
    from education_system.primary_school.cli.menus.timetable_cli import timetable_menu
    from education_system.primary_school.cli.menus.homework_cli import homework_menu
    from education_system.primary_school.cli.menus.sats_cli import sats_menu
    from education_system.primary_school.cli.menus.phonics_cli import phonics_menu
    from education_system.primary_school.cli.menus.reading_records_cli import reading_records_menu
    from education_system.primary_school.cli.menus.progress_cli import progress_menu
    _run_submenu(auth, "Academics", [
        ("1", "Pupils", lambda a: pupils_menu(a)),
        ("2", "Subjects", lambda a: subjects_menu(a)),
        ("3", "Classes", lambda a: classes_menu(a)),
        ("4", "Assessment", lambda a: assessment_menu(a)),
        ("5", "Attendance", lambda a: attendance_menu(a)),
        ("6", "Timetable", lambda a: timetable_menu(a)),
        ("7", "Homework", lambda a: homework_menu(a)),
        ("8", "SATs", lambda a: sats_menu(a)),
        ("9", "Phonics", lambda a: phonics_menu(a)),
        ("A", "Reading Records", lambda a: reading_records_menu(a)),
        ("B", "Progress", lambda a: progress_menu(a)),
    ])


def _pastoral(auth):
    from education_system.primary_school.cli.menus.behaviour_cli import behaviour_menu
    from education_system.primary_school.cli.menus.rewards_cli import rewards_menu
    from education_system.primary_school.cli.menus.safeguarding_cli import safeguarding_menu
    from education_system.primary_school.cli.menus.send_cli import send_menu
    from education_system.primary_school.cli.menus.pastoral_cli import pastoral_notes_menu
    _run_submenu(auth, "Pastoral Care", [
        ("1", "Behaviour", lambda a: behaviour_menu(a)),
        ("2", "Rewards", lambda a: rewards_menu(a)),
        ("3", "Safeguarding", lambda a: safeguarding_menu(a)),
        ("4", "SEND", lambda a: send_menu(a)),
        ("5", "Pastoral Notes", lambda a: pastoral_notes_menu(a)),
    ])


def _staff(auth):
    from education_system.primary_school.cli.menus.hr_cli import hr_menu
    from education_system.primary_school.cli.menus.cpd_cli import cpd_records_menu
    from education_system.primary_school.cli.menus.cover_cli import cover_lessons_menu
    from education_system.primary_school.cli.menus.staff_directory_cli import staff_directory_menu
    _run_submenu(auth, "Staff", [
        ("1", "HR", lambda a: hr_menu(a)),
        ("2", "CPD Records", lambda a: cpd_records_menu(a)),
        ("3", "Cover Lessons", lambda a: cover_lessons_menu(a)),
        ("4", "Staff Directory", lambda a: staff_directory_menu(a)),
    ])


def _administration(auth):
    from education_system.primary_school.cli.menus.users_cli import user_management_menu
    from education_system.primary_school.cli.menus.settings_cli import settings_menu
    from education_system.primary_school.cli.menus.admissions_cli import admissions_menu
    from education_system.primary_school.cli.menus.finance_cli import finance_menu
    from education_system.primary_school.cli.menus.data_export_cli import data_export_menu
    from education_system.primary_school.cli.menus.audit_log_cli import audit_log_menu
    from education_system.primary_school.cli.menus.policies_cli import policies_menu
    from education_system.primary_school.cli.menus.documents_cli import documents_menu
    _run_submenu(auth, "Administration", [
        ("1", "User Management", lambda a: user_management_menu(a)),
        ("2", "Settings", lambda a: settings_menu(a)),
        ("3", "Admissions", lambda a: admissions_menu(a)),
        ("4", "Finance", lambda a: finance_menu(a)),
        ("5", "Data Export", lambda a: data_export_menu(a)),
        ("6", "Audit Log", lambda a: audit_log_menu(a)),
        ("7", "Policies", lambda a: policies_menu(a)),
        ("8", "Documents", lambda a: documents_menu(a)),
    ])


def _pupil_life(auth):
    from education_system.primary_school.cli.menus.clubs_cli import clubs_menu
    from education_system.primary_school.cli.menus.meals_cli import meals_menu
    from education_system.primary_school.cli.menus.transport_cli import transport_menu
    from education_system.primary_school.cli.menus.trips_cli import trips_menu
    from education_system.primary_school.cli.menus.library_cli import library_menu
    from education_system.primary_school.cli.menus.medical_cli import medical_menu
    from education_system.primary_school.cli.menus.class_groups_cli import class_groups_menu
    from education_system.primary_school.cli.menus.consent_cli import consent_menu
    _run_submenu(auth, "Pupil Life", [
        ("1", "Clubs", lambda a: clubs_menu(a)),
        ("2", "Meals", lambda a: meals_menu(a)),
        ("3", "Transport", lambda a: transport_menu(a)),
        ("4", "Trips", lambda a: trips_menu(a)),
        ("5", "Library", lambda a: library_menu(a)),
        ("6", "Medical", lambda a: medical_menu(a)),
        ("7", "Class Groups", lambda a: class_groups_menu(a)),
        ("8", "Consent", lambda a: consent_menu(a)),
    ])


def _communication(auth):
    from education_system.primary_school.cli.menus.email_cli import email_menu
    from education_system.primary_school.cli.menus.notifications_cli import notifications_menu
    from education_system.primary_school.cli.menus.announcements_cli import announcements_menu
    from education_system.primary_school.cli.menus.calendar_cli import calendar_menu
    from education_system.primary_school.cli.menus.parents_evening_cli import parents_evening_menu
    from education_system.primary_school.cli.menus.communication_log_cli import communication_log_menu
    _run_submenu(auth, "Communication", [
        ("1", "Email", lambda a: email_menu(a)),
        ("2", "Notifications", lambda a: notifications_menu(a)),
        ("3", "Announcements", lambda a: announcements_menu(a)),
        ("4", "Calendar", lambda a: calendar_menu(a)),
        ("5", "Parents Evening", lambda a: parents_evening_menu(a)),
        ("6", "Communication Log", lambda a: communication_log_menu(a)),
    ])


def _facilities(auth):
    from education_system.primary_school.cli.menus.room_booking_cli import room_booking_menu
    from education_system.primary_school.cli.menus.assets_cli import assets_menu
    from education_system.primary_school.cli.menus.visitors_cli import visitors_menu
    from education_system.primary_school.cli.menus.incidents_cli import incidents_menu
    _run_submenu(auth, "Facilities", [
        ("1", "Room Booking", lambda a: room_booking_menu(a)),
        ("2", "Assets", lambda a: assets_menu(a)),
        ("3", "Visitors", lambda a: visitors_menu(a)),
        ("4", "Incidents", lambda a: incidents_menu(a)),
    ])


def _cross_system_tools(auth):
    """Cross-system shared tools available across all education systems."""
    db_path = getattr(auth, '_db_path', None)

    def _run_shared(module_path, label):
        """Lazily import and run a shared CLI module."""
        def handler(a):
            try:
                import importlib
                mod = importlib.import_module(module_path)
                mod.run(db_path=db_path, auth=a)
            except ImportError:
                print(f"\n  {label} module is not available.")
            except Exception as e:
                print(f"\n  Error running {label}: {e}")
        return handler

    _run_submenu(auth, "Cross-System Tools", [
        ("1", "Analytics Dashboard", _run_shared("education_system.shared.analytics.analytics_cli", "Analytics Dashboard")),
        ("2", "Outcome Tracking", _run_shared("education_system.shared.outcomes.outcomes_cli", "Outcome Tracking")),
        ("3", "Predictive Alerts", _run_shared("education_system.shared.predictive.predictive_cli", "Predictive Alerts")),
        ("4", "Bulk Transfer", _run_shared("education_system.shared.bulk_transfer.bulk_transfer_cli", "Bulk Transfer")),
        ("5", "Transfer Documents", _run_shared("education_system.shared.transfer_docs.transfer_docs_cli", "Transfer Documents")),
        ("6", "Reverse Lookup", _run_shared("education_system.shared.reverse_lookup.reverse_lookup_cli", "Reverse Lookup")),
        ("7", "Parent Continuity", _run_shared("education_system.shared.parent_continuity.parent_cli", "Parent Continuity")),
        ("8", "Cross-System Calendar", _run_shared("education_system.shared.calendar.calendar_cli", "Cross-System Calendar")),
        ("9", "Inter-System Messaging", _run_shared("education_system.shared.messaging.cross_system_cli", "Inter-System Messaging")),
        ("A", "Central Admin Portal", _run_shared("education_system.shared.admin_portal.admin_cli", "Central Admin Portal")),
        ("B", "GDPR Compliance", _run_shared("education_system.shared.gdpr.gdpr_cli", "GDPR Compliance")),
        ("C", "Shared Documents", _run_shared("education_system.shared.documents.document_cli", "Shared Documents")),
        ("D", "Student Self-Service", _run_shared("education_system.shared.student_portal.portal_cli", "Student Self-Service")),
        ("E", "Digital Transcript", _run_shared("education_system.shared.transcript.transcript_cli", "Digital Transcript")),
    ])


# ================================================================
# Superadmin detection
# ================================================================

def _is_superadmin(auth):
    """Check if user is superadmin (admin in all 4 systems)."""
    cu = getattr(auth, 'current_user', None) or {}
    systems = cu.get('systems', []) if isinstance(cu, dict) else []
    admin_keys = {s["system_key"] for s in systems if s.get("role") == "admin"}
    return admin_keys >= {"university", "college", "school", "primary"}


def _superadmin_switch_options(auth, this_system):
    """Return switch menu options and handler for superadmin users."""
    if not _is_superadmin(auth):
        return [], {}

    targets = [
        ("primary", "Primary School"),
        ("school", "Secondary School"),
        ("college", "Sixth Form College"),
        ("university", "University System"),
        ("__superadmin__", "Super Admin Dashboard"),
    ]
    options = []
    handler = {}
    idx = 1
    for key, label in targets:
        if key == this_system:
            continue
        opt_key = f"SW{idx}"
        options.append((opt_key, label))
        handler[opt_key] = key
        idx += 1
    return options, handler


# ================================================================
# Role-based menus
# ================================================================

def admin_menu(auth: UserAuth):
    """Admin menu with all modules."""
    while True:
        print_header("Primary School - Admin")
        options = [
            ("1", "Academics"),
            ("2", "Pastoral Care"),
            ("3", "Staff"),
            ("4", "Administration"),
            ("5", "Pupil Life"),
            ("6", "Communication"),
            ("7", "Facilities"),
            ("8", "Cross-System Tools"),
            ("M", "MFA Settings"),
            ("P", "Change Password"),
            ("Q", "Security Questions"),
            ("G", "Switch to GUI"),
            ("L", "Logout"),
            ("0", "Exit"),
        ]
        switch_opts, switch_map = _superadmin_switch_options(auth, "primary")
        if switch_opts:
            options[-2:-2] = [("", "── Switch System ──")] + switch_opts
        print_menu(options)

        choice = get_choice().upper()
        if choice == "1":
            _academics(auth)
        elif choice == "2":
            _pastoral(auth)
        elif choice == "3":
            _staff(auth)
        elif choice == "4":
            _administration(auth)
        elif choice == "5":
            _pupil_life(auth)
        elif choice == "6":
            _communication(auth)
        elif choice == "7":
            _facilities(auth)
        elif choice == "8":
            _cross_system_tools(auth)
        elif choice == "M":
            from education_system.primary_school.cli.mfa_cli import mfa_settings_menu
            mfa_settings_menu(auth)
        elif choice == "P":
            change_password_prompt(auth)
        elif choice == "Q":
            from education_system.shared.cli.security_questions_cli import security_questions_menu
            security_questions_menu(auth)
        elif choice == "G":
            from education_system.switch import request_switch
            request_switch("primary", "gui")
            return "switch"
        elif choice in switch_map:
            from education_system.switch import request_switch
            request_switch(switch_map[choice], "cli")
            return "switch"
        elif choice == "L":
            auth.logout()
            print("\n  Logged out.")
            return "logout"
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def teacher_menu(auth: UserAuth):
    """Teacher menu."""
    while True:
        print_header("Primary School - Teacher")
        options = [
            ("1", "Academics"),
            ("2", "Pastoral Care"),
            ("3", "Staff"),
            ("4", "Pupil Life"),
            ("5", "Communication"),
            ("6", "Facilities"),
            ("M", "MFA Settings"),
            ("P", "Change Password"),
            ("Q", "Security Questions"),
            ("G", "Switch to GUI"),
            ("L", "Logout"),
            ("0", "Exit"),
        ]
        switch_opts, switch_map = _superadmin_switch_options(auth, "primary")
        if switch_opts:
            options[-2:-2] = [("", "── Switch System ──")] + switch_opts
        print_menu(options)

        choice = get_choice().upper()
        if choice == "1":
            _academics(auth)
        elif choice == "2":
            _pastoral(auth)
        elif choice == "3":
            _staff(auth)
        elif choice == "4":
            _pupil_life(auth)
        elif choice == "5":
            _communication(auth)
        elif choice == "6":
            _facilities(auth)
        elif choice == "M":
            from education_system.primary_school.cli.mfa_cli import mfa_settings_menu
            mfa_settings_menu(auth)
        elif choice == "P":
            change_password_prompt(auth)
        elif choice == "Q":
            from education_system.shared.cli.security_questions_cli import security_questions_menu
            security_questions_menu(auth)
        elif choice == "G":
            from education_system.switch import request_switch
            request_switch("primary", "gui")
            return "switch"
        elif choice in switch_map:
            from education_system.switch import request_switch
            request_switch(switch_map[choice], "cli")
            return "switch"
        elif choice == "L":
            auth.logout()
            print("\n  Logged out.")
            return "logout"
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def parent_menu(auth: UserAuth):
    """Parent menu."""
    while True:
        print_header("Primary School - Parent")
        options = [
            ("1", "Announcements"),
            ("2", "Calendar"),
            ("3", "Parents Evening"),
            ("4", "Communication Log"),
            ("M", "MFA Settings"),
            ("P", "Change Password"),
            ("Q", "Security Questions"),
            ("G", "Switch to GUI"),
            ("L", "Logout"),
            ("0", "Exit"),
        ]
        print_menu(options)

        choice = get_choice().upper()
        if choice == "1":
            from education_system.primary_school.cli.menus.announcements_cli import announcements_menu
            announcements_menu(auth)
        elif choice == "2":
            from education_system.primary_school.cli.menus.calendar_cli import calendar_menu
            calendar_menu(auth)
        elif choice == "3":
            from education_system.primary_school.cli.menus.parents_evening_cli import parents_evening_menu
            parents_evening_menu(auth)
        elif choice == "4":
            from education_system.primary_school.cli.menus.communication_log_cli import communication_log_menu
            communication_log_menu(auth)
        elif choice == "M":
            from education_system.primary_school.cli.mfa_cli import mfa_settings_menu
            mfa_settings_menu(auth)
        elif choice == "P":
            change_password_prompt(auth)
        elif choice == "Q":
            from education_system.shared.cli.security_questions_cli import security_questions_menu
            security_questions_menu(auth)
        elif choice == "G":
            from education_system.switch import request_switch
            request_switch("primary", "gui")
            return "switch"
        elif choice == "L":
            auth.logout()
            print("\n  Logged out.")
            return "logout"
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def student_menu(auth: UserAuth):
    """Student menu (limited)."""
    while True:
        print_header("Primary School - Student")
        options = [
            ("1", "Announcements"),
            ("2", "Calendar"),
            ("3", "Library"),
            ("M", "MFA Settings"),
            ("P", "Change Password"),
            ("Q", "Security Questions"),
            ("G", "Switch to GUI"),
            ("L", "Logout"),
            ("0", "Exit"),
        ]
        print_menu(options)

        choice = get_choice().upper()
        if choice == "1":
            from education_system.primary_school.cli.menus.announcements_cli import announcements_menu
            announcements_menu(auth)
        elif choice == "2":
            from education_system.primary_school.cli.menus.calendar_cli import calendar_menu
            calendar_menu(auth)
        elif choice == "3":
            from education_system.primary_school.cli.menus.library_cli import library_menu
            library_menu(auth)
        elif choice == "M":
            from education_system.primary_school.cli.mfa_cli import mfa_settings_menu
            mfa_settings_menu(auth)
        elif choice == "P":
            change_password_prompt(auth)
        elif choice == "Q":
            from education_system.shared.cli.security_questions_cli import security_questions_menu
            security_questions_menu(auth)
        elif choice == "G":
            from education_system.switch import request_switch
            request_switch("primary", "gui")
            return "switch"
        elif choice == "L":
            auth.logout()
            print("\n  Logged out.")
            return "logout"
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


_FLAT_MENU_MODULES = {
    "parent": ["Announcements", "Calendar", "Parents Evening", "Communication Log"],
    "student": ["Announcements", "Calendar", "Library"],
}


def _show_dashboard_summary(auth, role):
    """Print a dashboard summary showing role and available sections."""
    flat = _FLAT_MENU_MODULES.get(role)
    if flat is not None:
        # Parent / student: show individual modules, not sections
        sections = [m for m in flat if _role_mgr.can_access_module(role, m)]
    else:
        sections = _role_mgr.accessible_sections(role)
    role_display = role.replace("_", " ").title()

    # Format sections with wrapping at ~55 chars
    lines = []
    current_line = ""
    for i, s in enumerate(sections):
        sep = ", " if i > 0 else ""
        candidate = current_line + sep + s
        if len(candidate) > 55 and current_line:
            lines.append(current_line + ",")
            current_line = s
        else:
            current_line = candidate
    if current_line:
        lines.append(current_line)

    print()
    print("  =======================================================")
    print("    Dashboard Summary")
    print("  =======================================================")
    print()
    print(f"    Role: {role_display}")
    if lines:
        print(f"    Available Sections: {lines[0]}")
        for line in lines[1:]:
            print(f"                        {line}")
    print()


def main(db_path: str | None = None, user_info=None, role=None, shared_auth=None):
    """Main CLI entry point.

    If *user_info* and *role* are provided (from universal login), the
    login dialog is skipped.
    """
    ensure_directories()
    setup_logging()

    path = db_path or get_db_path()
    initialise_database(path)
    seed_default_users(path)
    seed_default_staff(path)

    auth = UserAuth()

    if user_info and role and shared_auth:
        # Pre-authenticated via universal CLI login
        auth = shared_auth
        # Set current_user on the auth object so menus work
        display = user_info.get("display_name", user_info.get("username", "User"))
        auth._current_user = {
            "user_id": user_info.get("user_id"),
            "username": user_info.get("username"),
            "display_name": display,
            "email": user_info.get("email"),
            "role": role,
            "systems": user_info.get("systems", []),
        }
        print(f"\n  Welcome, {display}! (Role: {role})")
    else:
        if not login_prompt(auth):
            sys.exit(1)

        # Determine role for the primary system
        role = "student"
        for s in auth.current_user.get("systems", []):
            if s["system_key"] == "primary":
                role = s["role"]
                break
        auth._current_user["role"] = role

    _show_dashboard_summary(auth, role)

    # Idle / inactivity auto-logout (30 minutes)
    from education_system.shared.cli.cli_helpers import enable_idle_timeout

    def _idle_logout():
        try:
            auth.logout()
        except Exception:
            pass
        logger.info("CLI session ended via idle timeout")

    enable_idle_timeout(30, _idle_logout)

    while True:
        result = None
        try:
            if _role_mgr.has_minimum_role(role, "staff"):
                result = admin_menu(auth)
            elif _role_mgr.has_minimum_role(role, "teaching_assistant"):
                result = teacher_menu(auth)
            elif role == "parent":
                result = parent_menu(auth)
            else:
                result = student_menu(auth)
        except Exception:
            logger.exception("Menu error")

        if result == "switch":
            break
        elif result == "logout":
            # Signal back to run.py for universal login (system selection)
            auth.logout()
            from education_system.switch import request_logout
            request_logout(mode="cli")
            break
        else:
            # Normal exit (choice "0")
            auth.logout()
            logger.info("CLI session ended")
            print("\n  Goodbye!")
            break
