import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.database.db import sqlite3, DatabaseManager
from datetime import datetime
import os
import random
import string
# Use email and calendar helpers from the refactored modules
from education_system.systems.university.infrastructure.i18n import (
    get_text,
    get_current_language,
)
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.database.schemas.student_union_elections_schema import (
    ELECTION_CANDIDATES_DDL,
    ELECTION_VOTES_DDL,
    RANKED_VOTES_DDL,
    ensure_election_tables,
    ensure_elections_table,
    fold_legacy_union_elections,
    sync_voting_window,
)
from education_system.systems.university.domains.student_life.domain.student_life.student_union.calendar_bridge import (
    mirror as _mirror_to_calendar,
)


# Global variable to store the auth object passed from main.py
# Import auth instance management from user_authentication
try:
    from education_system.systems.university.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

# NOTE: student_union_club_management module does not exist
# These functions need to be implemented or imported from existing modules
# NOTE: student_union_event_management module does not exist
# These functions need to be implemented or imported from existing modules
# NOTE: student_union_facility_management module does not exist
# These functions need to be implemented or imported from existing modules
# NOTE: student_union_election_management module does not exist
# These functions need to be implemented or imported from existing modules
# NOTE: student_union_admin_management module does not exist
# These functions need to be implemented or imported from existing modules
# NOTE: student_union_finance_management module does not exist
# These functions need to be implemented or imported from existing modules
from education_system.systems.university.domains.student_life.domain.student_life.student_union.services import view_all_checkouts, view_leaderboard, view_point_opportunities, award_points_to_student, auto_award_points, view_active_competitions, view_competition_results, view_my_competition_history, create_new_competition, update_competition_scores, view_facilities, manage_peer_support_system, browse_support_groups, join_support_group, view_my_support_groups, create_support_group, anonymous_peer_matching, view_wellness_resources, manage_academic_support, manage_study_groups, manage_peer_tutoring, manage_shared_resources, exam_preparation_groups, view_academic_workshops, manage_green_initiatives, track_carbon_footprint, waste_reduction_tracking, green_transport_tracking, view_eco_suppliers, green_certification_system, browse_volunteer_opportunities, signup_for_volunteer_opportunity, view_my_volunteer_activities, track_community_service_hours, generate_advanced_analytics, activity_correlation_analysis, generate_personalized_recommendations, performance_benchmarking, manage_live_streaming, interactive_virtual_features, recording_and_replay_management, manage_learning_integration, organize_academic_conferences, research_presentation_platform, learning_analytics_dashboard, manage_enhanced_voting, ranked_choice_voting, configure_voting_methods, send_confirmation_email, review_pending_materials, send_spending_warnings, view_detailed_spending, approve_reject_materials, access_control_review, log_configuration_change, test_email_notifications, reset_voting_configuration


# Every Student Union sub-package keeps its own module-level `auth`, and each
# screen checks the one belonging to *its* module. Setting only this module's
# global is what made Peer Support, Academic Support and Green Initiatives tell
# a signed-in user to log in: they read `union_context.auth`, which nobody set.
# The CLI wires auth through `set_auth` (database_manager.init_auth_for_modules),
# so `set_auth` itself has to reach all of them — a login must never leave half
# the portal thinking it is anonymous.
_AUTH_TARGET_MODULES = (
    # (module path, setter attribute)
    ("education_system.systems.university.domains.student_life.domain."
     "student_life.student_union.services.context_setup", "set_auth"),
    ("education_system.systems.university.domains.student_life.domain."
     "student_life.student_union.clubs.club_management._imports", "set_auth"),
    ("education_system.systems.university.domains.student_life.domain."
     "student_life.student_union.administration.admin_management", "set_auth"),
    ("education_system.systems.university.domains.student_life.domain."
     "student_life.student_union.administration.finance_oversight", "set_auth"),
    ("education_system.systems.university.domains.student_life.domain."
     "student_life.student_union.elections.election_management", "set_auth"),
    # events.event_management forwards to the student_union_events CLI context.
    ("education_system.systems.university.domains.student_life.domain."
     "student_life.student_union.events.event_management", "set_auth"),
    ("education_system.systems.university.domains.student_life.domain."
     "student_life.student_union.facilities.facility_management", "set_auth"),
    # The CLI menus moved to union_core.menus, which checks its own `auth`.
    ("education_system.systems.university.domains.student_life.domain."
     "student_life.student_union.administration.union_core.menus", "set_auth"),
)


