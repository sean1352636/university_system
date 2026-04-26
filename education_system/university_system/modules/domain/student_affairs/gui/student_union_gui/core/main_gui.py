import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.university_system.infrastructure.email.template_utils import render_template
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

try:
    # Import CLI components to maintain backwards compatibility. If available,
    # include the full database initializer so the GUI can create the
    # comprehensive schema when running stand‑alone.
    from education_system.university_system.infrastructure.database.db import get_connection
    from education_system.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False

# Import navigation functions to be bound to class
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.core.navigation import (
    change_language as _change_language,
    refresh_ui_text as _refresh_ui_text,
    add_sidebar_header as _add_sidebar_header,
    add_sidebar_button as _add_sidebar_button,
    add_sidebar_separator as _add_sidebar_separator,
    switch_to_cli as _switch_to_cli,
    return_to_homescreen as _return_to_homescreen,
    setup_main_menu as _setup_main_menu,
    create_main_menu_button as _create_main_menu_button,
    return_to_main_menu as _return_to_main_menu,
)

# Import dashboard functions to be bound to class
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.core.dashboard import (
    show_main_dashboard as _show_main_dashboard,
    show_dashboard_content as _show_dashboard_content,
    _render_dashboard_tab as _render_dashboard_tab_func,
    show_dashboard_tab as _show_dashboard_tab,
)

# Import utility functions to be bound to class
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.core.utilities import (
    _get_all_student_emails as _get_all_student_emails_func,
    _send_email_via_gui as _send_email_via_gui_func,
    _show_email_fallback as _show_email_fallback_func,
    DatabaseQueryDialog as _DatabaseQueryDialog,
)

# Import misc functions to be bound to class
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.misc import (
    _on_mousewheel as _on_mousewheel_func,
    open_event_attendance_dialog as _open_event_attendance_dialog,
)

# Import profile functions
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.core.profile import (
    show_profile as _show_profile,
    show_database_info as _show_database_info,
    show_about as _show_about,
    change_password as _change_password,
)

