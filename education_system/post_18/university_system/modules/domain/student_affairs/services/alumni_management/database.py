from datetime import datetime
from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.core import safe_execute


def init_alumni_db():
    """Initialize the enhanced alumni database with all new tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Original tables (keeping existing structure)
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

        # Unified events table
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

        # Unified event registrations with payment info
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS unified_event_registrations (
            registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            user_id TEXT,
            user_type TEXT DEFAULT 'alumni',
            registration_date TEXT,
            attendance_status TEXT,
            checked_in_at TEXT,
            check_out_time TEXT,
            payment_status TEXT DEFAULT 'pending',
            payment_amount REAL DEFAULT 0.0,
            payment_method TEXT,
            is_waitlisted BOOLEAN DEFAULT 0,
            num_guests INTEGER DEFAULT 0,
            feedback_rating REAL,
            feedback_comment TEXT,
            qr_code TEXT,
            cpd_credits REAL DEFAULT 0.0,
            FOREIGN KEY (event_id) REFERENCES unified_events (event_id),
            FOREIGN KEY (user_id) REFERENCES alumni (alumni_id)
        )
        ''')

        # Enhanced donations table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS donations (
            donation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_id TEXT,
            amount REAL,
            donation_date TEXT,
            campaign TEXT,
            campaign_id INTEGER,
            payment_method TEXT,
            is_recurring BOOLEAN,
            recurring_frequency TEXT,
            receipt_sent BOOLEAN,
            notes TEXT,
            donation_type TEXT DEFAULT 'general',
            tribute_type TEXT,
            tribute_name TEXT,
            employer_match_eligible BOOLEAN DEFAULT 0,
            employer_match_amount REAL DEFAULT 0.0,
            recognition_level TEXT,
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id),
            FOREIGN KEY (campaign_id) REFERENCES fundraising_campaigns (campaign_id)
        )
        ''')

        # Enhanced mentorships table
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

        # Alumni Directory Search & Networking
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

        # Communication System
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS newsletters (
            newsletter_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT,
            template_id INTEGER,
            target_audience TEXT,
            send_date TEXT,
            created_date TEXT,
            created_by TEXT,
            status TEXT DEFAULT 'draft',
            open_rate REAL DEFAULT 0.0,
            click_rate REAL DEFAULT 0.0
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name TEXT,
            template_content TEXT,
            template_type TEXT,
            created_date TEXT,
            created_by TEXT
        )
        ''')

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

        # Job Board & Career Services
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS job_postings (
            job_id INTEGER PRIMARY KEY AUTOINCREMENT,
            posted_by TEXT,
            company_name TEXT,
            job_title TEXT,
            job_description TEXT,
            location TEXT,
            job_type TEXT,
            salary_range TEXT,
            requirements TEXT,
            application_method TEXT,
            contact_email TEXT,
            post_date TEXT,
            expiry_date TEXT,
            is_active BOOLEAN DEFAULT 1,
            category TEXT,
            experience_level TEXT,
            FOREIGN KEY (posted_by) REFERENCES alumni (alumni_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS job_applications (
            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            applicant_id TEXT,
            application_date TEXT,
            status TEXT DEFAULT 'submitted',
            cover_letter TEXT,
            resume_path TEXT,
            FOREIGN KEY (job_id) REFERENCES job_postings (job_id),
            FOREIGN KEY (applicant_id) REFERENCES alumni (alumni_id)
        )
        ''')

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

        # Fundraising Campaigns
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS fundraising_campaigns (
            campaign_id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_name TEXT,
            description TEXT,
            goal_amount REAL,
            current_amount REAL DEFAULT 0.0,
            start_date TEXT,
            end_date TEXT,
            created_by TEXT,
            created_date TEXT,
            status TEXT DEFAULT 'active',
            category TEXT,
            is_featured BOOLEAN DEFAULT 0
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS donor_recognition (
            recognition_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_id TEXT,
            recognition_level TEXT,
            total_donated REAL,
            recognition_date TEXT,
            benefits TEXT,
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
        )
        ''')

        # Social Features & Engagement
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alumni_achievements (
            achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_id TEXT,
            achievement_title TEXT,
            achievement_description TEXT,
            achievement_date TEXT,
            category TEXT,
            verification_status TEXT DEFAULT 'pending',
            verified_by TEXT,
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
        )
        ''')

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

        # Gamification System
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS engagement_points (
            point_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_id TEXT,
            activity_type TEXT,
            points_earned INTEGER,
            activity_date TEXT,
            description TEXT,
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS achievement_badges (
            badge_id INTEGER PRIMARY KEY AUTOINCREMENT,
            badge_name TEXT,
            badge_description TEXT,
            points_required INTEGER,
            badge_icon TEXT,
            category TEXT
        )
        ''')

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

        # Content Management
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

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS photo_gallery (
            photo_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            uploaded_by TEXT,
            photo_path TEXT,
            caption TEXT,
            upload_date TEXT,
            is_featured BOOLEAN DEFAULT 0,
            FOREIGN KEY (event_id) REFERENCES unified_events (event_id),
            FOREIGN KEY (uploaded_by) REFERENCES alumni (alumni_id)
        )
        ''')

        # Advanced Networking
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS networking_connections (
            connection_id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_id TEXT,
            recipient_id TEXT,
            connection_date TEXT,
            status TEXT DEFAULT 'pending',
            message TEXT,
            FOREIGN KEY (requester_id) REFERENCES alumni (alumni_id),
            FOREIGN KEY (recipient_id) REFERENCES alumni (alumni_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS business_directory (
            business_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_id TEXT,
            business_name TEXT,
            business_description TEXT,
            industry TEXT,
            website TEXT,
            contact_email TEXT,
            services_offered TEXT,
            location TEXT,
            created_date TEXT,
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
        )
        ''')

        # System Integration & Analytics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_integrations (
            integration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            integration_name TEXT,
            integration_type TEXT,
            api_endpoint TEXT,
            api_key TEXT,
            status TEXT DEFAULT 'active',
            last_sync TEXT,
            sync_frequency TEXT
        )
        ''')

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

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS analytics_data (
            analytics_id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT,
            metric_value REAL,
            metric_date TEXT,
            category TEXT,
            additional_data TEXT
        )
        ''')

        # Ambassador Program
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

        # Event Surveys and Feedback
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_surveys (
            survey_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            survey_title TEXT,
            questions TEXT,
            created_date TEXT,
            FOREIGN KEY (event_id) REFERENCES unified_events (event_id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS survey_responses (
            response_id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER,
            alumni_id TEXT,
            responses TEXT,
            submission_date TEXT,
            FOREIGN KEY (survey_id) REFERENCES event_surveys (survey_id),
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
        )
        ''')

        # Initialize default data
        init_default_enhanced_data(cursor)

        # Add Gift Aid column if not present (v8.2.0 migration)
        try:
            cursor.execute("ALTER TABLE donations ADD COLUMN is_gift_aided INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists

        conn.commit()
        conn.close()
        print("Enhanced alumni database initialized successfully with all new features!")

    except sqlite3.Error as e:
        print(f"An error occurred while initializing the enhanced alumni database: {e}")

def init_default_enhanced_data(cursor):
    """Initialize default data for enhanced features"""
    # Create default email templates
    default_templates = [
        ('Welcome Email', 'Welcome to our Alumni Network! We are excited to have you join our community.', 'welcome'),
        ('Event Invitation', 'You are invited to our upcoming alumni event. Please find details below.', 'event'),
        ('Newsletter Template', 'Alumni Newsletter - Stay connected with your alma mater and fellow alumni.', 'newsletter'),
        ('Job Posting', 'New job opportunity available through our alumni network.', 'job'),
        ('Donation Thank You', 'Thank you for your generous donation to our institution.', 'donation')
    ]

    for name, content, template_type in default_templates:
        cursor.execute('''
            INSERT OR IGNORE INTO email_templates (template_name, template_content, template_type, created_date, created_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, content, template_type, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'system'))

    # Create default achievement badges
    default_badges = [
        ('New Member', 'Welcome to the alumni community!', 0, 'badge_new.png', 'engagement'),
        ('Active Networker', 'Made 10 networking connections', 100, 'badge_network.png', 'networking'),
        ('Generous Donor', 'Made your first donation', 50, 'badge_donor.png', 'giving'),
        ('Event Enthusiast', 'Attended 5 events', 150, 'badge_events.png', 'events'),
        ('Mentor', 'Became a mentor to fellow alumni', 200, 'badge_mentor.png', 'mentoring'),
        ('Ambassador', 'Joined the ambassador program', 300, 'badge_ambassador.png', 'leadership')
    ]

    for name, desc, points, icon, category in default_badges:
        cursor.execute('''
            INSERT OR IGNORE INTO achievement_badges (badge_name, badge_description, points_required, badge_icon, category)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, desc, points, icon, category))

    # Create default fundraising campaign
    cursor.execute('''
        INSERT OR IGNORE INTO fundraising_campaigns
        (campaign_name, description, goal_amount, start_date, end_date, created_by, created_date, category)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'Annual Alumni Fund 2025',
        'Support current students and enhance campus facilities through your alumni contributions.',
        100000.0,
        '2025-01-01',
        '2025-12-31',
        'system',
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'Annual Fund'
    ))