def set_auth(auth_obj):
    """Set the auth object for this module and every Student Union submodule."""
    global auth
    auth = auth_obj

    import importlib

    for module_path, setter_name in _AUTH_TARGET_MODULES:
        try:
            module = importlib.import_module(module_path)
            setter = getattr(module, setter_name, None)
            if callable(setter):
                setter(auth_obj)
        except Exception as e:  # pragma: no cover - optional submodule
            print(f"(warning) Failed to propagate auth to {module_path}: {e}")

    # union_context has no set_auth of its own — context_setup owns the setter.
    # Assign directly as a backstop in case that import failed above.
    try:
        from education_system.systems.university.domains.student_life.domain.student_life.student_union.services import (
            union_context as su_misc,
        )
        if su_misc.auth is not auth_obj:
            su_misc.auth = auth_obj
    except Exception as e:
        print(f"(warning) Failed to propagate auth to union_context: {e}")


def set_auth_all(auth_obj):
    """Propagate the auth object to all Student Union submodules.

    Kept as the explicit name callers use; ``set_auth`` now does the same
    propagation, so a caller that only knows about ``set_auth`` cannot end
    up with a half-wired portal.
    """
    set_auth(auth_obj)

def _rebuild_child_table(cursor, table, create_sql):
    """Rebuild one election child table against elections(id), keeping every column.

    Columns other code added later with ALTER TABLE (candidate_name,
    nomination_date, student_id, vote_date, …) are carried across too, so the
    rebuild never drops data.
    """
    if table not in ('election_candidates', 'election_votes', 'ranked_votes'):
        raise ValueError(f"Not an election child table: {table!r}")
    # db-audit: ignore[DBW001] - table is one of the three fixed election child tables
    old_cols = [row[1] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()]
    cursor.execute(f"DROP TABLE IF EXISTS {table}_new")
    cursor.execute(create_sql.replace(f"CREATE TABLE IF NOT EXISTS {table} (",
                                      f"CREATE TABLE {table}_new (", 1))
    new_cols = {row[1] for row in cursor.execute(f"PRAGMA table_info({table}_new)").fetchall()}
    for column in old_cols:
        if column not in new_cols:
            cursor.execute(f'ALTER TABLE {table}_new ADD COLUMN "{column}"')
    column_list = ", ".join(f'"{c}"' for c in old_cols)
    cursor.execute(f"INSERT INTO {table}_new ({column_list}) SELECT {column_list} FROM {table}")
    cursor.execute(f"DROP TABLE {table}")
    cursor.execute(f"ALTER TABLE {table}_new RENAME TO {table}")


def _reconcile_election_schema():
    """Make `elections` the only election table everything points at.

    Two election tables grew up side by side: `elections` and the legacy
    `union_elections`. Every reader and writer now uses `elections` (title =
    position, start/end date = voting window). This adds the columns the
    screens need, folds any legacy `union_elections` rows across (same ids,
    nomination/voting dates included), pairs the voting window with
    start/end date, and rebuilds election_candidates / election_votes /
    ranked_votes if they still declare foreign keys against `union_elections`.
    It is idempotent. The legacy table itself is never dropped.
    """
    rebuilds = {
        'election_candidates': ELECTION_CANDIDATES_DDL,
        'election_votes': ELECTION_VOTES_DDL,
        'ranked_votes': RANKED_VOTES_DDL,
    }
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        ensure_elections_table(cursor)
        fold_legacy_union_elections(cursor)
        sync_voting_window(cursor)
        conn.commit()

        cursor.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'table'"
            " AND name IN ('election_candidates','election_votes','ranked_votes')")
        schema = {name: (sql or '') for name, sql in cursor.fetchall()}
        stale = [name for name in rebuilds if 'union_elections' in schema.get(name, '')]
        if not stale:
            return

        cursor.execute("PRAGMA foreign_keys = off")
        for table in stale:
            _rebuild_child_table(cursor, table, rebuilds[table])
        conn.commit()
        cursor.execute("PRAGMA foreign_keys = on")

    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        print(f"Could not reconcile the election tables: {e}")
    finally:
        if conn:
            conn.close()


