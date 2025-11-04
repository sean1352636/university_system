from university_system.infrastructure.database.db import sqlite3, DatabaseManager
from datetime import datetime
import os
import random
import string
# Use email and calendar helpers from the refactored modules
from university_system.infrastructure.email import send_confirmation_email
from university_system.modules.domain.academics.services.academic_calendar import AcademicCalendarManager
from university_system.infrastructure.database.db import get_connection


# Global variable to store the auth object passed from main.py
# Import auth instance management from user_authentication
try:
    from university_system.infrastructure.auth.user_authentication import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)
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
from university_system.modules.core.services.student_union_misc import (
    view_all_checkouts,
    view_leaderboard,
    view_point_opportunities,
    award_points_to_student,
    auto_award_points,
    view_active_competitions,
    view_competition_results,
    view_my_competition_history,
    create_new_competition,
    update_competition_scores,
    view_facilities,
    manage_peer_support_system,
    browse_support_groups,
    join_support_group,
    view_my_support_groups,
    create_support_group,
    anonymous_peer_matching,
    view_wellness_resources,
    manage_academic_support,
    manage_study_groups,
    manage_peer_tutoring,
    manage_shared_resources,
    exam_preparation_groups,
    view_academic_workshops,
    manage_green_initiatives,
    track_carbon_footprint,
    waste_reduction_tracking,
    green_transport_tracking,
    view_eco_suppliers,
    green_certification_system,
    browse_volunteer_opportunities,
    signup_for_volunteer_opportunity,
    view_my_volunteer_activities,
    track_community_service_hours,
    generate_advanced_analytics,
    activity_correlation_analysis,
    generate_personalized_recommendations,
    performance_benchmarking,
    manage_live_streaming,
    interactive_virtual_features,
    recording_and_replay_management,
    manage_learning_integration,
    organize_academic_conferences,
    research_presentation_platform,
    learning_analytics_dashboard,
    manage_enhanced_voting,
    ranked_choice_voting,
    configure_voting_methods,
    send_confirmation_email,
    review_pending_materials,
    send_spending_warnings,
    view_detailed_spending,
    approve_reject_materials,
    access_control_review,
    log_configuration_change,
    test_email_notifications,
    reset_voting_configuration,
    manage_union_reps,
)


def set_auth(auth_obj):
    """Set the auth object for use in this module"""
    global auth
    auth = auth_obj

