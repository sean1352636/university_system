from __future__ import annotations
from datetime import datetime
from education_system.post_18.university_system.infrastructure.database.db import get_connection, sqlite3
from education_system.post_18.university_system.core.i18n import get_text as _t, init_i18n

# Initialize i18n
init_i18n()

def init_student_union_db():
    """Initialize the Student Union database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="student union"))

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

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="Student union"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="student union", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# EMAIL SYSTEM SCHEMAS
# ============================================================================


def init_student_affairs_tables():
    """Initialize student_affairs system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="student_affairs"))

        # Create activity_log table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT,
                    timestamp TEXT NOT NULL,
                    ip_address TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
        ''')

        # Create book_clubs table
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

        # Create class_reunions table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS class_reunions (
                    reunion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    graduation_year INTEGER,
                    reunion_date TEXT,
                    location TEXT,
                    organizer_id TEXT,
                    description TEXT,
                    registration_fee REAL DEFAULT 0.0,
                    max_attendees INTEGER,
                    created_date TEXT,
                    FOREIGN KEY (organizer_id) REFERENCES alumni (alumni_id)
                )
        ''')

        # Create club_competitions table
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

        # Create club_discussions table
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

        # Create club_expenses table
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

        # Create club_media table
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

        # Create course_events table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS course_events (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            event_id TEXT NOT NULL,
                            course_id TEXT NOT NULL,
                            event_sub_type TEXT,
                            date_added TEXT NOT NULL,
                            FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE,
                            FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE,
                            UNIQUE(event_id, course_id)
                        )
        ''')

        # Create election_candidates table
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

        # Create election_votes table
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

        # Create event_categories table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_categories (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT UNIQUE NOT NULL,
                            color_code TEXT,
                            description TEXT,
                            date_added TEXT NOT NULL
                        )
        ''')

        # Create event_dependencies table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_dependencies (
                            id TEXT PRIMARY KEY,
                            prerequisite_event_id TEXT NOT NULL,
                            dependent_event_id TEXT NOT NULL,
                            dependency_type TEXT NOT NULL,
                            delay_days INTEGER DEFAULT 0,
                            delay_hours INTEGER DEFAULT 0,
                            is_mandatory BOOLEAN DEFAULT TRUE,
                            created_at TEXT NOT NULL,
                            FOREIGN KEY (prerequisite_event_id) REFERENCES events (id) ON DELETE CASCADE,
                            FOREIGN KEY (dependent_event_id) REFERENCES events (id) ON DELETE CASCADE,
                            UNIQUE(prerequisite_event_id, dependent_event_id)
                        )
        ''')

        # Create event_finances table
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

        # Create event_sequences table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_sequences (
                            id TEXT PRIMARY KEY,
                            workflow_id TEXT NOT NULL,
                            event_id TEXT NOT NULL,
                            sequence_order INTEGER NOT NULL,
                            completion_status TEXT DEFAULT 'pending',
                            completion_date TEXT,
                            FOREIGN KEY (workflow_id) REFERENCES event_workflows (id) ON DELETE CASCADE,
                            FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
                        )
        ''')

        # Create event_surveys table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_surveys (
                    survey_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER,
                    survey_title TEXT,
                    questions TEXT,
                    created_date TEXT,
                    FOREIGN KEY (event_id) REFERENCES alumni_events (event_id)
                )
        ''')

        # Create event_tags table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_tags (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT UNIQUE NOT NULL,
                            color_code TEXT,
                            date_added TEXT NOT NULL
                        )
        ''')

        # Create event_tickets table
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

        # Create event_timezones table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_timezones (
                            event_id TEXT PRIMARY KEY,
                            timezone_name TEXT NOT NULL,
                            utc_offset_hours INTEGER NOT NULL,
                            is_dst_active BOOLEAN DEFAULT FALSE,
                            created_at TEXT NOT NULL,
                            FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
                        )
        ''')

        # Create event_workflows table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_workflows (
                            id TEXT PRIMARY KEY,
                            workflow_name TEXT NOT NULL,
                            description TEXT,
                            template_data TEXT,
                            is_active BOOLEAN DEFAULT TRUE,
                            created_by TEXT,
                            created_at TEXT NOT NULL
                        )
        ''')

        # Create unified_events table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS unified_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            source_event_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            event_type TEXT,
            event_category TEXT,
            start_datetime TEXT,
            end_datetime TEXT,
            location TEXT,
            building TEXT,
            room TEXT,
            room_id INTEGER,
            organizer_id TEXT,
            organizer_name TEXT,
            organizer_type TEXT,
            max_capacity INTEGER,
            registration_required INTEGER DEFAULT 0,
            registration_deadline TEXT,
            is_public INTEGER DEFAULT 1,
            is_featured INTEGER DEFAULT 0,
            status TEXT DEFAULT 'scheduled',
            tags TEXT,
            image_url TEXT,
            virtual_link TEXT,
            event_fee REAL DEFAULT 0,
            payment_required INTEGER DEFAULT 0,
            waitlist_enabled INTEGER DEFAULT 0,
            qr_code_path TEXT,
            club_id INTEGER,
            created_by TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT,
            notes TEXT
        )
        ''')

        # Create organizations table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS organizations (
                    org_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    domain TEXT,
                    contact_email TEXT,
                    phone TEXT,
                    address TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                )
        ''')

        # Create parent_activity_log table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_activity_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        parent_id TEXT,
                        action TEXT,
                        details TEXT,
                        ip_address TEXT,
                        user_agent TEXT,
                        timestamp TEXT,
                        FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
                    )
        ''')

        # Create recurring_events table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS recurring_events (
                            id TEXT PRIMARY KEY,
                            base_event_id TEXT NOT NULL,
                            frequency TEXT NOT NULL,
                            interval_count INTEGER DEFAULT 1,
                            days_of_week TEXT,
                            day_of_month INTEGER,
                            month_of_year INTEGER,
                            end_date TEXT,
                            occurrence_count INTEGER,
                            timezone TEXT DEFAULT 'UTC',
                            exceptions TEXT,
                            date_added TEXT NOT NULL,
                            FOREIGN KEY (base_event_id) REFERENCES events (id) ON DELETE CASCADE
                        )
        ''')

        # Create union_elections table
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

        # Create union_equipment table
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

        # Create union_facilities table
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

        # Create union_representatives table
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

        # Create user_activity_log table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_activity_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    activity_type TEXT,
                    activity_description TEXT,
                    timestamp TEXT,
                    ip_address TEXT,
                    user_agent TEXT
                )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="student_affairs"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="student_affairs", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# SUPPORT TABLES (15 tables)
# ============================================================================


def init_social_tables():
    """Initialize social system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="social"))

        # Create forum_replies table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS forum_replies (
                    reply_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id INTEGER,
                    author_id TEXT,
                    content TEXT,
                    reply_date TEXT,
                    parent_reply_id INTEGER,
                    FOREIGN KEY (post_id) REFERENCES alumni_forum (post_id),
                    FOREIGN KEY (author_id) REFERENCES alumni (alumni_id)
                )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="social"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="social", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# STUDENT_AFFAIRS TABLES (28 tables)
# ============================================================================