def init_student_union_db():
    """Initialize the Student Union database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Create clubs/societies table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_clubs (
            club_id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_name TEXT UNIQUE,
            description TEXT,
            category TEXT,
            founding_date TEXT,
            status TEXT,
            president_id TEXT,
            treasurer_id TEXT,
            secretary_id TEXT,
            member_count INTEGER DEFAULT 0,
            budget REAL DEFAULT 0.0,
            FOREIGN KEY (president_id) REFERENCES students (student_id),
            FOREIGN KEY (treasurer_id) REFERENCES students (student_id),
            FOREIGN KEY (secretary_id) REFERENCES students (student_id)
        )
        ''')

        # Create club membership table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS club_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_id INTEGER,
            student_id TEXT,
            join_date TEXT,
            role TEXT,
            FOREIGN KEY (club_id) REFERENCES student_clubs (club_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Create unified events table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS unified_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT,
            source_event_id TEXT,
            title TEXT,
            description TEXT,
            event_type TEXT,
            event_category TEXT,
            start_datetime TEXT,
            end_datetime TEXT,
            location TEXT,
            building TEXT,
            room TEXT,
            room_id TEXT,
            organizer_id TEXT,
            organizer_name TEXT,
            organizer_type TEXT,
            max_capacity INTEGER,
            registration_required BOOLEAN,
            registration_deadline TEXT,
            is_public BOOLEAN,
            is_featured BOOLEAN,
            status TEXT DEFAULT 'upcoming',
            tags TEXT,
            image_url TEXT,
            virtual_link TEXT,
            event_fee REAL DEFAULT 0.0,
            payment_required BOOLEAN DEFAULT 0,
            waitlist_enabled BOOLEAN DEFAULT 1,
            qr_code_path TEXT,
            club_id TEXT,
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT,
            notes TEXT
        )
        ''')

        # Create unified event registrations table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS unified_event_registrations (
            registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            user_id TEXT,
            user_type TEXT DEFAULT 'student',
            registration_date TEXT,
            attendance_status TEXT DEFAULT 'registered',
            checked_in_at TEXT,
            check_out_time TEXT,
            payment_status TEXT,
            payment_amount REAL DEFAULT 0.0,
            payment_method TEXT,
            is_waitlisted BOOLEAN DEFAULT 0,
            num_guests INTEGER DEFAULT 0,
            feedback_rating REAL,
            feedback_comment TEXT,
            qr_code TEXT,
            cpd_credits REAL DEFAULT 0.0,
            FOREIGN KEY (event_id) REFERENCES unified_events (event_id)
        )
        ''')

        # Create facility bookings table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS facility_bookings (
            booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
            facility_name TEXT,
            booker_id TEXT,
            club_id INTEGER,
            booking_date TEXT,
            start_time TEXT,
            end_time TEXT,
            purpose TEXT,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            FOREIGN KEY (booker_id) REFERENCES students (student_id),
            FOREIGN KEY (club_id) REFERENCES student_clubs (club_id)
        )
        ''')

        # Create student union representatives table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS union_representatives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            position TEXT,
            department TEXT,
            election_date TEXT,
            term_end_date TEXT,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Election tables. `elections` is the canonical one — every election screen,
        # service and CLI reads and writes it, and election_candidates /
        # election_votes / ranked_votes key to elections(id). Fresh databases no
        # longer get `union_elections`; an existing one is folded in by
        # _reconcile_election_schema().
        ensure_election_tables(cursor)

        # Create facilities inventory table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS union_facilities (
            facility_id INTEGER PRIMARY KEY AUTOINCREMENT,
            facility_name TEXT UNIQUE,
            location TEXT,
            capacity INTEGER,
            description TEXT,
            status TEXT DEFAULT 'available',
            equipment TEXT,
            booking_fee REAL DEFAULT 0.0
        )
        ''')

        # Club Financial Management Tables
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS club_expenses (
            expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_id INTEGER,
            requester_id TEXT,
            expense_type TEXT,
            amount REAL,
            description TEXT,
            receipt_path TEXT,
            request_date TEXT,
            approval_date TEXT,
            approver_id TEXT,
            status TEXT DEFAULT 'pending',
            budget_category TEXT,
            FOREIGN KEY (club_id) REFERENCES student_clubs (club_id),
            FOREIGN KEY (requester_id) REFERENCES students (student_id),
            FOREIGN KEY (approver_id) REFERENCES students (student_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS club_budgets (
            budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_id INTEGER,
            fiscal_year TEXT,
            total_budget REAL,
            allocated_budget REAL,
            spent_amount REAL DEFAULT 0.0,
            category TEXT,
            created_date TEXT,
            updated_date TEXT,
            FOREIGN KEY (club_id) REFERENCES student_clubs (club_id)
        )
        ''')

        # Event Financial Tracking
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_finances (
            finance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            expense_type TEXT,
            amount REAL,
            description TEXT,
            date_recorded TEXT,
            receipt_path TEXT,
            revenue_type TEXT,
            FOREIGN KEY (event_id) REFERENCES unified_events (event_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            ticket_type TEXT,
            price REAL,
            quantity_available INTEGER,
            quantity_sold INTEGER DEFAULT 0,
            student_id TEXT,
            purchase_date TEXT,
            payment_status TEXT DEFAULT 'pending',
            FOREIGN KEY (event_id) REFERENCES unified_events (event_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Event Attendance System (now uses unified_event_registrations)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS unified_event_registrations (
            registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            user_id TEXT,
            user_type TEXT DEFAULT 'student',
            registration_date TEXT,
            attendance_status TEXT,
            checked_in_at TEXT,
            check_out_time TEXT,
            payment_status TEXT,
            payment_amount REAL DEFAULT 0.0,
            payment_method TEXT,
            is_waitlisted BOOLEAN DEFAULT 0,
            num_guests INTEGER DEFAULT 0,
            feedback_rating REAL,
            feedback_comment TEXT,
            qr_code TEXT,
            cpd_credits REAL DEFAULT 0.0,
            FOREIGN KEY (event_id) REFERENCES unified_events (event_id)
        )
        ''')

        # Recurring Events
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS recurring_events (
            recurring_id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_event_id INTEGER,
            recurrence_type TEXT,
            recurrence_interval INTEGER,
            end_date TEXT,
            days_of_week TEXT,
            max_occurrences INTEGER,
            current_occurrences INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (parent_event_id) REFERENCES unified_events (event_id)
        )
        ''')

        # Club Social Platform
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS club_discussions (
            discussion_id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_id INTEGER,
            author_id TEXT,
            title TEXT,
            content TEXT,
            post_date TEXT,
            last_updated TEXT,
            is_announcement BOOLEAN DEFAULT 0,
            pinned BOOLEAN DEFAULT 0,
            FOREIGN KEY (club_id) REFERENCES student_clubs (club_id),
            FOREIGN KEY (author_id) REFERENCES students (student_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS club_media (
            media_id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_id INTEGER,
            uploader_id TEXT,
            event_id INTEGER,
            file_path TEXT,
            file_type TEXT,
            caption TEXT,
            upload_date TEXT,
            FOREIGN KEY (club_id) REFERENCES student_clubs (club_id),
            FOREIGN KEY (uploader_id) REFERENCES students (student_id),
            FOREIGN KEY (event_id) REFERENCES unified_events (event_id)
        )
        ''')

        # Mentorship System
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS mentorship_relationships (
            relationship_id INTEGER PRIMARY KEY AUTOINCREMENT,
            mentor_id TEXT,
            mentee_id TEXT,
            skill_area TEXT,
            start_date TEXT,
            end_date TEXT,
            status TEXT DEFAULT 'active',
            mentor_rating REAL,
            mentee_rating REAL,
            notes TEXT,
            FOREIGN KEY (mentor_id) REFERENCES students (student_id),
            FOREIGN KEY (mentee_id) REFERENCES students (student_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS mentorship_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            relationship_id INTEGER,
            session_date TEXT,
            duration_minutes INTEGER,
            notes TEXT,
            mentor_feedback TEXT,
            mentee_feedback TEXT,
            progress_rating INTEGER,
            FOREIGN KEY (relationship_id) REFERENCES mentorship_relationships (relationship_id)
        )
        ''')

        # Equipment Management
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS union_equipment (
            equipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_name TEXT,
            category TEXT,
            description TEXT,
            serial_number TEXT,
            purchase_date TEXT,
            condition_status TEXT DEFAULT 'good',
            location TEXT,
            availability_status TEXT DEFAULT 'available',
            maintenance_due TEXT,
            replacement_cost REAL
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS equipment_checkouts (
            checkout_id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_id INTEGER,
            borrower_id TEXT,
            club_id INTEGER,
            checkout_date TEXT,
            expected_return TEXT,
            actual_return TEXT,
            condition_out TEXT,
            condition_in TEXT,
            notes TEXT,
            status TEXT DEFAULT 'checked_out',
            FOREIGN KEY (equipment_id) REFERENCES union_equipment (equipment_id),
            FOREIGN KEY (borrower_id) REFERENCES students (student_id),
            FOREIGN KEY (club_id) REFERENCES student_clubs (club_id)
        )
        ''')

        # Engagement Rewards System
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_points (
            points_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            points_earned INTEGER,
            points_spent INTEGER DEFAULT 0,
            current_balance INTEGER,
            activity_type TEXT,
            activity_description TEXT,
            earned_date TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS achievement_badges (
            badge_id INTEGER PRIMARY KEY AUTOINCREMENT,
            badge_name TEXT,
            description TEXT,
            points_required INTEGER,
            badge_icon TEXT,
            category TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            badge_id INTEGER,
            earned_date TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (badge_id) REFERENCES achievement_badges (badge_id)
        )
        ''')

        # Inter-club Competitions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS club_competitions (
            competition_id INTEGER PRIMARY KEY AUTOINCREMENT,
            competition_name TEXT,
            description TEXT,
            competition_type TEXT,
            start_date TEXT,
            end_date TEXT,
            registration_deadline TEXT,
            max_participants_per_club INTEGER,
            prizes TEXT,
            status TEXT DEFAULT 'upcoming',
            organizer_id TEXT,
            FOREIGN KEY (organizer_id) REFERENCES students (student_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS competition_participants (
            participant_id INTEGER PRIMARY KEY AUTOINCREMENT,
            competition_id INTEGER,
            club_id INTEGER,
            student_id TEXT,
            registration_date TEXT,
            score REAL DEFAULT 0.0,
            rank_position INTEGER,
            FOREIGN KEY (competition_id) REFERENCES club_competitions (competition_id),
            FOREIGN KEY (club_id) REFERENCES student_clubs (club_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Peer Support System
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS peer_support_groups (
            group_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT,
            description TEXT,
            support_type TEXT,
            facilitator_id TEXT,
            max_members INTEGER,
            current_members INTEGER DEFAULT 0,
            meeting_schedule TEXT,
            status TEXT DEFAULT 'active',
            created_date TEXT,
            FOREIGN KEY (facilitator_id) REFERENCES students (student_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS support_group_members (
            membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            student_id TEXT,
            join_date TEXT,
            anonymous_id TEXT,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (group_id) REFERENCES peer_support_groups (group_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Academic Support
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS study_groups (
            study_group_id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT,
            topic TEXT,
            organizer_id TEXT,
            max_members INTEGER,
            current_members INTEGER DEFAULT 1,
            meeting_time TEXT,
            location TEXT,
            study_date TEXT,
            status TEXT DEFAULT 'open',
            description TEXT,
            FOREIGN KEY (organizer_id) REFERENCES students (student_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tutoring_offers (
            offer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tutor_id TEXT,
            subject TEXT,
            topic TEXT,
            hourly_rate REAL,
            availability TEXT,
            experience_level TEXT,
            description TEXT,
            rating REAL DEFAULT 0.0,
            total_sessions INTEGER DEFAULT 0,
            status TEXT DEFAULT 'available',
            FOREIGN KEY (tutor_id) REFERENCES students (student_id)
        )
        ''')

        # Green Initiatives
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sustainability_tracking (
            tracking_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            club_id INTEGER,
            carbon_footprint REAL,
            waste_generated REAL,
            waste_recycled REAL,
            transport_method TEXT,
            sustainability_score REAL,
            notes TEXT,
            recorded_date TEXT,
            FOREIGN KEY (event_id) REFERENCES unified_events (event_id),
            FOREIGN KEY (club_id) REFERENCES student_clubs (club_id)
        )
        ''')

        # Community Engagement
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS volunteer_opportunities (
            opportunity_id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_name TEXT,
            contact_person TEXT,
            contact_email TEXT,
            description TEXT,
            location TEXT,
            start_date TEXT,
            end_date TEXT,
            hours_required REAL,
            skills_needed TEXT,
            max_volunteers INTEGER,
            current_volunteers INTEGER DEFAULT 0,
            status TEXT DEFAULT 'open'
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS volunteer_signups (
            signup_id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_id INTEGER,
            student_id TEXT,
            signup_date TEXT,
            hours_completed REAL DEFAULT 0.0,
            completion_date TEXT,
            feedback TEXT,
            status TEXT DEFAULT 'signed_up',
            FOREIGN KEY (opportunity_id) REFERENCES volunteer_opportunities (opportunity_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Enhanced Voting System
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS campaign_materials (
            material_id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER,
            material_type TEXT,
            content TEXT,
            file_path TEXT,
            upload_date TEXT,
            status TEXT DEFAULT 'pending_approval',
            reviewed_at TEXT,
            reviewed_by INTEGER,
            rejection_reason TEXT,
            FOREIGN KEY (candidate_id) REFERENCES election_candidates (id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS campaign_expenses (
            expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER,
            amount REAL,
            description TEXT,
            receipt_path TEXT,
            expense_date TEXT,
            approved BOOLEAN DEFAULT 0,
            FOREIGN KEY (candidate_id) REFERENCES election_candidates (id)
        )
        ''')

        # ranked_votes is created with the other election tables above.

        # Learning Integration
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS book_clubs (
            book_club_id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_name TEXT,
            current_book TEXT,
            book_author TEXT,
            discussion_leader_id TEXT,
            meeting_schedule TEXT,
            max_members INTEGER,
            current_members INTEGER DEFAULT 1,
            status TEXT DEFAULT 'active',
            description TEXT,
            FOREIGN KEY (discussion_leader_id) REFERENCES students (student_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shared_resources (
            resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
            uploader_id TEXT,
            resource_title TEXT,
            resource_type TEXT,
            subject TEXT,
            file_path TEXT,
            description TEXT,
            upload_date TEXT,
            downloads INTEGER DEFAULT 0,
            rating REAL DEFAULT 0.0,
            FOREIGN KEY (uploader_id) REFERENCES students (student_id)
        )
        ''')

        # Create some sample data for testing
        # Add sample facilities
        facilities = [
            ('Main Hall', 'Student Union Building', 500, 'Large event space with stage', 'available', 'Projector, Sound System, Chairs x500', 50.0),
            ('Meeting Room 1', 'Student Union Building', 20, 'Small meeting room', 'available', 'Whiteboard, Conference Table, Chairs x20', 10.0),
            ('Meeting Room 2', 'Student Union Building', 15, 'Small meeting room', 'available', 'Whiteboard, Conference Table, Chairs x15', 10.0),
            ('Activity Space', 'Student Union Building', 100, 'Open space for activities', 'available', 'Mats, Basic Sound System', 25.0)
        ]

        # Check if facilities already exist
        cursor.execute('SELECT COUNT(*) FROM union_facilities')
        if cursor.fetchone()[0] == 0:
            cursor.executemany(
                'INSERT INTO union_facilities (facility_name, location, capacity, description, status, equipment, booking_fee) VALUES (?, ?, ?, ?, ?, ?, ?)',
                facilities
            )
            print("Sample union facilities added!")

        conn.commit()
        conn.close()
        _reconcile_election_schema()
        print("Student Union database initialized successfully!")
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def setup_student_union_permissions(auth_manager):
    """Setup permissions for Student Union module"""
    conn = get_connection()
    cursor = conn.cursor()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    role_permissions = {
        'student':      ['view_clubs', 'join_clubs', 'view_events', 'register_for_events', 'vote_in_elections', 'view_facilities', 'request_facility_booking'],
        'club_leader':  ['manage_own_club', 'create_club_events', 'view_own_club_members', 'remove_club_members'],
        'union_rep':    ['create_club', 'approve_events', 'manage_facilities', 'approve_facility_bookings', 'view_all_clubs'],
        'admin':        ['manage_all_clubs', 'manage_all_events', 'set_up_elections', 'view_election_results', 'manage_union_reps', 'manage_all_facilities']
    }

    # 1) Ensure each permission exists
    for perms in role_permissions.values():
        for perm in perms:
            desc = perm.replace('_', ' ').capitalize()
            cursor.execute(
                'INSERT OR IGNORE INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                (perm, desc, timestamp)
            )

    # 2) Map to roles
    for role, perms in role_permissions.items():
        cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role,))
        r = cursor.fetchone()
        if not r:
            continue
        role_id = r[0]
        for perm in perms:
            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm,))
            p = cursor.fetchone()
            if not p:
                continue
            cursor.execute(
                'INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                (role_id, p[0])
            )

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# The menus and feature functions live in union_core/; re-exported here so
# every existing import, and getattr(student_union_core, name), still works.
# ---------------------------------------------------------------------------
from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.union_core.common import (  # noqa: E402
    _club_current_student,
    _send_club_email,
)
from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.union_core.clubs import (  # noqa: E402
    CLUB_JOIN_TEMPLATE,
    _club_name_exists,
    CLUB_REMOVED_TEMPLATE,
    create_club,
    delete_club,
    join_club,
    manage_club,
    update_club,
    view_clubs,
    view_my_clubs,
)
from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.union_core.events import (  # noqa: E402
    create_event,
    delete_event,
    EVENT_CANCELLED_TEMPLATE,
    EVENT_REGISTERED_TEMPLATE,
    _event_registrants,
    EVENT_UPDATED_TEMPLATE,
    _notify_registrants,
    _pick_event,
    register_for_event,
    update_event,
    view_events,
    view_my_events,
)
from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.union_core.elections import (  # noqa: E402
    create_election,
    delete_election,
    nominate_for_election,
    _pick_election,
    update_election,
    view_election_results,
    view_elections,
    vote_in_election,
)
from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.union_core.facility_bookings import (  # noqa: E402
    approve_facility_bookings,
    _current_user_row_id,
    FACILITY_DECISION_TEMPLATE,
    request_facility_booking,
    view_my_bookings,
)
from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.union_core.admin_tasks import (  # noqa: E402
    manage_union_reps,
    set_up_election,
)
from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.union_core.menus import (  # noqa: E402
    display_admin_menu,
    display_club_menu,
    display_election_menu,
    display_event_menu,
    display_facility_menu,
    display_student_union_menu,
)
