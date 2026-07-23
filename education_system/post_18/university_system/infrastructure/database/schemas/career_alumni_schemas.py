from __future__ import annotations
from datetime import datetime
from education_system.post_18.university_system.infrastructure.database.db import get_connection, sqlite3
from education_system.post_18.university_system.core.i18n import get_text as _t, init_i18n

# Initialize i18n
init_i18n()

def init_career_services_system_db():
    """Initialize the Career Services Platform database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="Career Services Platform"))

        # Student resumes/CVs
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_resumes (
            resume_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            resume_name TEXT NOT NULL,
            file_url TEXT NOT NULL,
            template_used TEXT,
            is_primary BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Job postings
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS job_postings (
            job_id INTEGER PRIMARY KEY AUTOINCREMENT,
            employer_id INTEGER,
            job_title TEXT NOT NULL,
            company_name TEXT NOT NULL,
            job_type TEXT NOT NULL,
            location TEXT,
            salary_range TEXT,
            description TEXT,
            requirements TEXT,
            responsibilities TEXT,
            application_deadline TEXT,
            posted_date TEXT DEFAULT CURRENT_DATE,
            status TEXT DEFAULT 'active',
            views_count INTEGER DEFAULT 0,
            applications_count INTEGER DEFAULT 0
        )
        ''')

        # Employer profiles
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS employers (
            employer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            industry TEXT,
            company_size TEXT,
            website TEXT,
            contact_person TEXT,
            contact_email TEXT,
            contact_phone TEXT,
            description TEXT,
            logo_url TEXT,
            is_verified BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Job applications
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS job_applications (
            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            resume_id INTEGER,
            cover_letter TEXT,
            status TEXT DEFAULT 'submitted',
            applied_date TEXT DEFAULT CURRENT_TIMESTAMP,
            reviewed_date TEXT,
            notes TEXT,
            FOREIGN KEY (job_id) REFERENCES job_postings (job_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (resume_id) REFERENCES student_resumes (resume_id)
        )
        ''')

        # Interview scheduling
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS interview_schedules (
            interview_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            interview_type TEXT NOT NULL,
            interview_date TEXT NOT NULL,
            interview_time TEXT NOT NULL,
            duration_minutes INTEGER DEFAULT 60,
            location TEXT,
            interviewer_name TEXT,
            meeting_link TEXT,
            status TEXT DEFAULT 'scheduled',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (application_id) REFERENCES job_applications (application_id)
        )
        ''')

        # Career fairs and events (unified_events)
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

        # Event registrations (unified_event_registrations)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS unified_event_registrations (
            registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id TEXT,
            user_type TEXT,
            registration_date TEXT DEFAULT (datetime('now')),
            attendance_status TEXT DEFAULT 'registered',
            checked_in_at TEXT,
            check_out_time TEXT,
            payment_status TEXT,
            payment_amount REAL,
            payment_method TEXT,
            is_waitlisted INTEGER DEFAULT 0,
            num_guests INTEGER DEFAULT 0,
            feedback_rating INTEGER,
            feedback_comment TEXT,
            qr_code TEXT,
            cpd_credits REAL,
            FOREIGN KEY (event_id) REFERENCES unified_events(event_id)
        )
        ''')

        # Alumni mentorship
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alumni_mentors (
            mentor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_student_id TEXT NOT NULL,
            job_title TEXT,
            company TEXT,
            industry TEXT,
            expertise_areas TEXT,
            max_mentees INTEGER DEFAULT 3,
            is_active BOOLEAN DEFAULT 1,
            bio TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Mentorship matches
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS mentorship_matches (
            match_id INTEGER PRIMARY KEY AUTOINCREMENT,
            mentor_id INTEGER NOT NULL,
            mentee_student_id TEXT NOT NULL,
            match_date TEXT DEFAULT CURRENT_DATE,
            status TEXT DEFAULT 'active',
            meeting_frequency TEXT DEFAULT 'monthly',
            last_meeting_date TEXT,
            notes TEXT,
            FOREIGN KEY (mentor_id) REFERENCES alumni_mentors (mentor_id),
            FOREIGN KEY (mentee_student_id) REFERENCES students (student_id)
        )
        ''')

        # Student skills tracking
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_skills (
            skill_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            skill_name TEXT NOT NULL,
            skill_category TEXT,
            proficiency_level TEXT,
            verified BOOLEAN DEFAULT 0,
            acquired_date TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="Career Services Platform"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="Career Services Platform", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# ADMISSIONS & RECRUITMENT CRM SCHEMAS
# ============================================================================


def init_alumni_relations_system_db():
    """Initialize the Alumni Relations & Engagement database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="Alumni Relations & Engagement"))

        # Alumni profiles
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alumni_profiles (
            alumni_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL UNIQUE,
            graduation_year INTEGER NOT NULL,
            degree_earned TEXT NOT NULL,
            major TEXT,
            current_employer TEXT,
            current_position TEXT,
            current_industry TEXT,
            current_location TEXT,
            linkedin_url TEXT,
            personal_website TEXT,
            biography TEXT,
            willing_to_mentor BOOLEAN DEFAULT 0,
            willing_to_recruit BOOLEAN DEFAULT 0,
            privacy_level TEXT DEFAULT 'public',
            profile_updated_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Alumni donations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alumni_donations (
            donation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_id INTEGER NOT NULL,
            donation_amount REAL NOT NULL,
            donation_date TEXT DEFAULT CURRENT_DATE,
            donation_type TEXT NOT NULL,
            fund_designation TEXT,
            campaign_id INTEGER,
            payment_method TEXT,
            is_recurring BOOLEAN DEFAULT 0,
            recurrence_frequency TEXT,
            tax_receipt_sent BOOLEAN DEFAULT 0,
            acknowledgment_sent BOOLEAN DEFAULT 0,
            FOREIGN KEY (alumni_id) REFERENCES alumni_profiles (alumni_id)
        )
        ''')

        # Giving campaigns
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS giving_campaigns (
            campaign_id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_name TEXT NOT NULL,
            campaign_description TEXT,
            goal_amount REAL NOT NULL,
            current_amount REAL DEFAULT 0,
            donor_count INTEGER DEFAULT 0,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            campaign_type TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Alumni events (unified_events - IF NOT EXISTS so safe to call multiple times)
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

        # Alumni event registrations (unified_event_registrations - IF NOT EXISTS)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS unified_event_registrations (
            registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id TEXT,
            user_type TEXT,
            registration_date TEXT DEFAULT (datetime('now')),
            attendance_status TEXT DEFAULT 'registered',
            checked_in_at TEXT,
            check_out_time TEXT,
            payment_status TEXT,
            payment_amount REAL,
            payment_method TEXT,
            is_waitlisted INTEGER DEFAULT 0,
            num_guests INTEGER DEFAULT 0,
            feedback_rating INTEGER,
            feedback_comment TEXT,
            qr_code TEXT,
            cpd_credits REAL,
            FOREIGN KEY (event_id) REFERENCES unified_events(event_id)
        )
        ''')

        # Alumni achievements
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alumni_achievements (
            achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_id INTEGER NOT NULL,
            achievement_type TEXT NOT NULL,
            achievement_title TEXT NOT NULL,
            achievement_description TEXT,
            date_achieved TEXT,
            is_featured BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (alumni_id) REFERENCES alumni_profiles (alumni_id)
        )
        ''')

        # Alumni chapters (regional groups)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alumni_chapters (
            chapter_id INTEGER PRIMARY KEY AUTOINCREMENT,
            chapter_name TEXT NOT NULL,
            region TEXT NOT NULL,
            chapter_leader_id INTEGER,
            contact_email TEXT,
            description TEXT,
            meeting_frequency TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chapter_leader_id) REFERENCES alumni_profiles (alumni_id)
        )
        ''')

        # Alumni chapter memberships
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alumni_chapter_memberships (
            membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
            chapter_id INTEGER NOT NULL,
            alumni_id INTEGER NOT NULL,
            join_date TEXT DEFAULT CURRENT_DATE,
            membership_status TEXT DEFAULT 'active',
            FOREIGN KEY (chapter_id) REFERENCES alumni_chapters (chapter_id),
            FOREIGN KEY (alumni_id) REFERENCES alumni_profiles (alumni_id)
        )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="Alumni Relations & Engagement"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="Alumni Relations", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# RESEARCH & GRANTS MANAGEMENT SCHEMAS