# Import club functions
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.clubs.club_views import (
    show_clubs_content as _show_clubs_content,
    _render_clubs_tab as _render_clubs_tab_func,
    on_club_select as _on_club_select,
    refresh_clubs_list as _refresh_clubs_list,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.clubs.club_actions import (
    join_selected_club as _join_selected_club,
    create_club_dialog as _create_club_dialog,
)

# Import event functions
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.events.event_views import (
    show_events_content as _show_events_content,
    _render_events_tab as _render_events_tab_func,
    refresh_events_list as _refresh_events_list,
    show_my_events as _show_my_events,
    view_event_details as _view_event_details,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.events.event_actions import (
    _register_event_operation as _register_event_operation_func,
    create_event_dialog as _create_event_dialog,
    register_for_selected_event as _register_for_selected_event,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.events.event_virtual import open_virtual_events_dialog as _open_virtual_events_dialog
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.events.event_finance import open_event_financial_tracking_dialog as _open_event_financial_tracking_dialog
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.events.event_ticketing import open_event_ticketing_dialog as _open_event_ticketing_dialog
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.events.event_recurring import open_recurring_events_dialog as _open_recurring_events_dialog

# Import facility functions
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.facilities.facility_booking import (
    show_facilities_content as _show_facilities_content,
    _render_facilities_tab as _render_facilities_tab_func,
    open_approve_facility_bookings_dialog as _open_approve_facility_bookings_dialog,
    submit_booking_request as _submit_booking_request,
    load_facilities as _load_facilities,
    refresh_my_bookings as _refresh_my_bookings,
)

# Import admin functions
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.admin.admin_panel import (
    show_admin_content as _show_admin_content,
    _render_admin_tab as _render_admin_tab_func,
    setup_users_management as _setup_users_management,
    setup_club_administration as _setup_club_administration,
    setup_system_info as _setup_system_info,
    refresh_users_list as _refresh_users_list,
    change_user_role as _change_user_role,
    delete_user as _delete_user,
    view_all_clubs_admin as _view_all_clubs_admin,
    show_club_statistics as _show_club_statistics,
    export_club_data as _export_club_data,
    refresh_system_info as _refresh_system_info,
    backup_database as _backup_database,
    check_database_integrity as _check_database_integrity,
)

# Import payment functions
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.payments.payment_processing import (
    show_club_payments_content as _show_club_payments_content,
    _create_payment_overview_tab as _create_payment_overview_tab_func,
    _create_payment_history_tab as _create_payment_history_tab_func,
    _create_payment_reports_tab as _create_payment_reports_tab_func,
    _create_record_payment_tab as _create_record_payment_tab_func,
    _create_refunds_tab as _create_refunds_tab_func,
)

# Import election functions
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.elections.election_core import open_elections_dialog as _open_elections_dialog
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.elections.election_campaigns import (
    open_campaign_expenses_dialog as _open_campaign_expenses_dialog,
    open_candidate_profiles_dialog as _open_candidate_profiles_dialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.elections.election_voting_methods import (
    open_manage_enhanced_voting_dialog as _open_manage_enhanced_voting_dialog,
    open_ranked_choice_voting_dialog as _open_ranked_choice_voting_dialog,
    open_configure_voting_methods_dialog as _open_configure_voting_methods_dialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.elections.election_setup import open_setup_election_dialog as _open_setup_election_dialog
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.elections.election_accessibility import open_election_accessibility_dialog as _open_election_accessibility_dialog
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.elections.election_compliance import (
    open_campaign_compliance_dialog as _open_campaign_compliance_dialog,
    open_election_security_dialog as _open_election_security_dialog,
    open_vote_integrity_dialog as _open_vote_integrity_dialog,
)

# Import volunteer functions
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.volunteer.volunteer import (
    open_volunteer_opportunities_dialog as _open_volunteer_opportunities_dialog,
    open_community_service_hours_dialog as _open_community_service_hours_dialog,
    open_community_engagement_dialog as _open_community_engagement_dialog,
)

# Import competition functions
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.competitions.interclub_competitions import open_interclub_competitions_dialog as _open_interclub_competitions_dialog

# Import analytics functions
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.analytics.analytics import (
    open_advanced_analytics_dialog as _open_advanced_analytics_dialog,
    open_engagement_trends_dialog as _open_engagement_trends_dialog,
    open_retention_insights_dialog as _open_retention_insights_dialog,
)

# Import equipment functions
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.equipment.equipment_admin import (
    open_manage_equipment_system_dialog as _open_manage_equipment_system_dialog,
    open_add_new_equipment_dialog as _open_add_new_equipment_dialog,
    open_update_equipment_status_dialog as _open_update_equipment_status_dialog,
    open_equipment_maintenance_tracking_dialog as _open_equipment_maintenance_tracking_dialog,
    open_generate_equipment_reports_dialog as _open_generate_equipment_reports_dialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.equipment.equipment_browse import (
    open_browse_available_equipment_dialog as _open_browse_available_equipment_dialog,
    open_view_equipment_details_dialog as _open_view_equipment_details_dialog,
    open_search_equipment_dialog as _open_search_equipment_dialog,
)
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.equipment.equipment_checkout import (
    open_checkout_equipment_dialog as _open_checkout_equipment_dialog,
    open_return_equipment_dialog as _open_return_equipment_dialog,
    open_my_equipment_checkouts_dialog as _open_my_equipment_checkouts_dialog,
)

# Import support functions
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.support.peer_support import open_peer_support_wellness_dialog as _open_peer_support_wellness_dialog

# Import academic functions
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.academic.academic_support import open_academic_support_dialog as _open_academic_support_dialog

# Import green initiatives functions
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.green.green_initiatives import open_green_initiatives_dialog as _open_green_initiatives_dialog

# Import integration functions
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.integrations.external_integrations import (
    open_calendar_with_club_events as _open_calendar_with_club_events,
    _add_club_events_to_calendar as _add_club_events_to_calendar_func,
    open_shop_gui_direct as _open_shop_gui_direct,
    open_shop_for_club_merchandise as _open_shop_for_club_merchandise,
    open_restaurant_for_club_booking as _open_restaurant_for_club_booking,
)

# Import trip management dialog
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.trips.trips import (
    open_trip_management_dialog as _open_trip_management_dialog,
)

# Import streaming functions
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.streaming.live_streaming import open_live_streaming_dialog as _open_live_streaming_dialog

# Import conference functions
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.conferences.conferences import open_academic_conferences_dialog as _open_academic_conferences_dialog

# Import knowledge sharing functions
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.knowledge.knowledge_sharing import open_knowledge_sharing_dialog as _open_knowledge_sharing_dialog

# Import student council launcher
from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.core.navigation import (
    open_student_council_dialog as _open_student_council_dialog,
)

class StudentUnionGUI:
    """Main GUI application for Student Union Management System"""

    # Bind navigation functions as methods
    change_language = _change_language
    refresh_ui_text = _refresh_ui_text
    add_sidebar_header = _add_sidebar_header
    add_sidebar_button = _add_sidebar_button
    add_sidebar_separator = _add_sidebar_separator
    switch_to_cli = _switch_to_cli
    return_to_homescreen = _return_to_homescreen
    setup_main_menu = _setup_main_menu
    create_main_menu_button = _create_main_menu_button
    return_to_main_menu = _return_to_main_menu

    # Bind dashboard functions as methods
    show_main_dashboard = _show_main_dashboard
    show_dashboard_content = _show_dashboard_content
    _render_dashboard_tab = _render_dashboard_tab_func
    show_dashboard_tab = _show_dashboard_tab

    # Bind utility functions as methods
    _get_all_student_emails = _get_all_student_emails_func
    _send_email_via_gui = _send_email_via_gui_func
    _show_email_fallback = _show_email_fallback_func
    send_event_notification_to_all_students = _DatabaseQueryDialog.send_event_notification_to_all_students
    send_new_club_announcement = _DatabaseQueryDialog.send_new_club_announcement
    send_club_join_confirmation = _DatabaseQueryDialog.send_club_join_confirmation

    # Bind misc functions as methods
    _on_mousewheel = _on_mousewheel_func
    open_event_attendance_dialog = _open_event_attendance_dialog

    # Bind profile functions
    show_profile = _show_profile
    show_database_info = _show_database_info
    show_about = _show_about
    change_password = _change_password

    # Bind club functions
    show_clubs_content = _show_clubs_content
    _render_clubs_tab = _render_clubs_tab_func
    on_club_select = _on_club_select
    refresh_clubs_list = _refresh_clubs_list
    join_selected_club = _join_selected_club
    create_club_dialog = _create_club_dialog

    # Bind event functions
    show_events_content = _show_events_content
    _render_events_tab = _render_events_tab_func
    _register_event_operation = _register_event_operation_func
    open_virtual_events_dialog = _open_virtual_events_dialog
    open_event_financial_tracking_dialog = _open_event_financial_tracking_dialog
    open_event_ticketing_dialog = _open_event_ticketing_dialog
    open_recurring_events_dialog = _open_recurring_events_dialog
    refresh_events_list = _refresh_events_list
    create_event_dialog = _create_event_dialog
    show_my_events = _show_my_events
    register_for_selected_event = _register_for_selected_event
    view_event_details = _view_event_details

    # Bind facility functions
    show_facilities_content = _show_facilities_content
    _render_facilities_tab = _render_facilities_tab_func
    open_approve_facility_bookings_dialog = _open_approve_facility_bookings_dialog
    submit_booking_request = _submit_booking_request
    load_facilities = _load_facilities
    refresh_my_bookings = _refresh_my_bookings

    # Bind admin functions
    show_admin_content = _show_admin_content
    _render_admin_tab = _render_admin_tab_func
    setup_users_management = _setup_users_management
    setup_club_administration = _setup_club_administration
    setup_system_info = _setup_system_info
    refresh_users_list = _refresh_users_list
    change_user_role = _change_user_role
    delete_user = _delete_user
    view_all_clubs_admin = _view_all_clubs_admin
    show_club_statistics = _show_club_statistics
    export_club_data = _export_club_data
    refresh_system_info = _refresh_system_info
    backup_database = _backup_database
    check_database_integrity = _check_database_integrity

    # Bind payment functions
    show_club_payments_content = _show_club_payments_content
    _create_payment_overview_tab = _create_payment_overview_tab_func
    _create_payment_history_tab = _create_payment_history_tab_func
    _create_payment_reports_tab = _create_payment_reports_tab_func
    _create_record_payment_tab = _create_record_payment_tab_func
    _create_refunds_tab = _create_refunds_tab_func

    # Bind election functions
    open_elections_dialog = _open_elections_dialog
    open_campaign_expenses_dialog = _open_campaign_expenses_dialog
    open_candidate_profiles_dialog = _open_candidate_profiles_dialog
    open_manage_enhanced_voting_dialog = _open_manage_enhanced_voting_dialog
    open_ranked_choice_voting_dialog = _open_ranked_choice_voting_dialog
    open_configure_voting_methods_dialog = _open_configure_voting_methods_dialog
    open_setup_election_dialog = _open_setup_election_dialog
    open_election_accessibility_dialog = _open_election_accessibility_dialog
    open_campaign_compliance_dialog = _open_campaign_compliance_dialog
    open_election_security_dialog = _open_election_security_dialog
    open_vote_integrity_dialog = _open_vote_integrity_dialog

    def open_election_voting_portal(self):
        """Launch the merged Tk voting GUI in a Toplevel.

        This is the polished card-based voting interface; the other
        ``Elections & Voting`` entries above are the per-feature CLI
        dialogs that wrap the underlying service layer.
        """
        try:
            from education_system.university_system.modules.domain.student_affairs.student_union.elections.election_gui import (  # noqa: E501
                open_in_toplevel,
            )
            open_in_toplevel(self.root, getattr(self, 'auth', None))
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror(
                "Election Voting Portal",
                f"Could not launch the voting portal:\n{e}",
                parent=getattr(self, 'root', None))

    # Bind volunteer functions
    open_volunteer_opportunities_dialog = _open_volunteer_opportunities_dialog
    open_community_service_hours_dialog = _open_community_service_hours_dialog
    open_community_engagement_dialog = _open_community_engagement_dialog

    # Bind competition functions
    open_interclub_competitions_dialog = _open_interclub_competitions_dialog

    # Bind analytics functions
    open_advanced_analytics_dialog = _open_advanced_analytics_dialog
    open_engagement_trends_dialog = _open_engagement_trends_dialog
    open_retention_insights_dialog = _open_retention_insights_dialog

    # Bind equipment functions
    open_manage_equipment_system_dialog = _open_manage_equipment_system_dialog
    open_add_new_equipment_dialog = _open_add_new_equipment_dialog
    open_update_equipment_status_dialog = _open_update_equipment_status_dialog
    open_equipment_maintenance_tracking_dialog = _open_equipment_maintenance_tracking_dialog
    open_generate_equipment_reports_dialog = _open_generate_equipment_reports_dialog
    open_browse_available_equipment_dialog = _open_browse_available_equipment_dialog
    open_view_equipment_details_dialog = _open_view_equipment_details_dialog
    open_search_equipment_dialog = _open_search_equipment_dialog
    open_checkout_equipment_dialog = _open_checkout_equipment_dialog
    open_return_equipment_dialog = _open_return_equipment_dialog
    open_my_equipment_checkouts_dialog = _open_my_equipment_checkouts_dialog

    # Bind support functions
    open_peer_support_wellness_dialog = _open_peer_support_wellness_dialog

    # Bind academic functions
    open_academic_support_dialog = _open_academic_support_dialog

    # Bind green initiatives functions
    open_green_initiatives_dialog = _open_green_initiatives_dialog

    # Bind integration functions
    open_calendar_with_club_events = _open_calendar_with_club_events
    _add_club_events_to_calendar = _add_club_events_to_calendar_func
    open_shop_gui_direct = _open_shop_gui_direct
    open_shop_for_club_merchandise = _open_shop_for_club_merchandise
    open_restaurant_for_club_booking = _open_restaurant_for_club_booking
    open_trip_management_dialog = _open_trip_management_dialog

    # Bind streaming functions
    open_live_streaming_dialog = _open_live_streaming_dialog

    # Bind conference functions
    open_academic_conferences_dialog = _open_academic_conferences_dialog

    # Bind knowledge sharing functions
    open_knowledge_sharing_dialog = _open_knowledge_sharing_dialog

    # Bind student council launcher
    open_student_council_dialog = _open_student_council_dialog

    def __init__(self, parent=None):
        if parent:
            self.root = parent
            self.master = parent  # Set master for consistency
            # Don't create a new Tk instance if parent is provided
        else:
            self.root = tk.Tk()
            self.master = self.root  # Set master for consistency

        # Initialize i18n for multi-language support
        init_i18n()

        self.root.title(_t("student_union.window_title"))
        self.root.geometry("1400x900")
        self.root.minsize(1000, 700)

        # Initialize variables
        self.current_user = None
        self.auth_manager = None
        self.initialized = False  # Track if GUI was properly initialized

        # Use centralized path configuration
        # Always use the central student_records.db in university_system/data/db_files
        self.db_path = str(paths.DEFAULT_DB_PATH)

        # GUI components
        self.main_frame = None
        self.content_frame = None
        self.status_bar = None
        self.menu_bar = None

        # Setup database
        self.setup_database()

        # Get authenticated user from centralized auth
        auth = get_auth()
        if auth is None:
            auth = UserAuth()
        if not auth.current_user:
            # If no user is authenticated and this is standalone mode (no parent)
            if not parent:
                messagebox.showerror(
                    _t("student_union.auth_required_title"),
                    _t("student_union.auth_required_msg")
                )
                # Destroy the window and mark as not initialized
                self.root.destroy()
                self.initialized = False
                return
            else:
                # In embedded mode (has parent), don't destroy window yet
                # The parent will set authentication after initialization
                # Mark as not fully initialized yet
                self.initialized = False
                # Don't setup GUI yet - wait for parent to set auth
                return

        # User is authenticated, get their info
        self.current_user = {
            'id': auth.current_user['id'],
            'username': auth.current_user['username'],
            'email': auth.current_user.get('email', ''),
            'role': auth.current_user['role'],
            'student_id': auth.current_user.get('student_id')
        }
        self.auth_manager = auth

        # Setup GUI (works for both embedded and standalone)
        self.setup_gui()

        # Mark as successfully initialized
        self.initialized = True

        # Always populate the dashboard. The old `if not parent` guard left
        # every embedded caller (e.g. the role shells opening via a fresh
        # Toplevel) with a blank window because nothing downstream called
        # show_main_dashboard().
        self.show_main_dashboard()

    # ------------------------------------------------------------------ helpers
    def _safe_db_call(self, operation_func, *args, **kwargs):
        """
        Execute a database operation with basic error handling.

        Returns the operation result on success, or False/None on failure.
        """
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            result = operation_func(conn, *args, **kwargs)
            conn.commit()
            return result
        except sqlite3.Error as exc:
            logging_error = getattr(logging, "error", print)
            logging_error(f"StudentUnionGUI DB error: {exc}")
            if conn:
                try:
                    conn.rollback()
                except sqlite3.Error:
                    pass
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except sqlite3.Error:
                    pass

    def setup_database(self):
        """Initialize database connection and tables"""
        try:
            # If the CLI's enhanced initializer is available, invoke it first.
            # To ensure that the tables are created in the same file used by
            # this GUI (self.db_path), temporarily override the default
            # database path used by the refactored.database.db module. This
            # allows the CLI initializer to operate on the same database file.
            if init_student_union_db:
                try:
                    import education_system.university_system.infrastructure.database.db as _db_module
                    # Backup original default path and override it
                    _old_db_path = getattr(_db_module, 'DEFAULT_DB_PATH', None)
                    _db_module.DEFAULT_DB_PATH = self.db_path
                    init_student_union_db()
                    # Restore original default path
                    if _old_db_path is not None:
                        _db_module.DEFAULT_DB_PATH = _old_db_path
                except (sqlite3.Error, OSError, IOError) as e:
                    # Log but do not crash if enhanced initialization fails
                    print(f"Warning: failed to initialize enhanced student union database: {e}")

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                # Create basic tables if they don't exist
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        email TEXT,
                        role TEXT DEFAULT 'student',
                        created_at TEXT,
                        last_login TEXT
                    )
                ''')

                # Add last_login column if it doesn't exist (migration)
                try:
                    cursor.execute("SELECT last_login FROM users LIMIT 1")
                except sqlite3.OperationalError:
                    cursor.execute("ALTER TABLE users ADD COLUMN last_login TEXT")
                    conn.commit()

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS students (
                        student_id TEXT PRIMARY KEY,
                        first_name TEXT NOT NULL,
                        last_name TEXT NOT NULL,
                        email_address TEXT UNIQUE NOT NULL,
                        course TEXT,
                        year_of_study INTEGER,
                        enrollment_date TEXT
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS student_clubs (
                        club_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        club_name TEXT UNIQUE NOT NULL,
                        description TEXT,
                        category TEXT,
                        member_count INTEGER DEFAULT 0,
                        president_id TEXT,
                        treasurer_id TEXT,
                        secretary_id TEXT,
                        status TEXT DEFAULT 'active',
                        created_date TEXT,
                        FOREIGN KEY (president_id) REFERENCES students (student_id),
                        FOREIGN KEY (treasurer_id) REFERENCES students (student_id),
                        FOREIGN KEY (secretary_id) REFERENCES students (student_id)
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS union_events (
                        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_name TEXT NOT NULL,
                        description TEXT,
                        organizer_id INTEGER,
                        event_date TEXT,
                        start_time TEXT,
                        end_time TEXT,
                        location TEXT,
                        category TEXT,
                        max_attendees INTEGER,
                        current_attendees INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'upcoming',
                        created_at TEXT,
                        FOREIGN KEY (organizer_id) REFERENCES student_clubs (club_id)
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS club_members (
                        member_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        club_id INTEGER,
                        student_id TEXT,
                        role TEXT DEFAULT 'member',
                        join_date TEXT,
                        FOREIGN KEY (club_id) REFERENCES student_clubs (club_id),
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS facility_bookings (
                        booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        facility_name TEXT,
                        user_id INTEGER,
                        booking_date TEXT,
                        start_time TEXT,
                        end_time TEXT,
                        purpose TEXT,
                        status TEXT DEFAULT 'pending',
                        created_at TEXT,
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS union_events (
                        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_name TEXT NOT NULL,
                        description TEXT,
                        organizer_id INTEGER,
                        event_date TEXT,
                        start_time TEXT,
                        end_time TEXT,
                        location TEXT,
                        category TEXT,
                        max_attendees INTEGER,
                        current_attendees INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'upcoming',
                        created_at TEXT,
                        FOREIGN KEY (organizer_id) REFERENCES student_clubs (club_id)
                    )
                ''')

                conn.commit()
            finally:
                conn.close()

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to initialize database: {e}")
            sys.exit(1)

    def set_auth(self, auth_manager):
        """Set authentication manager for integration with main system"""
        self.auth_manager = auth_manager
        if auth_manager and hasattr(auth_manager, 'current_user') and auth_manager.current_user:
            self.current_user = {
                'id': auth_manager.current_user.get('id'),
                'username': auth_manager.current_user.get('username'),
                'email': auth_manager.current_user.get('email', ''),
                'role': auth_manager.current_user.get('role', 'student'),
                'student_id': auth_manager.current_user.get('student_id')
            }
            print(f"Authentication context set for user: {self.current_user['username']}")

    def setup_gui_embedded(self, parent_window):
        """Setup GUI for embedded use in parent window"""
        self.root = parent_window
        self.setup_gui()

        # Override the window close behavior to not exit the entire application
        def on_closing():
            self.root.destroy()

        self.root.protocol("WM_DELETE_WINDOW", on_closing)

    def setup_gui(self):
        """Setup the main GUI structure with sidebar navigation"""
        # Configure style
        style = ttk.Style()
        style.theme_use('clam')

        # Configure colors for sidebar
        style.configure('Sidebar.TFrame', background='#2c3e50')
        style.configure('SidebarButton.TButton', padding=10, font=('Arial', 10))
        style.configure('SidebarHeader.TLabel', background='#34495e', foreground='white',
                       font=('Arial', 11, 'bold'), padding=10)

        # Menu bar setup (without File menu)
        self.menu_bar = tk.Menu(self.root)
        self.root.config(menu=self.menu_bar)

        # Language menu
        language_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label=_t("menu.language"), menu=language_menu)
        language_menu.add_command(
            label=f"{_t('menu.change_language')} [{get_current_language_name()}]",
            command=self.change_language
        )

        # Main container - horizontal split
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Left sidebar with scrollbar
        sidebar_container = ttk.Frame(main_container, style='Sidebar.TFrame')
        sidebar_container.pack(side=tk.LEFT, fill=tk.Y, padx=0, pady=0)

        # Canvas for scrollable sidebar
        self.sidebar_canvas = tk.Canvas(sidebar_container, width=280, bg='#2c3e50',
                                        highlightthickness=0)
        self.sidebar_scrollbar = ttk.Scrollbar(sidebar_container, orient="vertical",
                                               command=self.sidebar_canvas.yview)
        self.scrollable_sidebar = ttk.Frame(self.sidebar_canvas, style='Sidebar.TFrame')

        self.scrollable_sidebar.bind(
            "<Configure>",
            lambda e: self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all"))
        )

        self.sidebar_window = self.sidebar_canvas.create_window((0, 0), window=self.scrollable_sidebar, anchor="nw")
        self.sidebar_canvas.configure(yscrollcommand=self.sidebar_scrollbar.set)

        # Bind canvas configure to update sidebar width
        def on_sidebar_canvas_configure(event):
            self.sidebar_canvas.itemconfigure(self.sidebar_window, width=event.width)
        self.sidebar_canvas.bind("<Configure>", on_sidebar_canvas_configure)

        self.sidebar_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.sidebar_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Enable mouse wheel scrolling
        self.sidebar_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        # Linux scroll support
        self.sidebar_canvas.bind_all("<Button-4>", lambda e: self.sidebar_canvas.yview_scroll(-1, "units"))
        self.sidebar_canvas.bind_all("<Button-5>", lambda e: self.sidebar_canvas.yview_scroll(1, "units"))

        # Right content area
        content_container = ttk.Frame(main_container)
        content_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Main frame (for content)
        self.main_frame = content_container

        # Status bar
        self.status_label = ttk.Label(self.root, text=_t("common.ready"), relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

        # Build sidebar navigation
        self.build_sidebar_navigation()

    def build_sidebar_navigation(self):
        """Build the complete sidebar navigation with all features"""
        # Dashboard Section
        self.add_sidebar_header("📊 Main", "")
        self.add_sidebar_button("Dashboard", self.show_dashboard_content, "🏠")
        self.add_sidebar_button("My Profile", self.show_profile, "👤")

        # Core Features
        self.add_sidebar_separator()
        self.add_sidebar_header("🎓 Core Features", "")
        self.add_sidebar_button("Clubs", self.show_clubs_content, "👥")
        self.add_sidebar_button("Events", self.show_events_content, "📅")
        self.add_sidebar_button("Facilities", self.show_facilities_content, "🏢")

        # Elections & Voting
        self.add_sidebar_separator()
        self.add_sidebar_header("🗳️ Elections & Voting", "")
        # Single canonical entry — replaces the older "Elections & Voting"
        # data-grid dialog. Self-nomination is now reachable from the
        # voter dashboard inside this same window.
        self.add_sidebar_button("Elections & Voting",
                                self.open_election_voting_portal, "🗳️")
        self.add_sidebar_button("Student Council", self.open_student_council_dialog, "🏛️")
        self.add_sidebar_button("Candidate Profiles", self.open_candidate_profiles_dialog, "👤")
        self.add_sidebar_button("Ranked Choice Voting", self.open_ranked_choice_voting_dialog, "🥇")
        self.add_sidebar_button("Election Accessibility", self.open_election_accessibility_dialog, "♿")
        self.add_sidebar_button("Setup Election", self.open_setup_election_dialog, "⚙️", admin_only=True)
        self.add_sidebar_button("Campaign Expenses", self.open_campaign_expenses_dialog, "💰", staff_only=True)
        self.add_sidebar_button("Campaign Compliance", self.open_campaign_compliance_dialog, "⚖️", staff_only=True)
        self.add_sidebar_button("Election Security", self.open_election_security_dialog, "🔒", staff_only=True)
        self.add_sidebar_button("Vote Integrity Check", self.open_vote_integrity_dialog, "✅", staff_only=True)
        self.add_sidebar_button("Manage Enhanced Voting", self.open_manage_enhanced_voting_dialog, "🔧", admin_only=True)
        self.add_sidebar_button("Configure Voting Methods", self.open_configure_voting_methods_dialog, "⚙️", admin_only=True)

        # Community & Engagement
        self.add_sidebar_separator()
        self.add_sidebar_header("🤝 Community & Engagement", "")
        self.add_sidebar_button("Community Engagement", self.open_community_engagement_dialog, "🤝")
        self.add_sidebar_button("Volunteer Opportunities", self.open_volunteer_opportunities_dialog, "🌱")
        self.add_sidebar_button("Community Service Hours", self.open_community_service_hours_dialog, "📋")
        self.add_sidebar_button("Inter-Club Competitions", self.open_interclub_competitions_dialog, "🏆")
        self.add_sidebar_button("Engagement Trends", self.open_engagement_trends_dialog, "📊", staff_only=True)
        self.add_sidebar_button("Retention Insights", self.open_retention_insights_dialog, "📈", staff_only=True)

        # Events & Activities
        self.add_sidebar_separator()
        self.add_sidebar_header("🎉 Advanced Events", "")
        self.add_sidebar_button("Event Ticketing", self.open_event_ticketing_dialog, "🎫")
        self.add_sidebar_button("Recurring Events", self.open_recurring_events_dialog, "🔄")
        self.add_sidebar_button("Event Attendance", self.open_event_attendance_dialog, "📊")
        self.add_sidebar_button("Virtual Events", self.open_virtual_events_dialog, "💻")
        self.add_sidebar_button("Knowledge Sharing", self.open_knowledge_sharing_dialog, "🎓")
        self.add_sidebar_button("Event Financial Tracking", self.open_event_financial_tracking_dialog, "💰", staff_only=True)

        # Facilities & Equipment
        self.add_sidebar_separator()
        self.add_sidebar_header("🏢 Facilities & Equipment", "")
        self.add_sidebar_button("Browse Equipment", self.open_browse_available_equipment_dialog, "📋")
        self.add_sidebar_button("Search Equipment", self.open_search_equipment_dialog, "🔍")
        self.add_sidebar_button("Equipment Details", self.open_view_equipment_details_dialog, "ℹ️")
        self.add_sidebar_button("Check Out Equipment", self.open_checkout_equipment_dialog, "📤")
        self.add_sidebar_button("Return Equipment", self.open_return_equipment_dialog, "📥")
        self.add_sidebar_button("My Equipment Checkouts", self.open_my_equipment_checkouts_dialog, "📜")
        self.add_sidebar_button("Equipment System Hub", self.open_manage_equipment_system_dialog, "🏠", admin_only=True)
        self.add_sidebar_button("Add Equipment", self.open_add_new_equipment_dialog, "➕", admin_only=True)
        self.add_sidebar_button("Update Equipment Status", self.open_update_equipment_status_dialog, "🔧", admin_only=True)
        self.add_sidebar_button("Maintenance Tracking", self.open_equipment_maintenance_tracking_dialog, "🛠️", admin_only=True)
        self.add_sidebar_button("Equipment Reports", self.open_generate_equipment_reports_dialog, "📊", admin_only=True)
        self.add_sidebar_button("Approve Facility Bookings", self.open_approve_facility_bookings_dialog, "✅", admin_only=True)

        # Support & Wellness
        self.add_sidebar_separator()
        self.add_sidebar_header("💚 Support & Wellness", "")
        self.add_sidebar_button("Peer Support & Wellness", self.open_peer_support_wellness_dialog, "🤝")
        self.add_sidebar_button("Academic Support", self.open_academic_support_dialog, "🎓")

        # Sustainability
        self.add_sidebar_separator()
        self.add_sidebar_header("🌱 Sustainability", "")
        self.add_sidebar_button("Green Initiatives", self.open_green_initiatives_dialog, "🌱")

        # Integrations
        self.add_sidebar_separator()
        self.add_sidebar_header("🔗 Integrations", "")
        self.add_sidebar_button("Club Payment Management", self.show_club_payments_content, "💰")
        self.add_sidebar_button("Club Merchandise", self.open_shop_for_club_merchandise, "👕")
        self.add_sidebar_button("University Shop", self.open_shop_gui_direct, "🛒")
        self.add_sidebar_button("University Restaurant", lambda: self.open_restaurant_for_club_booking("General"), "🍽️")
        self.add_sidebar_button("Student Union Calendar", self.open_calendar_with_club_events, "📅")
        self.add_sidebar_button("Trip Management", self.open_trip_management_dialog, "🧳")

        # Advanced Features
        self.add_sidebar_separator()
        self.add_sidebar_header("🚀 Advanced Features", "")
        self.add_sidebar_button("Advanced Analytics", self.open_advanced_analytics_dialog, "📊", staff_only=True)
        self.add_sidebar_button("Live Streaming", self.open_live_streaming_dialog, "📡", staff_only=True)
        self.add_sidebar_button("Academic Conferences", self.open_academic_conferences_dialog, "🎓", staff_only=True)

        # Administration
        if self.is_admin() or self.is_staff():
            self.add_sidebar_separator()
            self.add_sidebar_header("⚙️ Administration", "")
            self.add_sidebar_button("Admin Panel", self.show_admin_content, "🔧", staff_only=True)
            self.add_sidebar_button("Database Info", self.show_database_info, "💾", staff_only=True)

        # Help & About
        self.add_sidebar_separator()
        self.add_sidebar_header("❓ Help", "")
        self.add_sidebar_button("About", self.show_about, "ℹ️")
        if CLI_AVAILABLE:
            self.add_sidebar_button("Switch to CLI", self.switch_to_cli, "💻")

        # Return to Homescreen
        self.add_sidebar_separator()
        self.add_sidebar_button("🏠 Return to Homescreen", self.return_to_homescreen, "")

        # Force scrollregion update to ensure all buttons are accessible
        self.scrollable_sidebar.update_idletasks()
        self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all"))

    def clear_content(self):
        """Clear the current content frame"""
        if self.content_frame:
            self.content_frame.destroy()
        self.content_frame = ttk.Frame(self.main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True)

    def update_status(self, message: str):
        """Update status bar message"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        status_text = f"{timestamp} - {message}"

        if hasattr(self, 'status_label'):
            self.status_label.config(text=status_text)
        elif hasattr(self, 'status_bar'):
            self.status_bar.config(text=status_text)

    def get_user_role(self):
        """Get the current user's role"""
        try:
            if self.current_user and isinstance(self.current_user, dict):
                return self.current_user.get('role', '').lower()
            return None
        except (KeyError, TypeError, AttributeError) as e:
            print(f"Error getting user role: {e}")
            return None

    def is_admin(self):
        """Check if current user is admin"""
        role = self.get_user_role()
        return role == 'admin'

    def is_staff(self):
        """Check if current user is staff"""
        role = self.get_user_role()
        return role == 'staff'

    def is_student(self):
        """Check if current user is student"""
        role = self.get_user_role()
        return role == 'student'

    def run(self):
        """Run the GUI application"""
        try:
            self.update_status("Application started")
            self.root.mainloop()
        except (tk.TclError, AttributeError) as e:
            messagebox.showerror("Application Error", f"An unexpected error occurred: {e}")
        finally:
            try:
                if hasattr(self, 'root'):
                    self.root.quit()
            except (tk.TclError, AttributeError):
                pass

    def update_status(self, message: str):
        """Update status bar message"""
        self.status_label.config(text=message)
        self.master.update_idletasks()


