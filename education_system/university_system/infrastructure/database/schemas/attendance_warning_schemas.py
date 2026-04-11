from __future__ import annotations
from datetime import datetime
from education_system.university_system.infrastructure.database.db import get_connection, sqlite3
from education_system.university_system.core.i18n import get_text as _t, init_i18n

# Initialize i18n
init_i18n()

def init_attendance_system_db():
    """Initialize the Advanced Attendance System database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="Advanced Attendance System"))

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
        print(_t("schemas.initialized_success", name="Advanced Attendance System"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="Advanced Attendance System", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# MENTAL HEALTH & WELLNESS PORTAL SCHEMAS
# ============================================================================


def init_early_warning_system_db():
    """Initialize the Student Success Early Warning System database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="Student Success Early Warning System"))

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
        print(_t("schemas.initialized_success", name="Student Success Early Warning System"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="Student Success Early Warning System", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# DEGREE AUDIT & ACADEMIC ADVISING SCHEMAS
# ============================================================================


def init_peer_support_tables():
    """Initialize peer_support system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="peer_support"))

        # Create peer_review_criteria table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS peer_review_criteria (
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
        CREATE TABLE IF NOT EXISTS peer_reviews (
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

        # Create tutoring_offers table
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

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="peer_support"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="peer_support", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# SOCIAL TABLES (1 tables)
# ============================================================================


