"""
Centralized database schema initialization for all system modules.

This module consolidates schema initialization functions from across the system
to provide a single source of truth for database setup.
"""

from __future__ import annotations

from datetime import datetime
from university_system.infrastructure.database.db import get_connection, sqlite3

# ============================================================================
# GRADE SYSTEM SCHEMAS
# ============================================================================

def init_grade_system_db():
    """Initialize the grade system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing grade system tables...")

        # Create students table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            middle_name TEXT,
            last_name TEXT NOT NULL,
            course TEXT NOT NULL,
            email_address TEXT,
            gender TEXT,
            dob TEXT,
            enrollment_date TEXT DEFAULT (date('now')),
            status TEXT DEFAULT 'Active',
            grade_level TEXT
        )
        ''')

        # Create modules table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS modules (
            module_code TEXT PRIMARY KEY,
            module_name TEXT NOT NULL,
            module_type TEXT,
            credits INTEGER DEFAULT 1,
            description TEXT,
            course TEXT,
            semester TEXT,
            year INTEGER
        )
        ''')

        # Create student_modules table (enrollment)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_code TEXT,
            module_name TEXT,
            module_type TEXT DEFAULT 'Standard',
            enrollment_date TEXT DEFAULT CURRENT_TIMESTAMP,
            grade TEXT,
            completion_date TEXT,
            status TEXT DEFAULT 'Enrolled',
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        conn.commit()
        conn.close()
        print("Grade system database initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing grade system database: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# FINANCE SYSTEM SCHEMAS
# ============================================================================

def init_finance_system_db():
    """Initialize the enhanced finance database with all tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing finance system tables...")

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Fee types table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS fee_types (
            fee_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
            fee_name TEXT NOT NULL,
            description TEXT,
            is_recurring BOOLEAN DEFAULT 0,
            academic_year TEXT,
            is_late_fee BOOLEAN DEFAULT 0,
            late_fee_calculation TEXT,
            late_fee_amount DECIMAL(10,2),
            grace_period_days INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
        ''')

        # Program fees table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS program_fees (
            program_fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            fee_type_id INTEGER,
            course TEXT NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            currency TEXT DEFAULT 'GBP',
            academic_year TEXT,
            due_date TEXT,
            early_payment_discount DECIMAL(5,2) DEFAULT 0,
            early_payment_days INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (fee_type_id) REFERENCES fee_types (fee_type_id)
        )
        ''')

        # Scholarships table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS scholarships (
            scholarship_id INTEGER PRIMARY KEY AUTOINCREMENT,
            scholarship_name TEXT NOT NULL,
            description TEXT,
            amount DECIMAL(10,2),
            academic_year TEXT,
            criteria TEXT,
            deadline TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
        ''')

        # Student scholarships table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_scholarships (
            student_scholarship_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            scholarship_id INTEGER NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            status TEXT DEFAULT 'active',
            awarded_date TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (scholarship_id) REFERENCES scholarships (scholarship_id)
        )
        ''')

        # Payment plans table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_plan_templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name TEXT NOT NULL,
            description TEXT,
            number_of_installments INTEGER NOT NULL,
            installment_frequency TEXT NOT NULL,
            setup_fee DECIMAL(10,2) DEFAULT 0,
            interest_rate DECIMAL(5,2) DEFAULT 0,
            early_payment_discount DECIMAL(5,2) DEFAULT 0,
            late_payment_penalty DECIMAL(5,2) DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
        ''')

        conn.commit()
        conn.close()
        print("Finance system database initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing finance database: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# STUDENT UNION SCHEMAS
# ============================================================================

def init_student_union_db():
    """Initialize the Student Union database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing student union tables...")

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
        print("Student union database initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing student union database: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# EMAIL SYSTEM SCHEMAS
# ============================================================================

def init_email_system_db():
    """Initialize email system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing email system tables...")

        # Email log table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            status TEXT DEFAULT 'sent',
            error_message TEXT
        )
        ''')

        # Email templates table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            created_by TEXT,
            is_shared INTEGER DEFAULT 0,
            version INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT
        )
        ''')

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_templates_category ON email_templates(category)")

        conn.commit()
        conn.close()
        print("Email system database initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing email database: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# HEALTH SYSTEM SCHEMAS
# ============================================================================

def init_health_system_db():
    """Initialize the health system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing health system tables...")

        # Create health_records table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            email TEXT,
            last_checkup TEXT,
            screening_type TEXT,
            next_screening_due TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Create screening_results table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS screening_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            screening_type TEXT NOT NULL,
            results TEXT,
            date_performed TEXT NOT NULL,
            next_due_date TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Create lab_results table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lab_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            test_type TEXT NOT NULL,
            result_value TEXT,
            normal_range TEXT,
            date_performed TEXT NOT NULL,
            abnormal_flag INTEGER DEFAULT 0,
            reviewed INTEGER DEFAULT 0,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Create vaccination_records table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS vaccination_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            vaccine_type TEXT NOT NULL,
            last_vaccination_date TEXT NOT NULL,
            next_due_date TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        conn.commit()
        conn.close()
        print("Health system database initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing health system database: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# LMS (LEARNING MANAGEMENT SYSTEM) SCHEMAS
# ============================================================================

def init_lms_system_db():
    """Initialize the Learning Management System database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing LMS system tables...")

        # Courses table (extends existing courses)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lms_courses (
            lms_course_id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT NOT NULL,
            instructor_id TEXT NOT NULL,
            course_description TEXT,
            syllabus_url TEXT,
            start_date TEXT,
            end_date TEXT,
            is_published BOOLEAN DEFAULT 0,
            enrollment_limit INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        # Course content/materials
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lms_course_content (
            content_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lms_course_id INTEGER NOT NULL,
            content_type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            content_url TEXT,
            content_order INTEGER DEFAULT 0,
            is_published BOOLEAN DEFAULT 1,
            release_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lms_course_id) REFERENCES lms_courses (lms_course_id)
        )
        ''')

        # Video lectures
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lms_video_lectures (
            video_id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER NOT NULL,
            video_url TEXT NOT NULL,
            duration_minutes INTEGER,
            thumbnail_url TEXT,
            transcript_url TEXT,
            video_quality TEXT DEFAULT '720p',
            view_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (content_id) REFERENCES lms_course_content (content_id)
        )
        ''')

        # Discussion forums
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lms_discussion_forums (
            forum_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lms_course_id INTEGER NOT NULL,
            topic TEXT NOT NULL,
            description TEXT,
            created_by TEXT NOT NULL,
            is_pinned BOOLEAN DEFAULT 0,
            is_locked BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lms_course_id) REFERENCES lms_courses (lms_course_id)
        )
        ''')

        # Discussion posts
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lms_discussion_posts (
            post_id INTEGER PRIMARY KEY AUTOINCREMENT,
            forum_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            parent_post_id INTEGER,
            content TEXT NOT NULL,
            attachments TEXT,
            likes_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (forum_id) REFERENCES lms_discussion_forums (forum_id),
            FOREIGN KEY (parent_post_id) REFERENCES lms_discussion_posts (post_id)
        )
        ''')

        # Quizzes
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lms_quizzes (
            quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lms_course_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            duration_minutes INTEGER,
            passing_score DECIMAL(5,2),
            max_attempts INTEGER DEFAULT 1,
            randomize_questions BOOLEAN DEFAULT 0,
            show_correct_answers BOOLEAN DEFAULT 1,
            available_from TEXT,
            available_until TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lms_course_id) REFERENCES lms_courses (lms_course_id)
        )
        ''')

        # Quiz questions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lms_quiz_questions (
            question_id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            question_type TEXT NOT NULL,
            points INTEGER DEFAULT 1,
            correct_answer TEXT NOT NULL,
            options TEXT,
            explanation TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (quiz_id) REFERENCES lms_quizzes (quiz_id)
        )
        ''')

        # Quiz submissions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lms_quiz_submissions (
            submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            attempt_number INTEGER NOT NULL,
            score DECIMAL(5,2),
            total_points INTEGER,
            time_taken_minutes INTEGER,
            submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            graded_at TEXT,
            graded_by TEXT,
            FOREIGN KEY (quiz_id) REFERENCES lms_quizzes (quiz_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Gradebook entries
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lms_gradebook (
            grade_entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lms_course_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            assignment_type TEXT NOT NULL,
            assignment_id INTEGER,
            score DECIMAL(5,2),
            max_score DECIMAL(5,2),
            weight DECIMAL(5,2) DEFAULT 1.0,
            feedback TEXT,
            graded_by TEXT,
            graded_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lms_course_id) REFERENCES lms_courses (lms_course_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        conn.commit()
        conn.close()
        print("LMS system database initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing LMS system database: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# ADVANCED ATTENDANCE SYSTEM SCHEMAS
# ============================================================================

def init_attendance_system_db():
    """Initialize the Advanced Attendance System database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing Advanced Attendance System tables...")

        # Attendance sessions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT NOT NULL,
            session_type TEXT NOT NULL,
            session_date TEXT NOT NULL,
            session_time TEXT NOT NULL,
            location TEXT,
            qr_code TEXT UNIQUE,
            qr_code_expires_at TEXT,
            geofence_latitude REAL,
            geofence_longitude REAL,
            geofence_radius_meters INTEGER DEFAULT 50,
            beacon_id TEXT,
            require_facial_recognition BOOLEAN DEFAULT 0,
            created_by TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        # Attendance records
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            check_in_method TEXT NOT NULL,
            check_in_time TEXT DEFAULT CURRENT_TIMESTAMP,
            latitude REAL,
            longitude REAL,
            device_id TEXT,
            facial_recognition_confidence REAL,
            status TEXT DEFAULT 'present',
            notes TEXT,
            FOREIGN KEY (session_id) REFERENCES attendance_sessions (session_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Attendance patterns/analytics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_analytics (
            analytics_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            module_code TEXT NOT NULL,
            total_sessions INTEGER DEFAULT 0,
            attended_sessions INTEGER DEFAULT 0,
            attendance_percentage REAL DEFAULT 0.0,
            consecutive_absences INTEGER DEFAULT 0,
            late_arrivals INTEGER DEFAULT 0,
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        # Absence notifications
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_notifications (
            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            session_id INTEGER NOT NULL,
            recipient_type TEXT NOT NULL,
            recipient_email TEXT NOT NULL,
            notification_type TEXT NOT NULL,
            sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_read BOOLEAN DEFAULT 0,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (session_id) REFERENCES attendance_sessions (session_id)
        )
        ''')

        # Facial recognition data
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS facial_recognition_profiles (
            profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL UNIQUE,
            face_encoding TEXT NOT NULL,
            photo_url TEXT,
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        conn.commit()
        conn.close()
        print("Advanced Attendance System database initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing Advanced Attendance System database: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# MENTAL HEALTH & WELLNESS PORTAL SCHEMAS
# ============================================================================

def init_mental_health_system_db():
    """Initialize the Mental Health & Wellness Portal database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing Mental Health & Wellness Portal tables...")

        # Counselors/therapists
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS mental_health_counselors (
            counselor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            specialization TEXT,
            qualifications TEXT,
            availability_schedule TEXT,
            max_daily_appointments INTEGER DEFAULT 8,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Anonymous counseling appointments
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS mental_health_appointments (
            appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            counselor_id INTEGER,
            appointment_type TEXT NOT NULL,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            duration_minutes INTEGER DEFAULT 50,
            status TEXT DEFAULT 'scheduled',
            is_anonymous BOOLEAN DEFAULT 0,
            anonymous_code TEXT UNIQUE,
            mode TEXT DEFAULT 'in-person',
            location TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (counselor_id) REFERENCES mental_health_counselors (counselor_id)
        )
        ''')

        # Wellness resources library
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS mental_health_resources (
            resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            content_type TEXT NOT NULL,
            content_url TEXT,
            tags TEXT,
            view_count INTEGER DEFAULT 0,
            is_published BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Crisis hotlines
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS mental_health_crisis_contacts (
            contact_id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_name TEXT NOT NULL,
            hotline_number TEXT NOT NULL,
            availability TEXT NOT NULL,
            description TEXT,
            is_emergency BOOLEAN DEFAULT 0,
            display_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1
        )
        ''')

        # Wellness check-ins
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS mental_health_checkins (
            checkin_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            mood_rating INTEGER NOT NULL,
            stress_level INTEGER NOT NULL,
            sleep_quality INTEGER,
            notes TEXT,
            checkin_date TEXT DEFAULT CURRENT_DATE,
            checkin_time TEXT DEFAULT CURRENT_TIME,
            follow_up_required BOOLEAN DEFAULT 0,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Peer support matching
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS mental_health_peer_support (
            support_id INTEGER PRIMARY KEY AUTOINCREMENT,
            supporter_student_id TEXT NOT NULL,
            supported_student_id TEXT NOT NULL,
            support_type TEXT NOT NULL,
            match_date TEXT DEFAULT CURRENT_DATE,
            status TEXT DEFAULT 'active',
            session_count INTEGER DEFAULT 0,
            last_session_date TEXT,
            notes TEXT,
            FOREIGN KEY (supporter_student_id) REFERENCES students (student_id),
            FOREIGN KEY (supported_student_id) REFERENCES students (student_id)
        )
        ''')

        # Mindfulness/meditation sessions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS mental_health_meditation_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            audio_url TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            category TEXT NOT NULL,
            difficulty_level TEXT DEFAULT 'beginner',
            play_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # User meditation tracking
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS mental_health_meditation_tracking (
            tracking_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            session_id INTEGER NOT NULL,
            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT,
            completion_percentage INTEGER DEFAULT 0,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (session_id) REFERENCES mental_health_meditation_sessions (session_id)
        )
        ''')

        conn.commit()
        conn.close()
        print("Mental Health & Wellness Portal database initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing Mental Health & Wellness Portal database: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# STUDENT SUCCESS EARLY WARNING SYSTEM SCHEMAS
# ============================================================================

def init_early_warning_system_db():
    """Initialize the Student Success Early Warning System database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing Student Success Early Warning System tables...")

        # Risk assessment profiles
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS early_warning_profiles (
            profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL UNIQUE,
            overall_risk_score INTEGER DEFAULT 0,
            risk_level TEXT DEFAULT 'low',
            academic_risk_score INTEGER DEFAULT 0,
            attendance_risk_score INTEGER DEFAULT 0,
            engagement_risk_score INTEGER DEFAULT 0,
            financial_risk_score INTEGER DEFAULT 0,
            last_assessed TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Risk indicators/flags
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS early_warning_indicators (
            indicator_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            indicator_type TEXT NOT NULL,
            indicator_value TEXT NOT NULL,
            severity TEXT NOT NULL,
            detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_resolved BOOLEAN DEFAULT 0,
            resolved_at TEXT,
            notes TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Intervention triggers and actions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS early_warning_interventions (
            intervention_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            trigger_type TEXT NOT NULL,
            intervention_type TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            assigned_to TEXT,
            description TEXT,
            scheduled_date TEXT,
            completed_date TEXT,
            outcome TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Success coaches
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS early_warning_coaches (
            coach_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            specialization TEXT,
            max_students INTEGER DEFAULT 30,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Student-coach assignments
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS early_warning_coaching_assignments (
            assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            coach_id INTEGER NOT NULL,
            assigned_date TEXT DEFAULT CURRENT_DATE,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            meeting_frequency TEXT DEFAULT 'weekly',
            last_meeting_date TEXT,
            next_meeting_date TEXT,
            progress_notes TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (coach_id) REFERENCES early_warning_coaches (coach_id)
        )
        ''')

        # Progress monitoring
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS early_warning_progress_monitoring (
            monitoring_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            coach_id INTEGER NOT NULL,
            monitoring_date TEXT DEFAULT CURRENT_DATE,
            academic_progress TEXT,
            attendance_progress TEXT,
            engagement_progress TEXT,
            goals_achieved TEXT,
            concerns TEXT,
            next_steps TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (coach_id) REFERENCES early_warning_coaches (coach_id)
        )
        ''')

        # Tutoring recommendations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS early_warning_tutoring_recommendations (
            recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            module_code TEXT NOT NULL,
            recommended_by TEXT NOT NULL,
            recommendation_type TEXT NOT NULL,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'pending',
            tutor_assigned TEXT,
            sessions_scheduled INTEGER DEFAULT 0,
            sessions_completed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        # Parent/guardian notifications for at-risk students
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS early_warning_notifications (
            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            recipient_type TEXT NOT NULL,
            recipient_email TEXT NOT NULL,
            notification_type TEXT NOT NULL,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_read BOOLEAN DEFAULT 0,
            read_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        conn.commit()
        conn.close()
        print("Student Success Early Warning System database initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing Student Success Early Warning System database: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# DEGREE AUDIT & ACADEMIC ADVISING SCHEMAS
# ============================================================================

def init_degree_audit_system_db():
    """Initialize the Degree Audit & Academic Advising System database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing Degree Audit & Academic Advising System tables...")

        # Degree programs/majors
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS degree_programs (
            program_id INTEGER PRIMARY KEY AUTOINCREMENT,
            program_code TEXT NOT NULL UNIQUE,
            program_name TEXT NOT NULL,
            degree_type TEXT NOT NULL,
            department TEXT,
            total_credits_required INTEGER NOT NULL,
            min_gpa_required REAL DEFAULT 2.0,
            max_years_allowed INTEGER DEFAULT 4,
            description TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Program requirements (core courses, electives, etc.)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS degree_requirements (
            requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            program_id INTEGER NOT NULL,
            requirement_type TEXT NOT NULL,
            requirement_name TEXT NOT NULL,
            description TEXT,
            credits_required INTEGER NOT NULL,
            min_grade TEXT,
            is_mandatory BOOLEAN DEFAULT 1,
            display_order INTEGER DEFAULT 0,
            FOREIGN KEY (program_id) REFERENCES degree_programs (program_id)
        )
        ''')

        # Required courses for each requirement category
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS requirement_courses (
            req_course_id INTEGER PRIMARY KEY AUTOINCREMENT,
            requirement_id INTEGER NOT NULL,
            module_code TEXT NOT NULL,
            is_alternative BOOLEAN DEFAULT 0,
            alternative_group INTEGER,
            FOREIGN KEY (requirement_id) REFERENCES degree_requirements (requirement_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        # Course prerequisites
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS course_prerequisites (
            prerequisite_id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT NOT NULL,
            prerequisite_module_code TEXT NOT NULL,
            min_grade TEXT,
            is_corequisite BOOLEAN DEFAULT 0,
            FOREIGN KEY (module_code) REFERENCES modules (module_code),
            FOREIGN KEY (prerequisite_module_code) REFERENCES modules (module_code)
        )
        ''')

        # Student degree progress tracking
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_degree_progress (
            progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            program_id INTEGER NOT NULL,
            enrollment_year INTEGER NOT NULL,
            total_credits_earned REAL DEFAULT 0,
            current_gpa REAL DEFAULT 0,
            completion_percentage REAL DEFAULT 0,
            expected_graduation_date TEXT,
            status TEXT DEFAULT 'in_progress',
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (program_id) REFERENCES degree_programs (program_id)
        )
        ''')

        # Requirement completion tracking
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS requirement_completion (
            completion_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            requirement_id INTEGER NOT NULL,
            credits_completed REAL DEFAULT 0,
            is_completed BOOLEAN DEFAULT 0,
            completed_date TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (requirement_id) REFERENCES degree_requirements (requirement_id)
        )
        ''')

        # What-if scenarios for degree planning
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS degree_what_if_scenarios (
            scenario_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            scenario_name TEXT NOT NULL,
            target_program_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (target_program_id) REFERENCES degree_programs (program_id)
        )
        ''')

        # Academic advising appointments
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS advising_appointments (
            appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            advisor_id TEXT NOT NULL,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            duration_minutes INTEGER DEFAULT 30,
            appointment_type TEXT NOT NULL,
            status TEXT DEFAULT 'scheduled',
            topic TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Graduation audit checklist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS graduation_checklist (
            checklist_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            program_id INTEGER NOT NULL,
            all_requirements_met BOOLEAN DEFAULT 0,
            gpa_requirement_met BOOLEAN DEFAULT 0,
            credit_requirement_met BOOLEAN DEFAULT 0,
            residency_requirement_met BOOLEAN DEFAULT 0,
            financial_clearance BOOLEAN DEFAULT 0,
            audit_date TEXT DEFAULT CURRENT_DATE,
            graduation_date TEXT,
            conferral_status TEXT DEFAULT 'pending',
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (program_id) REFERENCES degree_programs (program_id)
        )
        ''')

        conn.commit()
        conn.close()
        print("Degree Audit & Academic Advising System database initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing Degree Audit System database: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# CAREER SERVICES PLATFORM SCHEMAS
# ============================================================================

def init_career_services_system_db():
    """Initialize the Career Services Platform database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing Career Services Platform tables...")

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

        # Career fairs and events
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS career_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_date TEXT NOT NULL,
            event_time TEXT NOT NULL,
            location TEXT,
            description TEXT,
            max_attendees INTEGER,
            registration_deadline TEXT,
            is_published BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Event registrations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS career_event_registrations (
            registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
            attended BOOLEAN DEFAULT 0,
            feedback TEXT,
            FOREIGN KEY (event_id) REFERENCES career_events (event_id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
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
        print("Career Services Platform database initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing Career Services Platform database: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# ADMISSIONS & RECRUITMENT CRM SCHEMAS
# ============================================================================

def init_admissions_crm_system_db():
    """Initialize the Admissions & Recruitment CRM database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing Admissions & Recruitment CRM tables...")

        # Prospects (leads)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admission_prospects (
            prospect_id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            date_of_birth TEXT,
            country TEXT,
            state TEXT,
            city TEXT,
            high_school TEXT,
            intended_major TEXT,
            source TEXT,
            status TEXT DEFAULT 'prospect',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_contact_date TEXT
        )
        ''')

        # Applications
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admission_applications (
            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
            prospect_id INTEGER NOT NULL,
            application_type TEXT NOT NULL,
            program_applied TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            semester TEXT NOT NULL,
            submission_date TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'submitted',
            decision TEXT,
            decision_date TEXT,
            enrollment_confirmed BOOLEAN DEFAULT 0,
            application_fee_paid BOOLEAN DEFAULT 0,
            FOREIGN KEY (prospect_id) REFERENCES admission_prospects (prospect_id)
        )
        ''')

        # Application documents
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS application_documents (
            document_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            document_type TEXT NOT NULL,
            document_name TEXT NOT NULL,
            file_url TEXT NOT NULL,
            upload_date TEXT DEFAULT CURRENT_TIMESTAMP,
            verified BOOLEAN DEFAULT 0,
            verified_by TEXT,
            verified_date TEXT,
            FOREIGN KEY (application_id) REFERENCES admission_applications (application_id)
        )
        ''')

        # Application review workflow
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS application_reviews (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            reviewer_id TEXT NOT NULL,
            review_stage TEXT NOT NULL,
            score INTEGER,
            recommendation TEXT,
            comments TEXT,
            review_date TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (application_id) REFERENCES admission_applications (application_id)
        )
        ''')

        # Communication campaigns
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS recruitment_campaigns (
            campaign_id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_name TEXT NOT NULL,
            campaign_type TEXT NOT NULL,
            target_audience TEXT,
            start_date TEXT,
            end_date TEXT,
            status TEXT DEFAULT 'draft',
            message_template TEXT,
            sent_count INTEGER DEFAULT 0,
            opened_count INTEGER DEFAULT 0,
            clicked_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Campaign messages
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS campaign_messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            prospect_id INTEGER NOT NULL,
            sent_date TEXT DEFAULT CURRENT_TIMESTAMP,
            opened_date TEXT,
            clicked_date TEXT,
            status TEXT DEFAULT 'sent',
            FOREIGN KEY (campaign_id) REFERENCES recruitment_campaigns (campaign_id),
            FOREIGN KEY (prospect_id) REFERENCES admission_prospects (prospect_id)
        )
        ''')

        # Campus tours
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS campus_tours (
            tour_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tour_date TEXT NOT NULL,
            tour_time TEXT NOT NULL,
            tour_guide TEXT,
            max_attendees INTEGER DEFAULT 20,
            current_attendees INTEGER DEFAULT 0,
            meeting_point TEXT,
            duration_minutes INTEGER DEFAULT 90,
            status TEXT DEFAULT 'scheduled',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Tour registrations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tour_registrations (
            registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tour_id INTEGER NOT NULL,
            prospect_id INTEGER NOT NULL,
            num_guests INTEGER DEFAULT 0,
            registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
            attended BOOLEAN DEFAULT 0,
            feedback TEXT,
            FOREIGN KEY (tour_id) REFERENCES campus_tours (tour_id),
            FOREIGN KEY (prospect_id) REFERENCES admission_prospects (prospect_id)
        )
        ''')

        # Yield prediction (ML model results)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS yield_predictions (
            prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            predicted_enrollment_probability REAL,
            prediction_date TEXT DEFAULT CURRENT_TIMESTAMP,
            model_version TEXT,
            factors TEXT,
            FOREIGN KEY (application_id) REFERENCES admission_applications (application_id)
        )
        ''')

        # Prospect interactions/touchpoints
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS prospect_interactions (
            interaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            prospect_id INTEGER NOT NULL,
            interaction_type TEXT NOT NULL,
            interaction_date TEXT DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            next_followup_date TEXT,
            staff_member TEXT,
            FOREIGN KEY (prospect_id) REFERENCES admission_prospects (prospect_id)
        )
        ''')

        conn.commit()
        conn.close()
        print("Admissions & Recruitment CRM database initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing Admissions CRM database: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# PREDICTIVE ANALYTICS DASHBOARD SCHEMAS
# ============================================================================

def init_analytics_dashboard_system_db():
    """Initialize the Predictive Analytics Dashboard database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing Predictive Analytics Dashboard tables...")

        # Analytics models registry
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS analytics_models (
            model_id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name TEXT NOT NULL,
            model_type TEXT NOT NULL,
            description TEXT,
            model_version TEXT,
            accuracy_score REAL,
            created_date TEXT DEFAULT CURRENT_TIMESTAMP,
            last_trained_date TEXT,
            is_active BOOLEAN DEFAULT 1,
            parameters TEXT
        )
        ''')

        # Student retention predictions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS retention_predictions (
            prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            model_id INTEGER NOT NULL,
            retention_probability REAL NOT NULL,
            risk_level TEXT NOT NULL,
            prediction_date TEXT DEFAULT CURRENT_TIMESTAMP,
            prediction_year INTEGER,
            factors TEXT,
            recommendations TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (model_id) REFERENCES analytics_models (model_id)
        )
        ''')

        # Graduation rate forecasts
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS graduation_forecasts (
            forecast_id INTEGER PRIMARY KEY AUTOINCREMENT,
            cohort_year INTEGER NOT NULL,
            program_id INTEGER,
            predicted_graduation_rate REAL,
            predicted_4year_rate REAL,
            predicted_5year_rate REAL,
            predicted_6year_rate REAL,
            forecast_date TEXT DEFAULT CURRENT_TIMESTAMP,
            model_id INTEGER,
            confidence_interval TEXT,
            FOREIGN KEY (model_id) REFERENCES analytics_models (model_id)
        )
        ''')

        # Course demand predictions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS course_demand_predictions (
            prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            semester TEXT NOT NULL,
            predicted_enrollment INTEGER,
            actual_enrollment INTEGER,
            prediction_date TEXT DEFAULT CURRENT_TIMESTAMP,
            model_id INTEGER,
            factors TEXT,
            FOREIGN KEY (module_code) REFERENCES modules (module_code),
            FOREIGN KEY (model_id) REFERENCES analytics_models (model_id)
        )
        ''')

        # Enrollment projections
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS enrollment_projections (
            projection_id INTEGER PRIMARY KEY AUTOINCREMENT,
            academic_year TEXT NOT NULL,
            program_id INTEGER,
            projected_new_students INTEGER,
            projected_continuing_students INTEGER,
            projected_total_enrollment INTEGER,
            projection_date TEXT DEFAULT CURRENT_TIMESTAMP,
            model_id INTEGER,
            scenario TEXT,
            FOREIGN KEY (model_id) REFERENCES analytics_models (model_id)
        )
        ''')

        # KPI tracking
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS kpi_metrics (
            kpi_id INTEGER PRIMARY KEY AUTOINCREMENT,
            kpi_name TEXT NOT NULL,
            kpi_category TEXT NOT NULL,
            current_value REAL NOT NULL,
            target_value REAL,
            measurement_date TEXT DEFAULT CURRENT_DATE,
            period TEXT,
            trend TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Custom dashboards
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS analytics_dashboards (
            dashboard_id INTEGER PRIMARY KEY AUTOINCREMENT,
            dashboard_name TEXT NOT NULL,
            dashboard_type TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            is_public BOOLEAN DEFAULT 0,
            layout_config TEXT,
            widget_config TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Dashboard widgets
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS dashboard_widgets (
            widget_id INTEGER PRIMARY KEY AUTOINCREMENT,
            dashboard_id INTEGER NOT NULL,
            widget_type TEXT NOT NULL,
            widget_title TEXT NOT NULL,
            data_source TEXT,
            chart_type TEXT,
            position_x INTEGER,
            position_y INTEGER,
            width INTEGER DEFAULT 4,
            height INTEGER DEFAULT 3,
            config TEXT,
            FOREIGN KEY (dashboard_id) REFERENCES analytics_dashboards (dashboard_id)
        )
        ''')

        # Scheduled reports
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS scheduled_reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_name TEXT NOT NULL,
            report_type TEXT NOT NULL,
            schedule_frequency TEXT NOT NULL,
            recipients TEXT NOT NULL,
            last_run_date TEXT,
            next_run_date TEXT,
            is_active BOOLEAN DEFAULT 1,
            report_config TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Data snapshots for trend analysis
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS analytics_snapshots (
            snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_type TEXT NOT NULL,
            snapshot_date TEXT DEFAULT CURRENT_DATE,
            data_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Performance trends
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS performance_trends (
            trend_id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT NOT NULL,
            metric_category TEXT NOT NULL,
            time_period TEXT NOT NULL,
            value REAL NOT NULL,
            change_from_previous REAL,
            trend_direction TEXT,
            recorded_date TEXT DEFAULT CURRENT_DATE
        )
        ''')

        # Insert default analytics model if it doesn't exist
        cursor.execute('SELECT COUNT(*) FROM analytics_models WHERE model_id = 1')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO analytics_models (
                    model_id, model_name, model_type, description,
                    model_version, accuracy_score, is_active, parameters
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                1,
                'Default Prediction Model',
                'baseline',
                'Default model for initial predictions and testing',
                '1.0',
                0.75,
                1,
                '{}'
            ))
            print("  ✓ Created default analytics model (ID: 1)")

        conn.commit()
        conn.close()
        print("Predictive Analytics Dashboard database initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing Analytics Dashboard database: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# SMART TIMETABLE OPTIMIZER SCHEMAS
# ============================================================================

def init_smart_timetable_system_db():
    """Initialize the Smart Timetable Optimizer database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing Smart Timetable Optimizer tables...")

        # Timetable configurations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS timetable_configurations (
            config_id INTEGER PRIMARY KEY AUTOINCREMENT,
            academic_year TEXT NOT NULL,
            semester TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            optimization_status TEXT DEFAULT 'pending',
            last_optimized_date TEXT,
            conflicts_detected INTEGER DEFAULT 0,
            conflicts_resolved INTEGER DEFAULT 0,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Time slots
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS timetable_time_slots (
            slot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_name TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            is_available BOOLEAN DEFAULT 1,
            priority_level INTEGER DEFAULT 3
        )
        ''')

        # Class schedules
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS timetable_classes (
            schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_id INTEGER NOT NULL,
            module_code TEXT NOT NULL,
            class_type TEXT NOT NULL,
            instructor_id TEXT,
            room_id INTEGER,
            slot_id INTEGER NOT NULL,
            capacity INTEGER DEFAULT 30,
            enrolled_count INTEGER DEFAULT 0,
            recurrence_pattern TEXT DEFAULT 'weekly',
            status TEXT DEFAULT 'scheduled',
            FOREIGN KEY (config_id) REFERENCES timetable_configurations (config_id),
            FOREIGN KEY (slot_id) REFERENCES timetable_time_slots (slot_id)
        )
        ''')

        # Scheduling constraints
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS timetable_constraints (
            constraint_id INTEGER PRIMARY KEY AUTOINCREMENT,
            constraint_type TEXT NOT NULL,
            constraint_name TEXT NOT NULL,
            applies_to TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            constraint_rule TEXT NOT NULL,
            priority INTEGER DEFAULT 5,
            is_hard_constraint BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Scheduling conflicts
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS timetable_conflicts (
            conflict_id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_id INTEGER NOT NULL,
            conflict_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            description TEXT NOT NULL,
            affected_schedules TEXT,
            resolution_status TEXT DEFAULT 'unresolved',
            resolution_notes TEXT,
            detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
            resolved_at TEXT,
            FOREIGN KEY (config_id) REFERENCES timetable_configurations (config_id)
        )
        ''')

        # Student preferences
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS timetable_student_preferences (
            preference_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            preference_type TEXT NOT NULL,
            preferred_days TEXT,
            preferred_times TEXT,
            avoid_days TEXT,
            avoid_times TEXT,
            max_daily_hours INTEGER,
            gap_preference TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        conn.commit()
        conn.close()
        print("Smart Timetable Optimizer database initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing Smart Timetable database: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# CAMPUS EVENTS HUB SCHEMAS
# ============================================================================

def init_campus_events_system_db():
    """Initialize the Campus Events Hub database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing Campus Events Hub tables...")

        # Events
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS campus_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_category TEXT NOT NULL,
            description TEXT,
            organizer_id TEXT NOT NULL,
            organizer_type TEXT NOT NULL,
            event_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            location TEXT,
            room_id INTEGER,
            capacity INTEGER,
            registration_required BOOLEAN DEFAULT 0,
            registration_deadline TEXT,
            is_public BOOLEAN DEFAULT 1,
            is_featured BOOLEAN DEFAULT 0,
            tags TEXT,
            image_url TEXT,
            status TEXT DEFAULT 'scheduled',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Event registrations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_registrations (
            registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            user_type TEXT NOT NULL,
            registration_date TEXT DEFAULT CURRENT_TIMESTAMP,
            attendance_status TEXT DEFAULT 'registered',
            checked_in_at TEXT,
            feedback_rating INTEGER,
            feedback_comment TEXT,
            FOREIGN KEY (event_id) REFERENCES campus_events (event_id)
        )
        ''')

        # Event series/recurring events
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_series (
            series_id INTEGER PRIMARY KEY AUTOINCREMENT,
            series_name TEXT NOT NULL,
            series_description TEXT,
            organizer_id TEXT NOT NULL,
            recurrence_pattern TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Event announcements
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_announcements (
            announcement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            announcement_text TEXT NOT NULL,
            sent_to TEXT NOT NULL,
            sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
            sent_by TEXT,
            FOREIGN KEY (event_id) REFERENCES campus_events (event_id)
        )
        ''')

        # Event sponsors
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_sponsors (
            sponsor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            sponsor_name TEXT NOT NULL,
            sponsor_type TEXT,
            contribution_amount REAL,
            logo_url TEXT,
            website_url TEXT,
            FOREIGN KEY (event_id) REFERENCES campus_events (event_id)
        )
        ''')

        # Event calendar subscriptions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_calendar_subscriptions (
            subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            calendar_feed_url TEXT NOT NULL,
            filter_categories TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        conn.commit()
        conn.close()
        print("Campus Events Hub database initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing Campus Events database: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# ALUMNI RELATIONS & ENGAGEMENT SCHEMAS
# ============================================================================

def init_alumni_relations_system_db():
    """Initialize the Alumni Relations & Engagement database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing Alumni Relations & Engagement tables...")

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

        # Alumni events
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alumni_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_date TEXT NOT NULL,
            event_time TEXT NOT NULL,
            location TEXT,
            is_virtual BOOLEAN DEFAULT 0,
            meeting_link TEXT,
            description TEXT,
            target_class_year TEXT,
            max_attendees INTEGER,
            current_attendees INTEGER DEFAULT 0,
            registration_fee REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Alumni event registrations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alumni_event_registrations (
            registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            alumni_id INTEGER NOT NULL,
            num_guests INTEGER DEFAULT 0,
            registration_date TEXT DEFAULT CURRENT_TIMESTAMP,
            payment_status TEXT DEFAULT 'pending',
            attended BOOLEAN DEFAULT 0,
            FOREIGN KEY (event_id) REFERENCES alumni_events (event_id),
            FOREIGN KEY (alumni_id) REFERENCES alumni_profiles (alumni_id)
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
        print("Alumni Relations & Engagement database initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing Alumni Relations database: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# RESEARCH & GRANTS MANAGEMENT SCHEMAS
# ============================================================================

def init_research_grants_system_db():
    """Initialize the Research & Grants Management database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing Research & Grants Management tables...")

        # Research projects
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS research_projects (
            project_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_title TEXT NOT NULL,
            project_description TEXT,
            principal_investigator_id TEXT NOT NULL,
            department TEXT NOT NULL,
            project_type TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT,
            status TEXT DEFAULT 'active',
            total_budget REAL DEFAULT 0,
            funding_source TEXT,
            ethics_approval_status TEXT DEFAULT 'pending',
            ethics_approval_date TEXT,
            publications_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Research team members
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS research_team_members (
            member_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            staff_id TEXT NOT NULL,
            role TEXT NOT NULL,
            join_date TEXT DEFAULT CURRENT_DATE,
            leave_date TEXT,
            contribution_percentage REAL,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (project_id) REFERENCES research_projects (project_id)
        )
        ''')

        # Grant applications
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS grant_applications (
            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
            grant_name TEXT NOT NULL,
            funding_agency TEXT NOT NULL,
            project_id INTEGER,
            principal_investigator_id TEXT NOT NULL,
            co_investigators TEXT,
            requested_amount REAL NOT NULL,
            application_deadline TEXT NOT NULL,
            submission_date TEXT,
            decision_date TEXT,
            decision_status TEXT DEFAULT 'pending',
            awarded_amount REAL,
            grant_period_start TEXT,
            grant_period_end TEXT,
            application_documents TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES research_projects (project_id)
        )
        ''')

        # Grant budgets
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS grant_budgets (
            budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            requested_amount REAL NOT NULL,
            approved_amount REAL,
            spent_amount REAL DEFAULT 0,
            remaining_amount REAL,
            FOREIGN KEY (application_id) REFERENCES grant_applications (application_id)
        )
        ''')

        # Research publications
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS research_publications (
            publication_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            title TEXT NOT NULL,
            authors TEXT NOT NULL,
            publication_type TEXT NOT NULL,
            journal_name TEXT,
            conference_name TEXT,
            publication_date TEXT,
            doi TEXT,
            url TEXT,
            abstract TEXT,
            keywords TEXT,
            citation_count INTEGER DEFAULT 0,
            is_peer_reviewed BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES research_projects (project_id)
        )
        ''')

        # Research milestones
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS research_milestones (
            milestone_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            milestone_name TEXT NOT NULL,
            milestone_description TEXT,
            target_date TEXT NOT NULL,
            completion_date TEXT,
            status TEXT DEFAULT 'pending',
            deliverables TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES research_projects (project_id)
        )
        ''')

        # Research equipment
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS research_equipment (
            equipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_name TEXT NOT NULL,
            equipment_type TEXT NOT NULL,
            model_number TEXT,
            serial_number TEXT,
            purchase_date TEXT,
            purchase_cost REAL,
            current_location TEXT,
            assigned_project_id INTEGER,
            maintenance_schedule TEXT,
            last_maintenance_date TEXT,
            status TEXT DEFAULT 'available',
            FOREIGN KEY (assigned_project_id) REFERENCES research_projects (project_id)
        )
        ''')

        # IRB/Ethics reviews
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ethics_reviews (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            review_type TEXT NOT NULL,
            submission_date TEXT NOT NULL,
            review_date TEXT,
            decision TEXT DEFAULT 'pending',
            decision_date TEXT,
            reviewer_comments TEXT,
            conditions TEXT,
            approval_expiry_date TEXT,
            FOREIGN KEY (project_id) REFERENCES research_projects (project_id)
        )
        ''')

        conn.commit()
        conn.close()
        print("Research & Grants Management database initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing Research & Grants database: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# FACILITIES & SPACE MANAGEMENT SCHEMAS
# ============================================================================

def init_facilities_management_system_db():
    """Initialize the Facilities & Space Management database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing Facilities & Space Management tables...")

        # Buildings
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS buildings (
            building_id INTEGER PRIMARY KEY AUTOINCREMENT,
            building_name TEXT NOT NULL,
            building_code TEXT UNIQUE NOT NULL,
            address TEXT,
            total_floors INTEGER,
            total_rooms INTEGER,
            building_type TEXT,
            year_built INTEGER,
            last_renovation_year INTEGER,
            accessibility_features TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Rooms
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            room_id INTEGER PRIMARY KEY AUTOINCREMENT,
            building_id INTEGER NOT NULL,
            room_number TEXT NOT NULL,
            room_name TEXT,
            floor_number INTEGER,
            room_type TEXT NOT NULL,
            capacity INTEGER,
            area_sqft REAL,
            features TEXT,
            equipment TEXT,
            accessibility_compliant BOOLEAN DEFAULT 1,
            status TEXT DEFAULT 'available',
            FOREIGN KEY (building_id) REFERENCES buildings (building_id)
        )
        ''')

        # Room bookings
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS room_bookings (
            booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            booked_by TEXT NOT NULL,
            booking_type TEXT NOT NULL,
            purpose TEXT,
            start_datetime TEXT NOT NULL,
            end_datetime TEXT NOT NULL,
            setup_required TEXT,
            equipment_needed TEXT,
            expected_attendees INTEGER,
            recurrence_pattern TEXT,
            booking_status TEXT DEFAULT 'confirmed',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (room_id) REFERENCES rooms (room_id)
        )
        ''')

        # Maintenance requests
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS maintenance_requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_type TEXT NOT NULL,
            building_id INTEGER,
            room_id INTEGER,
            request_type TEXT NOT NULL,
            priority TEXT NOT NULL,
            description TEXT NOT NULL,
            reported_by TEXT NOT NULL,
            reported_date TEXT DEFAULT CURRENT_TIMESTAMP,
            assigned_to TEXT,
            assigned_date TEXT,
            scheduled_date TEXT,
            completion_date TEXT,
            status TEXT DEFAULT 'open',
            cost REAL,
            notes TEXT,
            FOREIGN KEY (building_id) REFERENCES buildings (building_id),
            FOREIGN KEY (room_id) REFERENCES rooms (room_id)
        )
        ''')

        # Work orders
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS work_orders (
            work_order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            work_order_type TEXT NOT NULL,
            description TEXT NOT NULL,
            assigned_technician TEXT,
            estimated_hours REAL,
            actual_hours REAL,
            materials_cost REAL,
            labor_cost REAL,
            total_cost REAL,
            start_date TEXT,
            completion_date TEXT,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (request_id) REFERENCES maintenance_requests (request_id)
        )
        ''')

        # Asset inventory
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS facility_assets (
            asset_id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_name TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            asset_tag TEXT UNIQUE,
            building_id INTEGER,
            room_id INTEGER,
            purchase_date TEXT,
            purchase_cost REAL,
            warranty_expiry TEXT,
            maintenance_schedule TEXT,
            last_maintenance_date TEXT,
            condition TEXT DEFAULT 'good',
            status TEXT DEFAULT 'active',
            FOREIGN KEY (building_id) REFERENCES buildings (building_id),
            FOREIGN KEY (room_id) REFERENCES rooms (room_id)
        )
        ''')

        # Energy usage tracking
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS energy_usage (
            usage_id INTEGER PRIMARY KEY AUTOINCREMENT,
            building_id INTEGER NOT NULL,
            usage_type TEXT NOT NULL,
            reading_date TEXT NOT NULL,
            meter_reading REAL NOT NULL,
            consumption REAL,
            cost REAL,
            billing_period_start TEXT,
            billing_period_end TEXT,
            FOREIGN KEY (building_id) REFERENCES buildings (building_id)
        )
        ''')

        # Space utilization analytics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS space_utilization (
            utilization_id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            measurement_date TEXT NOT NULL,
            occupancy_rate REAL,
            booking_rate REAL,
            peak_usage_time TEXT,
            average_attendees REAL,
            total_booking_hours REAL,
            FOREIGN KEY (room_id) REFERENCES rooms (room_id)
        )
        ''')

        conn.commit()
        conn.close()
        print("Facilities & Space Management database initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing Facilities Management database: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# COURSE EVALUATION SYSTEM SCHEMAS
# ============================================================================

def init_course_evaluation_system_db():
    """Initialize the Course Evaluation System database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing Course Evaluation System tables...")

        # Evaluation templates
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluation_templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name TEXT NOT NULL,
            template_type TEXT NOT NULL,
            description TEXT,
            is_default BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Evaluation questions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluation_questions (
            question_id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            question_type TEXT NOT NULL,
            question_category TEXT NOT NULL,
            is_required BOOLEAN DEFAULT 1,
            scale_min INTEGER,
            scale_max INTEGER,
            options TEXT,
            display_order INTEGER,
            FOREIGN KEY (template_id) REFERENCES evaluation_templates (template_id)
        )
        ''')

        # Course evaluations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS course_evaluations (
            evaluation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            semester TEXT NOT NULL,
            instructor_id TEXT NOT NULL,
            template_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            is_anonymous BOOLEAN DEFAULT 1,
            is_active BOOLEAN DEFAULT 1,
            response_count INTEGER DEFAULT 0,
            completion_rate REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (template_id) REFERENCES evaluation_templates (template_id)
        )
        ''')

        # Evaluation responses
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluation_responses (
            response_id INTEGER PRIMARY KEY AUTOINCREMENT,
            evaluation_id INTEGER NOT NULL,
            student_id TEXT,
            response_date TEXT DEFAULT CURRENT_TIMESTAMP,
            is_complete BOOLEAN DEFAULT 0,
            time_taken_minutes INTEGER,
            FOREIGN KEY (evaluation_id) REFERENCES course_evaluations (evaluation_id)
        )
        ''')

        # Response answers
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluation_answers (
            answer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            response_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            answer_value TEXT,
            numeric_value REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (response_id) REFERENCES evaluation_responses (response_id),
            FOREIGN KEY (question_id) REFERENCES evaluation_questions (question_id)
        )
        ''')

        # Evaluation results/analytics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluation_results (
            result_id INTEGER PRIMARY KEY AUTOINCREMENT,
            evaluation_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            average_score REAL,
            median_score REAL,
            mode_score REAL,
            standard_deviation REAL,
            response_count INTEGER,
            percentile_25 REAL,
            percentile_75 REAL,
            calculated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (evaluation_id) REFERENCES course_evaluations (evaluation_id),
            FOREIGN KEY (question_id) REFERENCES evaluation_questions (question_id)
        )
        ''')

        # Instructor performance tracking
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS instructor_performance_history (
            performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            instructor_id TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            semester TEXT NOT NULL,
            avg_overall_rating REAL,
            avg_teaching_effectiveness REAL,
            avg_course_organization REAL,
            avg_student_engagement REAL,
            total_evaluations INTEGER,
            total_responses INTEGER,
            calculated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        conn.commit()
        conn.close()
        print("Course Evaluation System database initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing Course Evaluation database: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# BUSINESS INTELLIGENCE REPORTS SCHEMAS
# ============================================================================

def init_business_intelligence_system_db():
    """Initialize the Business Intelligence Reports database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing Business Intelligence Reports tables...")

        # Report definitions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bi_report_definitions (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_name TEXT NOT NULL,
            report_category TEXT NOT NULL,
            description TEXT,
            sql_query TEXT,
            data_source TEXT,
            parameters TEXT,
            visualization_type TEXT,
            created_by TEXT,
            is_public BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT
        )
        ''')

        # Saved reports/exports
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bi_report_exports (
            export_id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            export_format TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            generated_by TEXT NOT NULL,
            generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            parameters_used TEXT,
            row_count INTEGER,
            FOREIGN KEY (report_id) REFERENCES bi_report_definitions (report_id)
        )
        ''')

        # Report schedules
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bi_report_schedules (
            schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            schedule_name TEXT NOT NULL,
            frequency TEXT NOT NULL,
            delivery_method TEXT NOT NULL,
            recipients TEXT NOT NULL,
            export_format TEXT NOT NULL,
            last_run_date TEXT,
            next_run_date TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (report_id) REFERENCES bi_report_definitions (report_id)
        )
        ''')

        # Data visualizations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bi_visualizations (
            visualization_id INTEGER PRIMARY KEY AUTOINCREMENT,
            visualization_name TEXT NOT NULL,
            chart_type TEXT NOT NULL,
            data_source TEXT NOT NULL,
            x_axis TEXT,
            y_axis TEXT,
            filters TEXT,
            color_scheme TEXT,
            configuration TEXT,
            created_by TEXT,
            is_public BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Custom metrics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bi_custom_metrics (
            metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT NOT NULL,
            metric_category TEXT NOT NULL,
            description TEXT,
            calculation_formula TEXT NOT NULL,
            data_sources TEXT,
            unit_of_measure TEXT,
            target_value REAL,
            created_by TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Data quality checks
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bi_data_quality_checks (
            check_id INTEGER PRIMARY KEY AUTOINCREMENT,
            check_name TEXT NOT NULL,
            data_source TEXT NOT NULL,
            check_type TEXT NOT NULL,
            check_rule TEXT NOT NULL,
            last_run_date TEXT,
            passed BOOLEAN,
            issues_found INTEGER,
            details TEXT,
            is_active BOOLEAN DEFAULT 1
        )
        ''')

        conn.commit()
        conn.close()
        print("Business Intelligence Reports database initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing Business Intelligence database: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# AI-POWERED FEATURES SCHEMAS
# ============================================================================

def init_ai_features_system_db():
    """Initialize the AI-Powered Features database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing AI-Powered Features tables...")

        # Chatbot conversations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_chatbot_conversations (
            conversation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            user_type TEXT NOT NULL,
            start_time TEXT DEFAULT CURRENT_TIMESTAMP,
            end_time TEXT,
            message_count INTEGER DEFAULT 0,
            satisfaction_rating INTEGER,
            was_helpful BOOLEAN,
            escalated_to_human BOOLEAN DEFAULT 0
        )
        ''')

        # Chatbot messages
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_chatbot_messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            sender_type TEXT NOT NULL,
            message_text TEXT NOT NULL,
            intent_detected TEXT,
            confidence_score REAL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES ai_chatbot_conversations (conversation_id)
        )
        ''')

        # AI recommendations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_recommendations (
            recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            recommendation_type TEXT NOT NULL,
            recommendation_content TEXT NOT NULL,
            algorithm_used TEXT,
            confidence_score REAL,
            context_data TEXT,
            was_accepted BOOLEAN,
            feedback_rating INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Auto-grading results
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_grading_results (
            grading_id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            assignment_type TEXT NOT NULL,
            auto_score REAL,
            max_score REAL,
            grading_criteria TEXT,
            feedback_generated TEXT,
            confidence_score REAL,
            requires_manual_review BOOLEAN DEFAULT 0,
            manual_override_score REAL,
            graded_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Smart content suggestions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_content_suggestions (
            suggestion_id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_type TEXT NOT NULL,
            context TEXT NOT NULL,
            suggested_content TEXT NOT NULL,
            relevance_score REAL,
            source TEXT,
            was_used BOOLEAN DEFAULT 0,
            created_for TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Sentiment analysis
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_sentiment_analysis (
            analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id TEXT NOT NULL,
            content_type TEXT NOT NULL,
            content_text TEXT NOT NULL,
            sentiment_score REAL,
            sentiment_category TEXT,
            emotions_detected TEXT,
            key_phrases TEXT,
            analyzed_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Plagiarism detection
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_plagiarism_checks (
            check_id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            document_text TEXT NOT NULL,
            similarity_score REAL,
            matched_sources TEXT,
            flagged BOOLEAN DEFAULT 0,
            review_status TEXT DEFAULT 'pending',
            checked_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # AI model performance tracking
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_model_performance (
            performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name TEXT NOT NULL,
            model_version TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            test_dataset TEXT,
            measured_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        conn.commit()
        conn.close()
        print("AI-Powered Features database initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing AI Features database: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# INTEGRATION MARKETPLACE SCHEMAS
# ============================================================================

def init_integration_marketplace_system_db():
    """Initialize the Integration Marketplace database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing Integration Marketplace tables...")

        # Available integrations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS integration_catalog (
            integration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            integration_name TEXT NOT NULL,
            provider_name TEXT NOT NULL,
            integration_type TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            version TEXT,
            logo_url TEXT,
            documentation_url TEXT,
            pricing_model TEXT,
            is_official BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            rating REAL DEFAULT 0,
            install_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Installed integrations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS installed_integrations (
            install_id INTEGER PRIMARY KEY AUTOINCREMENT,
            integration_id INTEGER NOT NULL,
            installed_by TEXT NOT NULL,
            installation_date TEXT DEFAULT CURRENT_TIMESTAMP,
            version_installed TEXT,
            configuration TEXT,
            status TEXT DEFAULT 'active',
            last_sync_date TEXT,
            sync_frequency TEXT,
            is_enabled BOOLEAN DEFAULT 1,
            FOREIGN KEY (integration_id) REFERENCES integration_catalog (integration_id)
        )
        ''')

        # Integration credentials
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS integration_credentials (
            credential_id INTEGER PRIMARY KEY AUTOINCREMENT,
            install_id INTEGER NOT NULL,
            credential_type TEXT NOT NULL,
            api_key TEXT,
            api_secret TEXT,
            oauth_token TEXT,
            refresh_token TEXT,
            token_expiry TEXT,
            endpoint_url TEXT,
            additional_config TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT,
            FOREIGN KEY (install_id) REFERENCES installed_integrations (install_id)
        )
        ''')

        # Integration sync logs
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS integration_sync_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            install_id INTEGER NOT NULL,
            sync_start_time TEXT DEFAULT CURRENT_TIMESTAMP,
            sync_end_time TEXT,
            sync_status TEXT NOT NULL,
            records_synced INTEGER DEFAULT 0,
            errors_encountered INTEGER DEFAULT 0,
            error_details TEXT,
            FOREIGN KEY (install_id) REFERENCES installed_integrations (install_id)
        )
        ''')

        # Data mappings
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS integration_data_mappings (
            mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
            install_id INTEGER NOT NULL,
            source_field TEXT NOT NULL,
            target_field TEXT NOT NULL,
            transformation_rule TEXT,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (install_id) REFERENCES installed_integrations (install_id)
        )
        ''')

        # Webhook endpoints
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS integration_webhooks (
            webhook_id INTEGER PRIMARY KEY AUTOINCREMENT,
            install_id INTEGER NOT NULL,
            webhook_url TEXT NOT NULL,
            event_type TEXT NOT NULL,
            secret_key TEXT,
            is_active BOOLEAN DEFAULT 1,
            last_triggered_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (install_id) REFERENCES installed_integrations (install_id)
        )
        ''')

        # Integration usage analytics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS integration_usage_analytics (
            analytics_id INTEGER PRIMARY KEY AUTOINCREMENT,
            install_id INTEGER NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            measurement_date TEXT DEFAULT CURRENT_DATE,
            FOREIGN KEY (install_id) REFERENCES installed_integrations (install_id)
        )
        ''')

        conn.commit()
        conn.close()
        print("Integration Marketplace database initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing Integration Marketplace database: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# MASTER INITIALIZATION
# ============================================================================

def initialize_all_schemas():
    """Initialize all system database schemas"""
    print("=" * 60)
    print("INITIALIZING ALL SYSTEM DATABASE SCHEMAS")
    print("=" * 60)

    # Original systems
    init_grade_system_db()
    init_finance_system_db()
    init_student_union_db()
    init_email_system_db()
    init_health_system_db()

    # Phase 1: HIGH Priority Features
    init_lms_system_db()
    init_attendance_system_db()
    init_mental_health_system_db()
    init_early_warning_system_db()

    # Phase 2: MEDIUM-HIGH Priority Features
    init_degree_audit_system_db()
    init_career_services_system_db()
    init_admissions_crm_system_db()
    init_analytics_dashboard_system_db()

    # Phase 3: MEDIUM Priority Features
    init_smart_timetable_system_db()
    init_campus_events_system_db()
    init_alumni_relations_system_db()
    init_research_grants_system_db()
    init_facilities_management_system_db()
    init_course_evaluation_system_db()
    init_business_intelligence_system_db()
    init_ai_features_system_db()
    init_integration_marketplace_system_db()

    # Phase 4: Missing tables from database schema
    print("\n" + "=" * 60)
    print("INITIALIZING MISSING TABLES FROM DATABASE")
    print("=" * 60)
    init_academics_tables()
    init_ai_tables()
    init_alumni_tables()
    init_analytics_tables()
    init_audit_tables()
    init_auth_tables()
    init_career_tables()
    init_commerce_tables()
    init_communication_tables()
    init_courses_tables()
    init_documents_tables()
    init_finance_tables()
    init_health_tables()
    init_housing_tables()
    init_integration_tables()
    init_library_tables()
    init_other_tables()
    init_parent_tables()
    init_parking_tables()
    init_peer_support_tables()
    init_social_tables()
    init_student_affairs_tables()
    init_support_tables()
    init_travel_tables()
    init_wellness_tables()

    print("=" * 60)
    print("ALL DATABASE SCHEMAS INITIALIZED SUCCESSFULLY")
    print("=" * 60)



# ============================================================================
# MISSING TABLES ADDED FROM DATABASE SCHEMA
# Generated automatically to synchronize with actual database
# ============================================================================

# ============================================================================
# ACADEMICS TABLES (40 tables)
# ============================================================================

def init_academics_tables():
    """Initialize academics system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing academics tables...")

        # Create assignment_submissions table
        cursor.execute('''
        CREATE TABLE assignment_submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assignment_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    submission_date TIMESTAMP NOT NULL,
                    file_path TEXT,
                    file_name TEXT NOT NULL,
                    file_size INTEGER,
                    file_hash TEXT,
                    status TEXT DEFAULT 'submitted',
                    grade REAL,
                    feedback TEXT,
                    late_submission BOOLEAN DEFAULT 0,
                    late_days INTEGER DEFAULT 0,
                    version_number INTEGER DEFAULT 1,
                    is_final_submission BOOLEAN DEFAULT 1,
                    graded_by INTEGER,
                    graded_date TIMESTAMP,
                    FOREIGN KEY (assignment_id) REFERENCES assignments (id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (graded_by) REFERENCES users (id)
                )
        ''')

        # Create assignments table
        cursor.execute('''
        CREATE TABLE assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    module_code TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    instructions TEXT,
                    due_date TIMESTAMP NOT NULL,
                    max_marks INTEGER NOT NULL,
                    file_types_allowed TEXT,
                    max_file_size_mb INTEGER DEFAULT 10,
                    assignment_type TEXT DEFAULT 'individual',
                    group_size_min INTEGER DEFAULT 1,
                    group_size_max INTEGER DEFAULT 1,
                    allow_late_submission BOOLEAN DEFAULT 1,
                    late_penalty_per_day REAL DEFAULT 0,
                    auto_release_grades BOOLEAN DEFAULT 0,
                    peer_review_enabled BOOLEAN DEFAULT 0,
                    rubric_id INTEGER,
                    is_active BOOLEAN DEFAULT 1,
                    created_by INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (module_code) REFERENCES modules (module_code),
                    FOREIGN KEY (created_by) REFERENCES users (id)
                )
        ''')

        # Create attendance_alerts table
        cursor.execute('''
        CREATE TABLE attendance_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_id TEXT UNIQUE,
                    student_id TEXT,
                    module_code TEXT,
                    alert_type TEXT,
                    severity TEXT,
                    message TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    sent_at TEXT,
                    acknowledged_at TEXT,
                    status TEXT DEFAULT 'pending',
                    recipient_email TEXT,
                    recipient_phone TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (module_code) REFERENCES modules (module_code)
                )
        ''')

        # Create attendance_appeals table
        cursor.execute('''
        CREATE TABLE attendance_appeals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    appeal_id TEXT UNIQUE,
                    student_id TEXT,
                    module_code TEXT,
                    attendance_record_id INTEGER,
                    original_status TEXT,
                    requested_status TEXT,
                    reason TEXT,
                    evidence_files TEXT,
                    submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    reviewed_by TEXT,
                    reviewed_at TEXT,
                    decision TEXT,
                    decision_reason TEXT,
                    status TEXT DEFAULT 'pending',
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (module_code) REFERENCES modules (module_code),
                    FOREIGN KEY (attendance_record_id) REFERENCES attendance_records (id)
                )
        ''')

        # Create attendance_audit_log table
        cursor.execute('''
        CREATE TABLE attendance_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    action TEXT,
                    table_name TEXT,
                    record_id TEXT,
                    old_values TEXT,
                    new_values TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    ip_address TEXT,
                    user_agent TEXT
                )
        ''')

        # Create attendance_calendar_links table
        cursor.execute('''
        CREATE TABLE attendance_calendar_links (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        attendance_record_id INTEGER,
                        event_id TEXT,
                        module_code TEXT,
                        date TEXT,
                        created_at TEXT,
                        FOREIGN KEY (attendance_record_id) REFERENCES attendance_records (id),
                        FOREIGN KEY (event_id) REFERENCES events (id)
                    )
        ''')

        # Create attendance_gamification table
        cursor.execute('''
        CREATE TABLE attendance_gamification (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    points INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    badges TEXT,
                    achievements TEXT,
                    streak_days INTEGER DEFAULT 0,
                    best_streak INTEGER DEFAULT 0,
                    last_attendance_date TEXT,
                    total_rewards INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
        ''')

        # Create attendance_policies table
        cursor.execute('''
        CREATE TABLE attendance_policies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    policy_id TEXT UNIQUE,
                    name TEXT,
                    description TEXT,
                    module_code TEXT,
                    course TEXT,
                    min_attendance_percentage REAL,
                    max_consecutive_absences INTEGER,
                    late_tolerance_minutes INTEGER DEFAULT 15,
                    makeup_allowed BOOLEAN DEFAULT 1,
                    auto_fail_threshold REAL,
                    grace_period_days INTEGER DEFAULT 0,
                    effective_from TEXT,
                    effective_until TEXT,
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'active'
                )
        ''')

        # Create attendance_predictions table
        cursor.execute('''
        CREATE TABLE attendance_predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    module_code TEXT,
                    prediction_date TEXT,
                    predicted_attendance_rate REAL,
                    risk_level TEXT,
                    confidence_score REAL,
                    factors TEXT,
                    recommendations TEXT,
                    model_version TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (module_code) REFERENCES modules (module_code)
                )
        ''')

        # Create attendance_settings table
        cursor.execute('''
        CREATE TABLE attendance_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    setting_name TEXT UNIQUE,
                    setting_value TEXT,
                    description TEXT,
                    category TEXT DEFAULT 'general',
                    data_type TEXT DEFAULT 'string',
                    last_modified TEXT DEFAULT CURRENT_TIMESTAMP
                )
        ''')

        # Create course_event_attendance table
        cursor.execute('''
        CREATE TABLE course_event_attendance (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            event_id TEXT NOT NULL,
                            student_id TEXT NOT NULL,
                            attendance_status TEXT DEFAULT 'present',
                            notes TEXT,
                            recorded_at TEXT NOT NULL,
                            FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE,
                            UNIQUE(event_id, student_id)
                        )
        ''')

        # Create event_attendance table
        cursor.execute('''
        CREATE TABLE event_attendance (
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

        # Create event_tag_assignments table
        cursor.execute('''
        CREATE TABLE event_tag_assignments (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            event_id TEXT NOT NULL,
                            tag_id INTEGER NOT NULL,
                            date_added TEXT NOT NULL,
                            FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE,
                            FOREIGN KEY (tag_id) REFERENCES event_tags (id) ON DELETE CASCADE,
                            UNIQUE(event_id, tag_id)
                        )
        ''')

        # Create grade_analytics table
        cursor.execute('''
        CREATE TABLE grade_analytics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        module_code TEXT,
                        assessment_date TEXT,
                        grade_value DECIMAL(5,2),
                        class_average DECIMAL(5,2),
                        percentile_rank INTEGER,
                        trend_direction TEXT,
                        FOREIGN KEY (student_id) REFERENCES students (student_id),
                        FOREIGN KEY (module_code) REFERENCES modules (module_code)
                    )
        ''')

        # Create grade_statistics table
        cursor.execute('''
        CREATE TABLE grade_statistics (
                    stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assessment_id INTEGER,
                    mean REAL,
                    median REAL,
                    std_dev REAL,
                    min_score REAL,
                    max_score REAL,
                    q1 REAL,
                    q3 REAL,
                    skewness REAL,
                    kurtosis REAL,
                    date_calculated TEXT,
                    FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id)
                )
        ''')

        # Create grades table
        cursor.execute('''
        CREATE TABLE grades (
                    grade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    assessment_id INTEGER,
                    score REAL,
                    letter_grade TEXT,
                    submission_date TEXT,
                    comments TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id)
                )
        ''')

        # Create homework_assignments table
        cursor.execute('''
        CREATE TABLE homework_assignments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        module_code TEXT,
                        assignment_title TEXT,
                        description TEXT,
                        assigned_date TEXT,
                        due_date TEXT,
                        completion_status TEXT DEFAULT 'pending',
                        submitted_date TEXT,
                        grade TEXT,
                        teacher_comments TEXT,
                        FOREIGN KEY (student_id) REFERENCES students (student_id),
                        FOREIGN KEY (module_code) REFERENCES modules (module_code)
                    )
        ''')

        # Create housing_assignments table
        cursor.execute('''
        CREATE TABLE housing_assignments (
                    assignment_id TEXT PRIMARY KEY,
                    application_id TEXT,
                    student_id TEXT NOT NULL,
                    room_id TEXT NOT NULL,
                    move_in_date TEXT NOT NULL,
                    planned_move_out_date TEXT NOT NULL,
                    actual_move_out_date TEXT,
                    contract_number TEXT UNIQUE,
                    monthly_rent REAL NOT NULL,
                    status TEXT NOT NULL,
                    assigned_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (application_id) REFERENCES housing_applications (application_id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (room_id) REFERENCES housing_rooms (room_id)
                )
        ''')

        # Create module_grades table
        cursor.execute('''
        CREATE TABLE module_grades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    module_code TEXT,
                    final_score REAL,
                    final_grade TEXT,
                    completion_date TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (module_code) REFERENCES modules (module_code)
                )
        ''')

        # Create normalized_grades table
        cursor.execute('''
        CREATE TABLE normalized_grades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    grade_id INTEGER,
                    z_score REAL,
                    percentile REAL,
                    curved_score REAL,
                    curved_letter TEXT,
                    FOREIGN KEY (grade_id) REFERENCES grades (grade_id)
                )
        ''')

        # Create parent_student_relationships table
        cursor.execute('''
        CREATE TABLE parent_student_relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id TEXT,
                    student_id TEXT,
                    relationship_type TEXT,
                    access_level TEXT DEFAULT 'full',
                    date_added TEXT,
                    FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
        ''')

        # Create peer_review_assignments table
        cursor.execute('''
        CREATE TABLE peer_review_assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assignment_id TEXT UNIQUE NOT NULL,
                    session_id TEXT NOT NULL,
                    reviewer_id TEXT NOT NULL,
                    reviewee_id TEXT NOT NULL,
                    submission_id INTEGER,
                    due_date TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (reviewer_id) REFERENCES students (student_id),
                    FOREIGN KEY (reviewee_id) REFERENCES students (student_id),
                    FOREIGN KEY (submission_id) REFERENCES assignment_submissions (id)
                )
        ''')

        # Create staff_assignments table
        cursor.execute('''
        CREATE TABLE staff_assignments (
                    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    staff_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    is_primary BOOLEAN DEFAULT 0,
                    max_concurrent_tickets INTEGER DEFAULT 10,
                    current_ticket_count INTEGER DEFAULT 0,
                    expertise_level INTEGER DEFAULT 1,  -- 1-5 scale
                    auto_assign_enabled BOOLEAN DEFAULT 1
                )
        ''')

        # Create student_absences table
        cursor.execute('''
        CREATE TABLE student_absences (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        absence_date TEXT,
                        return_date TEXT,
                        reason TEXT,
                        reported_by TEXT,
                        reported_date TEXT,
                        notes TEXT,
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create student_activities table
        cursor.execute('''
        CREATE TABLE student_activities (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        activity_id INTEGER,
                        enrollment_date TEXT,
                        status TEXT DEFAULT 'active',
                        FOREIGN KEY (student_id) REFERENCES students (student_id),
                        FOREIGN KEY (activity_id) REFERENCES extracurricular_activities (id)
                    )
        ''')

        # Create student_attendance table
        cursor.execute('''
        CREATE TABLE student_attendance(
          student_id TEXT,
          module_code TEXT,
          date TEXT,
          status TEXT,
          notes TEXT,
          recorded_at TEXT
        )
        ''')

        # Create student_badges table
        cursor.execute('''
        CREATE TABLE student_badges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    badge_id INTEGER,
                    earned_date TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (badge_id) REFERENCES achievement_badges (badge_id)
                )
        ''')

        # Create student_behavior table
        cursor.execute('''
        CREATE TABLE student_behavior (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        incident_date TEXT,
                        behavior_type TEXT,
                        severity TEXT,
                        description TEXT,
                        action_taken TEXT,
                        reported_by TEXT,
                        follow_up_required BOOLEAN DEFAULT 0,
                        resolved BOOLEAN DEFAULT 0,
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create student_biometrics table
        cursor.execute('''
        CREATE TABLE student_biometrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    face_encoding BLOB,
                    face_photo_path TEXT,
                    enrolled_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'active',
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
        ''')

        # Create student_competencies table
        cursor.execute('''
        CREATE TABLE student_competencies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    competency_id INTEGER NOT NULL,
                    level_id INTEGER NOT NULL,
                    assessment_date TEXT,
                    evidence TEXT,
                    FOREIGN KEY (student_id) REFERENCES students(student_id),
                    FOREIGN KEY (competency_id) REFERENCES competencies(competency_id),
                    FOREIGN KEY (level_id) REFERENCES competency_levels(level_id)
                )
        ''')

        # Create student_credits table
        cursor.execute('''
        CREATE TABLE student_credits (
                    credit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    credit_amount DECIMAL(10,2) NOT NULL,
                    currency TEXT DEFAULT 'GBP',
                    credit_source TEXT, -- 'overpayment', 'refund', 'scholarship', 'adjustment'
                    description TEXT,
                    expiry_date TEXT,
                    remaining_amount DECIMAL(10,2) NOT NULL,
                    status TEXT DEFAULT 'active', -- active, used, expired
                    created_by TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
        ''')

        # Create student_demographics table
        cursor.execute('''
        CREATE TABLE student_demographics (
                        student_id TEXT PRIMARY KEY,
                        age_group TEXT,
                        gender TEXT,
                        ethnicity TEXT,
                        native_language TEXT,
                        academic_level TEXT,
                        accommodations TEXT
                    )
        ''')

        # Create student_financial_aid table
        cursor.execute('''
        CREATE TABLE student_financial_aid (
                    aid_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    aid_type_id INTEGER NOT NULL,
                    awarded_amount DECIMAL(10,2) NOT NULL,
                    disbursed_amount DECIMAL(10,2) DEFAULT 0,
                    remaining_amount DECIMAL(10,2) NOT NULL,
                    currency TEXT DEFAULT 'GBP',
                    status TEXT DEFAULT 'pending', -- pending, approved, disbursed, completed, cancelled
                    application_date TEXT,
                    approval_date TEXT,
                    disbursement_schedule TEXT, -- JSON with disbursement dates and amounts
                    repayment_start_date TEXT,
                    monthly_payment_amount DECIMAL(10,2),
                    total_repaid DECIMAL(10,2) DEFAULT 0,
                    approved_by TEXT,
                    notes TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (aid_type_id) REFERENCES financial_aid_types (aid_type_id)
                )
        ''')

        # Create student_medical_info table
        cursor.execute('''
        CREATE TABLE student_medical_info (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        condition_type TEXT,
                        description TEXT,
                        medication_name TEXT,
                        dosage TEXT,
                        administration_time TEXT,
                        emergency_contact TEXT,
                        doctor_contact TEXT,
                        expiry_date TEXT,
                        notes TEXT,
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create student_payment_plans table
        cursor.execute('''
        CREATE TABLE student_payment_plans (
                    payment_plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    template_id INTEGER,
                    total_amount DECIMAL(10,2) NOT NULL,
                    remaining_amount DECIMAL(10,2) NOT NULL,
                    currency TEXT DEFAULT 'GBP',
                    status TEXT DEFAULT 'active', -- active, completed, defaulted, cancelled
                    start_date TEXT NOT NULL,
                    next_due_date TEXT,
                    setup_fee_paid BOOLEAN DEFAULT 0,
                    auto_payment_enabled BOOLEAN DEFAULT 0,
                    payment_method_id INTEGER,
                    notes TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (template_id) REFERENCES payment_plan_templates (template_id)
                )
        ''')

        # Create student_points table
        cursor.execute('''
        CREATE TABLE student_points (
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

        # Create student_requirement_progress table
        cursor.execute('''
        CREATE TABLE student_requirement_progress (
                            id TEXT PRIMARY KEY,
                            student_id TEXT NOT NULL,
                            requirement_id TEXT NOT NULL,
                            credits_completed REAL DEFAULT 0.0,
                            completion_percentage REAL DEFAULT 0.0,
                            status TEXT DEFAULT 'in_progress',
                            completion_date TEXT,
                            notes TEXT,
                            FOREIGN KEY (student_id) REFERENCES students (student_id),
                            FOREIGN KEY (requirement_id) REFERENCES graduation_requirements (id),
                            UNIQUE(student_id, requirement_id)
                        )
        ''')

        # Create student_risk_assessment table
        cursor.execute('''
        CREATE TABLE student_risk_assessment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    risk_score REAL NOT NULL,
                    risk_level TEXT NOT NULL,
                    assessment_date TEXT,
                    prediction_model TEXT,
                    confidence REAL,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
        ''')

        # Create teacher_student_permissions table
        cursor.execute('''
        CREATE TABLE teacher_student_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    teacher_id INTEGER,
                    student_id TEXT,
                    permission_type TEXT,
                    FOREIGN KEY (teacher_id) REFERENCES users (id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
        ''')

        # Create ticket_assignments table
        cursor.execute('''
        CREATE TABLE ticket_assignments (
                    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER,
                    assigned_from INTEGER,
                    assigned_to INTEGER,
                    assignment_reason TEXT,
                    created_at TEXT,
                    FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                    FOREIGN KEY (assigned_from) REFERENCES users (id),
                    FOREIGN KEY (assigned_to) REFERENCES users (id)
                )
        ''')

        conn.commit()
        conn.close()
        print("academics tables initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing academics tables: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# AI TABLES (11 tables)
# ============================================================================

def init_ai_tables():
    """Initialize ai system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing ai tables...")

        # Create ai_detector_metadata table
        cursor.execute('''
        CREATE TABLE ai_detector_metadata (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        submission_id INTEGER NOT NULL,
                        time_taken INTEGER,
                        browser_info TEXT,
                        device_fingerprint TEXT,
                        ip_address TEXT,
                        location_data TEXT,
                        keystroke_data TEXT,
                        FOREIGN KEY (submission_id) REFERENCES ai_detector_submissions (id)
                    )
        ''')

        # Create ai_detector_results table
        cursor.execute('''
        CREATE TABLE ai_detector_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        submission_id INTEGER NOT NULL,
                        ai_score REAL NOT NULL,
                        confidence REAL NOT NULL,
                        detailed_results TEXT,
                        created_at TEXT NOT NULL,
                        style_deviation REAL,
                        FOREIGN KEY (submission_id) REFERENCES ai_detector_submissions (id)
                    )
        ''')

        # Create ai_detector_submissions table
        cursor.execute('''
        CREATE TABLE ai_detector_submissions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        submission_text TEXT NOT NULL,
                        title TEXT,
                        course_code TEXT,
                        assignment_id TEXT,
                        submission_date TEXT NOT NULL,
                        word_count INTEGER,
                        character_count INTEGER,
                        institution_id TEXT
                    )
        ''')

        # Create campaign_expenses table
        cursor.execute('''
        CREATE TABLE campaign_expenses (
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

        # Create campaign_materials table
        cursor.execute('''
        CREATE TABLE campaign_materials (
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

        # Create chatbot_conversations table
        cursor.execute('''
        CREATE TABLE chatbot_conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT NOT NULL,
                    message TEXT NOT NULL,
                    response TEXT NOT NULL,
                    intent TEXT,
                    confidence REAL,
                    timestamp TEXT NOT NULL,
                    session_id TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
        ''')

        # Create fundraising_campaigns table
        cursor.execute('''
        CREATE TABLE fundraising_campaigns (
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

        # Create plagiarism_results table
        cursor.execute('''
        CREATE TABLE plagiarism_results (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            document_id INTEGER NOT NULL,
                            matched_document_id INTEGER,
                            similarity_score REAL NOT NULL CHECK(similarity_score >= 0 AND similarity_score <= 1),
                            check_date TEXT NOT NULL,
                            checked_by INTEGER,
                            status TEXT NOT NULL,
                            report TEXT,
                            threshold_used REAL DEFAULT 0.3,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (document_id) REFERENCES document_repository (id) ON DELETE CASCADE,
                            FOREIGN KEY (matched_document_id) REFERENCES document_repository (id) ON DELETE SET NULL,
                            FOREIGN KEY (checked_by) REFERENCES users (id) ON DELETE SET NULL
                        )
        ''')

        # Create risk_details table
        cursor.execute('''
        CREATE TABLE risk_details (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    risk_factor_id INTEGER,
                    detail TEXT,
                    weight REAL,
                    created_at TEXT,
                    FOREIGN KEY (risk_factor_id) REFERENCES risk_factors (id)
                )
        ''')

        # Create sustainability_tracking table
        cursor.execute('''
        CREATE TABLE sustainability_tracking (
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

        # Create teacher_availability table
        cursor.execute('''
        CREATE TABLE teacher_availability (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        teacher_id INTEGER,
                        day_of_week TEXT,
                        start_time TEXT,
                        end_time TEXT,
                        meeting_type TEXT,
                        location TEXT,
                        active BOOLEAN DEFAULT 1,
                        FOREIGN KEY (teacher_id) REFERENCES users (id)
                    )
        ''')

        conn.commit()
        conn.close()
        print("ai tables initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing ai tables: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# ALUMNI TABLES (8 tables)
# ============================================================================

def init_alumni_tables():
    """Initialize alumni system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing alumni tables...")

        # Create alumni table
        cursor.execute('''
        CREATE TABLE alumni (
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
        CREATE TABLE alumni_badges (
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
        CREATE TABLE alumni_directory_settings (
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
        CREATE TABLE alumni_forum (
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
        CREATE TABLE alumni_stories (
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
        CREATE TABLE ambassador_program (
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
        CREATE TABLE chapter_memberships (
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
        CREATE TABLE regional_chapters (
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
        print("alumni tables initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing alumni tables: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# ANALYTICS TABLES (7 tables)
# ============================================================================

def init_analytics_tables():
    """Initialize analytics system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing analytics tables...")

        # Create analytics_cache table
        cursor.execute('''
        CREATE TABLE analytics_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT UNIQUE NOT NULL,
                    cache_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL
                )
        ''')

        # Create analytics_data table
        cursor.execute('''
        CREATE TABLE analytics_data (
                    analytics_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT,
                    metric_value REAL,
                    metric_date TEXT,
                    category TEXT,
                    additional_data TEXT
                )
        ''')

        # Create quality_metrics table
        cursor.execute('''
        CREATE TABLE quality_metrics (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            metric_name TEXT,
                            metric_category TEXT,
                            target_value REAL,
                            actual_value REAL,
                            measurement_period TEXT,
                            measured_date TEXT,
                            status TEXT,
                            improvement_needed INTEGER DEFAULT 0,
                            created_at TEXT
                        )
        ''')

        # Create search_analytics table
        cursor.execute('''
        CREATE TABLE search_analytics (
                    search_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    search_query TEXT NOT NULL,
                    search_type TEXT NOT NULL,  -- faq, resource, ticket, global
                    results_count INTEGER NOT NULL,
                    clicked_result_id TEXT,
                    search_datetime TEXT NOT NULL,
                    session_id TEXT
                , search_criteria TEXT, execution_time REAL)
        ''')

        # Create system_metrics table
        cursor.execute('''
        CREATE TABLE system_metrics (
                    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    category TEXT NOT NULL,
                    recorded_datetime TEXT NOT NULL,
                    metadata TEXT  -- JSON data
                )
        ''')

        # Create teacher_reports table
        cursor.execute('''
        CREATE TABLE teacher_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    teacher_id INTEGER,
                    module_code TEXT,
                    report_type TEXT,
                    report_content TEXT,
                    created_date TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (module_code) REFERENCES modules (module_code)
                )
        ''')

        # Create usage_analytics table
        cursor.execute('''
        CREATE TABLE usage_analytics (
                    analytics_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    category TEXT,
                    additional_data TEXT
                )
        ''')

        conn.commit()
        conn.close()
        print("analytics tables initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing analytics tables: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# AUDIT TABLES (5 tables)
# ============================================================================

def init_audit_tables():
    """Initialize audit system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing audit tables...")

        # Create audit_log table
        cursor.execute('''
        CREATE TABLE audit_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    action TEXT NOT NULL,
                    table_name TEXT,
                    record_id TEXT,
                    old_values TEXT, -- JSON
                    new_values TEXT, -- JSON
                    ip_address TEXT,
                    user_agent TEXT,
                    session_id TEXT,
                    timestamp TEXT NOT NULL
                , accommodation_id INTEGER, details TEXT)
        ''')

        # Create audit_trail table
        cursor.execute('''
        CREATE TABLE audit_trail (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT,
                    old_values TEXT,  -- JSON
                    new_values TEXT,  -- JSON
                    ip_address TEXT,
                    user_agent TEXT,
                    success BOOLEAN NOT NULL,
                    error_message TEXT,
                    duration REAL,
                    timestamp TEXT NOT NULL
                )
        ''')

        # Create backup_history table
        cursor.execute('''
        CREATE TABLE backup_history (
                            id TEXT PRIMARY KEY,
                            backup_type TEXT NOT NULL,
                            file_path TEXT NOT NULL,
                            file_size INTEGER,
                            backup_time TEXT NOT NULL,
                            status TEXT NOT NULL,
                            notes TEXT
                        )
        ''')

        # Create backups table
        cursor.execute('''
        CREATE TABLE backups (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        backup_name TEXT,
                        backup_path TEXT,
                        backup_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        backup_size INTEGER,
                        description TEXT
                    )
        ''')

        # Create privacy_audit_log table
        cursor.execute('''
        CREATE TABLE privacy_audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        action TEXT NOT NULL,
                        student_id TEXT,
                        user_id INTEGER,
                        data_accessed TEXT,
                        timestamp TEXT NOT NULL,
                        ip_address TEXT
                    )
        ''')

        conn.commit()
        conn.close()
        print("audit tables initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing audit tables: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# AUTH TABLES (12 tables)
# ============================================================================

def init_auth_tables():
    """Initialize auth system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing auth tables...")

        # Create login_attempts table
        cursor.execute('''
        CREATE TABLE login_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    attempt_time TEXT NOT NULL,
                    ip_address TEXT,
                    success INTEGER NOT NULL
                )
        ''')

        # Create permissions table
        cursor.execute('''
        CREATE TABLE permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    permission_name TEXT UNIQUE NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
        ''')

        # Create photo_permissions table
        cursor.execute('''
        CREATE TABLE photo_permissions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        permission_type TEXT,
                        consent_given BOOLEAN DEFAULT 0,
                        conditions TEXT,
                        valid_from TEXT,
                        valid_until TEXT,
                        parent_signature TEXT,
                        date_signed TEXT,
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create role_permissions table
        cursor.execute('''
        CREATE TABLE role_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role_id INTEGER NOT NULL,
                    permission_id INTEGER NOT NULL,
                    FOREIGN KEY (role_id) REFERENCES roles (id),
                    FOREIGN KEY (permission_id) REFERENCES permissions (id),
                    UNIQUE(role_id, permission_id)
                )
        ''')

        # Create roles table
        cursor.execute('''
        CREATE TABLE roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role_name TEXT UNIQUE NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
        ''')

        # Create security_settings table
        cursor.execute('''
        CREATE TABLE security_settings (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            setting_name TEXT UNIQUE,
                            setting_value TEXT,
                            updated_at TEXT,
                            updated_by TEXT
                        )
        ''')

        # Create two_fa_recovery_codes table
        cursor.execute('''
        CREATE TABLE two_fa_recovery_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    code_hash TEXT NOT NULL,
                    is_used INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    used_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
        ''')

        # Create user_accounts table
        cursor.execute('''
        CREATE TABLE user_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    last_login TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    password_reset_required INTEGER DEFAULT 0,
                    two_fa_enabled INTEGER DEFAULT 0,
                    two_fa_secret TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
        ''')

        # Create user_achievements table
        cursor.execute('''
        CREATE TABLE user_achievements (
                    achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    achievement_type TEXT NOT NULL,
                    achievement_name TEXT NOT NULL,
                    description TEXT,
                    earned_date TEXT NOT NULL,
                    points INTEGER DEFAULT 0
                )
        ''')

        # Create user_permissions table
        cursor.execute('''
        CREATE TABLE user_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    permission_id INTEGER NOT NULL,
                    granted INTEGER NOT NULL,
                    UNIQUE(user_id, permission_id),
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY(permission_id) REFERENCES permissions(id) ON DELETE CASCADE
                )
        ''')

        # Create user_preferences table
        cursor.execute('''
        CREATE TABLE user_preferences (
                    user_id TEXT PRIMARY KEY,
                    email_notifications BOOLEAN DEFAULT 1,
                    in_app_notifications BOOLEAN DEFAULT 1,
                    push_notifications BOOLEAN DEFAULT 1,
                    digest_frequency TEXT DEFAULT 'daily',  -- immediate, daily, weekly
                    theme TEXT DEFAULT 'light',
                    language TEXT DEFAULT 'en',
                    timezone TEXT DEFAULT 'UTC',
                    preferences_json TEXT  -- Additional JSON preferences
                )
        ''')

        # Create user_timezone_preferences table
        cursor.execute('''
        CREATE TABLE user_timezone_preferences (
                            user_id TEXT PRIMARY KEY,
                            timezone_name TEXT NOT NULL,
                            auto_dst BOOLEAN DEFAULT TRUE,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            FOREIGN KEY (user_id) REFERENCES users (id)
                        )
        ''')

        conn.commit()
        conn.close()
        print("auth tables initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing auth tables: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# CAREER TABLES (7 tables)
# ============================================================================

def init_career_tables():
    """Initialize career system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing career tables...")

        # Create career_counseling table
        cursor.execute('''
        CREATE TABLE career_counseling (
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
        CREATE TABLE internship_applications (
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
        CREATE TABLE internship_placements (
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
        CREATE TABLE internships (
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
        CREATE TABLE mentorship_relationships (
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
        CREATE TABLE mentorship_sessions (
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
        CREATE TABLE mentorships (
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
        print("career tables initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing career tables: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# COMMERCE TABLES (12 tables)
# ============================================================================

def init_commerce_tables():
    """Initialize commerce system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing commerce tables...")

        # Create inventory table
        cursor.execute('''
        CREATE TABLE inventory (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        item_name TEXT NOT NULL,
                        quantity INTEGER NOT NULL,
                        unit TEXT NOT NULL,
                        minimum_threshold INTEGER DEFAULT 10,
                        supplier TEXT,
                        cost_per_unit REAL,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
        ''')

        # Create meal_accounts table
        cursor.execute('''
        CREATE TABLE meal_accounts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT UNIQUE,
                        balance DECIMAL(10,2) DEFAULT 0.00,
                        low_balance_threshold DECIMAL(10,2) DEFAULT 10.00,
                        auto_topup_enabled BOOLEAN DEFAULT 0,
                        auto_topup_amount DECIMAL(10,2) DEFAULT 20.00,
                        last_updated TEXT,
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create menu_items table
        cursor.execute('''
        CREATE TABLE menu_items (
                        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT,
                        price REAL NOT NULL,
                        category TEXT,
                        allergens TEXT,
                        vegetarian BOOLEAN DEFAULT 0,
                        vegan BOOLEAN DEFAULT 0,
                        available BOOLEAN DEFAULT 1
                    )
        ''')

        # Create restaurant_customers table
        cursor.execute('''
        CREATE TABLE restaurant_customers (
                        customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        email TEXT,
                        phone TEXT,
                        loyalty_tier TEXT DEFAULT 'Bronze',
                        loyalty_points INTEGER DEFAULT 0,
                        total_spent REAL DEFAULT 0
                    )
        ''')

        # Create restaurant_inventory table
        cursor.execute('''
        CREATE TABLE restaurant_inventory (
                        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        quantity REAL DEFAULT 0,
                        unit TEXT,
                        cost_per_unit REAL,
                        reorder_level REAL DEFAULT 0
                    )
        ''')

        # Create restaurant_orders table
        cursor.execute('''
        CREATE TABLE restaurant_orders (
                        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        customer_id INTEGER,
                        order_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                        total_price REAL,
                        tax_amount REAL,
                        status TEXT DEFAULT 'Pending',
                        payment_method TEXT
                    )
        ''')

        # Create restaurant_staff table
        cursor.execute('''
        CREATE TABLE restaurant_staff (
                        staff_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        role TEXT NOT NULL,
                        hourly_rate REAL,
                        status TEXT DEFAULT 'Active',
                        performance_score REAL
                    )
        ''')

        # Create restaurant_tables table
        cursor.execute('''
        CREATE TABLE restaurant_tables (
                        table_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        capacity INTEGER NOT NULL,
                        status TEXT DEFAULT 'Available',
                        location TEXT,
                        table_type TEXT DEFAULT 'Standard'
                    )
        ''')

        # Create shop_cart table
        cursor.execute('''
        CREATE TABLE shop_cart (
                    cart_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    product_id TEXT NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    added_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (product_id) REFERENCES shop_products (product_id),
                    UNIQUE(user_id, product_id)
                )
        ''')

        # Create shop_discounts table
        cursor.execute('''
        CREATE TABLE shop_discounts (
                    discount_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    discount_type TEXT NOT NULL,
                    discount_value REAL NOT NULL,
                    start_date TEXT,
                    end_date TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    applicable_products TEXT,
                    min_purchase_amount REAL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
        ''')

        # Create shop_inventory table
        cursor.execute('''
        CREATE TABLE shop_inventory (
                    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 0,
                    last_restock_date TEXT,
                    restock_threshold INTEGER DEFAULT 5,
                    FOREIGN KEY (product_id) REFERENCES shop_products (product_id)
                )
        ''')

        # Create shop_products table
        cursor.execute('''
        CREATE TABLE shop_products (
                    product_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    price REAL NOT NULL,
                    category TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    tax_rate REAL DEFAULT 0.2,
                    is_active BOOLEAN DEFAULT 1
                )
        ''')

        conn.commit()
        conn.close()
        print("commerce tables initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing commerce tables: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# COMMUNICATION TABLES (15 tables)
# ============================================================================

def init_communication_tables():
    """Initialize communication system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing communication tables...")

        # Create announcement_reads table
        cursor.execute('''
        CREATE TABLE announcement_reads (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        announcement_id INTEGER,
                        parent_id TEXT,
                        read_date TEXT,
                        acknowledged BOOLEAN DEFAULT 0,
                        FOREIGN KEY (announcement_id) REFERENCES school_announcements (id),
                        FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
                    )
        ''')

        # Create announcement_viewers table
        cursor.execute('''
        CREATE TABLE announcement_viewers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        announcement_id INTEGER NOT NULL,
                        viewer_id INTEGER NOT NULL,
                        viewed_at TEXT NOT NULL,
                        FOREIGN KEY (announcement_id) REFERENCES announcements (id),
                        FOREIGN KEY (viewer_id) REFERENCES users (id)
                    )
        ''')

        # Create chat_messages table
        cursor.execute('''
        CREATE TABLE chat_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        room_id INTEGER NOT NULL,
                        sender_id INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        sent_at TEXT NOT NULL,
                        FOREIGN KEY (room_id) REFERENCES chat_rooms (id),
                        FOREIGN KEY (sender_id) REFERENCES users (id)
                    )
        ''')

        # Create communication_log table
        cursor.execute('''
        CREATE TABLE communication_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        action_type TEXT NOT NULL,
                        action_details TEXT,
                        performed_at TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    )
        ''')

        # Create emails table
        cursor.execute('''
        CREATE TABLE emails (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            recipient TEXT NOT NULL,
                            subject TEXT,
                            body TEXT,
                            cc TEXT,
                            bcc TEXT,
                            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            status TEXT DEFAULT 'sent',
                            attachments TEXT
                        )
        ''')

        # Create group_message_recipients table
        cursor.execute('''
        CREATE TABLE group_message_recipients (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        message_id INTEGER NOT NULL,
                        recipient_id INTEGER NOT NULL,
                        is_read INTEGER DEFAULT 0,
                        is_archived INTEGER DEFAULT 0,
                        is_deleted INTEGER DEFAULT 0,
                        read_at TEXT,
                        FOREIGN KEY (message_id) REFERENCES group_messages (id),
                        FOREIGN KEY (recipient_id) REFERENCES users (id)
                    )
        ''')

        # Create group_messages table
        cursor.execute('''
        CREATE TABLE group_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sender_id INTEGER NOT NULL,
                        group_type TEXT NOT NULL,
                        group_id TEXT NOT NULL,
                        subject TEXT NOT NULL,
                        content TEXT NOT NULL,
                        attachment_path TEXT,
                        sent_at TEXT NOT NULL,
                        FOREIGN KEY (sender_id) REFERENCES users (id)
                    )
        ''')

        # Create notification_preferences table
        cursor.execute('''
        CREATE TABLE notification_preferences (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id TEXT NOT NULL,
                            notification_type TEXT NOT NULL,
                            enabled BOOLEAN DEFAULT TRUE,
                            advance_time INTEGER DEFAULT 60,
                            method TEXT DEFAULT 'email',
                            date_added TEXT NOT NULL,
                            UNIQUE(user_id, notification_type)
                        )
        ''')

        # Create notification_queue table
        cursor.execute('''
        CREATE TABLE notification_queue (
                            id TEXT PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            event_id TEXT,
                            notification_type TEXT NOT NULL,
                            scheduled_time TEXT NOT NULL,
                            status TEXT DEFAULT 'pending',
                            message TEXT,
                            date_added TEXT NOT NULL,
                            sent_at TEXT,
                            FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
                        )
        ''')

        # Create notification_schedules table
        cursor.execute('''
        CREATE TABLE notification_schedules (
                    schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_id INTEGER NOT NULL,
                    trigger_condition TEXT NOT NULL, -- JSON with conditions
                    days_before_due INTEGER,
                    max_reminders INTEGER DEFAULT 3,
                    reminder_interval_days INTEGER DEFAULT 7,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (template_id) REFERENCES notification_templates (template_id)
                )
        ''')

        # Create notification_templates table
        cursor.execute('''
        CREATE TABLE notification_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_name TEXT NOT NULL,
                    template_type TEXT NOT NULL, -- 'payment_reminder', 'overdue_notice', 'payment_confirmation', etc.
                    subject_template TEXT NOT NULL,
                    body_template TEXT NOT NULL,
                    send_method TEXT DEFAULT 'email', -- 'email', 'sms', 'push'
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                )
        ''')

        # Create notifications table
        cursor.execute('''
        CREATE TABLE notifications (
                    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    notification_type TEXT NOT NULL,
                    related_ticket_id INTEGER,
                    is_read BOOLEAN DEFAULT 0,
                    created_datetime TEXT NOT NULL,
                    read_datetime TEXT,
                    expires_at TEXT,
                    data TEXT, assignment_id INTEGER, recipient_type TEXT, recipient_id TEXT, sent BOOLEAN DEFAULT 0, created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- JSON data
                    FOREIGN KEY (related_ticket_id) REFERENCES support_tickets (ticket_id)
                )
        ''')

        # Create school_announcements table
        cursor.execute('''
        CREATE TABLE school_announcements (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT,
                        content TEXT,
                        priority TEXT DEFAULT 'normal',
                        category TEXT,
                        audience TEXT,
                        created_by INTEGER,
                        created_date TEXT,
                        expiry_date TEXT,
                        requires_acknowledgment BOOLEAN DEFAULT 0,
                        FOREIGN KEY (created_by) REFERENCES users (id)
                    )
        ''')

        # Create sent_notifications table
        cursor.execute('''
        CREATE TABLE sent_notifications (
                    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    template_id INTEGER NOT NULL,
                    recipient_email TEXT,
                    recipient_phone TEXT,
                    subject TEXT,
                    message_body TEXT,
                    send_method TEXT,
                    status TEXT DEFAULT 'pending', -- pending, sent, failed, bounced
                    sent_at TEXT,
                    error_message TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (template_id) REFERENCES notification_templates (template_id)
                )
        ''')

        # Create stored_emails table
        cursor.execute('''
        CREATE TABLE stored_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipient_email TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    sender_email TEXT NOT NULL,
                    sender_name TEXT NOT NULL,
                    cc_recipients TEXT,
                    bcc_recipients TEXT,
                    attachment_paths TEXT,
                    created_date TEXT NOT NULL,
                    template_name TEXT,
                    template_vars TEXT,
                    related_to TEXT,
                    student_id TEXT
                )
        ''')

        conn.commit()
        conn.close()
        print("communication tables initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing communication tables: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# COURSES TABLES (11 tables)
# ============================================================================

def init_courses_tables():
    """Initialize courses system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing courses tables...")

        # Create course_analytics table
        cursor.execute('''
        CREATE TABLE course_analytics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id INTEGER NOT NULL,
                    semester TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    total_enrolled INTEGER DEFAULT 0,
                    total_completed INTEGER DEFAULT 0,
                    average_grade REAL DEFAULT 0.0,
                    completion_rate REAL DEFAULT 0.0,
                    calculated_at TEXT NOT NULL,
                    FOREIGN KEY (course_id) REFERENCES courses (id)
                )
        ''')

        # Create course_categories table
        cursor.execute('''
        CREATE TABLE course_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    color_code TEXT,
                    created_at TEXT NOT NULL
                )
        ''')

        # Create course_history table
        cursor.execute('''
        CREATE TABLE course_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id INTEGER NOT NULL,
                    field_name TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    changed_by TEXT,
                    changed_at TEXT NOT NULL,
                    FOREIGN KEY (course_id) REFERENCES courses (id)
                )
        ''')

        # Create course_requirements table
        cursor.execute('''
        CREATE TABLE course_requirements (
                        requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        course_code TEXT,
                        program TEXT,
                        type_id INTEGER,
                        is_mandatory BOOLEAN DEFAULT 1,
                        deadline_days INTEGER,
                        FOREIGN KEY (type_id) REFERENCES document_types (type_id)
                    )
        ''')

        # Create course_schedule table
        cursor.execute('''
        CREATE TABLE course_schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id INTEGER NOT NULL,
                    semester TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    start_time TEXT,
                    end_time TEXT,
                    days_of_week TEXT,
                    classroom TEXT,
                    instructor_id INTEGER,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (course_id) REFERENCES courses (id),
                    UNIQUE(course_id, semester, year)
                )
        ''')

        # Create course_waitlist table
        cursor.execute('''
        CREATE TABLE course_waitlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    position INTEGER NOT NULL,
                    added_at TEXT NOT NULL,
                    status TEXT DEFAULT 'Waiting',
                    FOREIGN KEY (course_id) REFERENCES courses (id),
                    UNIQUE(course_id, student_id)
                )
        ''')

        # Create courses table
        cursor.execute('''
        CREATE TABLE courses (
                            id TEXT PRIMARY KEY,
                            code TEXT UNIQUE NOT NULL,
                            name TEXT NOT NULL,
                            credits INTEGER DEFAULT 3,
                            department TEXT,
                            instructor_id TEXT,
                            academic_year_id TEXT,
                            semester_id TEXT,
                            status TEXT DEFAULT 'active',
                            date_added TEXT NOT NULL, course_code TEXT, course_name TEXT, level TEXT, credit_hours INTEGER, current_enrollment INTEGER DEFAULT 0, max_enrollment INTEGER DEFAULT 30,
                            FOREIGN KEY (academic_year_id) REFERENCES academic_years (id),
                            FOREIGN KEY (semester_id) REFERENCES semesters (id)
                        )
        ''')

        # Create departments table
        cursor.execute('''
        CREATE TABLE departments (
                    dept_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    manager_id INTEGER,
                    email TEXT,
                    sla_policy_id INTEGER,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (manager_id) REFERENCES users (id),
                    FOREIGN KEY (sla_policy_id) REFERENCES sla_policies (sla_id)
                )
        ''')

        # Create instructors table
        cursor.execute('''
        CREATE TABLE instructors (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        first_name TEXT NOT NULL,
                        last_name TEXT NOT NULL,
                        email TEXT UNIQUE NOT NULL,
                        department TEXT DEFAULT '',
                        specialization TEXT DEFAULT '',
                        max_courses_per_semester INTEGER DEFAULT 4,
                        max_hours_per_week INTEGER DEFAULT 40,
                        preferred_days TEXT,
                        preferred_times TEXT,
                        status TEXT DEFAULT 'Active',
                        is_active BOOLEAN DEFAULT 1,
                        created_at TEXT DEFAULT (datetime('now')),
                        updated_at TEXT DEFAULT (datetime('now'))
                    )
        ''')

        # Create module_schedule table
        cursor.execute('''
        CREATE TABLE module_schedule (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        module_code TEXT,
                        day_of_week TEXT,
                        start_time TEXT,
                        end_time TEXT,
                        room_id INTEGER,
                        instructor_id INTEGER,
                        session_type TEXT,
                        created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (module_code) REFERENCES modules (module_code),
                        FOREIGN KEY (room_id) REFERENCES rooms (id),
                        FOREIGN KEY (instructor_id) REFERENCES instructors (id)
                    )
        ''')

        # Create semesters table
        cursor.execute('''
        CREATE TABLE semesters (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            academic_year_id TEXT NOT NULL,
                            name TEXT NOT NULL,
                            start_date TEXT NOT NULL,
                            end_date TEXT NOT NULL,
                            registration_start TEXT,
                            registration_end TEXT,
                            final_exams_start TEXT,
                            final_exams_end TEXT,
                            date_added TEXT NOT NULL,
                            FOREIGN KEY (academic_year_id) REFERENCES academic_years (id) ON DELETE CASCADE,
                            UNIQUE(academic_year_id, name),
                            CONSTRAINT valid_semester_dates CHECK (start_date < end_date)
                        )
        ''')

        conn.commit()
        conn.close()
        print("courses tables initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing courses tables: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# DOCUMENTS TABLES (7 tables)
# ============================================================================

def init_documents_tables():
    """Initialize documents system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing documents tables...")

        # Create document_repository table
        cursor.execute('''
        CREATE TABLE document_repository (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            title TEXT NOT NULL CHECK(length(title) > 0),
                            content TEXT NOT NULL CHECK(length(content) > 0),
                            content_hash TEXT NOT NULL,
                            author_id INTEGER NOT NULL,
                            module_code TEXT,
                            submission_date TEXT NOT NULL,
                            file_type TEXT,
                            word_count INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (author_id) REFERENCES users (id) ON DELETE CASCADE,
                            FOREIGN KEY (module_code) REFERENCES modules (module_code) ON DELETE SET NULL
                        )
        ''')

        # Create document_tags table
        cursor.execute('''
        CREATE TABLE document_tags (
                        tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tag_name TEXT UNIQUE,
                        tag_color TEXT,
                        description TEXT
                    )
        ''')

        # Create document_workflow table
        cursor.execute('''
        CREATE TABLE document_workflow (
                        workflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        document_id INTEGER,
                        step_name TEXT,
                        step_order INTEGER,
                        assigned_to TEXT,
                        status TEXT,
                        comments TEXT,
                        completed_date TEXT,
                        completed_by TEXT,
                        FOREIGN KEY (document_id) REFERENCES student_documents (document_id)
                    )
        ''')

        # Create response_templates table
        cursor.execute('''
        CREATE TABLE response_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    subject TEXT,
                    content TEXT NOT NULL,
                    category TEXT,
                    created_by TEXT NOT NULL,
                    created_datetime TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    usage_count INTEGER DEFAULT 0,
                    variables TEXT  -- JSON array of variable names
                )
        ''')

        # Create schedule_templates table
        cursor.execute('''
        CREATE TABLE schedule_templates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        template_name TEXT UNIQUE,
                        description TEXT,
                        template_data TEXT,
                        created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT
                    )
        ''')

        # Create workflow_instances table
        cursor.execute('''
        CREATE TABLE workflow_instances (
                    instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id INTEGER NOT NULL,
                    entity_type TEXT NOT NULL, -- 'refund', 'payment_plan', 'scholarship', etc.
                    entity_id INTEGER NOT NULL,
                    current_step INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'pending', -- pending, in_progress, completed, cancelled
                    assigned_to TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    metadata TEXT, -- JSON with instance-specific data
                    FOREIGN KEY (workflow_id) REFERENCES workflows (workflow_id)
                )
        ''')

        # Create workflows table
        cursor.execute('''
        CREATE TABLE workflows (
                    workflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_name TEXT NOT NULL,
                    workflow_type TEXT NOT NULL, -- 'approval', 'notification', 'automation'
                    trigger_conditions TEXT, -- JSON
                    workflow_steps TEXT, -- JSON with step definitions
                    is_active BOOLEAN DEFAULT 1,
                    created_by TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
        ''')

        conn.commit()
        conn.close()
        print("documents tables initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing documents tables: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# FINANCE TABLES (18 tables)
# ============================================================================

def init_finance_tables():
    """Initialize finance system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing finance tables...")

        # Create budget_categories table
        cursor.execute('''
        CREATE TABLE budget_categories (
                    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_name TEXT NOT NULL,
                    category_type TEXT NOT NULL, -- 'revenue', 'expense'
                    parent_category_id INTEGER,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (parent_category_id) REFERENCES budget_categories (category_id)
                )
        ''')

        # Create budget_line_items table
        cursor.execute('''
        CREATE TABLE budget_line_items (
                    line_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    budget_id INTEGER NOT NULL,
                    category_id INTEGER NOT NULL,
                    budgeted_amount DECIMAL(12,2) NOT NULL,
                    actual_amount DECIMAL(12,2) DEFAULT 0,
                    variance DECIMAL(12,2) DEFAULT 0,
                    notes TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (budget_id) REFERENCES budget_plans (budget_id),
                    FOREIGN KEY (category_id) REFERENCES budget_categories (category_id)
                )
        ''')

        # Create budget_plans table
        cursor.execute('''
        CREATE TABLE budget_plans (
                    budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_name TEXT NOT NULL,
                    academic_year TEXT NOT NULL,
                    currency TEXT DEFAULT 'GBP',
                    status TEXT DEFAULT 'draft', -- draft, approved, active, closed
                    total_revenue_budget DECIMAL(12,2) DEFAULT 0,
                    total_expense_budget DECIMAL(12,2) DEFAULT 0,
                    created_by TEXT,
                    approved_by TEXT,
                    notes TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
        ''')

        # Create club_budgets table
        cursor.execute('''
        CREATE TABLE club_budgets (
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

        # Create donations table
        cursor.execute('''
        CREATE TABLE donations (
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

        # Create financial_aid_types table
        cursor.execute('''
        CREATE TABLE financial_aid_types (
                    aid_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    aid_name TEXT NOT NULL,
                    aid_category TEXT, -- 'grant', 'loan', 'work_study', 'emergency'
                    description TEXT,
                    max_amount DECIMAL(10,2),
                    eligibility_criteria TEXT,
                    application_deadline TEXT,
                    is_renewable BOOLEAN DEFAULT 0,
                    requires_repayment BOOLEAN DEFAULT 0,
                    interest_rate DECIMAL(5,2),
                    grace_period_months INTEGER,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                )
        ''')

        # Create financial_kpis table
        cursor.execute('''
        CREATE TABLE financial_kpis (
                    kpi_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kpi_name TEXT NOT NULL,
                    kpi_value DECIMAL(15,2) NOT NULL,
                    kpi_type TEXT NOT NULL, -- 'amount', 'percentage', 'count', 'ratio'
                    calculation_period TEXT NOT NULL, -- 'daily', 'weekly', 'monthly', 'yearly'
                    calculation_date TEXT NOT NULL,
                    academic_year TEXT,
                    created_at TEXT
                )
        ''')

        # Create fundraising_donations table
        cursor.execute('''
        CREATE TABLE fundraising_donations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        campaign_id INTEGER,
                        parent_id TEXT,
                        student_id TEXT,
                        amount DECIMAL(10,2),
                        donation_date TEXT,
                        anonymous BOOLEAN DEFAULT 0,
                        FOREIGN KEY (campaign_id) REFERENCES fundraising_campaigns (id),
                        FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create gateway_transactions table
        cursor.execute('''
        CREATE TABLE gateway_transactions (
                    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payment_id INTEGER,
                    gateway_id INTEGER NOT NULL,
                    gateway_transaction_id TEXT NOT NULL,
                    amount DECIMAL(10,2) NOT NULL,
                    currency TEXT NOT NULL,
                    status TEXT NOT NULL,
                    gateway_fee DECIMAL(10,2),
                    raw_response TEXT, -- JSON response from gateway
                    webhook_verified BOOLEAN DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (payment_id) REFERENCES payments (payment_id),
                    FOREIGN KEY (gateway_id) REFERENCES payment_gateways (gateway_id)
                )
        ''')

        # Create housing_payments table
        cursor.execute('''
        CREATE TABLE housing_payments (
                    payment_id TEXT PRIMARY KEY,
                    assignment_id TEXT NOT NULL,
                    student_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    payment_date TEXT NOT NULL,
                    payment_method TEXT NOT NULL,
                    transaction_reference TEXT,
                    payment_period_start TEXT NOT NULL,
                    payment_period_end TEXT NOT NULL,
                    status TEXT NOT NULL,
                    received_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (assignment_id) REFERENCES housing_assignments (assignment_id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
        ''')

        # Create late_fees table
        cursor.execute('''
        CREATE TABLE late_fees (
                    late_fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_fee_id INTEGER NOT NULL,
                    late_fee_amount DECIMAL(10,2) NOT NULL,
                    calculation_method TEXT, -- 'fixed', 'percentage', 'daily'
                    days_overdue INTEGER NOT NULL,
                    applied_date TEXT NOT NULL,
                    waived BOOLEAN DEFAULT 0,
                    waived_by TEXT,
                    waived_date TEXT,
                    waiver_reason TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_fee_id) REFERENCES student_fees (student_fee_id)
                )
        ''')

        # Create meal_transactions table
        cursor.execute('''
        CREATE TABLE meal_transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        transaction_type TEXT,
                        amount DECIMAL(10,2),
                        description TEXT,
                        transaction_date TEXT,
                        balance_after DECIMAL(10,2),
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create payment_gateways table
        cursor.execute('''
        CREATE TABLE payment_gateways (
                    gateway_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    gateway_name TEXT NOT NULL,
                    gateway_type TEXT NOT NULL, -- 'stripe', 'paypal', 'bank_transfer', etc.
                    configuration TEXT, -- JSON with gateway config
                    is_active BOOLEAN DEFAULT 1,
                    transaction_fee_percentage DECIMAL(5,4),
                    transaction_fee_fixed DECIMAL(10,2),
                    supported_currencies TEXT, -- JSON array
                    webhook_url TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
        ''')

        # Create payment_plan_installments table
        cursor.execute('''
        CREATE TABLE payment_plan_installments (
                    installment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payment_plan_id INTEGER NOT NULL,
                    installment_number INTEGER NOT NULL,
                    amount DECIMAL(10,2) NOT NULL,
                    due_date TEXT NOT NULL,
                    status TEXT DEFAULT 'pending', -- pending, paid, overdue, waived
                    payment_id INTEGER,
                    late_fee_amount DECIMAL(10,2) DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (payment_plan_id) REFERENCES student_payment_plans (payment_plan_id),
                    FOREIGN KEY (payment_id) REFERENCES payments (payment_id)
                )
        ''')

        # Create payment_risk_scores table
        cursor.execute('''
        CREATE TABLE payment_risk_scores (
                    score_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    risk_score DECIMAL(5,2) NOT NULL, -- 0-100
                    risk_level TEXT NOT NULL, -- 'low', 'medium', 'high'
                    factors TEXT, -- JSON with risk factors
                    last_calculated TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
        ''')

        # Create refunds table
        cursor.execute('''
        CREATE TABLE refunds (
                    refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    original_payment_id INTEGER,
                    refund_amount DECIMAL(10,2) NOT NULL,
                    currency TEXT DEFAULT 'GBP',
                    refund_reason TEXT NOT NULL,
                    refund_type TEXT NOT NULL, -- 'full', 'partial', 'withdrawal'
                    refund_method TEXT, -- 'bank_transfer', 'original_payment_method', 'check'
                    status TEXT DEFAULT 'pending', -- pending, approved, processed, rejected
                    requested_by TEXT,
                    approved_by TEXT,
                    processed_by TEXT,
                    request_date TEXT,
                    approval_date TEXT,
                    processed_date TEXT,
                    notes TEXT,
                    created_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (original_payment_id) REFERENCES payments (payment_id)
                )
        ''')

        # Create shop_transaction_items table
        cursor.execute('''
        CREATE TABLE shop_transaction_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    price_per_item REAL NOT NULL,
                    subtotal REAL NOT NULL,
                    FOREIGN KEY (transaction_id) REFERENCES shop_transactions (transaction_id),
                    FOREIGN KEY (product_id) REFERENCES shop_products (product_id)
                )
        ''')

        # Create shop_transactions table
        cursor.execute('''
        CREATE TABLE shop_transactions (
                    transaction_id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    student_id TEXT,
                    total_amount REAL NOT NULL,
                    transaction_date TEXT NOT NULL,
                    payment_method TEXT,
                    status TEXT NOT NULL,
                    notes TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
        ''')

        conn.commit()
        conn.close()
        print("finance tables initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing finance tables: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# HEALTH TABLES (7 tables)
# ============================================================================

def init_health_tables():
    """Initialize health system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing health tables...")

        # Create disease_surveillance table
        cursor.execute('''
        CREATE TABLE disease_surveillance (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            disease_name TEXT,
                            case_date TEXT,
                            student_id TEXT,
                            symptoms TEXT,
                            severity TEXT,
                            status TEXT DEFAULT 'under_investigation',
                            contact_tracing_needed INTEGER DEFAULT 0,
                            contact_tracing_completed INTEGER DEFAULT 0,
                            contacts_identified INTEGER DEFAULT 0,
                            reported_to_health_dept INTEGER DEFAULT 0,
                            isolation_required INTEGER DEFAULT 0,
                            created_at TEXT,
                            FOREIGN KEY (student_id) REFERENCES students (student_id)
                        )
        ''')

        # Create health_appointments table
        cursor.execute('''
        CREATE TABLE health_appointments (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT,
                            appointment_type TEXT,
                            appointment_date TEXT,
                            appointment_time TEXT,
                            provider TEXT,
                            reason TEXT,
                            status TEXT DEFAULT 'scheduled',
                            notes TEXT,
                            scheduled_at TEXT,
                            FOREIGN KEY (student_id) REFERENCES students (student_id)
                        )
        ''')

        # Create health_campaigns table
        cursor.execute('''
        CREATE TABLE health_campaigns (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            campaign_name TEXT,
                            campaign_type TEXT,
                            start_date TEXT,
                            end_date TEXT,
                            target_population TEXT,
                            description TEXT,
                            goals TEXT,
                            status TEXT DEFAULT 'planned',
                            budget REAL,
                            created_by TEXT,
                            created_at TEXT
                        )
        ''')

        # Create health_metrics table
        cursor.execute('''
        CREATE TABLE health_metrics (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            metric_name TEXT,
                            metric_value REAL,
                            measurement_date TEXT,
                            category TEXT,
                            subcategory TEXT,
                            metadata TEXT,
                            calculated_at TEXT
                        )
        ''')

        # Create medical_conditions table
        cursor.execute('''
        CREATE TABLE medical_conditions (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT,
                            condition_name TEXT,
                            icd_code TEXT,
                            severity TEXT,
                            diagnosed_date TEXT,
                            status TEXT DEFAULT 'active',
                            provider TEXT,
                            notes TEXT,
                            created_at TEXT,
                            FOREIGN KEY (student_id) REFERENCES students (student_id)
                        )
        ''')

        # Create prescriptions table
        cursor.execute('''
        CREATE TABLE prescriptions (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT,
                            medication_name TEXT,
                            dosage TEXT,
                            frequency TEXT,
                            prescribed_date TEXT,
                            start_date TEXT,
                            end_date TEXT,
                            prescriber TEXT,
                            pharmacy TEXT,
                            status TEXT DEFAULT 'active',
                            notes TEXT,
                            created_at TEXT,
                            FOREIGN KEY (student_id) REFERENCES students (student_id)
                        )
        ''')

        # Create vital_signs table
        cursor.execute('''
        CREATE TABLE vital_signs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT,
                            measurement_date TEXT,
                            blood_pressure_systolic INTEGER,
                            blood_pressure_diastolic INTEGER,
                            heart_rate INTEGER,
                            temperature REAL,
                            weight REAL,
                            height REAL,
                            bmi REAL,
                            recorded_by TEXT,
                            notes TEXT,
                            created_at TEXT,
                            FOREIGN KEY (student_id) REFERENCES students (student_id)
                        )
        ''')

        conn.commit()
        conn.close()
        print("health tables initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing health tables: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# HOUSING TABLES (13 tables)
# ============================================================================

def init_housing_tables():
    """Initialize housing system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing housing tables...")

        # Create accommodation_documents table
        cursor.execute('''
        CREATE TABLE accommodation_documents (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            accommodation_id INTEGER NOT NULL,
                            document_name TEXT NOT NULL,
                            document_path TEXT NOT NULL,
                            uploaded_by TEXT,
                            uploaded_at TEXT,
                            FOREIGN KEY (accommodation_id) REFERENCES accommodations(id)
                        )
        ''')

        # Create accommodation_templates table
        cursor.execute('''
        CREATE TABLE accommodation_templates (
                            name TEXT PRIMARY KEY,
                            accommodation_type TEXT NOT NULL,
                            description TEXT,
                            start_offset_days INTEGER,
                            duration_days INTEGER,
                            created_by TEXT,
                            created_at TEXT,
                            updated_at TEXT
                        )
        ''')

        # Create accommodation_types table
        cursor.execute('''
        CREATE TABLE accommodation_types (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            type_name TEXT NOT NULL UNIQUE,
                            description TEXT,
                            requires_approval BOOLEAN DEFAULT 0,
                            max_duration_days INTEGER,
                            created_at TEXT
                        )
        ''')

        # Create accommodations table
        cursor.execute('''
        CREATE TABLE accommodations (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT NOT NULL,
                            accommodation_type TEXT NOT NULL,
                            description TEXT,
                            start_date TEXT,
                            end_date TEXT,
                            status TEXT DEFAULT 'active',
                            approved_by TEXT,
                            approval_date TEXT,
                            notes TEXT,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            FOREIGN KEY (student_id) REFERENCES students(student_id)
                        )
        ''')

        # Create chat_room_invitations table
        cursor.execute('''
        CREATE TABLE chat_room_invitations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    invited_by INTEGER NOT NULL,
                    invited_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    responded_at TEXT,
                    FOREIGN KEY (room_id) REFERENCES chat_rooms (id),
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (invited_by) REFERENCES users (id)
                )
        ''')

        # Create chat_room_members table
        cursor.execute('''
        CREATE TABLE chat_room_members (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        room_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        joined_at TEXT NOT NULL,
                        is_admin INTEGER DEFAULT 0,
                        FOREIGN KEY (room_id) REFERENCES chat_rooms (id),
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    )
        ''')

        # Create chat_rooms table
        cursor.execute('''
        CREATE TABLE chat_rooms (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT,
                        room_type TEXT NOT NULL,
                        created_by INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        is_active INTEGER DEFAULT 1,
                        FOREIGN KEY (created_by) REFERENCES users (id)
                    )
        ''')

        # Create housing_applications table
        cursor.execute('''
        CREATE TABLE housing_applications (
                    application_id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL,
                    application_date TEXT NOT NULL,
                    preferred_building_id TEXT,
                    preferred_room_type TEXT NOT NULL,
                    requested_move_in_date TEXT NOT NULL,
                    requested_duration_months INTEGER NOT NULL,
                    special_requirements TEXT,
                    status TEXT NOT NULL,
                    notes TEXT,
                    reviewed_by TEXT,
                    review_date TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (preferred_building_id) REFERENCES housing_buildings (building_id)
                )
        ''')

        # Create housing_buildings table
        cursor.execute('''
        CREATE TABLE housing_buildings (
                    building_id TEXT PRIMARY KEY,
                    building_name TEXT NOT NULL,
                    address TEXT NOT NULL,
                    campus_location TEXT NOT NULL,
                    total_rooms INTEGER NOT NULL,
                    available_rooms INTEGER NOT NULL,
                    has_elevator BOOLEAN DEFAULT 0,
                    has_accessible_rooms BOOLEAN DEFAULT 0,
                    has_kitchen BOOLEAN DEFAULT 0,
                    has_laundry BOOLEAN DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
        ''')

        # Create housing_inspections table
        cursor.execute('''
        CREATE TABLE housing_inspections (
                    inspection_id TEXT PRIMARY KEY,
                    room_id TEXT NOT NULL,
                    inspector TEXT NOT NULL,
                    inspection_date TEXT NOT NULL,
                    inspection_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    findings TEXT,
                    action_required TEXT,
                    follow_up_date TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (room_id) REFERENCES housing_rooms (room_id)
                )
        ''')

        # Create housing_inventory table
        cursor.execute('''
        CREATE TABLE housing_inventory (
                    item_id TEXT PRIMARY KEY,
                    room_id TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    item_type TEXT NOT NULL,
                    condition TEXT NOT NULL,
                    acquisition_date TEXT,
                    status TEXT NOT NULL,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (room_id) REFERENCES housing_rooms (room_id)
                )
        ''')

        # Create housing_maintenance_requests table
        cursor.execute('''
        CREATE TABLE housing_maintenance_requests (
                    request_id TEXT PRIMARY KEY,
                    room_id TEXT NOT NULL,
                    student_id TEXT NOT NULL,
                    request_date TEXT NOT NULL,
                    issue_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL,
                    assigned_to TEXT,
                    scheduled_date TEXT,
                    completion_date TEXT,
                    feedback TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (room_id) REFERENCES housing_rooms (room_id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
        ''')

        # Create housing_rooms table
        cursor.execute('''
        CREATE TABLE housing_rooms (
                    room_id TEXT PRIMARY KEY,
                    building_id TEXT NOT NULL,
                    room_number TEXT NOT NULL,
                    floor_number INTEGER NOT NULL,
                    room_type TEXT NOT NULL,
                    max_occupants INTEGER NOT NULL,
                    current_occupants INTEGER DEFAULT 0,
                    is_accessible BOOLEAN DEFAULT 0,
                    status TEXT NOT NULL,
                    monthly_rent REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (building_id) REFERENCES housing_buildings (building_id)
                )
        ''')

        conn.commit()
        conn.close()
        print("housing tables initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing housing tables: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# INTEGRATION TABLES (6 tables)
# ============================================================================

def init_integration_tables():
    """Initialize integration system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing integration tables...")

        # Create api_integrations table
        cursor.execute('''
        CREATE TABLE api_integrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    integration_name TEXT UNIQUE,
                    api_key TEXT,
                    endpoint_url TEXT,
                    status TEXT DEFAULT 'active',
                    last_sync TEXT,
                    sync_frequency TEXT DEFAULT 'daily',
                    config_data TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
        ''')

        # Create api_keys table
        cursor.execute('''
        CREATE TABLE api_keys (
                    key_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_name TEXT NOT NULL,
                    api_key TEXT NOT NULL,
                    key_hash TEXT NOT NULL,
                    permissions TEXT, -- JSON array
                    rate_limit INTEGER DEFAULT 1000,
                    is_active BOOLEAN DEFAULT 1,
                    expires_at TEXT,
                    last_used_at TEXT,
                    created_by TEXT,
                    created_at TEXT
                )
        ''')

        # Create api_usage_log table
        cursor.execute('''
        CREATE TABLE api_usage_log (
                    usage_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    api_key_id INTEGER,
                    endpoint TEXT NOT NULL,
                    method TEXT NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    response_status INTEGER,
                    response_time_ms INTEGER,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (api_key_id) REFERENCES api_keys (key_id)
                )
        ''')

        # Create system_integration_log table
        cursor.execute('''
        CREATE TABLE system_integration_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_system TEXT,
                        target_system TEXT,
                        operation TEXT,
                        status TEXT,
                        details TEXT,
                        timestamp TEXT
                    )
        ''')

        # Create system_integrations table
        cursor.execute('''
        CREATE TABLE system_integrations (
                    integration_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,  -- sso, lms, sis, calendar, etc.
                    config TEXT NOT NULL,  -- JSON configuration
                    is_active BOOLEAN DEFAULT 0,
                    last_sync_datetime TEXT,
                    sync_status TEXT DEFAULT 'never',
                    error_log TEXT
                )
        ''')

        # Create system_settings table
        cursor.execute('''
        CREATE TABLE system_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        description TEXT,
                        last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
        ''')

        conn.commit()
        conn.close()
        print("integration tables initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing integration tables: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# LIBRARY TABLES (14 tables)
# ============================================================================

def init_library_tables():
    """Initialize library system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing library tables...")

        # Create book_loans table
        cursor.execute('''
        CREATE TABLE book_loans (
                    loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    checkout_date TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    return_date TEXT,
                    status TEXT DEFAULT 'active',
                    fine_amount REAL DEFAULT 0.0,
                    renewal_count INTEGER DEFAULT 0,
                    reading_progress INTEGER DEFAULT 0,
                    checkout_method TEXT DEFAULT 'manual',
                    staff_id TEXT,
                    notes TEXT
                )
        ''')

        # Create book_recommendations table
        cursor.execute('''
        CREATE TABLE book_recommendations (
                    recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    book_id TEXT NOT NULL,
                    recommendation_type TEXT NOT NULL,
                    confidence_score REAL DEFAULT 0.0,
                    generated_date TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    clicked BOOLEAN DEFAULT FALSE
                )
        ''')

        # Create book_requests table
        cursor.execute('''
        CREATE TABLE book_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT,
                    isbn TEXT,
                    reason TEXT,
                    status TEXT DEFAULT 'pending',
                    priority INTEGER DEFAULT 1,
                    requested_date TEXT NOT NULL,
                    processed_date TEXT,
                    processed_by TEXT,
                    notes TEXT
                )
        ''')

        # Create book_reservations table
        cursor.execute('''
        CREATE TABLE book_reservations (
                    reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    reservation_date TEXT NOT NULL,
                    expiry_date TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    priority_order INTEGER DEFAULT 1,
                    notification_sent BOOLEAN DEFAULT FALSE
                )
        ''')

        # Create book_reviews table
        cursor.execute('''
        CREATE TABLE book_reviews (
                    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    rating INTEGER CHECK(rating >= 1 AND rating <= 5),
                    review_text TEXT,
                    review_date TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    helpful_votes INTEGER DEFAULT 0,
                    moderated_by TEXT,
                    moderation_date TEXT
                )
        ''')

        # Create books table
        cursor.execute('''
        CREATE TABLE books (
                    book_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    author TEXT NOT NULL,
                    isbn TEXT UNIQUE,
                    publisher TEXT,
                    category TEXT,
                    year_published INTEGER,
                    description TEXT,
                    location TEXT,
                    status TEXT DEFAULT 'available',
                    added_date TEXT,
                    last_updated TEXT,
                    reading_level TEXT,
                    tags TEXT,
                    cover_image_path TEXT,
                    digital_copy_path TEXT,
                    acquisition_cost REAL DEFAULT 0.0,
                    barcode TEXT UNIQUE,
                    qr_code_path TEXT,
                    total_pages INTEGER,
                    language TEXT DEFAULT 'English',
                    edition TEXT,
                    condition_notes TEXT
                )
        ''')

        # Create digital_library table
        cursor.execute('''
        CREATE TABLE digital_library (
                    digital_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    author TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    file_size INTEGER,
                    category TEXT,
                    description TEXT,
                    access_level TEXT DEFAULT 'public',
                    download_count INTEGER DEFAULT 0,
                    added_date TEXT NOT NULL
                )
        ''')

        # Create interlibrary_loans table
        cursor.execute('''
        CREATE TABLE interlibrary_loans (
                    ill_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT,
                    isbn TEXT,
                    source_library TEXT,
                    request_date TEXT NOT NULL,
                    expected_arrival TEXT,
                    actual_arrival TEXT,
                    due_date TEXT,
                    return_date TEXT,
                    status TEXT DEFAULT 'requested',
                    cost REAL DEFAULT 0.0
                )
        ''')

        # Create library_accounts table
        cursor.execute('''
        CREATE TABLE library_accounts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        book_title TEXT,
                        author TEXT,
                        isbn TEXT,
                        checkout_date TEXT,
                        due_date TEXT,
                        return_date TEXT,
                        fine_amount DECIMAL(10,2) DEFAULT 0.00,
                        status TEXT DEFAULT 'checked_out',
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create library_settings table
        cursor.execute('''
        CREATE TABLE library_settings (
                        setting_name TEXT PRIMARY KEY,
                        setting_value TEXT NOT NULL,
                        description TEXT,
                        setting_type TEXT DEFAULT 'string',
                        min_value REAL,
                        max_value REAL,
                        allowed_values TEXT
                    )
        ''')

        # Create reading_goals table
        cursor.execute('''
        CREATE TABLE reading_goals (
                    goal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    goal_type TEXT NOT NULL,
                    target_value INTEGER NOT NULL,
                    current_value INTEGER DEFAULT 0,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_date TEXT NOT NULL
                )
        ''')

        # Create reading_list_items table
        cursor.execute('''
        CREATE TABLE reading_list_items (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    list_id INTEGER NOT NULL,
                    book_id TEXT NOT NULL,
                    added_date TEXT NOT NULL,
                    added_by TEXT NOT NULL,
                    notes TEXT,
                    order_index INTEGER DEFAULT 0
                )
        ''')

        # Create reading_lists table
        cursor.execute('''
        CREATE TABLE reading_lists (
                    list_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    creator_id TEXT NOT NULL,
                    created_date TEXT NOT NULL,
                    is_public BOOLEAN DEFAULT FALSE,
                    is_collaborative BOOLEAN DEFAULT FALSE,
                    category TEXT,
                    target_reading_level TEXT
                )
        ''')

        # Create resource_bookings table
        cursor.execute('''
        CREATE TABLE resource_bookings (
                            id TEXT PRIMARY KEY,
                            resource_id TEXT NOT NULL,
                            event_id TEXT,
                            start_time TEXT NOT NULL,
                            end_time TEXT NOT NULL,
                            status TEXT DEFAULT 'confirmed',
                            notes TEXT,
                            date_added TEXT NOT NULL,
                            FOREIGN KEY (resource_id) REFERENCES resources (id) ON DELETE CASCADE,
                            FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE
                        )
        ''')

        conn.commit()
        conn.close()
        print("library tables initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing library tables: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# OTHER TABLES (58 tables)
# ============================================================================

def init_other_tables():
    """Initialize other system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing other tables...")

        # Create academic_goals table
        cursor.execute('''
        CREATE TABLE academic_goals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        parent_id TEXT,
                        goal_title TEXT,
                        description TEXT,
                        target_grade TEXT,
                        target_date TEXT,
                        current_progress TEXT,
                        status TEXT DEFAULT 'active',
                        created_date TEXT,
                        FOREIGN KEY (student_id) REFERENCES students (student_id),
                        FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
                    )
        ''')

        # Create academic_years table
        cursor.execute('''
        CREATE TABLE academic_years (
                            id TEXT PRIMARY KEY,
                            start_date TEXT NOT NULL,
                            end_date TEXT NOT NULL,
                            date_added TEXT NOT NULL,
                            CONSTRAINT valid_dates CHECK (start_date < end_date)
                        )
        ''')

        # Create achievement_badges table
        cursor.execute('''
        CREATE TABLE achievement_badges (
                    badge_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    badge_name TEXT,
                    badge_description TEXT,
                    points_required INTEGER,
                    badge_icon TEXT,
                    category TEXT
                )
        ''')

        # Create advanced_detection_results table
        cursor.execute('''
        CREATE TABLE advanced_detection_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        submission_id INTEGER NOT NULL,
                        temporal_analysis TEXT,
                        citation_analysis TEXT,
                        behavioral_analysis TEXT,
                        multimodal_analysis TEXT,
                        adversarial_analysis TEXT,
                        ensemble_prediction TEXT,
                        risk_prediction TEXT,
                        bias_adjusted_score REAL,
                        blockchain_hash TEXT,
                        FOREIGN KEY (submission_id) REFERENCES ai_detector_submissions (id)
                    )
        ''')

        # Create allergies table
        cursor.execute('''
        CREATE TABLE allergies (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT,
                            allergen TEXT,
                            severity TEXT,
                            reaction_description TEXT,
                            diagnosed_date TEXT,
                            provider TEXT,
                            verified INTEGER DEFAULT 0,
                            created_at TEXT,
                            FOREIGN KEY (student_id) REFERENCES students (student_id)
                        )
        ''')

        # Create assessment_competencies table
        cursor.execute('''
        CREATE TABLE assessment_competencies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assessment_id INTEGER NOT NULL,
                    competency_id INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    FOREIGN KEY (assessment_id) REFERENCES assessments(assessment_id),
                    FOREIGN KEY (competency_id) REFERENCES competencies(competency_id)
                )
        ''')

        # Create assessment_outcomes table
        cursor.execute('''
        CREATE TABLE assessment_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assessment_id INTEGER NOT NULL,
                    outcome_id INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    FOREIGN KEY (assessment_id) REFERENCES assessments(assessment_id),
                    FOREIGN KEY (outcome_id) REFERENCES learning_outcomes(outcome_id)
                )
        ''')

        # Create assessments table
        cursor.execute('''
        CREATE TABLE assessments (
                    assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assessment_name TEXT NOT NULL,
                    assessment_type TEXT NOT NULL,
                    module_code TEXT NOT NULL,
                    max_points REAL NOT NULL,
                    weight REAL NOT NULL,
                    due_date TEXT,
                    date_created TEXT DEFAULT (datetime('now')),
                    description TEXT,
                    rubric TEXT,
                    FOREIGN KEY (module_code) REFERENCES modules (module_code)
                )
        ''')

        # Create business_directory table
        cursor.execute('''
        CREATE TABLE business_directory (
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

        # Create care_plans table
        cursor.execute('''
        CREATE TABLE care_plans (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT,
                            condition_id INTEGER,
                            plan_name TEXT,
                            description TEXT,
                            start_date TEXT,
                            end_date TEXT,
                            provider TEXT,
                            status TEXT DEFAULT 'active',
                            goals TEXT,
                            interventions TEXT,
                            created_at TEXT,
                            FOREIGN KEY (student_id) REFERENCES students (student_id),
                            FOREIGN KEY (condition_id) REFERENCES medical_conditions (id)
                        )
        ''')

        # Create collection_agencies table
        cursor.execute('''
        CREATE TABLE collection_agencies (
                    agency_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agency_name TEXT NOT NULL,
                    contact_email TEXT,
                    contact_phone TEXT,
                    commission_rate DECIMAL(5,2),
                    minimum_amount DECIMAL(10,2),
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                )
        ''')

        # Create collection_cases table
        cursor.execute('''
        CREATE TABLE collection_cases (
                    case_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    agency_id INTEGER,
                    total_debt DECIMAL(10,2) NOT NULL,
                    case_status TEXT DEFAULT 'new', -- new, assigned, in_progress, resolved, closed
                    assigned_date TEXT,
                    resolution_date TEXT,
                    amount_collected DECIMAL(10,2) DEFAULT 0,
                    commission_paid DECIMAL(10,2) DEFAULT 0,
                    notes TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (agency_id) REFERENCES collection_agencies (agency_id)
                )
        ''')

        # Create competencies table
        cursor.execute('''
        CREATE TABLE competencies (
                    competency_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    category TEXT
                )
        ''')

        # Create competency_levels table
        cursor.execute('''
        CREATE TABLE competency_levels (
                    level_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    competency_id INTEGER NOT NULL,
                    level_name TEXT NOT NULL,
                    level_value INTEGER NOT NULL,
                    description TEXT,
                    FOREIGN KEY (competency_id) REFERENCES competencies(competency_id)
                )
        ''')

        # Create competition_participants table
        cursor.execute('''
        CREATE TABLE competition_participants (
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

        # Create currency_settings table
        cursor.execute('''
        CREATE TABLE currency_settings (
                    setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    base_currency TEXT DEFAULT 'GBP',
                    auto_update_rates BOOLEAN DEFAULT 1,
                    rate_update_frequency INTEGER DEFAULT 24, -- hours
                    last_rate_update TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
        ''')

        # Create data_retention table
        cursor.execute('''
        CREATE TABLE data_retention (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        data_type TEXT NOT NULL,
                        retention_period INTEGER NOT NULL,
                        deletion_date TEXT,
                        status TEXT DEFAULT 'active'
                    )
        ''')

        # Create data_retention_policies table
        cursor.execute('''
        CREATE TABLE data_retention_policies (
                    policy_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data_type TEXT NOT NULL,
                    retention_period_months INTEGER NOT NULL,
                    deletion_method TEXT DEFAULT 'soft', -- 'soft', 'hard', 'anonymize'
                    last_cleanup_date TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                )
        ''')

        # Create donor_recognition table
        cursor.execute('''
        CREATE TABLE donor_recognition (
                    recognition_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alumni_id TEXT,
                    recognition_level TEXT,
                    total_donated REAL,
                    recognition_date TEXT,
                    benefits TEXT,
                    FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
                )
        ''')

        # Create emergency_contacts table
        cursor.execute('''
        CREATE TABLE emergency_contacts (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT,
                            contact_name TEXT,
                            relationship TEXT,
                            phone_primary TEXT,
                            phone_secondary TEXT,
                            email TEXT,
                            address TEXT,
                            priority_order INTEGER,
                            medical_decision_maker INTEGER DEFAULT 0,
                            created_at TEXT,
                            FOREIGN KEY (student_id) REFERENCES students (student_id)
                        )
        ''')

        # Create engagement_points table
        cursor.execute('''
        CREATE TABLE engagement_points (
                    point_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alumni_id TEXT,
                    activity_type TEXT,
                    points_earned INTEGER,
                    activity_date TEXT,
                    description TEXT,
                    FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
                )
        ''')

        # Create equipment_checkouts table
        cursor.execute('''
        CREATE TABLE equipment_checkouts (
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

        # Create exchange_rates table
        cursor.execute('''
        CREATE TABLE exchange_rates (
                    rate_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_currency TEXT NOT NULL,
                    to_currency TEXT NOT NULL,
                    exchange_rate DECIMAL(10,6) NOT NULL,
                    rate_date TEXT NOT NULL,
                    source TEXT, -- 'manual', 'api', 'bank'
                    created_at TEXT
                )
        ''')

        # Create extension_requests table
        cursor.execute('''
        CREATE TABLE extension_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assignment_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    requested_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    new_due_date TIMESTAMP NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    reviewed_by INTEGER,
                    reviewed_date TIMESTAMP,
                    review_comments TEXT,
                    FOREIGN KEY (assignment_id) REFERENCES assignments (id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (reviewed_by) REFERENCES users (id)
                )
        ''')

        # Create extracurricular_activities table
        cursor.execute('''
        CREATE TABLE extracurricular_activities (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        activity_name TEXT,
                        description TEXT,
                        supervisor TEXT,
                        meeting_schedule TEXT,
                        location TEXT,
                        max_participants INTEGER,
                        fee DECIMAL(10,2) DEFAULT 0.00,
                        status TEXT DEFAULT 'active'
                    )
        ''')

        # Create graduation_requirements table
        cursor.execute('''
        CREATE TABLE graduation_requirements (
                            id TEXT PRIMARY KEY,
                            requirement_name TEXT NOT NULL,
                            requirement_type TEXT NOT NULL,
                            credits_required INTEGER,
                            course_category TEXT,
                            deadline_date TEXT,
                            is_mandatory BOOLEAN DEFAULT TRUE,
                            created_at TEXT NOT NULL
                        )
        ''')

        # Create holiday_calendars table
        cursor.execute('''
        CREATE TABLE holiday_calendars (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            country_code TEXT NOT NULL,
                            region TEXT,
                            is_active BOOLEAN DEFAULT TRUE,
                            date_added TEXT NOT NULL
                        )
        ''')

        # Create holidays table
        cursor.execute('''
        CREATE TABLE holidays (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        holiday_name TEXT,
                        start_date DATE,
                        end_date DATE,
                        description TEXT,
                        recurring BOOLEAN DEFAULT 0
                    )
        ''')

        # Create institutions table
        cursor.execute('''
        CREATE TABLE institutions (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        type TEXT,
                        country TEXT,
                        created_at TEXT NOT NULL
                    )
        ''')

        # Create intervention_types table
        cursor.execute('''
        CREATE TABLE intervention_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    description TEXT
                )
        ''')

        # Create kb_articles table
        cursor.execute('''
        CREATE TABLE kb_articles (
                    article_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    summary TEXT,
                    category TEXT NOT NULL,
                    tags TEXT,  -- JSON array
                    author_id TEXT NOT NULL,
                    created_datetime TEXT NOT NULL,
                    updated_datetime TEXT,
                    published_datetime TEXT,
                    is_published BOOLEAN DEFAULT 0,
                    view_count INTEGER DEFAULT 0,
                    helpful_votes INTEGER DEFAULT 0,
                    not_helpful_votes INTEGER DEFAULT 0,
                    search_keywords TEXT,  -- Space-separated keywords for search
                    related_articles TEXT  -- JSON array of related article IDs
                )
        ''')

        # Create knowledge_base table
        cursor.execute('''
        CREATE TABLE knowledge_base (
                    article_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT,
                    tags TEXT,
                    author_id INTEGER,
                    status TEXT DEFAULT 'draft',
                    views INTEGER DEFAULT 0,
                    helpful_votes INTEGER DEFAULT 0,
                    unhelpful_votes INTEGER DEFAULT 0,
                    search_keywords TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (author_id) REFERENCES users (id)
                )
        ''')

        # Create learning_outcomes table
        cursor.execute('''
        CREATE TABLE learning_outcomes (
                    outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    outcome_code TEXT NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT,
                    level INTEGER
                )
        ''')

        # Create networking_connections table
        cursor.execute('''
        CREATE TABLE networking_connections (
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

        # Create newsletters table
        cursor.execute('''
        CREATE TABLE newsletters (
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

        # Create outcome_results table
        cursor.execute('''
        CREATE TABLE outcome_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    outcome_id INTEGER NOT NULL,
                    achievement_level REAL,
                    assessment_date TEXT,
                    evidence TEXT,
                    FOREIGN KEY (student_id) REFERENCES students(student_id),
                    FOREIGN KEY (outcome_id) REFERENCES learning_outcomes(outcome_id)
                )
        ''')

        # Create photo_gallery table
        cursor.execute('''
        CREATE TABLE photo_gallery (
                    photo_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER,
                    uploaded_by TEXT,
                    photo_path TEXT,
                    caption TEXT,
                    upload_date TEXT,
                    is_featured BOOLEAN DEFAULT 0,
                    FOREIGN KEY (event_id) REFERENCES alumni_events (event_id),
                    FOREIGN KEY (uploaded_by) REFERENCES alumni (alumni_id)
                )
        ''')

        # Create privacy_consent table
        cursor.execute('''
        CREATE TABLE privacy_consent (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        consent_type TEXT NOT NULL,
                        granted INTEGER NOT NULL,
                        granted_at TEXT NOT NULL,
                        expires_at TEXT,
                        version TEXT NOT NULL,
                        UNIQUE(student_id, consent_type)
                    )
        ''')

        # Create processing_queue table
        cursor.execute('''
        CREATE TABLE processing_queue (
                        id TEXT PRIMARY KEY,
                        submission_data TEXT NOT NULL,
                        priority INTEGER DEFAULT 1,
                        status TEXT DEFAULT 'queued',
                        created_at TEXT NOT NULL,
                        processed_at TEXT
                    )
        ''')

        # Create project_milestones table
        cursor.execute('''
        CREATE TABLE project_milestones (
                            id TEXT PRIMARY KEY,
                            project_name TEXT NOT NULL,
                            milestone_name TEXT NOT NULL,
                            due_date TEXT NOT NULL,
                            completion_percentage REAL DEFAULT 0.0,
                            status TEXT DEFAULT 'pending',
                            course_id TEXT,
                            student_id TEXT,
                            description TEXT,
                            created_at TEXT NOT NULL,
                            FOREIGN KEY (course_id) REFERENCES courses (id),
                            FOREIGN KEY (student_id) REFERENCES students (student_id)
                        )
        ''')

        # Create provider_schedules table
        cursor.execute('''
        CREATE TABLE provider_schedules (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            provider_name TEXT,
                            day_of_week INTEGER,
                            start_time TEXT,
                            end_time TEXT,
                            max_appointments INTEGER DEFAULT 10,
                            specialty TEXT,
                            location TEXT,
                            active INTEGER DEFAULT 1,
                            created_at TEXT
                        )
        ''')

        # Create ranked_votes table
        cursor.execute('''
        CREATE TABLE ranked_votes (
                    vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    election_id INTEGER,
                    voter_id TEXT,
                    candidate_preferences TEXT,  -- JSON string of ranked preferences
                    vote_time TEXT,
                    FOREIGN KEY (election_id) REFERENCES union_elections (election_id),
                    FOREIGN KEY (voter_id) REFERENCES students (student_id)
                )
        ''')

        # Create recommended_interventions table
        cursor.execute('''
        CREATE TABLE recommended_interventions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    risk_factor_id INTEGER,
                    intervention_type_id INTEGER,
                    recommended_date TEXT,
                    status TEXT DEFAULT 'pending',
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (risk_factor_id) REFERENCES risk_factors (id),
                    FOREIGN KEY (intervention_type_id) REFERENCES intervention_types (id)
                )
        ''')

        # Create referrals table
        cursor.execute('''
        CREATE TABLE referrals (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT,
                            referring_provider TEXT,
                            specialist_provider TEXT,
                            specialty TEXT,
                            reason TEXT,
                            urgency TEXT,
                            referral_date TEXT,
                            appointment_date TEXT,
                            status TEXT DEFAULT 'pending',
                            notes TEXT,
                            created_at TEXT,
                            FOREIGN KEY (student_id) REFERENCES students (student_id)
                        )
        ''')

        # Create resources table
        cursor.execute('''
        CREATE TABLE resources (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            type TEXT NOT NULL,
                            capacity INTEGER,
                            location TEXT,
                            equipment TEXT,
                            status TEXT DEFAULT 'available',
                            date_added TEXT NOT NULL
                        )
        ''')

        # Create risk_assessments table
        cursor.execute('''
        CREATE TABLE risk_assessments (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT,
                            assessment_type TEXT,
                            risk_score INTEGER,
                            risk_factors TEXT,
                            recommendations TEXT,
                            assessed_date TEXT,
                            assessed_by TEXT,
                            follow_up_date TEXT,
                            created_at TEXT,
                            FOREIGN KEY (student_id) REFERENCES students (student_id)
                        )
        ''')

        # Create risk_factors table
        cursor.execute('''
        CREATE TABLE risk_factors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    factor_name TEXT,
                    factor_value REAL,
                    assessment_id INTEGER,
                    date_calculated TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (assessment_id) REFERENCES assessments (assessment_id)
                )
        ''')

        # Create rubric_criteria table
        cursor.execute('''
        CREATE TABLE rubric_criteria (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rubric_id INTEGER NOT NULL,
                    criteria_name TEXT NOT NULL,
                    description TEXT,
                    max_points REAL NOT NULL,
                    weight REAL DEFAULT 1.0,
                    display_order INTEGER DEFAULT 0,
                    FOREIGN KEY (rubric_id) REFERENCES rubrics (id) ON DELETE CASCADE
                )
        ''')

        # Create rubrics table
        cursor.execute('''
        CREATE TABLE rubrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    total_points REAL NOT NULL DEFAULT 100,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by INTEGER,
                    FOREIGN KEY (created_by) REFERENCES users (id)
                )
        ''')

        # Create schedule_conflicts table
        cursor.execute('''
        CREATE TABLE schedule_conflicts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        conflict_type TEXT,
                        description TEXT,
                        affected_schedules TEXT,
                        resolved BOOLEAN DEFAULT 0,
                        resolution_notes TEXT,
                        detected_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        resolved_date TIMESTAMP
                    )
        ''')

        # Create schedule_history table
        cursor.execute('''
        CREATE TABLE schedule_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        schedule_id INTEGER,
                        action TEXT,
                        old_values TEXT,
                        new_values TEXT,
                        changed_by TEXT,
                        change_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
        ''')

        # Create school_calendar table
        cursor.execute('''
        CREATE TABLE school_calendar (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_name TEXT,
                        event_description TEXT,
                        event_date TEXT,
                        start_time TEXT,
                        end_time TEXT,
                        location TEXT,
                        event_type TEXT,
                        audience TEXT
                    )
        ''')

        # Create screening_schedules table
        cursor.execute('''
        CREATE TABLE screening_schedules (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT,
                            screening_type TEXT,
                            due_date TEXT,
                            completed_date TEXT,
                            status TEXT DEFAULT 'due',
                            provider TEXT,
                            results TEXT,
                            next_due_date TEXT,
                            created_at TEXT,
                            FOREIGN KEY (student_id) REFERENCES students (student_id)
                        )
        ''')

        # Create search_presets table
        cursor.execute('''
        CREATE TABLE search_presets (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            user_id TEXT NOT NULL,
                            filters TEXT NOT NULL,
                            date_added TEXT NOT NULL,
                            is_active BOOLEAN DEFAULT TRUE
                        )
        ''')

        # Create shared_resources table
        cursor.execute('''
        CREATE TABLE shared_resources (
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

        # Create sla_policies table
        cursor.execute('''
        CREATE TABLE sla_policies (
                    sla_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    priority TEXT,
                    impact TEXT,
                    urgency TEXT,
                    first_response_hours INTEGER,
                    resolution_hours INTEGER,
                    escalation_hours INTEGER,
                    business_hours_only BOOLEAN DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT,
                    updated_at TEXT
                )
        ''')

        # Create staff_schedules table
        cursor.execute('''
        CREATE TABLE staff_schedules (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        staff_id TEXT NOT NULL,
                        shift_date DATE NOT NULL,
                        start_time TIME NOT NULL,
                        end_time TIME NOT NULL,
                        position TEXT NOT NULL,
                        status TEXT DEFAULT 'scheduled',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
        ''')

        # Create survey_responses table
        cursor.execute('''
        CREATE TABLE survey_responses (
                    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    survey_id INTEGER,
                    alumni_id TEXT,
                    responses TEXT,
                    submission_date TEXT,
                    FOREIGN KEY (survey_id) REFERENCES event_surveys (survey_id),
                    FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
                )
        ''')

        conn.commit()
        conn.close()
        print("other tables initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing other tables: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# PARENT TABLES (6 tables)
# ============================================================================

def init_parent_tables():
    """Initialize parent system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing parent tables...")

        # Create parent_documents table
        cursor.execute('''
        CREATE TABLE parent_documents (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        parent_id TEXT,
                        student_id TEXT,
                        document_type TEXT,
                        document_name TEXT,
                        file_path TEXT,
                        upload_date TEXT,
                        status TEXT DEFAULT 'pending',
                        expiry_date TEXT,
                        FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create parent_messages table
        cursor.execute('''
        CREATE TABLE parent_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        parent_id TEXT,
                        teacher_id INTEGER,
                        student_id TEXT,
                        message_content TEXT,
                        created_date TEXT,
                        is_read BOOLEAN DEFAULT 0,
                        is_from_parent BOOLEAN DEFAULT 1,
                        message_type TEXT DEFAULT 'individual',
                        group_id TEXT,
                        FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                        FOREIGN KEY (teacher_id) REFERENCES users (id),
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create parent_preferences table
        cursor.execute('''
        CREATE TABLE parent_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id TEXT UNIQUE,
                    email_notifications BOOLEAN DEFAULT 1,
                    sms_notifications BOOLEAN DEFAULT 0,
                    grade_alerts BOOLEAN DEFAULT 1,
                    attendance_alerts BOOLEAN DEFAULT 1,
                    behavior_alerts BOOLEAN DEFAULT 1,
                    assignment_alerts BOOLEAN DEFAULT 0,
                    weekly_summary BOOLEAN DEFAULT 1,
                    notification_timing TEXT DEFAULT '08:00',
                    quiet_hours_start TEXT DEFAULT '20:00',
                    quiet_hours_end TEXT DEFAULT '07:00',
                    FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
                )
        ''')

        # Create parent_teacher_meetings table
        cursor.execute('''
        CREATE TABLE parent_teacher_meetings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        parent_id TEXT,
                        teacher_id INTEGER,
                        student_id TEXT,
                        meeting_date TEXT,
                        start_time TEXT,
                        end_time TEXT,
                        location TEXT,
                        meeting_type TEXT,
                        status TEXT DEFAULT 'scheduled',
                        agenda TEXT,
                        notes TEXT,
                        FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                        FOREIGN KEY (teacher_id) REFERENCES users (id),
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create parent_user_mapping table
        cursor.execute('''
        CREATE TABLE parent_user_mapping (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    parent_id TEXT UNIQUE,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
                )
        ''')

        # Create pickup_authorizations table
        cursor.execute('''
        CREATE TABLE pickup_authorizations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        authorized_person_name TEXT,
                        relationship TEXT,
                        phone_number TEXT,
                        id_number TEXT,
                        photo_path TEXT,
                        valid_from TEXT,
                        valid_until TEXT,
                        active BOOLEAN DEFAULT 1,
                        created_by TEXT,
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        conn.commit()
        conn.close()
        print("parent tables initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing parent tables: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# PARKING TABLES (1 tables)
# ============================================================================

def init_parking_tables():
    """Initialize parking system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing parking tables...")

        # Create transportation table
        cursor.execute('''
        CREATE TABLE transportation (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        route_name TEXT,
                        bus_number TEXT,
                        pickup_time TEXT,
                        dropoff_time TEXT,
                        pickup_location TEXT,
                        dropoff_location TEXT,
                        driver_name TEXT,
                        driver_phone TEXT,
                        active BOOLEAN DEFAULT 1,
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        conn.commit()
        conn.close()
        print("parking tables initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing parking tables: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# PEER_SUPPORT TABLES (4 tables)
# ============================================================================

def init_peer_support_tables():
    """Initialize peer_support system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing peer_support tables...")

        # Create peer_review_criteria table
        cursor.execute('''
        CREATE TABLE peer_review_criteria (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    review_id INTEGER NOT NULL,
                    criteria_name TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    comment TEXT,
                    FOREIGN KEY (review_id) REFERENCES peer_reviews (id)
                )
        ''')

        # Create peer_reviews table
        cursor.execute('''
        CREATE TABLE peer_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            reviewer_id INTEGER NOT NULL,
            reviewee_submission_id INTEGER NOT NULL,
            score REAL,
            feedback TEXT,
            rubric_scores TEXT,
            status TEXT DEFAULT 'pending',
            submitted_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, reviewee_id TEXT,
            FOREIGN KEY (assignment_id) REFERENCES assignments (id),
            FOREIGN KEY (reviewer_id) REFERENCES users (id),
            FOREIGN KEY (reviewee_submission_id) REFERENCES assignment_submissions (id)
        )
        ''')

        # Create study_groups table
        cursor.execute('''
        CREATE TABLE study_groups (
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

        # Create tutoring_offers table
        cursor.execute('''
        CREATE TABLE tutoring_offers (
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

        conn.commit()
        conn.close()
        print("peer_support tables initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing peer_support tables: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# SOCIAL TABLES (1 tables)
# ============================================================================

def init_social_tables():
    """Initialize social system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing social tables...")

        # Create forum_replies table
        cursor.execute('''
        CREATE TABLE forum_replies (
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
        print("social tables initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing social tables: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# STUDENT_AFFAIRS TABLES (28 tables)
# ============================================================================

def init_student_affairs_tables():
    """Initialize student_affairs system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing student_affairs tables...")

        # Create activity_log table
        cursor.execute('''
        CREATE TABLE activity_log (
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
        CREATE TABLE book_clubs (
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
        CREATE TABLE class_reunions (
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
        CREATE TABLE club_competitions (
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
        CREATE TABLE club_discussions (
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
        CREATE TABLE club_expenses (
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
        CREATE TABLE club_media (
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
        CREATE TABLE course_events (
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
        CREATE TABLE election_candidates (
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
        CREATE TABLE election_votes (
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
        CREATE TABLE event_categories (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT UNIQUE NOT NULL,
                            color_code TEXT,
                            description TEXT,
                            date_added TEXT NOT NULL
                        )
        ''')

        # Create event_dependencies table
        cursor.execute('''
        CREATE TABLE event_dependencies (
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
        CREATE TABLE event_finances (
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
        CREATE TABLE event_sequences (
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
        CREATE TABLE event_surveys (
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
        CREATE TABLE event_tags (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT UNIQUE NOT NULL,
                            color_code TEXT,
                            date_added TEXT NOT NULL
                        )
        ''')

        # Create event_tickets table
        cursor.execute('''
        CREATE TABLE event_tickets (
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
        CREATE TABLE event_timezones (
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
        CREATE TABLE event_workflows (
                            id TEXT PRIMARY KEY,
                            workflow_name TEXT NOT NULL,
                            description TEXT,
                            template_data TEXT,
                            is_active BOOLEAN DEFAULT TRUE,
                            created_by TEXT,
                            created_at TEXT NOT NULL
                        )
        ''')

        # Create events table
        cursor.execute('''
        CREATE TABLE events (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            date TEXT,
                            date_start TEXT,
                            date_end TEXT,
                            description TEXT,
                            event_type TEXT DEFAULT 'Academic',
                            date_added TEXT NOT NULL,
                            last_modified TEXT,
                            created_by TEXT,
                            CONSTRAINT valid_event_dates CHECK (
                                (date IS NOT NULL AND date_start IS NULL AND date_end IS NULL) OR
                                (date IS NULL AND date_start IS NOT NULL AND date_end IS NOT NULL AND date_start <= date_end)
                            )
                        )
        ''')

        # Create organizations table
        cursor.execute('''
        CREATE TABLE organizations (
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
        CREATE TABLE parent_activity_log (
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
        CREATE TABLE recurring_events (
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
        CREATE TABLE union_elections (
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
        CREATE TABLE union_equipment (
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
        CREATE TABLE union_facilities (
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
        CREATE TABLE union_representatives (
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
        CREATE TABLE user_activity_log (
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
        print("student_affairs tables initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing student_affairs tables: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# SUPPORT TABLES (15 tables)
# ============================================================================

def init_support_tables():
    """Initialize support system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing support tables...")

        # Create escalation_rules table
        cursor.execute('''
        CREATE TABLE escalation_rules (
                    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT,
                    priority TEXT,
                    condition_type TEXT NOT NULL,  -- time_based, status_based, keyword_based
                    condition_value TEXT NOT NULL,
                    action_type TEXT NOT NULL,  -- escalate, reassign, notify
                    action_target TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_by TEXT NOT NULL,
                    created_datetime TEXT NOT NULL
                )
        ''')

        # Create faqs table
        cursor.execute('''
        CREATE TABLE faqs (
                    faq_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    category TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_datetime TEXT NOT NULL,
                    updated_datetime TEXT,
                    view_count INTEGER DEFAULT 0,
                    helpful_votes INTEGER DEFAULT 0,
                    tags TEXT,  -- JSON array
                    is_featured BOOLEAN DEFAULT 0
                )
        ''')

        # Create peer_support_groups table
        cursor.execute('''
        CREATE TABLE peer_support_groups (
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

        # Create support_group_members table
        cursor.execute('''
        CREATE TABLE support_group_members (
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

        # Create support_resources table
        cursor.execute('''
        CREATE TABLE support_resources (
                    resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    url TEXT,
                    file_path TEXT,
                    created_by TEXT NOT NULL,
                    created_datetime TEXT NOT NULL,
                    updated_datetime TEXT,
                    access_count INTEGER DEFAULT 0,
                    tags TEXT,  -- JSON array
                    content_type TEXT,
                    is_featured BOOLEAN DEFAULT 0,
                    requires_auth BOOLEAN DEFAULT 0
                )
        ''')

        # Create support_tickets table
        cursor.execute('''
        CREATE TABLE support_tickets (
                    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_datetime TEXT NOT NULL,
                    last_updated_datetime TEXT,
                    assigned_to TEXT,
                    escalated_at TEXT,
                    resolved_at TEXT,
                    closed_at TEXT,
                    estimated_resolution TEXT,
                    sentiment TEXT DEFAULT 'neutral',
                    satisfaction_rating INTEGER,
                    tags TEXT,  -- JSON array of tags
                    parent_ticket_id INTEGER, due_date TEXT, user_id INTEGER, subject TEXT DEFAULT 'No Subject', created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,  -- For merged tickets
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (parent_ticket_id) REFERENCES support_tickets (ticket_id)
                )
        ''')

        # Create ticket_attachments table
        cursor.execute('''
        CREATE TABLE ticket_attachments (
                    attachment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    file_type TEXT NOT NULL,
                    mime_type TEXT,
                    uploaded_by TEXT NOT NULL,
                    uploaded_datetime TEXT NOT NULL,
                    is_public BOOLEAN DEFAULT 0,
                    FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id)
                )
        ''')

        # Create ticket_audit_log table
        cursor.execute('''
        CREATE TABLE ticket_audit_log (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER,
                    user_id INTEGER,
                    action TEXT NOT NULL,
                    old_values TEXT,
                    new_values TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at TEXT,
                    FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
        ''')

        # Create ticket_escalations table
        cursor.execute('''
        CREATE TABLE ticket_escalations (
                    escalation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER,
                    escalation_level INTEGER,
                    escalated_to INTEGER,
                    escalated_by INTEGER,
                    escalation_reason TEXT,
                    resolved BOOLEAN DEFAULT 0,
                    created_at TEXT,
                    FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                    FOREIGN KEY (escalated_to) REFERENCES users (id),
                    FOREIGN KEY (escalated_by) REFERENCES users (id)
                )
        ''')

        # Create ticket_links table
        cursor.execute('''
        CREATE TABLE ticket_links (
                    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER,
                    linked_ticket_id INTEGER,
                    link_type TEXT,
                    created_by INTEGER,
                    created_at TEXT,
                    FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                    FOREIGN KEY (linked_ticket_id) REFERENCES support_tickets (ticket_id),
                    FOREIGN KEY (created_by) REFERENCES users (id)
                )
        ''')

        # Create ticket_replies table
        cursor.execute('''
        CREATE TABLE ticket_replies (
                    reply_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER,
                    user_id INTEGER,
                    message TEXT NOT NULL,
                    is_internal BOOLEAN DEFAULT 0,
                    reply_type TEXT DEFAULT 'comment',
                    time_spent REAL DEFAULT 0,
                    created_at TEXT,
                    edited_at TEXT,
                    FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
        ''')

        # Create ticket_responses table
        cursor.execute('''
        CREATE TABLE ticket_responses (
                    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER NOT NULL,
                    responder_id TEXT NOT NULL,
                    responder_role TEXT NOT NULL,
                    response_text TEXT NOT NULL,
                    response_datetime TEXT NOT NULL,
                    is_internal BOOLEAN DEFAULT 0,
                    is_auto_generated BOOLEAN DEFAULT 0,
                    template_used TEXT,
                    FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id)
                )
        ''')

        # Create ticket_templates table
        cursor.execute('''
        CREATE TABLE ticket_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    title_template TEXT NOT NULL,
                    description_template TEXT NOT NULL,
                    category TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_datetime TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    usage_count INTEGER DEFAULT 0
                )
        ''')

        # Create ticket_time_tracking table
        cursor.execute('''
        CREATE TABLE ticket_time_tracking (
                    time_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER,
                    user_id INTEGER,
                    start_time TEXT,
                    end_time TEXT,
                    duration_minutes INTEGER,
                    description TEXT,
                    billable BOOLEAN DEFAULT 0,
                    created_at TEXT,
                    FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
        ''')

        # Create ticket_workflows table
        cursor.execute('''
        CREATE TABLE ticket_workflows (
                    workflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    trigger_type TEXT NOT NULL,
                    trigger_conditions TEXT,
                    actions TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_by INTEGER,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (created_by) REFERENCES users (id)
                )
        ''')

        conn.commit()
        conn.close()
        print("support tables initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing support tables: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# TRAVEL TABLES (5 tables)
# ============================================================================

def init_travel_tables():
    """Initialize travel system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing travel tables...")

        # Create trip_expenses table
        cursor.execute('''
        CREATE TABLE trip_expenses (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        trip_id INTEGER NOT NULL,
                        category TEXT NOT NULL,
                        description TEXT NOT NULL,
                        amount REAL NOT NULL,
                        date TEXT NOT NULL,
                        recorded_by INTEGER,
                        FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
                        FOREIGN KEY (recorded_by) REFERENCES users (id)
                    )
        ''')

        # Create trip_itinerary table
        cursor.execute('''
        CREATE TABLE trip_itinerary (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        trip_id INTEGER NOT NULL,
                        day_number INTEGER NOT NULL,
                        activity TEXT NOT NULL,
                        location TEXT,
                        start_time TEXT,
                        end_time TEXT,
                        notes TEXT,
                        FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
                        UNIQUE (trip_id, day_number, start_time)
                    )
        ''')

        # Create trip_participants table
        cursor.execute('''
        CREATE TABLE trip_participants (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        trip_id INTEGER NOT NULL,
                        student_id TEXT,
                        user_id INTEGER,
                        registration_date TEXT NOT NULL,
                        payment_status TEXT DEFAULT 'pending',
                        emergency_contact TEXT,
                        medical_info TEXT,
                        dietary_requirements TEXT,
                        status TEXT DEFAULT 'registered',
                        FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
                        FOREIGN KEY (student_id) REFERENCES students (student_id),
                        FOREIGN KEY (user_id) REFERENCES users (id),
                        UNIQUE (trip_id, student_id),
                        CHECK (payment_status IN ('pending', 'partial', 'paid', 'refunded')),
                        CHECK (status IN ('registered', 'waitlist', 'cancelled', 'attended'))
                    )
        ''')

        # Create trip_staff table
        cursor.execute('''
        CREATE TABLE trip_staff (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        trip_id INTEGER NOT NULL,
                        staff_user_id INTEGER NOT NULL,
                        role TEXT DEFAULT 'supervisor',
                        assigned_date TEXT NOT NULL,
                        FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
                        FOREIGN KEY (staff_user_id) REFERENCES users (id),
                        UNIQUE (trip_id, staff_user_id),
                        CHECK (role IN ('supervisor', 'coordinator', 'medical', 'transport'))
                    )
        ''')

        # Create trips table
        cursor.execute('''
        CREATE TABLE trips (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        trip_name TEXT NOT NULL,
                        description TEXT,
                        destination TEXT NOT NULL,
                        start_date TEXT NOT NULL,
                        end_date TEXT NOT NULL,
                        max_participants INTEGER DEFAULT 50,
                        cost REAL DEFAULT 0.0,
                        status TEXT DEFAULT 'planning',
                        created_by INTEGER,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY (created_by) REFERENCES users (id),
                        CHECK (status IN ('planning', 'open', 'full', 'cancelled', 'completed'))
                    )
        ''')

        conn.commit()
        conn.close()
        print("travel tables initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing travel tables: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# WELLNESS TABLES (3 tables)
# ============================================================================

def init_wellness_tables():
    """Initialize wellness system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("Initializing wellness tables...")

        # Create volunteer_opportunities table
        cursor.execute('''
        CREATE TABLE volunteer_opportunities (
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

        # Create volunteer_signups table
        cursor.execute('''
        CREATE TABLE volunteer_signups (
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

        # Create wellness_participation table
        cursor.execute('''
        CREATE TABLE wellness_participation (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT,
                            program_name TEXT,
                            enrollment_date TEXT,
                            completion_date TEXT,
                            status TEXT DEFAULT 'enrolled',
                            progress_score INTEGER DEFAULT 0,
                            goals_met INTEGER DEFAULT 0,
                            created_at TEXT,
                            FOREIGN KEY (student_id) REFERENCES students (student_id)
                        )
        ''')

        conn.commit()
        conn.close()
        print("wellness tables initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing wellness tables: {e}")
        if 'conn' in locals():
            conn.close()


# ============================================================================
# MASTER INITIALIZATION FUNCTION
# ============================================================================

def init_all_missing_tables():
    """Initialize all missing tables"""
    print("=" * 80)
    print("INITIALIZING ALL MISSING TABLES")
    print("=" * 80)
    print()

    init_academics_tables()
    init_ai_tables()
    init_alumni_tables()
    init_analytics_tables()
    init_audit_tables()
    init_auth_tables()
    init_career_tables()
    init_commerce_tables()
    init_communication_tables()
    init_courses_tables()
    init_documents_tables()
    init_finance_tables()
    init_health_tables()
    init_housing_tables()
    init_integration_tables()
    init_library_tables()
    init_other_tables()
    init_parent_tables()
    init_parking_tables()
    init_peer_support_tables()
    init_social_tables()
    init_student_affairs_tables()
    init_support_tables()
    init_travel_tables()
    init_wellness_tables()

    print()
    print("=" * 80)
    print("ALL MISSING TABLES INITIALIZED SUCCESSFULLY!")
    print("=" * 80)

__all__ = [
    'init_grade_system_db',
    'init_finance_system_db',
    'init_student_union_db',
    'init_email_system_db',
    'init_health_system_db',
    'init_lms_system_db',
    'init_attendance_system_db',
    'init_mental_health_system_db',
    'init_early_warning_system_db',
    'init_degree_audit_system_db',
    'init_career_services_system_db',
    'init_admissions_crm_system_db',
    'init_analytics_dashboard_system_db',
    'initialize_all_schemas',
]
