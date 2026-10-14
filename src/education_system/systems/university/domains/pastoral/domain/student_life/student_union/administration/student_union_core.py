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
from education_system.systems.university.domains.pastoral.domain.student_life.student_union.calendar_bridge import (
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
from education_system.systems.university.domains.pastoral.domain.student_life.student_union.services import view_all_checkouts, view_leaderboard, view_point_opportunities, award_points_to_student, auto_award_points, view_active_competitions, view_competition_results, view_my_competition_history, create_new_competition, update_competition_scores, view_facilities, manage_peer_support_system, browse_support_groups, join_support_group, view_my_support_groups, create_support_group, anonymous_peer_matching, view_wellness_resources, manage_academic_support, manage_study_groups, manage_peer_tutoring, manage_shared_resources, exam_preparation_groups, view_academic_workshops, manage_green_initiatives, track_carbon_footprint, waste_reduction_tracking, green_transport_tracking, view_eco_suppliers, green_certification_system, browse_volunteer_opportunities, signup_for_volunteer_opportunity, view_my_volunteer_activities, track_community_service_hours, generate_advanced_analytics, activity_correlation_analysis, generate_personalized_recommendations, performance_benchmarking, manage_live_streaming, interactive_virtual_features, recording_and_replay_management, manage_learning_integration, organize_academic_conferences, research_presentation_platform, learning_analytics_dashboard, manage_enhanced_voting, ranked_choice_voting, configure_voting_methods, send_confirmation_email, review_pending_materials, send_spending_warnings, view_detailed_spending, approve_reject_materials, access_control_review, log_configuration_change, test_email_notifications, reset_voting_configuration


# Every Student Union sub-package keeps its own module-level `auth`, and each
# screen checks the one belonging to *its* module. Setting only this module's
# global is what made Peer Support, Academic Support and Green Initiatives tell
# a signed-in user to log in: they read `union_context.auth`, which nobody set.
# The CLI wires auth through `set_auth` (database_manager.init_auth_for_modules),
# so `set_auth` itself has to reach all of them — a login must never leave half
# the portal thinking it is anonymous.
_AUTH_TARGET_MODULES = (
    # (module path, setter attribute)
    ("education_system.systems.university.domains.pastoral.domain.student_life"
     ".student_union.services.context_setup", "set_auth"),
    ("education_system.systems.university.domains.pastoral.domain.student_life"
     ".student_union.clubs.club_management._imports", "set_auth"),
    ("education_system.systems.university.domains.pastoral.domain.student_life"
     ".student_union.administration.admin_management", "set_auth"),
    ("education_system.systems.university.domains.pastoral.domain.student_life"
     ".student_union.administration.finance_oversight", "set_auth"),
    ("education_system.systems.university.domains.pastoral.domain.student_life"
     ".student_union.elections.election_management", "set_auth"),
    # events.event_management forwards to the student_union_events CLI context.
    ("education_system.systems.university.domains.pastoral.domain.student_life"
     ".student_union.events.event_management", "set_auth"),
    ("education_system.systems.university.domains.pastoral.domain.student_life"
     ".student_union.facilities.facility_management", "set_auth"),
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
        from education_system.systems.university.domains.pastoral.domain.student_life.student_union.services import (
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

def _reconcile_election_schema():
    """Point the election child tables at `elections` rather than `union_elections`.

    Two election tables grew up side by side: `elections` (what the screens read)
    and `union_elections` (what election_candidates/election_votes/ranked_votes
    declared their foreign keys against). Nominating or voting therefore failed a
    foreign key check. This folds any legacy rows into `elections` and rebuilds the
    child tables against it. It is idempotent — once rebuilt it does nothing.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'table'"
            " AND name IN ('elections','union_elections','election_candidates',"
            "'election_votes','ranked_votes')")
        schema = {name: (sql or '') for name, sql in cursor.fetchall()}

        stale = [name for name in ('election_candidates', 'election_votes', 'ranked_votes')
                 if 'union_elections' in schema.get(name, '')]
        if not stale:
            return

        # Fold legacy elections across first, keeping their ids so child rows still match.
        if 'union_elections' in schema and 'elections' in schema:
            cursor.execute("""
                INSERT INTO elections (id, title, description, start_date, end_date, status)
                SELECT u.election_id,
                       COALESCE(NULLIF(TRIM(u.position), ''), 'Election ' || u.election_id),
                       u.department, u.voting_start, u.voting_end, COALESCE(u.status, 'active')
                FROM union_elections u
                WHERE NOT EXISTS (SELECT 1 FROM elections e WHERE e.id = u.election_id)
            """)

        conn.commit()
        cursor.execute("PRAGMA foreign_keys = off")

        rebuilds = {
            'election_candidates': (
                """CREATE TABLE election_candidates_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    election_id INTEGER,
                    student_id TEXT,
                    manifesto TEXT,
                    votes INTEGER DEFAULT 0,
                    FOREIGN KEY (election_id) REFERENCES elections (id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )""",
                "INSERT INTO election_candidates_new (id, election_id, student_id, manifesto, votes)"
                " SELECT id, election_id, student_id, manifesto, votes FROM election_candidates"),
            'election_votes': (
                """CREATE TABLE election_votes_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    election_id INTEGER,
                    voter_id TEXT,
                    candidate_id INTEGER,
                    vote_time TEXT,
                    FOREIGN KEY (election_id) REFERENCES elections (id),
                    FOREIGN KEY (voter_id) REFERENCES students (student_id),
                    FOREIGN KEY (candidate_id) REFERENCES election_candidates (id)
                )""",
                "INSERT INTO election_votes_new (id, election_id, voter_id, candidate_id, vote_time)"
                " SELECT id, election_id, voter_id, candidate_id, vote_time FROM election_votes"),
            'ranked_votes': (
                """CREATE TABLE ranked_votes_new (
                    vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    election_id INTEGER,
                    voter_id TEXT,
                    candidate_preferences TEXT,
                    vote_time TEXT,
                    FOREIGN KEY (election_id) REFERENCES elections (id),
                    FOREIGN KEY (voter_id) REFERENCES students (student_id)
                )""",
                "INSERT INTO ranked_votes_new (vote_id, election_id, voter_id,"
                " candidate_preferences, vote_time)"
                " SELECT vote_id, election_id, voter_id, candidate_preferences, vote_time"
                " FROM ranked_votes"),
        }

        for table in stale:
            create_sql, copy_sql = rebuilds[table]
            cursor.execute(f"DROP TABLE IF EXISTS {table}_new")
            cursor.execute(create_sql)
            cursor.execute(copy_sql)
            cursor.execute(f"DROP TABLE {table}")
            cursor.execute(f"ALTER TABLE {table}_new RENAME TO {table}")

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

        # Create elections table. `elections` is the canonical one — it is what the
        # election screens read and write, and what the candidate/vote tables point at.
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS elections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            start_date TEXT,
            end_date TEXT,
            status TEXT DEFAULT 'active'
        )
        ''')

        # Legacy table, kept so older data is not lost. Rows here are folded into
        # `elections` by _reconcile_election_schema().
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS union_elections (
            election_id INTEGER PRIMARY KEY AUTOINCREMENT,
            position TEXT,
            department TEXT,
            nomination_start TEXT,
            nomination_end TEXT,
            voting_start TEXT,
            voting_end TEXT,
            status TEXT DEFAULT 'upcoming'
        )
        ''')

        # Create election candidates table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS election_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            election_id INTEGER,
            student_id TEXT,
            manifesto TEXT,
            votes INTEGER DEFAULT 0,
            FOREIGN KEY (election_id) REFERENCES elections (id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Create votes table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS election_votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            election_id INTEGER,
            voter_id TEXT,
            candidate_id INTEGER,
            vote_time TEXT,
            FOREIGN KEY (election_id) REFERENCES elections (id),
            FOREIGN KEY (voter_id) REFERENCES students (student_id),
            FOREIGN KEY (candidate_id) REFERENCES election_candidates (id)
        )
        ''')

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

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ranked_votes (
            vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
            election_id INTEGER,
            voter_id TEXT,
            candidate_preferences TEXT,  -- JSON string of ranked preferences
            vote_time TEXT,
            FOREIGN KEY (election_id) REFERENCES elections (id),
            FOREIGN KEY (voter_id) REFERENCES students (student_id)
        )
        ''')

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

def display_student_union_menu():
    """Enhanced Student Union Portal.

    Anything created here (clubs, events, elections, bookings, …) is
    mirrored onto the university academic calendar as it is created —
    see ``calendar_bridge`` — so there is no manual calendar sync.
    """
    global auth
    from education_system.systems.university.domains.pastoral.domain.student_life.student_union.clubs.club_management.rewards import manage_engagement_rewards
    from education_system.systems.university.domains.pastoral.domain.student_life.student_union.clubs.club_management.competitions import manage_interclub_competitions
    from education_system.systems.university.domains.pastoral.domain.student_life.student_union.clubs.club_management.mentorship import manage_mentorship_system
    from education_system.systems.university.domains.pastoral.domain.student_life.student_union.facilities.facility_management import manage_equipment_system
    from education_system.systems.university.domains.pastoral.domain.student_life.student_union.clubs.club_management.community import manage_community_engagement
    from education_system.systems.university.domains.pastoral.domain.student_life.student_union.events.event_management import manage_virtual_events

    if not auth or not auth.current_user:
        print(get_text('union.login_required', default="You must be logged in to access the Student Union Portal."))
        return

    while True:
        print(f"\n🏛️ {get_text('union.title', default='Enhanced Student Union Portal')}")
        print("=" * 45)

        # Core features
        print(f"📋 {get_text('union.section.core', default='CORE FEATURES')}")
        print(f"1. {get_text('union.menu.clubs', default='Club Management')}")
        print(f"2. {get_text('union.menu.events', default='Events & Activities')}")
        print(f"3. {get_text('union.menu.facilities', default='Facilities & Bookings')}")
        print(f"4. {get_text('union.menu.elections', default='Elections & Democracy')}")

        # Enhanced features
        print(f"\n🌟 {get_text('union.section.enhanced', default='ENHANCED FEATURES')}")
        print(f"5. {get_text('union.menu.rewards', default='Engagement Rewards System')}")
        print(f"6. {get_text('union.menu.competitions', default='Inter-club Competitions')}")
        print(f"7. {get_text('union.menu.peer_support', default='Peer Support & Wellness')}")
        print(f"8. {get_text('union.menu.academic_support', default='Academic Support')}")
        print(f"9. {get_text('union.menu.mentorship', default='Mentorship Program')}")

        # Specialized systems
        print(f"\n🎯 {get_text('union.section.specialized', default='SPECIALIZED SYSTEMS')}")
        print(f"10. {get_text('union.menu.equipment', default='Equipment Management')}")
        print(f"11. {get_text('union.menu.green', default='Green Initiatives')}")
        print(f"12. {get_text('union.menu.community', default='Community Engagement')}")
        print(f"13. {get_text('union.menu.virtual', default='Virtual Events')}")
        print(f"14. {get_text('union.menu.learning', default='Learning Integration')}")

        # Analytics and admin
        print(f"\n📊 {get_text('union.section.analytics', default='ANALYTICS & ADMIN')}")
        if auth.check_permission('manage_all_clubs') or auth.check_permission('view_election_results'):
            print(f"15. {get_text('union.menu.analytics', default='Advanced Analytics')}")
            print(f"16. {get_text('union.menu.voting', default='Enhanced Voting System')}")
            print(f"17. {get_text('union.menu.admin', default='Admin Dashboard')}")

        # Navigation options
        print(f"\n18. {get_text('union.menu.return_main', default='Return to Main Menu')}")

        choice = input(f"\n{get_text('union.prompt.choice', default='Choose an option (1-18)')}: ").strip()

        # Core features
        if choice == '1':
            display_club_menu()
        elif choice == '2':
            display_event_menu()
        elif choice == '3':
            display_facility_menu()
        elif choice == '4':
            display_election_menu()

        # Enhanced features
        elif choice == '5':
            manage_engagement_rewards()
        elif choice == '6':
            manage_interclub_competitions()
        elif choice == '7':
            manage_peer_support_system()
        elif choice == '8':
            manage_academic_support()
        elif choice == '9':
            manage_mentorship_system()

        # Specialized systems
        elif choice == '10':
            manage_equipment_system()
        elif choice == '11':
            manage_green_initiatives()
        elif choice == '12':
            manage_community_engagement()
        elif choice == '13':
            manage_virtual_events()
        elif choice == '14':
            manage_learning_integration()

        # Analytics and admin
        elif choice == '15' and (auth.check_permission('manage_all_clubs') or auth.check_permission('view_election_results')):
            generate_advanced_analytics()
        elif choice == '16' and auth.check_permission('set_up_elections'):
            manage_enhanced_voting()
        elif choice == '17' and (auth.check_permission('manage_all_clubs') or auth.check_permission('view_election_results')):
            display_admin_menu()

        # Navigation
        elif choice == '18':
            print(get_text('union.returning', default='Returning to main menu...'))
            return
        else:
            print(get_text('union.invalid_choice', default="Invalid choice. Please try again."))

def display_club_menu():
    """Display the club management menu"""
    global auth

    while True:
        print("\nClub Management")
        print("===============")

        # Options based on permissions
        options = []
        option_num = 1

        # View Clubs
        print(f"{option_num}. View Available Clubs")
        options.append("view_clubs")
        option_num += 1

        # View My Clubs
        print(f"{option_num}. View My Club Memberships")
        options.append("view_my_clubs")
        option_num += 1

        # Join a Club
        if auth.check_permission('join_clubs'):
            print(f"{option_num}. Join a Club")
            options.append("join_club")
            option_num += 1

        # Manage Club
        if auth.check_permission('manage_own_club') or auth.check_permission('manage_all_clubs'):
            print(f"{option_num}. Manage Club")
            options.append("manage_club")
            option_num += 1

        # Create Club
        if auth.check_permission('create_club') or auth.check_permission('manage_all_clubs'):
            print(f"{option_num}. Create New Club")
            options.append("create_club")
            option_num += 1

        # Update / Delete Club — previously there was no way to change a
        # club's details or close one down at all.
        if auth.check_permission('manage_own_club') or auth.check_permission('manage_all_clubs'):
            print(f"{option_num}. Update Club")
            options.append("update_club")
            option_num += 1

        if auth.check_permission('manage_all_clubs'):
            print(f"{option_num}. Delete Club")
            options.append("delete_club")
            option_num += 1

        # Return to Student Union Menu
        print(f"{option_num}. Return to Student Union Menu")

        choice = input("\nEnter your choice: ")

        # First check if user wants to return to main menu
        if choice == str(option_num):
            return

        # Then map the numeric choice to the actual option based on available permissions
        try:
            choice_index = int(choice) - 1  # Convert to 0-based index
            if 0 <= choice_index < len(options):
                selected_option = options[choice_index]

                if selected_option == "view_clubs":
                    view_clubs()
                elif selected_option == "view_my_clubs":
                    view_my_clubs()
                elif selected_option == "join_club":
                    join_club()
                elif selected_option == "manage_club":
                    manage_club()
                elif selected_option == "create_club":
                    create_club()
                elif selected_option == "update_club":
                    update_club()
                elif selected_option == "delete_club":
                    delete_club()
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Invalid choice. Please try again.")

def display_event_menu():
    """Display the event management menu"""
    global auth

    while True:
        print("\nEvents")
        print("======")

        # Options are built dynamically so the numbering stays correct when a
        # permission hides one. Create/Update/Delete previously did not exist.
        options = []
        option_num = 1

        print(f"{option_num}. View Upcoming Events")
        options.append("view_events")
        option_num += 1

        print(f"{option_num}. View My Registered Events")
        options.append("view_my_events")
        option_num += 1

        if auth.check_permission('register_for_events'):
            print(f"{option_num}. Register for an Event")
            options.append("register_for_event")
            option_num += 1

        if auth.check_permission('manage_events') or auth.check_permission('manage_all_clubs'):
            print(f"{option_num}. Create Event")
            options.append("create_event")
            option_num += 1

            print(f"{option_num}. Update Event")
            options.append("update_event")
            option_num += 1

            print(f"{option_num}. Delete Event")
            options.append("delete_event")
            option_num += 1

        print(f"{option_num}. Return to Student Union Menu")

        choice = input("\nEnter your choice: ")

        if choice == str(option_num):
            return

        try:
            choice_index = int(choice) - 1
        except ValueError:
            print("Invalid choice. Please try again.")
            continue

        if not (0 <= choice_index < len(options)):
            print("Invalid choice. Please try again.")
            continue

        selected = options[choice_index]
        if selected == "view_events":
            view_events()
        elif selected == "view_my_events":
            view_my_events()
        elif selected == "register_for_event":
            register_for_event()
        elif selected == "create_event":
            create_event()
        elif selected == "update_event":
            update_event()
        elif selected == "delete_event":
            delete_event()

def display_facility_menu():
    """Display the facility management menu"""
    global auth

    while True:
        print("\nFacilities")
        print("==========")

        # Built as a list. The old version hard-coded the numbers and then tried
        # to patch them up, so with some permission combinations "Approve" sat on
        # the same number as another option.
        options = [("View Available Facilities", view_facilities)]

        if auth.check_permission('request_facility_booking'):
            options.append(("Request Facility Booking", request_facility_booking))
            options.append(("View My Bookings", view_my_bookings))

        if auth.check_permission('approve_facility_bookings') or auth.check_permission('manage_facilities'):
            options.append(("Approve Facility Bookings", approve_facility_bookings))

        for index, (label, _action) in enumerate(options, 1):
            print(f"{index}. {label}")
        back = len(options) + 1
        print(f"{back}. Return to Student Union Menu")

        choice = input("\nEnter your choice: ").strip()

        if choice == str(back):
            return
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            options[int(choice) - 1][1]()
        else:
            print("Invalid choice. Please try again.")

def display_election_menu():
    """Display the election menu"""
    global auth

    while True:
        print("\nElections")
        print("=========")

        # Built as a list so the numbering stays correct whatever the signed-in
        # user is allowed to do.
        options = [
            ("View Current & Upcoming Elections", view_elections),
            ("View Election Results", view_election_results),
        ]

        if auth.check_permission('vote_in_elections'):
            options.append(("Vote in Active Election", vote_in_election))
            options.append(("Submit Nomination for Election", nominate_for_election))

        if auth.check_permission('manage_elections') or auth.check_permission('manage_union'):
            options.append(("Create Election", create_election))
            options.append(("Update Election", update_election))
            options.append(("Delete Election", delete_election))

        for index, (label, _action) in enumerate(options, 1):
            print(f"{index}. {label}")
        back = len(options) + 1
        print(f"{back}. Return to Student Union Menu")

        choice = input("\nEnter your choice: ").strip()

        if choice == str(back):
            return
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            options[int(choice) - 1][1]()
        else:
            print("Invalid choice. Please try again.")

def display_admin_menu():
    """Display the admin menu for student union"""
    global auth

    if not auth.check_permission('manage_all_clubs') and not auth.check_permission('approve_facility_bookings') and \
       not auth.check_permission('set_up_elections') and not auth.check_permission('manage_union_reps'):
        print("You don't have permission to access the admin menu.")
        return

    while True:
        print("\nStudent Union Administration")
        print("===========================")

        option_num = 1
        options = []

        if auth.check_permission('set_up_elections'):
            print(f"{option_num}. Set Up New Election")
            options.append("setup_election")
            option_num += 1

        if auth.check_permission('manage_union_reps'):
            print(f"{option_num}. Manage Union Representatives")
            options.append("manage_reps")
            option_num += 1

        if auth.check_permission('approve_facility_bookings'):
            print(f"{option_num}. Manage Facility Bookings")
            options.append("manage_bookings")
            option_num += 1

        if auth.check_permission('manage_all_clubs'):
            print(f"{option_num}. Manage All Clubs")
            options.append("manage_all_clubs")
            option_num += 1

        print(f"{option_num}. Return to Student Union Menu")

        choice = input("\nEnter your choice: ")

        try:
            choice_index = int(choice) - 1

            if choice == str(option_num):
                # Return to Student Union Menu
                return
            elif 0 <= choice_index < len(options):
                selected_option = options[choice_index]

                if selected_option == "setup_election":
                    # Call the imported function without cursor/conn arguments
                    conn = get_connection()
                    cursor = conn.cursor()
                    try:
                        set_up_election(cursor, conn)
                    finally:
                        try:
                            conn.close()
                        except Exception:
                            logger.debug("Suppressed exception", exc_info=True)
                elif selected_option == "manage_reps":
                    # Manage Representatives
                    manage_union_reps()
                elif selected_option == "manage_bookings":
                    # Manage Bookings
                    approve_facility_bookings()
                elif selected_option == "manage_all_clubs":
                    # Manage All Clubs
                    manage_club()  # The manage_club function will show all clubs for admins
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Invalid choice. Please try again.")
        except TypeError as e:
            print(f"Error calling function: {e}")
            print("This function may need to be updated to work with the current system.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            print("Please contact an administrator if this problem persists.")

# PLACEHOLDER FUNCTIONS FOR MISSING MODULES
# These functions need to be implemented to replace the missing imports


# ---------------------------------------------------------------------------
# Club helpers
# ---------------------------------------------------------------------------
# These screens used to ask the signed-in student to type their own student ID
# — which they may not know, and which let anyone join a club as anyone else.
# The id now comes from the authenticated session.

CLUB_JOIN_TEMPLATE = "student_life/clubs/club_join_confirmation"
CLUB_REMOVED_TEMPLATE = "student_life/clubs/club_removed"


def _club_current_student(conn=None):
    """(student_id, name, email) for the signed-in user, or (None, None, None).

    Resolved from the authenticated session rather than typed in.
    """
    user = None
    try:
        user = get_current_user()
    except Exception:
        user = None
    if not user:
        return None, None, None

    owns_conn = conn is None
    try:
        if owns_conn:
            conn = get_connection()
        row = conn.execute(
            "SELECT student_id FROM users WHERE id = ? OR username = ? LIMIT 1",
            (user.get('id'), user.get('username'))).fetchone()
        student_id = row[0] if row and row[0] else None
        if not student_id:
            return None, None, None

        detail = conn.execute(
            "SELECT first_name, last_name, email_address FROM students"
            " WHERE student_id = ? LIMIT 1", (student_id,)).fetchone()
        if detail:
            name = f"{detail[0] or ''} {detail[1] or ''}".strip() or student_id
            return student_id, name, detail[2]
        return student_id, user.get('username', student_id), user.get('email')
    except Exception as exc:
        print(f"Could not resolve your student record: {exc}")
        return None, None, None
    finally:
        if owns_conn and conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)


def _send_club_email(template_name, recipient_email, template_vars):
    """Render a club template and hand it to the university email system."""
    address = (recipient_email or '').strip()
    if not address:
        return False
    try:
        from education_system.systems.university.infrastructure.email.email_service import (
            send_email as _send,
        )
        from education_system.systems.university.infrastructure.email.template_utils import (
            render_template,
        )
    except ImportError:
        return False
    try:
        subject, body = render_template(template_name, template_vars)
        if subject is None or body is None:
            return False
        _send(recipient_email=address, subject=subject, body=body)
        return True
    except Exception:
        return False


def _club_name_exists(cursor, club_name, exclude_id=None):
    """Whether a club of this name already exists (case-insensitive)."""
    query = ("SELECT id FROM student_union_clubs"
             " WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))")
    params = [club_name]
    if exclude_id is not None:
        query += " AND id != ?"
        params.append(exclude_id)
    cursor.execute(query + " LIMIT 1", params)
    return cursor.fetchone() is not None


def create_club():
    """Create a new student club."""
    print("\n=== Create New Club ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Create clubs table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_union_clubs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                category TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        ''')

        # Names must be unique. Nothing stopped two "Chess Club" rows before,
        # which makes every later "enter the club ID" prompt ambiguous and
        # splits members across duplicates. Re-ask rather than abandoning what
        # they have already typed.
        club_name = None
        while club_name is None:
            entered = input("Enter club name (blank to cancel): ").strip()
            if not entered:
                print("Club creation cancelled.")
                return
            if _club_name_exists(cursor, entered):
                print(f"A club called '{entered}' already exists. "
                      "Please choose a different name.")
                continue
            club_name = entered

        description = input("Enter club description: ").strip()
        category = input("Enter category (Academic/Social/Sports/Cultural/Other): ").strip()

        cursor.execute('''
            INSERT INTO student_union_clubs (name, description, category)
            VALUES (?, ?, ?)
        ''', (club_name, description, category))

        conn.commit()
        club_id = cursor.lastrowid
        print(f"\n✓ Club '{club_name}' created successfully! (ID {club_id})")

        # A club has no date of its own — it goes on the calendar as a
        # founding entry so the union's activity is visible there too.
        if _mirror_to_calendar(
            name=f"SU Club founded: {club_name}", kind="club",
            description=description or f"{category or 'Student Union'} club",
            source_table="student_union_clubs", source_id=club_id,
            conn=conn,
        ):
            print("  Added to the university academic calendar.")

    except Exception as e:
        print(f"Error creating club: {e}")
    finally:
        if conn:
            conn.close()


def update_club():
    """Update an existing club's details."""
    print("\n=== Update Club ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        club_id = input("Enter club ID to update (blank to cancel): ").strip()
        if not club_id:
            return

        cursor.execute(
            'SELECT id, name, description, category, status'
            ' FROM student_union_clubs WHERE id = ?', (club_id,))
        club = cursor.fetchone()
        if not club:
            print("Club not found.")
            return

        _cid, name, description, category, status = club
        print(f"\nCurrent details:")
        print(f"  Name:        {name}")
        print(f"  Description: {description or '(none)'}")
        print(f"  Category:    {category or '(none)'}")
        print(f"  Status:      {status}")
        print("\nLeave a field blank to keep its current value.")

        new_name = name
        while True:
            entered = input(f"Name [{name}]: ").strip()
            if not entered:
                break
            if _club_name_exists(cursor, entered, exclude_id=club_id):
                print(f"A club called '{entered}' already exists. "
                      "Please choose a different name.")
                continue
            new_name = entered
            break

        new_description = input(f"Description [{description or 'none'}]: ").strip() or description
        new_category = input(f"Category [{category or 'none'}]: ").strip() or category
        new_status = input(f"Status (active/inactive) [{status}]: ").strip() or status

        changes = [(label, old, new) for label, old, new in (
            ("Name", name, new_name),
            ("Description", description, new_description),
            ("Category", category, new_category),
            ("Status", status, new_status),
        ) if (old or '') != (new or '')]

        if not changes:
            print("\nNothing was changed.")
            return

        print("\nAbout to apply these changes:")
        for label, old, new in changes:
            print(f"  - {label}: '{old or 'not set'}' -> '{new or 'not set'}'")

        if input("\nApply these changes? (y/n): ").strip().lower() != 'y':
            print("Update cancelled. Nothing has been changed.")
            return

        cursor.execute('''
            UPDATE student_union_clubs
            SET name = ?, description = ?, category = ?, status = ?
            WHERE id = ?
        ''', (new_name, new_description, new_category, new_status, club_id))
        conn.commit()
        print(f"\n✓ Club {club_id} updated ({len(changes)} change(s)).")

    except Exception as e:
        print(f"Error updating club: {e}")
    finally:
        if conn:
            conn.close()


def delete_club():
    """Delete a club, telling its members it is closing."""
    print("\n=== Delete Club ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        club_id = input("Enter club ID to delete (blank to cancel): ").strip()
        if not club_id:
            return

        cursor.execute(
            'SELECT id, name, category FROM student_union_clubs WHERE id = ?', (club_id,))
        club = cursor.fetchone()
        if not club:
            print("Club not found.")
            return
        _cid, club_name, category = club

        # Who is affected — gathered before the delete, so the notice can be
        # sent to people whose membership is about to disappear.
        members = []
        try:
            cursor.execute('''
                SELECT m.student_id, s.first_name, s.last_name, s.email_address
                FROM club_memberships m
                LEFT JOIN students s ON m.student_id = s.student_id
                WHERE m.club_id = ? AND m.status = 'active'
            ''', (club_id,))
            for sid, first, last, email in cursor.fetchall():
                members.append({
                    'student_id': sid,
                    'name': f"{first or ''} {last or ''}".strip() or sid,
                    'email': email,
                })
        except Exception as exc:
            print(f"(Could not read the member list: {exc})")

        print(f"\nAbout to delete '{club_name}' ({category or 'uncategorised'}).")
        if members:
            reachable = sum(1 for m in members if (m['email'] or '').strip())
            print(f"It has {len(members)} member(s); {reachable} can be emailed.")
            for member in members[:10]:
                mark = '' if (member['email'] or '').strip() else '  (no email on file)'
                print(f"  • {member['name']} ({member['student_id']}){mark}")
            if len(members) > 10:
                print(f"  … and {len(members) - 10} more")
        else:
            print("It has no members.")

        if input("\nDelete this club? (yes/no): ").strip().lower() != 'yes':
            print("Deletion cancelled. Nothing has been changed.")
            return

        reason = input("Reason for closing (shown to members, optional): ").strip()

        closed_by = 'the Students\' Union'
        try:
            user = get_current_user()
            if user:
                closed_by = user.get('username', closed_by)
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        cursor.execute('DELETE FROM club_memberships WHERE club_id = ?', (club_id,))
        cursor.execute('DELETE FROM student_union_clubs WHERE id = ?', (club_id,))
        conn.commit()
        print(f"\n✓ Club '{club_name}' deleted.")

        # Notify after the commit, so nobody is told about a deletion that
        # rolled back.
        if members:
            sent = failed = no_address = 0
            for member in members:
                if not (member['email'] or '').strip():
                    no_address += 1
                    continue
                if _send_club_email(CLUB_REMOVED_TEMPLATE, member['email'], {
                        'club_name': club_name,
                        'student_name': member['name'],
                        'category': category or 'Not specified',
                        'closed_date': datetime.now().strftime('%Y-%m-%d'),
                        'closed_by': closed_by,
                        'reason': reason or 'No reason was recorded.'}):
                    sent += 1
                else:
                    failed += 1
            summary = f"Member notices: {sent} sent"
            if failed:
                summary += f", {failed} failed"
            if no_address:
                summary += f", {no_address} with no address on file"
            print(summary + ".")

    except Exception as e:
        print(f"Error deleting club: {e}")
    finally:
        if conn:
            conn.close()

def view_clubs():
    """View all available clubs"""
    print("\n=== Available Clubs ===")
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, name, description, category, status
            FROM student_union_clubs
            WHERE status = 'active'
            ORDER BY category, name
        ''')

        clubs = cursor.fetchall()

        if not clubs:
            print("No clubs available.")
            return

        current_category = None
        for club in clubs:
            club_id, name, description, category, status = club
            if category != current_category:
                print(f"\n--- {category or 'Uncategorized'} ---")
                current_category = category
            print(f"{club_id}. {name}")
            if description:
                print(f"   {description}")

    except Exception as e:
        print(f"Error viewing clubs: {e}")
    finally:
        if conn:
            conn.close()

def join_club():
    """Join a student club as the signed-in student."""
    print("\n=== Join Club ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Identify the student from the session rather than asking them to
        # type their own id — they may not know it, and typing someone else's
        # would have enrolled that person instead.
        student_id, student_name, student_email = _club_current_student(conn)
        if not student_id:
            print("You must be signed in as a student to join a club.")
            return
        print(f"Joining as: {student_name} ({student_id})")

        club_id = input("Enter club ID to join: ").strip()
        if not club_id:
            print("Club ID required.")
            return

        # Create memberships table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS club_memberships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                club_id INTEGER,
                student_id TEXT,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        ''')

        # The club has to exist and be open. Nothing checked this before, so
        # a mistyped id created a membership of a club that does not exist —
        # invisible in "my memberships" (it joins on the clubs table) but
        # counted everywhere that trusts club_memberships.
        cursor.execute(
            'SELECT name, status FROM student_union_clubs WHERE id = ?', (club_id,))
        club = cursor.fetchone()
        if not club:
            print(f"No club with ID {club_id}. Use 'View Available Clubs' to see the list.")
            return
        club_name, club_status = club
        if (club_status or 'active').lower() != 'active':
            print(f"'{club_name}' is not currently active, so you cannot join it.")
            return

        # Check if already member
        cursor.execute('SELECT id FROM club_memberships WHERE club_id = ? AND student_id = ? AND status = "active"',
                      (club_id, student_id))
        if cursor.fetchone():
            print(f"You are already a member of {club_name}.")
            return

        cursor.execute('INSERT INTO club_memberships (club_id, student_id) VALUES (?, ?)',
                      (club_id, student_id))
        conn.commit()
        print(f"✓ Successfully joined {club_name}!")

        first, _, last = (student_name or '').partition(' ')
        if _send_club_email(CLUB_JOIN_TEMPLATE, student_email, {
                'club_name': club_name,
                'first_name': first or student_name or 'Student',
                'last_name': last or '',
                'student_name': student_name or 'Student'}):
            print(f"📧 Confirmation emailed to {student_email}.")
        elif student_email:
            print("Note: the confirmation email could not be sent.")
        else:
            print("No email address on file, so no confirmation was sent.")

    except Exception as e:
        print(f"Error joining club: {e}")
    finally:
        if conn:
            conn.close()

def view_my_clubs():
    """View the signed-in student's club memberships."""
    print("\n=== My Clubs ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Same as join_club: the id comes from the session, not a prompt.
        student_id, student_name, _email = _club_current_student(conn)
        if not student_id:
            print("You must be signed in as a student to view your memberships.")
            return
        print(f"Memberships for {student_name} ({student_id}):")

        cursor.execute('''
            SELECT c.name, c.category, m.join_date
            FROM club_memberships m
            JOIN student_union_clubs c ON m.club_id = c.id
            WHERE m.student_id = ? AND m.status = 'active'
            ORDER BY m.join_date DESC
        ''', (student_id,))

        clubs = cursor.fetchall()
        if not clubs:
            print("You are not a member of any clubs.")
            return

        for name, category, join_date in clubs:
            print(f"\n• {name} ({category})")
            print(f"  Joined: {join_date}")

    except Exception as e:
        print(f"Error viewing clubs: {e}")
    finally:
        if conn:
            conn.close()

def manage_club():
    """Manage club settings and members"""
    print("\n=== Manage Club ===")
    club_id = input("Enter club ID to manage: ").strip()

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT name FROM student_union_clubs WHERE id = ?', (club_id,))
        club = cursor.fetchone()
        if not club:
            print("Club not found.")
            return

        print(f"\nManaging: {club[0]}")
        print("1. Update club info")
        print("2. View members")
        print("3. Remove member")
        choice = input("Select option: ").strip()

        if choice == '1':
            new_desc = input("New description (or press Enter to skip): ").strip()
            if new_desc:
                cursor.execute('UPDATE student_union_clubs SET description = ? WHERE id = ?',
                             (new_desc, club_id))
                conn.commit()
                print("✓ Club updated!")
        elif choice == '2':
            cursor.execute('''
                SELECT student_id, join_date FROM club_memberships
                WHERE club_id = ? AND status = 'active'
            ''', (club_id,))
            members = cursor.fetchall()
            print(f"\nMembers ({len(members)}):")
            for sid, join_date in members:
                print(f"  • {sid} (joined {join_date})")

    except Exception as e:
        print(f"Error managing club: {e}")
    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# Event helpers
# ---------------------------------------------------------------------------

EVENT_REGISTERED_TEMPLATE = "student_life/student_union/event_registration_confirmation"
EVENT_UPDATED_TEMPLATE = "student_life/student_union/event_updated"
EVENT_CANCELLED_TEMPLATE = "student_life/student_union/event_cancelled"
FACILITY_DECISION_TEMPLATE = "student_life/student_union/facility_booking_decision"


def _pick_event(cursor, prompt="Select an event", statuses=("upcoming",)):
    """Show the events and let the operator pick one by number.

    Returns the chosen row, or None. Typing a raw event_id was the source of
    the "FOREIGN KEY constraint failed" on registration: any id that did not
    exist in unified_events failed the foreign key, and the error surfaced
    with no hint that the id was simply wrong.
    """
    if statuses:
        placeholders = ','.join('?' * len(statuses))
        # db-audit: ignore[DBW001] - join of placeholders
        cursor.execute(
            "SELECT event_id, title, start_datetime, location, max_capacity, status"
            " FROM unified_events"
            f" WHERE COALESCE(status, 'upcoming') IN ({placeholders})"
            " ORDER BY start_datetime", tuple(statuses))
    else:
        cursor.execute(
            "SELECT event_id, title, start_datetime, location, max_capacity, status"
            " FROM unified_events ORDER BY start_datetime")
    events = cursor.fetchall()
    if not events:
        print("There are no events to choose from.")
        return None

    print(f"\n{prompt}:")
    for index, (eid, title, start, location, capacity, status) in enumerate(events, 1):
        cursor.execute(
            "SELECT COUNT(*) FROM unified_event_registrations WHERE event_id = ?", (eid,))
        taken = cursor.fetchone()[0]
        places = f"{taken}/{capacity}" if capacity else f"{taken} registered"
        print(f"{index}. {title}")
        print(f"     {start or 'date TBC'} · {location or 'location TBC'} · "
              f"{places} · {status or 'upcoming'}")

    while True:
        raw = input(f"\nSelect an event (1-{len(events)}, blank to cancel): ").strip()
        if not raw:
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(events):
            return events[int(raw) - 1]
        print(f"Please enter a number between 1 and {len(events)}.")


def _event_registrants(cursor, event_id, exclude_student=None):
    """Everyone registered for an event, with their contact details."""
    cursor.execute('''
        SELECT r.user_id, s.first_name, s.last_name, s.email_address
        FROM unified_event_registrations r
        LEFT JOIN students s ON r.user_id = s.student_id
        WHERE r.event_id = ?
    ''', (event_id,))
    people = []
    for uid, first, last, email in cursor.fetchall():
        if exclude_student and uid == exclude_student:
            continue
        people.append({
            'student_id': uid,
            'name': f"{first or ''} {last or ''}".strip() or uid,
            'email': email,
        })
    return people


def _notify_registrants(people, template, base_vars, label):
    """Email each registrant, reporting sends, failures and missing addresses."""
    if not people:
        print(f"{label}: nobody is registered, so no email was sent.")
        return
    sent = failed = no_address = 0
    for person in people:
        if not (person['email'] or '').strip():
            no_address += 1
            continue
        template_vars = dict(base_vars)
        template_vars['student_name'] = person['name']
        template_vars['username'] = person['name']
        if _send_club_email(template, person['email'], template_vars):
            sent += 1
        else:
            failed += 1
    summary = f"{label}: {sent} sent"
    if failed:
        summary += f", {failed} failed"
    if no_address:
        summary += f", {no_address} with no address on file"
    print(summary + ".")


def view_events():
    """View all upcoming events"""
    print("\n=== Upcoming Events ===")
    try:
        conn = get_connection()
        cursor = conn.cursor()

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
                status TEXT,
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

        cursor.execute('''
            SELECT event_id, title, description, start_datetime, location, max_capacity
            FROM unified_events
            WHERE status = 'upcoming'
            ORDER BY start_datetime
        ''')

        events = cursor.fetchall()
        if not events:
            print("No upcoming events.")
            return

        for event_id, name, desc, date, location, capacity in events:
            print(f"\n{event_id}. {name}")
            print(f"   Date: {date}")
            print(f"   Location: {location}")
            if desc:
                print(f"   {desc}")

    except Exception as e:
        print(f"Error viewing events: {e}")
    finally:
        if conn:
            conn.close()

def register_for_event():
    """Register the signed-in student for an event they pick from a list."""
    print("\n=== Register for Event ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

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

        # Identify the student from the session rather than asking them to
        # type an id they may not know — and which let anyone register anyone.
        student_id, student_name, student_email = _club_current_student(conn)
        if not student_id:
            print("You must be signed in as a student to register for an event.")
            return
        print(f"Registering as: {student_name} ({student_id})")

        event = _pick_event(cursor, "Events open for registration")
        if not event:
            print("Registration cancelled.")
            return
        event_id, title, start_datetime, location, capacity, _status = event

        # Already registered?
        cursor.execute(
            "SELECT 1 FROM unified_event_registrations"
            " WHERE event_id = ? AND user_id = ? LIMIT 1", (event_id, student_id))
        if cursor.fetchone():
            print(f"You are already registered for {title}.")
            return

        # Respect the capacity rather than overbooking silently.
        if capacity:
            cursor.execute(
                "SELECT COUNT(*) FROM unified_event_registrations WHERE event_id = ?",
                (event_id,))
            if cursor.fetchone()[0] >= capacity:
                print(f"'{title}' is full ({capacity} places). "
                      "Contact the Students' Union about the waiting list.")
                return

        cursor.execute('INSERT INTO unified_event_registrations (event_id, user_id, user_type, registration_date) VALUES (?, ?, ?, CURRENT_TIMESTAMP)',
                      (event_id, student_id, 'student'))
        conn.commit()
        print(f"✓ Successfully registered for {title}!")

        event_date, _, event_time = (start_datetime or '').partition(' ')
        if _send_club_email(EVENT_REGISTERED_TEMPLATE, student_email, {
                'username': student_name or 'Student',
                'student_name': student_name or 'Student',
                'event_name': title,
                'event_date': event_date or 'To be confirmed',
                'event_time': event_time or 'To be confirmed',
                'location': location or 'To be confirmed'}):
            print(f"📧 Confirmation emailed to {student_email}.")
        elif student_email:
            print("Note: the confirmation email could not be sent.")
        else:
            print("No email address on file, so no confirmation was sent.")

    except Exception as e:
        print(f"Error registering: {e}")
    finally:
        if conn:
            conn.close()

def view_my_events():
    """View the signed-in student's event registrations."""
    print("\n=== My Events ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id, student_name, _email = _club_current_student(conn)
        if not student_id:
            print("You must be signed in as a student to view your registrations.")
            return
        print(f"Registrations for {student_name} ({student_id}):")

        cursor.execute('''
            SELECT e.title, e.start_datetime, e.location
            FROM unified_event_registrations r
            JOIN unified_events e ON r.event_id = e.event_id
            WHERE r.user_id = ? AND r.user_type = 'student'
            ORDER BY e.start_datetime
        ''', (student_id,))

        events = cursor.fetchall()
        if not events:
            print("No registered events.")
            return

        for name, date, location in events:
            print(f"\n• {name}")
            print(f"  Date: {date} | Location: {location}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

def create_event():
    """Create a new Students' Union event."""
    print("\n=== Create Event ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        title = input("Event title (blank to cancel): ").strip()
        if not title:
            print("Event creation cancelled.")
            return

        cursor.execute(
            "SELECT 1 FROM unified_events WHERE LOWER(TRIM(title)) = LOWER(TRIM(?))"
            " AND COALESCE(status,'upcoming') = 'upcoming' LIMIT 1", (title,))
        if cursor.fetchone():
            if input(f"An upcoming event called '{title}' already exists. "
                     "Create another with the same name? (y/n): ").strip().lower() != 'y':
                print("Event creation cancelled.")
                return

        description = input("Description: ").strip()

        start_datetime = None
        while start_datetime is None:
            raw = input("Start (YYYY-MM-DD HH:MM, blank to cancel): ").strip()
            if not raw:
                print("Event creation cancelled.")
                return
            try:
                datetime.strptime(raw, '%Y-%m-%d %H:%M')
                start_datetime = raw
            except ValueError:
                print("Invalid format. Please use YYYY-MM-DD HH:MM.")

        end_datetime = None
        while end_datetime is None:
            raw = input("End (YYYY-MM-DD HH:MM, blank for none): ").strip()
            if not raw:
                break
            try:
                if datetime.strptime(raw, '%Y-%m-%d %H:%M') <= datetime.strptime(
                        start_datetime, '%Y-%m-%d %H:%M'):
                    print("The end must be after the start.")
                    continue
                end_datetime = raw
            except ValueError:
                print("Invalid format. Please use YYYY-MM-DD HH:MM.")

        location = input("Location: ").strip()

        capacity = None
        while True:
            raw = input("Maximum capacity (blank for unlimited): ").strip()
            if not raw:
                break
            if raw.isdigit() and int(raw) > 0:
                capacity = int(raw)
                break
            print("Please enter a whole number greater than 0, or leave blank.")

        organizer = "Students' Union"
        try:
            user = get_current_user()
            if user:
                organizer = user.get('username', organizer)
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO unified_events
            (source_type, title, description, start_datetime, end_datetime,
             location, max_capacity, organizer_name, registration_required,
             is_public, status, created_by, created_at, updated_at)
            VALUES ('student_union', ?, ?, ?, ?, ?, ?, ?, 1, 1, 'upcoming', ?, ?, ?)
        ''', (title, description or None, start_datetime, end_datetime,
              location or None, capacity, organizer, organizer, now, now))
        conn.commit()
        event_row_id = cursor.lastrowid
        print(f"\n✓ Event '{title}' created (ID {event_row_id}).")

        if _mirror_to_calendar(
            name=f"SU Event: {title}", kind="event",
            date_start=start_datetime, date_end=end_datetime,
            description=description or None, location=location or None,
            organizer=organizer, created_by=organizer,
            source_table="unified_events", source_id=event_row_id,
            conn=conn,
        ):
            print("  Added to the university academic calendar.")

    except Exception as e:
        print(f"Error creating event: {e}")
    finally:
        if conn:
            conn.close()


def update_event():
    """Update an event and tell everyone registered what changed."""
    print("\n=== Update Event ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        chosen = _pick_event(cursor, "Select the event to update", statuses=None)
        if not chosen:
            print("Update cancelled.")
            return
        event_id = chosen[0]

        cursor.execute('''
            SELECT title, description, start_datetime, end_datetime, location,
                   max_capacity, status, organizer_name
            FROM unified_events WHERE event_id = ?
        ''', (event_id,))
        row = cursor.fetchone()
        if not row:
            print("Event not found.")
            return
        (title, description, start_datetime, end_datetime, location,
         capacity, status, organizer) = row

        print("\nLeave a field blank to keep its current value.")
        new_title = input(f"Title [{title}]: ").strip() or title
        new_description = input(f"Description [{description or 'none'}]: ").strip() or description

        new_start = start_datetime
        while True:
            raw = input(f"Start YYYY-MM-DD HH:MM [{start_datetime or 'not set'}]: ").strip()
            if not raw:
                break
            try:
                datetime.strptime(raw, '%Y-%m-%d %H:%M')
                new_start = raw
                break
            except ValueError:
                print("Invalid format. Please use YYYY-MM-DD HH:MM.")

        new_end = end_datetime
        while True:
            raw = input(f"End YYYY-MM-DD HH:MM [{end_datetime or 'not set'}]: ").strip()
            if not raw:
                break
            try:
                datetime.strptime(raw, '%Y-%m-%d %H:%M')
                new_end = raw
                break
            except ValueError:
                print("Invalid format. Please use YYYY-MM-DD HH:MM.")

        new_location = input(f"Location [{location or 'none'}]: ").strip() or location

        new_capacity = capacity
        while True:
            raw = input(f"Capacity [{capacity if capacity else 'unlimited'}]: ").strip()
            if not raw:
                break
            if raw.isdigit() and int(raw) > 0:
                new_capacity = int(raw)
                break
            print("Please enter a whole number greater than 0, or leave blank.")

        new_status = input(f"Status [{status or 'upcoming'}]: ").strip() or status

        changes = [(label, old, new) for label, old, new in (
            ("Title", title, new_title),
            ("Description", description, new_description),
            ("Start", start_datetime, new_start),
            ("End", end_datetime, new_end),
            ("Location", location, new_location),
            ("Capacity", capacity, new_capacity),
            ("Status", status, new_status),
        ) if (old if old is not None else '') != (new if new is not None else '')]

        if not changes:
            print("\nNothing was changed.")
            return

        registrants = _event_registrants(cursor, event_id)
        print("\nAbout to apply these changes:")
        for label, old, new in changes:
            print(f"  - {label}: '{old if old not in (None, '') else 'not set'}' "
                  f"-> '{new if new not in (None, '') else 'not set'}'")
        print(f"\n{len(registrants)} person(s) registered will be emailed this list.")

        if input("\nApply these changes? (y/n): ").strip().lower() != 'y':
            print("Update cancelled. Nothing has been changed.")
            return

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            UPDATE unified_events
            SET title = ?, description = ?, start_datetime = ?, end_datetime = ?,
                location = ?, max_capacity = ?, status = ?, updated_at = ?
            WHERE event_id = ?
        ''', (new_title, new_description, new_start, new_end, new_location,
              new_capacity, new_status, now, event_id))
        conn.commit()
        print(f"\n✓ Event {event_id} updated ({len(changes)} change(s)).")

        updated_by = "the Students' Union"
        try:
            user = get_current_user()
            if user:
                updated_by = user.get('username', updated_by)
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        change_list = "\n".join(
            f"  - {label}: '{old if old not in (None, '') else 'not set'}' "
            f"-> '{new if new not in (None, '') else 'not set'}'"
            for label, old, new in changes)

        _notify_registrants(registrants, EVENT_UPDATED_TEMPLATE, {
            'event_name': new_title,
            'change_list': change_list,
            'start_datetime': new_start or 'Not specified',
            'end_datetime': new_end or 'Not specified',
            'location': new_location or 'To be confirmed',
            'organizer_name': organizer or "Students' Union",
            'status': new_status or 'upcoming',
            'description': new_description or 'No description provided.',
            'updated_at': now,
            'updated_by': updated_by,
        }, "Change notices")

    except Exception as e:
        print(f"Error updating event: {e}")
    finally:
        if conn:
            conn.close()


def delete_event():
    """Cancel an event, telling everyone registered."""
    print("\n=== Delete Event ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        chosen = _pick_event(cursor, "Select the event to delete", statuses=None)
        if not chosen:
            print("Deletion cancelled.")
            return
        event_id, title, start_datetime, location, _capacity, _status = chosen

        cursor.execute("SELECT organizer_name FROM unified_events WHERE event_id = ?",
                       (event_id,))
        row = cursor.fetchone()
        organizer = row[0] if row else "Students' Union"

        registrants = _event_registrants(cursor, event_id)
        print(f"\nAbout to delete '{title}' ({start_datetime or 'date TBC'}).")
        if registrants:
            reachable = sum(1 for r in registrants if (r['email'] or '').strip())
            print(f"{len(registrants)} person(s) registered; {reachable} can be emailed.")
            for person in registrants[:10]:
                mark = '' if (person['email'] or '').strip() else '  (no email on file)'
                print(f"  • {person['name']} ({person['student_id']}){mark}")
            if len(registrants) > 10:
                print(f"  … and {len(registrants) - 10} more")
        else:
            print("Nobody is registered.")

        if input("\nDelete this event? (yes/no): ").strip().lower() != 'yes':
            print("Deletion cancelled. Nothing has been changed.")
            return

        reason = input("Reason for cancelling (shown to attendees, optional): ").strip()

        cancelled_by = "the Students' Union"
        try:
            user = get_current_user()
            if user:
                cancelled_by = user.get('username', cancelled_by)
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        cursor.execute("DELETE FROM unified_event_registrations WHERE event_id = ?",
                       (event_id,))
        cursor.execute("DELETE FROM unified_events WHERE event_id = ?", (event_id,))
        conn.commit()
        print(f"\n✓ Event '{title}' deleted.")

        _notify_registrants(registrants, EVENT_CANCELLED_TEMPLATE, {
            'event_name': title,
            'start_datetime': start_datetime or 'Not specified',
            'location': location or 'Not specified',
            'organizer_name': organizer or "Students' Union",
            'cancelled_date': datetime.now().strftime('%Y-%m-%d'),
            'cancelled_by': cancelled_by,
            'reason': reason or 'No reason was recorded.',
        }, "Cancellation notices")

    except Exception as e:
        print(f"Error deleting event: {e}")
    finally:
        if conn:
            conn.close()



def view_elections():
    """View elections, active ones first."""
    print("\n=== Elections ===")
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT e.id, e.title, e.description, e.start_date, e.end_date,
                   COALESCE(e.status, 'active'),
                   (SELECT COUNT(*) FROM election_candidates c WHERE c.election_id = e.id),
                   (SELECT COUNT(*) FROM election_votes v WHERE v.election_id = e.id)
            FROM elections e
            ORDER BY CASE WHEN COALESCE(e.status, 'active') = 'active' THEN 0 ELSE 1 END,
                     e.start_date DESC
        ''')
        elections = cursor.fetchall()

        if not elections:
            print("There are no elections yet.")
            return

        for eid, title, desc, start, end, status, candidates, votes in elections:
            print(f"\n{eid}. {title}  [{status}]")
            print(f"   Period: {start or 'start TBC'} to {end or 'end TBC'}")
            print(f"   Candidates: {candidates}   Votes cast: {votes}")
            if desc:
                print(f"   {desc}")

        print(f"\n{len(elections)} election(s).")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

def _pick_election(cursor, prompt="Select an election", statuses=None):
    """Show elections and let the operator pick one. Returns the row or None."""
    if statuses:
        placeholders = ','.join('?' * len(statuses))
        # db-audit: ignore[DBW001] - join of placeholders
        cursor.execute(
            "SELECT id, title, description, start_date, end_date,"
            " COALESCE(status,'active') FROM elections"
            f" WHERE COALESCE(status,'active') IN ({placeholders})"
            " ORDER BY start_date DESC", tuple(statuses))
    else:
        cursor.execute(
            "SELECT id, title, description, start_date, end_date,"
            " COALESCE(status,'active') FROM elections ORDER BY start_date DESC")
    elections = cursor.fetchall()
    if not elections:
        print("There are no elections to choose from.")
        return None

    print(f"\n{prompt}:")
    for index, (_eid, title, _desc, start, end, status) in enumerate(elections, 1):
        print(f"{index}. {title}")
        print(f"     {start or 'start TBC'} to {end or 'end TBC'} · {status}")

    while True:
        raw = input(f"\nSelect an election (1-{len(elections)}, blank to cancel): ").strip()
        if not raw:
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(elections):
            return elections[int(raw) - 1]
        print(f"Please enter a number between 1 and {len(elections)}.")


def create_election():
    """Create a new election."""
    print("\n=== Create Election ===")
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        title = input("Election title (blank to cancel): ").strip()
        if not title:
            print("Election creation cancelled.")
            return

        cursor.execute(
            "SELECT 1 FROM elections WHERE LOWER(TRIM(title)) = LOWER(TRIM(?)) LIMIT 1",
            (title,))
        if cursor.fetchone():
            print(f"An election called '{title}' already exists. "
                  "Please choose a different title.")
            return

        description = input("Description: ").strip()

        start_date = None
        while start_date is None:
            raw = input("Start date (YYYY-MM-DD, blank to cancel): ").strip()
            if not raw:
                print("Election creation cancelled.")
                return
            try:
                datetime.strptime(raw, '%Y-%m-%d')
                start_date = raw
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")

        end_date = None
        while end_date is None:
            raw = input("End date (YYYY-MM-DD, blank to cancel): ").strip()
            if not raw:
                print("Election creation cancelled.")
                return
            try:
                if datetime.strptime(raw, '%Y-%m-%d') < datetime.strptime(start_date, '%Y-%m-%d'):
                    print("The end date must be on or after the start date.")
                    continue
                end_date = raw
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")

        cursor.execute(
            "INSERT INTO elections (title, description, start_date, end_date, status)"
            " VALUES (?, ?, ?, ?, 'active')",
            (title, description or None, start_date, end_date))
        conn.commit()
        election_id = cursor.lastrowid
        print(f"\n✓ Election '{title}' created (ID {election_id}).")

        if _mirror_to_calendar(
            name=f"SU Election: {title}", kind="election",
            date_start=start_date, date_end=end_date,
            description=description or "Student Union election — voting open",
            source_table="elections", source_id=election_id,
            conn=conn,
        ):
            print("  Added to the university academic calendar.")

    except Exception as e:
        print(f"Error creating election: {e}")
    finally:
        if conn:
            conn.close()


def update_election():
    """Update an election's details."""
    print("\n=== Update Election ===")
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        chosen = _pick_election(cursor, "Select the election to update")
        if not chosen:
            print("Update cancelled.")
            return
        election_id, title, description, start_date, end_date, status = chosen

        print("\nLeave a field blank to keep its current value.")
        new_title = title
        while True:
            entered = input(f"Title [{title}]: ").strip()
            if not entered:
                break
            cursor.execute(
                "SELECT 1 FROM elections WHERE LOWER(TRIM(title)) = LOWER(TRIM(?))"
                " AND id != ? LIMIT 1", (entered, election_id))
            if cursor.fetchone():
                print(f"An election called '{entered}' already exists. "
                      "Please choose a different title.")
                continue
            new_title = entered
            break

        new_description = input(f"Description [{description or 'none'}]: ").strip() or description

        new_start = start_date
        while True:
            raw = input(f"Start date [{start_date or 'not set'}]: ").strip()
            if not raw:
                break
            try:
                datetime.strptime(raw, '%Y-%m-%d')
                new_start = raw
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")

        new_end = end_date
        while True:
            raw = input(f"End date [{end_date or 'not set'}]: ").strip()
            if not raw:
                break
            try:
                datetime.strptime(raw, '%Y-%m-%d')
                new_end = raw
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")

        new_status = input(f"Status (active/closed) [{status}]: ").strip() or status

        changes = [(label, old, new) for label, old, new in (
            ("Title", title, new_title),
            ("Description", description, new_description),
            ("Start date", start_date, new_start),
            ("End date", end_date, new_end),
            ("Status", status, new_status),
        ) if (old or '') != (new or '')]

        if not changes:
            print("\nNothing was changed.")
            return

        print("\nAbout to apply these changes:")
        for label, old, new in changes:
            print(f"  - {label}: '{old or 'not set'}' -> '{new or 'not set'}'")
        if input("\nApply these changes? (y/n): ").strip().lower() != 'y':
            print("Update cancelled. Nothing has been changed.")
            return

        cursor.execute(
            "UPDATE elections SET title = ?, description = ?, start_date = ?,"
            " end_date = ?, status = ? WHERE id = ?",
            (new_title, new_description, new_start, new_end, new_status, election_id))
        conn.commit()
        print(f"\n✓ Election {election_id} updated ({len(changes)} change(s)).")

    except Exception as e:
        print(f"Error updating election: {e}")
    finally:
        if conn:
            conn.close()


def delete_election():
    """Delete an election, along with its candidates and votes."""
    print("\n=== Delete Election ===")
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        chosen = _pick_election(cursor, "Select the election to delete")
        if not chosen:
            print("Deletion cancelled.")
            return
        election_id, title = chosen[0], chosen[1]

        cursor.execute("SELECT COUNT(*) FROM election_candidates WHERE election_id = ?",
                       (election_id,))
        candidates = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM election_votes WHERE election_id = ?",
                       (election_id,))
        votes = cursor.fetchone()[0]

        print(f"\nAbout to delete '{title}'.")
        print(f"It has {candidates} candidate(s) and {votes} vote(s) recorded.")
        if votes:
            print("Deleting it destroys the ballot record — this cannot be undone.")

        if input("\nDelete this election? (yes/no): ").strip().lower() != 'yes':
            print("Deletion cancelled. Nothing has been changed.")
            return

        cursor.execute("DELETE FROM election_votes WHERE election_id = ?", (election_id,))
        cursor.execute("DELETE FROM election_candidates WHERE election_id = ?", (election_id,))
        cursor.execute("DELETE FROM elections WHERE id = ?", (election_id,))
        conn.commit()
        print(f"\n✓ Election '{title}' deleted.")

    except Exception as e:
        print(f"Error deleting election: {e}")
    finally:
        if conn:
            conn.close()


def nominate_for_election():
    """Nominate the signed-in student for an election."""
    print("\n=== Election Nomination ===")
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id, student_name, _email = _club_current_student(conn)
        if not student_id:
            print("You must be signed in as a student to nominate yourself.")
            return
        print(f"Nominating: {student_name} ({student_id})")

        chosen = _pick_election(cursor, "Select the election to stand in",
                                statuses=("active", "nomination"))
        if not chosen:
            print("Nomination cancelled.")
            return
        election_id, title = chosen[0], chosen[1]

        cursor.execute(
            "SELECT 1 FROM election_candidates WHERE election_id = ? AND student_id = ? LIMIT 1",
            (election_id, student_id))
        if cursor.fetchone():
            print(f"You are already standing in {title}.")
            return

        manifesto = input("Your manifesto (what you would do): ").strip()

        cursor.execute(
            "INSERT INTO election_candidates (election_id, student_id, manifesto, votes)"
            " VALUES (?, ?, ?, 0)", (election_id, student_id, manifesto or None))
        conn.commit()
        print(f"✓ Nomination submitted for {title}!")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

def vote_in_election():
    """Cast the signed-in student's vote.

    The votes table uses voter_id and vote_time; this used to write student_id
    and vote_date, so voting failed outright.
    """
    print("\n=== Cast Vote ===")
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id, student_name, _email = _club_current_student(conn)
        if not student_id:
            print("You must be signed in as a student to vote.")
            return
        print(f"Voting as: {student_name} ({student_id})")

        chosen = _pick_election(cursor, "Select the election", statuses=("active",))
        if not chosen:
            print("Voting cancelled.")
            return
        election_id, title = chosen[0], chosen[1]

        # One vote per person.
        cursor.execute(
            "SELECT 1 FROM election_votes WHERE election_id = ? AND voter_id = ? LIMIT 1",
            (election_id, student_id))
        if cursor.fetchone():
            print(f"You have already voted in {title}.")
            return

        cursor.execute('''
            SELECT c.id, c.student_id, s.first_name, s.last_name, c.manifesto
            FROM election_candidates c
            LEFT JOIN students s ON c.student_id = s.student_id
            WHERE c.election_id = ?
            ORDER BY s.last_name, s.first_name
        ''', (election_id,))
        candidates = cursor.fetchall()
        if not candidates:
            print(f"There are no candidates standing in {title} yet.")
            return

        print(f"\nCandidates for {title}:")
        for index, (_cid, sid, first, last, manifesto) in enumerate(candidates, 1):
            who = f"{first or ''} {last or ''}".strip() or sid
            print(f"{index}. {who} ({sid})")
            if manifesto:
                print(f"     {manifesto}")

        candidate = None
        while candidate is None:
            raw = input(f"\nSelect a candidate (1-{len(candidates)}, blank to cancel): ").strip()
            if not raw:
                print("Voting cancelled. No vote has been recorded.")
                return
            if raw.isdigit() and 1 <= int(raw) <= len(candidates):
                candidate = candidates[int(raw) - 1]
            else:
                print(f"Please enter a number between 1 and {len(candidates)}.")

        candidate_id, candidate_sid, first, last, _m = candidate
        who = f"{first or ''} {last or ''}".strip() or candidate_sid
        if input(f"\nCast your vote for {who}? This cannot be changed. (yes/no): ").strip().lower() != 'yes':
            print("Voting cancelled. No vote has been recorded.")
            return

        cursor.execute(
            "INSERT INTO election_votes (election_id, voter_id, candidate_id, vote_time)"
            " VALUES (?, ?, ?, ?)",
            (election_id, student_id, candidate_id,
             datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        cursor.execute(
            "UPDATE election_candidates SET votes = COALESCE(votes, 0) + 1 WHERE id = ?",
            (candidate_id,))
        conn.commit()
        print(f"✓ Vote cast for {who} in {title}.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

def view_election_results():
    """View the results of an election.

    This used to ask for an election ID and then print raw candidate row ids
    against vote counts, which told nobody anything.
    """
    print("\n=== Election Results ===")
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        chosen = _pick_election(cursor, "Select an election")
        if not chosen:
            print("Cancelled.")
            return
        election_id, title, _desc, _start, _end, status = chosen

        cursor.execute('''
            SELECT c.id, c.student_id, s.first_name, s.last_name,
                   (SELECT COUNT(*) FROM election_votes v WHERE v.candidate_id = c.id)
            FROM election_candidates c
            LEFT JOIN students s ON c.student_id = s.student_id
            WHERE c.election_id = ?
        ''', (election_id,))
        candidates = cursor.fetchall()

        if not candidates:
            print(f"\nNobody stood in {title}.")
            return

        tallies = sorted(candidates, key=lambda row: row[4], reverse=True)
        total = sum(row[4] for row in tallies)

        print(f"\n{title}  [{status}]")
        print(f"Total votes cast: {total}")
        if not total:
            print("\nNo votes have been cast yet.")
            return

        print("\nResults:")
        for position, (_cid, sid, first, last, votes) in enumerate(tallies, 1):
            who = f"{first or ''} {last or ''}".strip() or sid
            share = (votes / total) * 100
            print(f"  {position}. {who} ({sid}): {votes} vote(s) — {share:.1f}%")

        top = tallies[0][4]
        leaders = [row for row in tallies if row[4] == top]
        if len(leaders) == 1:
            _cid, sid, first, last, votes = leaders[0]
            who = f"{first or ''} {last or ''}".strip() or sid
            label = "Winner" if status != 'active' else "Currently leading"
            print(f"\n{label}: {who} with {votes} vote(s).")
        else:
            names = ', '.join(
                (f"{row[2] or ''} {row[3] or ''}".strip() or row[1]) for row in leaders)
            print(f"\nTied on {top} vote(s): {names}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

def _current_user_row_id(conn):
    """The numeric users.id for the signed-in user, or None.

    facility_bookings.user_id is an INTEGER with a foreign key onto users(id),
    so writing a student_id string there fails the constraint. The student's
    own reference lives in the TEXT booker_id column instead.
    """
    try:
        user = get_current_user()
    except Exception:
        user = None
    if not user:
        return None
    row = conn.execute(
        "SELECT id FROM users WHERE id = ? OR username = ? LIMIT 1",
        (user.get('id'), user.get('username'))).fetchone()
    return row[0] if row else None


def request_facility_booking():
    """Request a facility booking as the signed-in student.

    The queries here targeted columns that do not exist: the real
    facility_bookings table uses booking_id / user_id / start_time / end_time,
    not id / student_id / time_slot. The CREATE TABLE IF NOT EXISTS above them
    declared the wrong shape but was a no-op against the existing table, so
    every booking failed with "no column named student_id".
    """
    print("\n=== Request Facility Booking ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id, student_name, student_email = _club_current_student(conn)
        if not student_id:
            print("You must be signed in as a student to request a booking.")
            return
        print(f"Booking as: {student_name} ({student_id})")

        cursor.execute(
            "SELECT facility_id, facility_name, location, capacity, booking_fee"
            " FROM union_facilities WHERE COALESCE(status,'available') = 'available'"
            " ORDER BY facility_name")
        facilities = cursor.fetchall()
        if not facilities:
            print("There are no facilities available to book.")
            return

        print("\nAvailable facilities:")
        for index, (_fid, name, location, capacity, fee) in enumerate(facilities, 1):
            bits = [location or 'location TBC']
            if capacity:
                bits.append(f"capacity {capacity}")
            if fee:
                bits.append(f"£{float(fee):.2f}")
            print(f"{index}. {name}  ({' · '.join(bits)})")

        facility_name = None
        while facility_name is None:
            raw = input(f"\nSelect a facility (1-{len(facilities)}, blank to cancel): ").strip()
            if not raw:
                print("Booking cancelled.")
                return
            if raw.isdigit() and 1 <= int(raw) <= len(facilities):
                facility_name = facilities[int(raw) - 1][1]
            else:
                print(f"Please enter a number between 1 and {len(facilities)}.")

        booking_date = None
        while booking_date is None:
            raw = input("Date (YYYY-MM-DD, blank to cancel): ").strip()
            if not raw:
                print("Booking cancelled.")
                return
            try:
                datetime.strptime(raw, '%Y-%m-%d')
                booking_date = raw
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")

        start_time = None
        while start_time is None:
            raw = input("Start time (HH:MM, blank to cancel): ").strip()
            if not raw:
                print("Booking cancelled.")
                return
            try:
                datetime.strptime(raw, '%H:%M')
                start_time = raw
            except ValueError:
                print("Invalid time format. Please use HH:MM.")

        end_time = None
        while end_time is None:
            raw = input("End time (HH:MM, blank to cancel): ").strip()
            if not raw:
                print("Booking cancelled.")
                return
            try:
                if datetime.strptime(raw, '%H:%M') <= datetime.strptime(start_time, '%H:%M'):
                    print("The end time must be after the start time.")
                    continue
                end_time = raw
            except ValueError:
                print("Invalid time format. Please use HH:MM.")

        purpose = input("Purpose of booking: ").strip()

        # Refuse an overlapping booking rather than double-booking the room.
        cursor.execute('''
            SELECT start_time, end_time FROM facility_bookings
            WHERE facility_name = ? AND booking_date = ?
              AND COALESCE(status, 'pending') IN ('pending', 'approved')
        ''', (facility_name, booking_date))
        for existing_start, existing_end in cursor.fetchall():
            if existing_start and existing_end and start_time < existing_end and end_time > existing_start:
                print(f"{facility_name} is already booked on {booking_date} "
                      f"from {existing_start} to {existing_end}.")
                return

        cursor.execute('''
            INSERT INTO facility_bookings
            (facility_name, user_id, booker_id, booking_date, start_time, end_time,
             purpose, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
        ''', (facility_name, _current_user_row_id(conn), student_id, booking_date,
              start_time, end_time, purpose or None,
              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        booking_id = cursor.lastrowid
        print(f"\n✓ Booking request submitted for {facility_name} on "
              f"{booking_date}, {start_time}-{end_time} (ID {booking_id}).")
        print("It is pending approval — you will be told once it is reviewed.")

        if _mirror_to_calendar(
            name=f"SU Booking: {facility_name}", kind="facility_booking",
            date=booking_date, start_time=start_time, end_time=end_time,
            location=facility_name,
            description=(purpose or "Student Union facility booking")
                        + " (pending approval)",
            created_by=student_id, organizer=student_name,
            source_table="facility_bookings", source_id=booking_id,
            conn=conn,
        ):
            print("It is on the university academic calendar.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

def view_my_bookings():
    """View the signed-in student's facility bookings."""
    print("\n=== My Bookings ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id, student_name, _email = _club_current_student(conn)
        if not student_id:
            print("You must be signed in as a student to view your bookings.")
            return
        print(f"Bookings for {student_name} ({student_id}):")

        cursor.execute('''
            SELECT facility_name, booking_date, start_time, end_time,
                   COALESCE(status, 'pending'), purpose
            FROM facility_bookings
            WHERE booker_id = ? OR user_id = ?
            ORDER BY booking_date DESC, start_time
        ''', (student_id, _current_user_row_id(cursor.connection)))

        bookings = cursor.fetchall()
        if not bookings:
            print("No bookings found.")
            return

        for facility, date, start, end, status, purpose in bookings:
            when = f"{start or '?'}-{end or '?'}"
            print(f"\n• {facility}")
            print(f"  Date: {date} | Time: {when}")
            print(f"  Status: {status}")
            if purpose:
                print(f"  Purpose: {purpose}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

def approve_facility_bookings():
    """Approve or reject pending facility bookings."""
    print("\n=== Approve Bookings ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT b.booking_id, b.facility_name,
                   COALESCE(b.booker_id, u.student_id) AS student_ref, b.booking_date,
                   b.start_time, b.end_time, b.purpose,
                   s.first_name, s.last_name, s.email_address
            FROM facility_bookings b
            LEFT JOIN users u ON b.user_id = u.id
            LEFT JOIN students s ON s.student_id = COALESCE(b.booker_id, u.student_id)
            WHERE COALESCE(b.status, 'pending') = 'pending'
            ORDER BY b.booking_date, b.start_time
        ''')

        bookings = cursor.fetchall()
        if not bookings:
            print("No pending bookings.")
            return

        for index, row in enumerate(bookings, 1):
            (_bid, facility, uid, date, start, end, purpose,
             first, last, _email) = row
            who = f"{first or ''} {last or ''}".strip() or uid
            print(f"\n{index}. {facility} — {who} ({uid})")
            print(f"   {date} {start or '?'}-{end or '?'}")
            if purpose:
                print(f"   Purpose: {purpose}")

        raw = input(f"\nSelect a booking to review (1-{len(bookings)}, blank to quit): ").strip()
        if not raw:
            return
        if not (raw.isdigit() and 1 <= int(raw) <= len(bookings)):
            print("Invalid choice.")
            return

        (booking_id, facility, uid, date, start, end, _purpose,
         first, last, email) = bookings[int(raw) - 1]
        who = f"{first or ''} {last or ''}".strip() or uid

        decision = input("Approve or reject? (a/r, blank to cancel): ").strip().lower()
        if decision not in ('a', 'r'):
            print("No decision recorded.")
            return
        new_status = 'approved' if decision == 'a' else 'rejected'

        cursor.execute('UPDATE facility_bookings SET status = ? WHERE booking_id = ?',
                       (new_status, booking_id))
        conn.commit()
        print(f"✓ Booking {booking_id} {new_status}.")

        # Tell the student either way — an approval nobody hears about is the
        # same as no booking, and a silent rejection means they turn up.
        if _send_club_email(FACILITY_DECISION_TEMPLATE, email, {
                'student_name': who,
                'facility_name': facility,
                'booking_date': date,
                'start_time': start or 'Not specified',
                'end_time': end or 'Not specified',
                'status': new_status,
                'decision_headline': ('APPROVED' if new_status == 'approved'
                                      else 'NOT APPROVED'),
                'decision_emoji': '✅' if new_status == 'approved' else '❌',
                'decision_message': (
                    'Your booking is confirmed. The space is yours for the time below.'
                    if new_status == 'approved' else
                    'Unfortunately this booking could not be approved.'),
                'next_steps': (
                    'Arrive a few minutes early. If you no longer need the space, '
                    'cancel it so someone else can use it.'
                    if new_status == 'approved' else
                    'Contact the Students\' Union to discuss alternative times or '
                    'facilities.'),
                'decided_on': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}):
            print(f"📧 Decision emailed to {email}.")
        elif email:
            print("Note: the decision email could not be sent.")
        else:
            print("No email address on file, so no decision email was sent.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

def set_up_election(cursor=None, conn=None):
    """Set up a new election"""
    print("\n=== Set Up Election ===")
    title = input("Enter election title: ").strip()
    description = input("Enter description: ").strip()
    start_date = input("Enter start date (YYYY-MM-DD): ").strip()
    end_date = input("Enter end date (YYYY-MM-DD): ").strip()

    close_conn = False
    if conn is None:
        conn = get_connection()
        cursor = conn.cursor()
        close_conn = True

    try:
        cursor.execute('''
            INSERT INTO elections (title, description, start_date, end_date)
            VALUES (?, ?, ?, ?)
        ''', (title, description, start_date, end_date))
        conn.commit()
        print("✓ Election created successfully!")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if close_conn and conn:
            conn.close()

def manage_union_reps():
    """Manage union representatives"""
    print("\n=== Manage Union Representatives ===")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS union_representatives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                position TEXT,
                term_start TEXT,
                term_end TEXT,
                status TEXT DEFAULT 'active'
            )
        ''')

        print("1. Add representative")
        print("2. View representatives")
        print("3. Remove representative")
        choice = input("Select option: ").strip()

        if choice == '1':
            # This one genuinely is somebody else's ID — an officer is being
            # appointed — so it stays a prompt, but it has to name a real student.
            student_id = input("Student ID of the representative: ").strip()
            if not student_id:
                print("Cancelled.")
                return
            cursor.execute(
                "SELECT first_name, last_name FROM students WHERE student_id = ?",
                (student_id,))
            student = cursor.fetchone()
            if not student:
                print(f"No student found with ID {student_id}.")
                return
            print(f"Appointing: {(student[0] or '')} {(student[1] or '')}".rstrip())
            position = input("Position: ").strip()
            term_start = input("Term start (YYYY-MM-DD): ").strip()
            term_end = input("Term end (YYYY-MM-DD): ").strip()

            cursor.execute('''
                INSERT INTO union_representatives (student_id, position, term_start, term_end)
                VALUES (?, ?, ?, ?)
            ''', (student_id, position, term_start, term_end))
            conn.commit()
            print("✓ Representative added!")

        elif choice == '2':
            cursor.execute('''
                SELECT student_id, position, term_start, term_end
                FROM union_representatives
                WHERE status = 'active'
            ''')
            reps = cursor.fetchall()
            if not reps:
                print("No active representatives.")
            else:
                for sid, pos, start, end in reps:
                    print(f"\n• {sid} - {pos}")
                    print(f"  Term: {start} to {end}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()