def set_auth_all(auth_obj):
    """Propagate the auth object to all Student Union submodules."""
    # Always set on this module first
    set_auth(auth_obj)

    # Best-effort propagation to submodules that expose set_auth
    try:
        # Only import modules that actually exist
        from university_system.modules.core.services import student_union_misc as su_misc
        if hasattr(su_misc, 'set_auth'):
            su_misc.set_auth(auth_obj)

    except Exception as e:
        print(f"(warning) Failed to propagate auth to all student union modules: {e}")

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
        
        # Create events table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS union_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name TEXT,
            description TEXT,
            event_date TEXT,
            start_time TEXT,
            end_time TEXT,
            location TEXT,
            organizer_id INTEGER,
            category TEXT,
            max_attendees INTEGER,
            current_attendees INTEGER DEFAULT 0,
            status TEXT DEFAULT 'upcoming',
            FOREIGN KEY (organizer_id) REFERENCES student_clubs (club_id)
        )
        ''')
        
        # Create event registrations table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            student_id TEXT,
            registration_date TEXT,
            attendance_status TEXT DEFAULT 'registered',
            FOREIGN KEY (event_id) REFERENCES union_events (event_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
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
        
        # Create elections table
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
            FOREIGN KEY (election_id) REFERENCES union_elections (election_id),
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
            FOREIGN KEY (election_id) REFERENCES union_elections (election_id),
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
            FOREIGN KEY (event_id) REFERENCES union_events (event_id)
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
            FOREIGN KEY (event_id) REFERENCES union_events (event_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # Event Attendance System
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_attendance (
            attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            student_id TEXT,
            check_in_time TEXT,
            check_out_time TEXT,
            qr_code TEXT,
            cpd_credits REAL DEFAULT 0.0,
            attendance_verified BOOLEAN DEFAULT 0,
            FOREIGN KEY (event_id) REFERENCES union_events (event_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
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
            FOREIGN KEY (parent_event_id) REFERENCES union_events (event_id)
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
            FOREIGN KEY (event_id) REFERENCES union_events (event_id)
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
            FOREIGN KEY (event_id) REFERENCES union_events (event_id),
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
            FOREIGN KEY (election_id) REFERENCES union_elections (election_id),
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
    """Enhanced Student Union Portal with academic calendar sync"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to access the Student Union Portal.")
        return

    while True:
        print("\n🏛️ Enhanced Student Union Portal")
        print("=" * 45)
        
        # Core features
        print("📋 CORE FEATURES")
        print("1. Club Management")
        print("2. Events & Activities")
        print("3. Facilities & Bookings")
        print("4. Elections & Democracy")
        
        # Enhanced features
        print("\n🌟 ENHANCED FEATURES")
        print("5. Engagement Rewards System")
        print("6. Inter-club Competitions")
        print("7. Peer Support & Wellness")
        print("8. Academic Support")
        print("9. Mentorship Program")
        
        # Specialized systems
        print("\n🎯 SPECIALIZED SYSTEMS")
        print("10. Equipment Management")
        print("11. Green Initiatives")
        print("12. Community Engagement")
        print("13. Virtual Events")
        print("14. Learning Integration")
        
        # Analytics and admin
        print("\n📊 ANALYTICS & ADMIN")
        if auth.check_permission('manage_all_clubs') or auth.check_permission('view_election_results'):
            print("15. Advanced Analytics")
            print("16. Enhanced Voting System")
            print("17. Admin Dashboard")
        
        # Navigation options
        print("\n18. Return to Main Menu")
        print("19. Sync Academic Calendar")
        
        choice = input("\nChoose an option (1-19): ").strip()
        
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
        
        # Navigation and calendar sync
        elif choice == '18':
            return
        elif choice == '19':
            # Sync Academic Calendar
            manager = AcademicCalendarManager()
            ical_url = input("Academic calendar iCal URL: ").strip()
            manager.calendar_sync(ical_url)
            print("Done syncing. Check your calendar for any conflicts or upcoming deadlines.")
        else:
            print("Invalid choice. Please try again.")

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
        
        # Options
        print("1. View Upcoming Events")
        print("2. View My Registered Events")
        
        if auth.check_permission('register_for_events'):
            print("3. Register for an Event")
            print("4. Return to Student Union Menu")
            max_option = 4
        else:
            print("3. Return to Student Union Menu")
            max_option = 3
        
        choice = input("\nEnter your choice: ")
        
        if choice == '1':
            # View Events
            view_events()
        elif choice == '2':
            # View My Events
            view_my_events()
        elif choice == '3' and auth.check_permission('register_for_events'):
            # Register for Event
            register_for_event()
        elif choice == str(max_option):
            # Return to Student Union Menu
            return
        else:
            print("Invalid choice. Please try again.")

def display_facility_menu():
    """Display the facility management menu"""
    global auth
    
    while True:
        print("\nFacilities")
        print("==========")
        
        # Options
        print("1. View Available Facilities")
        
        if auth.check_permission('request_facility_booking'):
            print("2. Request Facility Booking")
            print("3. View My Bookings")
            max_option = 4
        else:
            max_option = 2
        
        if auth.check_permission('approve_facility_bookings') or auth.check_permission('manage_facilities'):
            print(f"{max_option}. Approve Facility Bookings")
            max_option += 1
        
        print(f"{max_option}. Return to Student Union Menu")
        
        choice = input("\nEnter your choice: ")
        
        if choice == '1':
            # View Facilities
            view_facilities()
        elif choice == '2' and auth.check_permission('request_facility_booking'):
            # Request Booking
            request_facility_booking()
        elif choice == '3' and auth.check_permission('request_facility_booking'):
            # View My Bookings
            view_my_bookings()
        elif (choice == '4' and auth.check_permission('approve_facility_bookings')) or \
             (choice == '2' and not auth.check_permission('request_facility_booking') and 
              auth.check_permission('approve_facility_bookings')):
            # Approve Bookings
            approve_facility_bookings()
        elif choice == str(max_option):
            # Return to Student Union Menu
            return
        else:
            print("Invalid choice. Please try again.")

def display_election_menu():
    """Display the election menu"""
    global auth
    
    while True:
        print("\nElections")
        print("=========")
        
        # Options
        print("1. View Current & Upcoming Elections")
        print("2. View Election Results")
        
        max_option = 3
        if auth.check_permission('vote_in_elections'):
            print("3. Vote in Active Election")
            max_option = 4
            
            # Check if any elections are in nomination phase
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                current_date = datetime.now().strftime('%Y-%m-%d')
                cursor.execute('''
                SELECT COUNT(*) FROM union_elections
                WHERE status = 'nomination'
                AND nomination_start <= ? AND nomination_end >= ?
                ''', (current_date, current_date))
                
                if cursor.fetchone()[0] > 0:
                    print("4. Submit Nomination for Election")
                    max_option = 5
                
                conn.close()
            except sqlite3.Error:
                pass
        
        print(f"{max_option}. Return to Student Union Menu")
        
        choice = input("\nEnter your choice: ")
        
        if choice == '1':
            # View Elections
            view_elections()
        elif choice == '2':
            # View Results
            view_election_results()
        elif choice == '3' and auth.check_permission('vote_in_elections'):
            # Vote
            vote_in_election()
        elif choice == '4' and max_option >= 5:
            # Submit Nomination
            nominate_for_election()
        elif choice == str(max_option):
            # Return to Student Union Menu
            return
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
                            pass
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

def create_club():
    """Create a new student club"""
    print("\n=== Create New Club ===")
    club_name = input("Enter club name: ").strip()
    if not club_name:
        print("Club name cannot be empty.")
        return

    description = input("Enter club description: ").strip()
    category = input("Enter category (Academic/Social/Sports/Cultural/Other): ").strip()

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

        cursor.execute('''
            INSERT INTO student_union_clubs (name, description, category)
            VALUES (?, ?, ?)
        ''', (club_name, description, category))

        conn.commit()
        print(f"\n✓ Club '{club_name}' created successfully!")

    except Exception as e:
        print(f"Error creating club: {e}")
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
    """Join a student club"""
    print("\n=== Join Club ===")
    club_id = input("Enter club ID to join: ").strip()
    if not club_id:
        print("Club ID required.")
        return

    student_id = input("Enter your student ID: ").strip()
    if not student_id:
        print("Student ID required.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

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

        # Check if already member
        cursor.execute('SELECT id FROM club_memberships WHERE club_id = ? AND student_id = ? AND status = "active"',
                      (club_id, student_id))
        if cursor.fetchone():
            print("You are already a member of this club.")
            return

        cursor.execute('INSERT INTO club_memberships (club_id, student_id) VALUES (?, ?)',
                      (club_id, student_id))
        conn.commit()
        print(f"✓ Successfully joined club!")

    except Exception as e:
        print(f"Error joining club: {e}")
    finally:
        if conn:
            conn.close()

def view_my_clubs():
    """View user's club memberships"""
    print("\n=== My Clubs ===")
    student_id = input("Enter your student ID: ").strip()

    try:
        conn = get_connection()
        cursor = conn.cursor()

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

def view_events():
    """View all upcoming events"""
    print("\n=== Upcoming Events ===")
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_union_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                event_date TEXT,
                location TEXT,
                capacity INTEGER,
                status TEXT DEFAULT 'upcoming'
            )
        ''')

        cursor.execute('''
            SELECT id, name, description, event_date, location, capacity
            FROM student_union_events
            WHERE status = 'upcoming'
            ORDER BY event_date
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
    """Register for an event"""
    print("\n=== Register for Event ===")
    event_id = input("Enter event ID: ").strip()
    student_id = input("Enter your student ID: ").strip()

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS event_registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER,
                student_id TEXT,
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('INSERT INTO event_registrations (event_id, student_id) VALUES (?, ?)',
                      (event_id, student_id))
        conn.commit()
        print("✓ Successfully registered for event!")

    except Exception as e:
        print(f"Error registering: {e}")
    finally:
        if conn:
            conn.close()

def view_my_events():
    """View user's registered events"""
    print("\n=== My Events ===")
    student_id = input("Enter your student ID: ").strip()

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT e.name, e.event_date, e.location
            FROM event_registrations r
            JOIN student_union_events e ON r.event_id = e.id
            WHERE r.student_id = ?
            ORDER BY e.event_date
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

def view_elections():
    """View active elections"""
    print("\n=== Active Elections ===")
    try:
        conn = get_connection()
        cursor = conn.cursor()

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

        cursor.execute('SELECT id, title, description, start_date, end_date FROM elections WHERE status = "active"')
        elections = cursor.fetchall()

        if not elections:
            print("No active elections.")
            return

        for eid, title, desc, start, end in elections:
            print(f"\n{eid}. {title}")
            print(f"   Period: {start} to {end}")
            if desc:
                print(f"   {desc}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

def nominate_for_election():
    """Nominate for an election"""
    print("\n=== Election Nomination ===")
    election_id = input("Enter election ID: ").strip()
    student_id = input("Enter your student ID: ").strip()
    position = input("Enter position: ").strip()

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS election_nominations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                election_id INTEGER,
                student_id TEXT,
                position TEXT,
                nomination_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('INSERT INTO election_nominations (election_id, student_id, position) VALUES (?, ?, ?)',
                      (election_id, student_id, position))
        conn.commit()
        print("✓ Nomination submitted!")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

def vote_in_election():
    """Cast vote in election"""
    print("\n=== Cast Vote ===")
    election_id = input("Enter election ID: ").strip()
    student_id = input("Enter your student ID: ").strip()
    candidate_id = input("Enter candidate ID: ").strip()

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS election_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                election_id INTEGER,
                student_id TEXT,
                candidate_id TEXT,
                vote_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Check if already voted
        cursor.execute('SELECT id FROM election_votes WHERE election_id = ? AND student_id = ?',
                      (election_id, student_id))
        if cursor.fetchone():
            print("You have already voted in this election.")
            return

        cursor.execute('INSERT INTO election_votes (election_id, student_id, candidate_id) VALUES (?, ?, ?)',
                      (election_id, student_id, candidate_id))
        conn.commit()
        print("✓ Vote cast successfully!")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

def view_election_results():
    """View election results"""
    print("\n=== Election Results ===")
    election_id = input("Enter election ID: ").strip()

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT candidate_id, COUNT(*) as votes
            FROM election_votes
            WHERE election_id = ?
            GROUP BY candidate_id
            ORDER BY votes DESC
        ''', (election_id,))

        results = cursor.fetchall()
        if not results:
            print("No votes cast yet.")
            return

        print("\nResults:")
        for candidate, votes in results:
            print(f"  {candidate}: {votes} votes")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

