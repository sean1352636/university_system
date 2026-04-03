from __future__ import annotations
from datetime import datetime
from education_system.university_system.infrastructure.database.db import get_connection, sqlite3
from education_system.university_system.core.i18n import get_text as _t, init_i18n

# Initialize i18n
init_i18n()

def init_health_system_db():
    """Initialize the health system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="health system"))

        # Create health_records table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            record_type TEXT,
            record_date TEXT,
            description TEXT,
            provider TEXT,
            confidential INTEGER DEFAULT 0,
            created_at TEXT,
            encrypted_data TEXT,
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
        print(_t("schemas.initialized_success", name="Health system"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="health system", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# LMS (LEARNING MANAGEMENT SYSTEM) SCHEMAS
# ============================================================================


def init_mental_health_system_db():
    """Initialize the Mental Health & Wellness Portal database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="Mental Health & Wellness Portal"))

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
        print(_t("schemas.initialized_success", name="Mental Health & Wellness Portal"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="Mental Health & Wellness Portal", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# STUDENT SUCCESS EARLY WARNING SYSTEM SCHEMAS
# ============================================================================


def init_health_tables():
    """Initialize health system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="health"))

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
        print(_t("schemas.initialized_success", name="health"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="health", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# HOUSING TABLES (13 tables)
# ============================================================================


def init_wellness_tables():
    """Initialize wellness system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="wellness"))

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
        print(_t("schemas.initialized_success", name="wellness"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="wellness", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# ADDITIONAL MISSING TABLES (109 tables)
# Auto-generated from existing database schema
# ============================================================================