# ============================================================================


def init_career_tables():
    """Initialize career system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="career"))

        # Create career_counseling table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS career_counseling (
                    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    counselor_id TEXT,
                    client_id TEXT,
                    session_date TEXT,
                    session_type TEXT,
                    duration INTEGER,
                    notes TEXT,
                    status TEXT DEFAULT 'scheduled',
                    follow_up_required BOOLEAN DEFAULT 0,
                    FOREIGN KEY (counselor_id) REFERENCES alumni (alumni_id),
                    FOREIGN KEY (client_id) REFERENCES alumni (alumni_id)
                )
        ''')

        # Create internship_applications table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS internship_applications (
                    application_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    internship_id INTEGER,
                    application_date TEXT,
                    status TEXT DEFAULT 'pending',
                    cv_filename TEXT,
                    cover_letter TEXT,
                    feedback TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (internship_id) REFERENCES internships (internship_id)
                )
        ''')

        # Create internship_placements table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS internship_placements (
                    placement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    internship_id INTEGER,
                    start_date TEXT,
                    end_date TEXT,
                    supervisor_name TEXT,
                    supervisor_email TEXT,
                    status TEXT DEFAULT 'active',
                    feedback_student TEXT,
                    feedback_employer TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (internship_id) REFERENCES internships (internship_id)
                )
        ''')

        # Create internships table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS internships (
                    internship_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    location TEXT,
                    description TEXT,
                    requirements TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    is_paid BOOLEAN,
                    salary TEXT,
                    hours_per_week INTEGER,
                    posted_date TEXT,
                    deadline_date TEXT,
                    status TEXT DEFAULT 'active',
                    contact_email TEXT,
                    course_relevance TEXT,
                    created_by TEXT,
                    created_date TEXT
                )
        ''')

        # Create mentorship_relationships table
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

        # Create mentorship_sessions table
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

        # Create mentorships table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS mentorships (
                    mentorship_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mentor_id TEXT,
                    mentee_id TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    status TEXT,
                    focus_area TEXT,
                    notes TEXT,
                    match_score REAL DEFAULT 0.0,
                    meeting_frequency TEXT,
                    communication_preference TEXT,
                    goals TEXT,
                    FOREIGN KEY (mentor_id) REFERENCES alumni (alumni_id)
                )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="career"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="career", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# COMMERCE TABLES (12 tables)
# ============================================================================


def init_alumni_tables():
    """Initialize alumni system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="alumni"))

        # Create alumni table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alumni (
                    alumni_id TEXT PRIMARY KEY,
                    student_id TEXT,
                    email_address TEXT,
                    title TEXT,
                    first_name TEXT,
                    middle_name TEXT,
                    last_name TEXT,
                    gender TEXT,
                    dob TEXT,
                    graduation_year INTEGER,
                    degree_earned TEXT,
                    current_employer TEXT,
                    job_title TEXT,
                    industry TEXT,
                    address TEXT,
                    city TEXT,
                    country TEXT,
                    phone TEXT,
                    linkedin_url TEXT,
                    date_registered TEXT,
                    is_donor BOOLEAN,
                    is_mentor BOOLEAN,
                    is_board_member BOOLEAN,
                    profile_photo TEXT,
                    bio TEXT,
                    skills TEXT,
                    achievements TEXT,
                    privacy_level INTEGER DEFAULT 1,
                    engagement_score INTEGER DEFAULT 0,
                    last_activity TEXT,
                    social_media_links TEXT,
                    is_ambassador BOOLEAN DEFAULT 0,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
        ''')

        # Create alumni_badges table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alumni_badges (
                    alumni_badge_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alumni_id TEXT,
                    badge_id INTEGER,
                    earned_date TEXT,
                    FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id),
                    FOREIGN KEY (badge_id) REFERENCES achievement_badges (badge_id)
                )
        ''')

        # Create alumni_directory_settings table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alumni_directory_settings (
                    alumni_id TEXT PRIMARY KEY,
                    show_contact_info BOOLEAN DEFAULT 1,
                    show_employment BOOLEAN DEFAULT 1,
                    show_education BOOLEAN DEFAULT 1,
                    searchable BOOLEAN DEFAULT 1,
                    networking_available BOOLEAN DEFAULT 1,
                    mentor_available BOOLEAN DEFAULT 0,
                    FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
                )
        ''')

        # Create alumni_forum table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alumni_forum (
                    post_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    author_id TEXT,
                    title TEXT,
                    content TEXT,
                    category TEXT,
                    post_date TEXT,
                    last_updated TEXT,
                    reply_count INTEGER DEFAULT 0,
                    view_count INTEGER DEFAULT 0,
                    is_pinned BOOLEAN DEFAULT 0,
                    FOREIGN KEY (author_id) REFERENCES alumni (alumni_id)
                )
        ''')

        # Create alumni_stories table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alumni_stories (
                    story_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alumni_id TEXT,
                    title TEXT,
                    content TEXT,
                    story_type TEXT,
                    publish_date TEXT,
                    is_featured BOOLEAN DEFAULT 0,
                    view_count INTEGER DEFAULT 0,
                    category TEXT,
                    FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
                )
        ''')

        # Create ambassador_program table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ambassador_program (
                    ambassador_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alumni_id TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    status TEXT DEFAULT 'active',
                    region TEXT,
                    activities TEXT,
                    performance_score REAL DEFAULT 0.0,
                    FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
                )
        ''')

        # Create chapter_memberships table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS chapter_memberships (
                    membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chapter_id INTEGER,
                    alumni_id TEXT,
                    join_date TEXT,
                    role TEXT DEFAULT 'member',
                    FOREIGN KEY (chapter_id) REFERENCES regional_chapters (chapter_id),
                    FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
                )
        ''')

        # Create regional_chapters table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS regional_chapters (
                    chapter_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chapter_name TEXT,
                    location TEXT,
                    coordinator_id TEXT,
                    description TEXT,
                    created_date TEXT,
                    member_count INTEGER DEFAULT 0,
                    FOREIGN KEY (coordinator_id) REFERENCES alumni (alumni_id)
                )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="alumni"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="alumni", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# ANALYTICS TABLES (7 tables)
# ============================================================================