def request_facility_booking():
    """Request facility booking"""
    print("\n=== Request Facility Booking ===")
    facility_name = input("Enter facility name: ").strip()
    student_id = input("Enter your student ID: ").strip()
    booking_date = input("Enter date (YYYY-MM-DD): ").strip()
    time_slot = input("Enter time slot: ").strip()

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS facility_bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                facility_name TEXT,
                student_id TEXT,
                booking_date TEXT,
                time_slot TEXT,
                status TEXT DEFAULT 'pending',
                request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            INSERT INTO facility_bookings (facility_name, student_id, booking_date, time_slot)
            VALUES (?, ?, ?, ?)
        ''', (facility_name, student_id, booking_date, time_slot))
        conn.commit()
        print("✓ Booking request submitted!")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

def view_my_bookings():
    """View user's facility bookings"""
    print("\n=== My Bookings ===")
    student_id = input("Enter your student ID: ").strip()

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT facility_name, booking_date, time_slot, status
            FROM facility_bookings
            WHERE student_id = ?
            ORDER BY booking_date DESC
        ''', (student_id,))

        bookings = cursor.fetchall()
        if not bookings:
            print("No bookings found.")
            return

        for facility, date, time, status in bookings:
            print(f"\n• {facility}")
            print(f"  Date: {date} | Time: {time}")
            print(f"  Status: {status}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

def approve_facility_bookings():
    """Approve pending facility bookings"""
    print("\n=== Approve Bookings ===")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, facility_name, student_id, booking_date, time_slot
            FROM facility_bookings
            WHERE status = 'pending'
        ''')

        bookings = cursor.fetchall()
        if not bookings:
            print("No pending bookings.")
            return

        for booking_id, facility, student, date, time in bookings:
            print(f"\n{booking_id}. {facility} - {student}")
            print(f"   {date} at {time}")

        booking_id = input("\nEnter booking ID to approve (or 'q' to quit): ").strip()
        if booking_id.lower() == 'q':
            return

        cursor.execute('UPDATE facility_bookings SET status = "approved" WHERE id = ?', (booking_id,))
        conn.commit()
        print("✓ Booking approved!")

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
            student_id = input("Student ID: ").strip()
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
