"""Database schema definitions for the Primary School Management System."""

import sqlite3
import logging

from education_system.primary_school.infrastructure.auth.password_manager import hash_password

logger = logging.getLogger(__name__)

TABLES = {
    "users": """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'teacher',
            display_name TEXT,
            email TEXT,
            is_active INTEGER DEFAULT 1,
            failed_attempts INTEGER DEFAULT 0,
            locked_until TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            last_login TEXT
        )
    """,
    "pupils": """
        CREATE TABLE IF NOT EXISTS pupils (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id TEXT UNIQUE NOT NULL,
            user_id INTEGER REFERENCES users(id),
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            preferred_name TEXT,
            date_of_birth TEXT,
            gender TEXT,
            year_group TEXT NOT NULL,
            class_name TEXT,
            key_stage TEXT,
            ethnicity TEXT,
            first_language TEXT DEFAULT 'English',
            eal INTEGER DEFAULT 0,
            pupil_premium INTEGER DEFAULT 0,
            free_school_meals INTEGER DEFAULT 0,
            sen_status TEXT DEFAULT 'No SEN',
            looked_after INTEGER DEFAULT 0,
            parent1_name TEXT,
            parent1_email TEXT,
            parent1_phone TEXT,
            parent1_relationship TEXT DEFAULT 'Parent',
            parent2_name TEXT,
            parent2_email TEXT,
            parent2_phone TEXT,
            parent2_relationship TEXT,
            emergency_contact_name TEXT,
            emergency_contact_phone TEXT,
            emergency_contact_relationship TEXT,
            address TEXT,
            medical_notes TEXT,
            dietary_requirements TEXT,
            photo_consent INTEGER DEFAULT 1,
            status TEXT DEFAULT 'Active',
            admission_date TEXT DEFAULT (date('now')),
            leaving_date TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "staff": """
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id TEXT UNIQUE NOT NULL,
            user_id INTEGER REFERENCES users(id),
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            role TEXT DEFAULT 'Teacher',
            email TEXT,
            phone TEXT,
            class_teacher_of TEXT,
            department TEXT,
            start_date TEXT DEFAULT (date('now')),
            dbs_check_date TEXT,
            dbs_certificate_number TEXT,
            qualifications TEXT,
            emergency_contact_name TEXT,
            emergency_contact_phone TEXT,
            status TEXT DEFAULT 'Active',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "subjects": """
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_code TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            is_core INTEGER DEFAULT 0,
            key_stage TEXT,
            coordinator_staff_id TEXT REFERENCES staff(staff_id),
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "classes": """
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT UNIQUE NOT NULL,
            year_group TEXT NOT NULL,
            teacher_staff_id TEXT REFERENCES staff(staff_id),
            teaching_assistant_staff_id TEXT REFERENCES staff(staff_id),
            room TEXT,
            capacity INTEGER DEFAULT 30,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "assessments": """
        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id TEXT NOT NULL REFERENCES pupils(pupil_id),
            subject_code TEXT NOT NULL REFERENCES subjects(subject_code),
            assessment_type TEXT NOT NULL DEFAULT 'Formative',
            level TEXT,
            score REAL,
            max_score REAL,
            term TEXT,
            academic_year TEXT,
            year_group TEXT,
            assessed_by TEXT,
            comments TEXT,
            assessment_date TEXT DEFAULT (date('now')),
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "attendance_records": """
        CREATE TABLE IF NOT EXISTS attendance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id TEXT NOT NULL REFERENCES pupils(pupil_id),
            date TEXT NOT NULL,
            session TEXT NOT NULL DEFAULT 'AM',
            status TEXT NOT NULL DEFAULT '/',
            note TEXT,
            recorded_by TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(pupil_id, date, session)
        )
    """,
    "timetable_slots": """
        CREATE TABLE IF NOT EXISTS timetable_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT NOT NULL REFERENCES classes(class_name),
            subject_code TEXT REFERENCES subjects(subject_code),
            day_of_week TEXT NOT NULL,
            period INTEGER NOT NULL,
            start_time TEXT,
            end_time TEXT,
            room TEXT,
            teacher_staff_id TEXT REFERENCES staff(staff_id),
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "homework": """
        CREATE TABLE IF NOT EXISTS homework (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            class_name TEXT NOT NULL,
            subject_code TEXT REFERENCES subjects(subject_code),
            set_date TEXT DEFAULT (date('now')),
            due_date TEXT NOT NULL,
            set_by TEXT,
            status TEXT DEFAULT 'Active',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "homework_submissions": """
        CREATE TABLE IF NOT EXISTS homework_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            homework_id INTEGER NOT NULL REFERENCES homework(id),
            pupil_id TEXT NOT NULL REFERENCES pupils(pupil_id),
            submitted_date TEXT,
            status TEXT DEFAULT 'Pending',
            feedback TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "behaviour_records": """
        CREATE TABLE IF NOT EXISTS behaviour_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id TEXT NOT NULL REFERENCES pupils(pupil_id),
            type TEXT NOT NULL DEFAULT 'positive',
            category TEXT,
            description TEXT,
            points INTEGER DEFAULT 1,
            action_taken TEXT,
            recorded_by TEXT,
            incident_date TEXT DEFAULT (date('now')),
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "rewards": """
        CREATE TABLE IF NOT EXISTS rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id TEXT NOT NULL REFERENCES pupils(pupil_id),
            reward_type TEXT NOT NULL,
            reason TEXT,
            awarded_by TEXT,
            house TEXT,
            points INTEGER DEFAULT 1,
            award_date TEXT DEFAULT (date('now')),
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "safeguarding_concerns": """
        CREATE TABLE IF NOT EXISTS safeguarding_concerns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id TEXT NOT NULL REFERENCES pupils(pupil_id),
            concern_type TEXT NOT NULL,
            description TEXT NOT NULL,
            severity TEXT DEFAULT 'Low',
            reported_by TEXT NOT NULL,
            reported_date TEXT DEFAULT (date('now')),
            action_taken TEXT,
            status TEXT DEFAULT 'Open',
            follow_up_date TEXT,
            outcome TEXT,
            confidential INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "send_records": """
        CREATE TABLE IF NOT EXISTS send_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id TEXT UNIQUE NOT NULL REFERENCES pupils(pupil_id),
            sen_status TEXT DEFAULT 'SEN Support',
            primary_need TEXT,
            secondary_need TEXT,
            ehcp_status TEXT,
            ehcp_review_date TEXT,
            funding_band TEXT,
            key_worker_staff_id TEXT REFERENCES staff(staff_id),
            external_agencies TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "send_provisions": """
        CREATE TABLE IF NOT EXISTS send_provisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id TEXT NOT NULL REFERENCES pupils(pupil_id),
            provision_type TEXT NOT NULL,
            description TEXT,
            frequency TEXT,
            delivered_by TEXT,
            start_date TEXT,
            review_date TEXT,
            outcome TEXT,
            status TEXT DEFAULT 'Active',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "phonics_results": """
        CREATE TABLE IF NOT EXISTS phonics_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id TEXT NOT NULL REFERENCES pupils(pupil_id),
            academic_year TEXT NOT NULL,
            year_group TEXT NOT NULL,
            score INTEGER,
            threshold INTEGER DEFAULT 32,
            passed INTEGER DEFAULT 0,
            is_resit INTEGER DEFAULT 0,
            assessment_date TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "sats_results": """
        CREATE TABLE IF NOT EXISTS sats_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id TEXT NOT NULL REFERENCES pupils(pupil_id),
            academic_year TEXT NOT NULL,
            key_stage TEXT NOT NULL,
            subject TEXT NOT NULL,
            raw_score INTEGER,
            scaled_score INTEGER,
            outcome TEXT,
            teacher_assessment TEXT,
            assessment_date TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "reading_records": """
        CREATE TABLE IF NOT EXISTS reading_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id TEXT NOT NULL REFERENCES pupils(pupil_id),
            book_title TEXT,
            book_level TEXT,
            pages_read TEXT,
            reading_date TEXT DEFAULT (date('now')),
            read_with TEXT DEFAULT 'Independent',
            fluency TEXT,
            comprehension TEXT,
            comments TEXT,
            recorded_by TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "progress_records": """
        CREATE TABLE IF NOT EXISTS progress_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id TEXT NOT NULL REFERENCES pupils(pupil_id),
            subject_code TEXT NOT NULL,
            term TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            year_group TEXT,
            baseline_level TEXT,
            current_level TEXT,
            target_level TEXT,
            on_track INTEGER DEFAULT 1,
            intervention_needed INTEGER DEFAULT 0,
            comments TEXT,
            assessed_by TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "staff_hr": """
        CREATE TABLE IF NOT EXISTS staff_hr (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id TEXT NOT NULL REFERENCES staff(staff_id),
            record_type TEXT NOT NULL,
            details TEXT,
            start_date TEXT,
            end_date TEXT,
            status TEXT DEFAULT 'Active',
            approved_by TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "staff_leave": """
        CREATE TABLE IF NOT EXISTS staff_leave (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id TEXT NOT NULL REFERENCES staff(staff_id),
            leave_type TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            reason TEXT,
            status TEXT DEFAULT 'Pending',
            approved_by TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "cpd_records": """
        CREATE TABLE IF NOT EXISTS cpd_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id TEXT NOT NULL REFERENCES staff(staff_id),
            title TEXT NOT NULL,
            provider TEXT,
            description TEXT,
            cpd_type TEXT,
            hours REAL,
            completion_date TEXT,
            certificate TEXT,
            impact TEXT,
            status TEXT DEFAULT 'Planned',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "cover_lessons": """
        CREATE TABLE IF NOT EXISTS cover_lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            absent_staff_id TEXT NOT NULL REFERENCES staff(staff_id),
            cover_staff_id TEXT REFERENCES staff(staff_id),
            class_name TEXT NOT NULL,
            date TEXT NOT NULL,
            period INTEGER,
            subject_code TEXT,
            cover_notes TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "finance_transactions": """
        CREATE TABLE IF NOT EXISTS finance_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_type TEXT NOT NULL,
            category TEXT,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            pupil_id TEXT REFERENCES pupils(pupil_id),
            payment_method TEXT,
            reference TEXT,
            transaction_date TEXT DEFAULT (date('now')),
            recorded_by TEXT,
            status TEXT DEFAULT 'Completed',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "finance_budgets": """
        CREATE TABLE IF NOT EXISTS finance_budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            budget_name TEXT NOT NULL,
            category TEXT,
            allocated_amount REAL NOT NULL DEFAULT 0,
            spent_amount REAL NOT NULL DEFAULT 0,
            academic_year TEXT,
            status TEXT DEFAULT 'Active',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "admissions": """
        CREATE TABLE IF NOT EXISTS admissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            date_of_birth TEXT,
            gender TEXT,
            year_group_applied TEXT NOT NULL,
            parent_name TEXT,
            parent_email TEXT,
            parent_phone TEXT,
            address TEXT,
            previous_school TEXT,
            application_date TEXT DEFAULT (date('now')),
            status TEXT DEFAULT 'Pending',
            decision_date TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "clubs": """
        CREATE TABLE IF NOT EXISTS clubs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_name TEXT NOT NULL,
            description TEXT,
            day_of_week TEXT,
            start_time TEXT,
            end_time TEXT,
            location TEXT,
            staff_id TEXT REFERENCES staff(staff_id),
            max_capacity INTEGER,
            year_groups TEXT,
            term TEXT,
            status TEXT DEFAULT 'Active',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "club_members": """
        CREATE TABLE IF NOT EXISTS club_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_id INTEGER NOT NULL REFERENCES clubs(id),
            pupil_id TEXT NOT NULL REFERENCES pupils(pupil_id),
            joined_date TEXT DEFAULT (date('now')),
            status TEXT DEFAULT 'Active',
            UNIQUE(club_id, pupil_id)
        )
    """,
    "meals": """
        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id TEXT NOT NULL REFERENCES pupils(pupil_id),
            date TEXT NOT NULL,
            meal_type TEXT NOT NULL,
            meal_choice TEXT,
            entitlement TEXT DEFAULT 'Paid',
            recorded_by TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(pupil_id, date)
        )
    """,
    "transport": """
        CREATE TABLE IF NOT EXISTS transport (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id TEXT NOT NULL REFERENCES pupils(pupil_id),
            transport_type TEXT NOT NULL,
            route TEXT,
            pickup_point TEXT,
            pickup_time TEXT,
            dropoff_time TEXT,
            contact_name TEXT,
            contact_phone TEXT,
            notes TEXT,
            status TEXT DEFAULT 'Active',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "trips": """
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_name TEXT NOT NULL,
            destination TEXT,
            description TEXT,
            trip_date TEXT NOT NULL,
            return_date TEXT,
            year_groups TEXT,
            lead_staff_id TEXT REFERENCES staff(staff_id),
            cost REAL DEFAULT 0,
            max_places INTEGER,
            risk_assessment INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Planned',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "trip_attendees": """
        CREATE TABLE IF NOT EXISTS trip_attendees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id INTEGER NOT NULL REFERENCES trips(id),
            pupil_id TEXT NOT NULL REFERENCES pupils(pupil_id),
            consent_received INTEGER DEFAULT 0,
            payment_received INTEGER DEFAULT 0,
            medical_info TEXT,
            UNIQUE(trip_id, pupil_id)
        )
    """,
    "library_books": """
        CREATE TABLE IF NOT EXISTS library_books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isbn TEXT,
            title TEXT NOT NULL,
            author TEXT,
            category TEXT,
            reading_level TEXT,
            location TEXT,
            copies INTEGER DEFAULT 1,
            available INTEGER DEFAULT 1,
            status TEXT DEFAULT 'Available',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "library_loans": """
        CREATE TABLE IF NOT EXISTS library_loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL REFERENCES library_books(id),
            pupil_id TEXT NOT NULL REFERENCES pupils(pupil_id),
            loan_date TEXT DEFAULT (date('now')),
            due_date TEXT,
            return_date TEXT,
            status TEXT DEFAULT 'On Loan',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "medical_records": """
        CREATE TABLE IF NOT EXISTS medical_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id TEXT NOT NULL REFERENCES pupils(pupil_id),
            condition TEXT,
            medication TEXT,
            dosage TEXT,
            administration_time TEXT,
            care_plan INTEGER DEFAULT 0,
            allergy TEXT,
            allergy_severity TEXT,
            emergency_protocol TEXT,
            doctor_name TEXT,
            doctor_phone TEXT,
            notes TEXT,
            last_updated TEXT DEFAULT (datetime('now')),
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "consent_records": """
        CREATE TABLE IF NOT EXISTS consent_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id TEXT NOT NULL REFERENCES pupils(pupil_id),
            consent_type TEXT NOT NULL,
            description TEXT,
            granted INTEGER DEFAULT 0,
            granted_by TEXT,
            granted_date TEXT,
            expiry_date TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "pastoral_notes": """
        CREATE TABLE IF NOT EXISTS pastoral_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id TEXT NOT NULL REFERENCES pupils(pupil_id),
            note_type TEXT NOT NULL,
            subject TEXT,
            details TEXT NOT NULL,
            recorded_by TEXT,
            follow_up_required INTEGER DEFAULT 0,
            follow_up_date TEXT,
            status TEXT DEFAULT 'Open',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "parents_evening_events": """
        CREATE TABLE IF NOT EXISTS parents_evening_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            event_date TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            slot_duration INTEGER DEFAULT 10,
            year_groups TEXT,
            status TEXT DEFAULT 'Scheduled',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "parents_evening_slots": """
        CREATE TABLE IF NOT EXISTS parents_evening_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL REFERENCES parents_evening_events(id),
            teacher_staff_id TEXT NOT NULL REFERENCES staff(staff_id),
            pupil_id TEXT REFERENCES pupils(pupil_id),
            slot_time TEXT NOT NULL,
            parent_name TEXT,
            status TEXT DEFAULT 'Available',
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "calendar_events": """
        CREATE TABLE IF NOT EXISTS calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            event_type TEXT DEFAULT 'General',
            start_date TEXT NOT NULL,
            end_date TEXT,
            start_time TEXT,
            end_time TEXT,
            location TEXT,
            all_day INTEGER DEFAULT 0,
            year_groups TEXT,
            created_by TEXT,
            status TEXT DEFAULT 'Active',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "announcements": """
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            audience TEXT DEFAULT 'All',
            priority TEXT DEFAULT 'Normal',
            publish_date TEXT DEFAULT (date('now')),
            expiry_date TEXT,
            created_by TEXT,
            status TEXT DEFAULT 'Active',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "notifications": """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            title TEXT NOT NULL,
            message TEXT,
            notification_type TEXT DEFAULT 'Info',
            is_read INTEGER DEFAULT 0,
            link TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "communication_log": """
        CREATE TABLE IF NOT EXISTS communication_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id TEXT REFERENCES pupils(pupil_id),
            contact_type TEXT NOT NULL,
            contact_with TEXT,
            subject TEXT,
            details TEXT,
            outcome TEXT,
            follow_up_required INTEGER DEFAULT 0,
            follow_up_date TEXT,
            recorded_by TEXT,
            contact_date TEXT DEFAULT (date('now')),
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "email_log": """
        CREATE TABLE IF NOT EXISTS email_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            to_address TEXT NOT NULL,
            from_address TEXT,
            subject TEXT,
            body TEXT,
            status TEXT DEFAULT 'Logged',
            sent_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "room_bookings": """
        CREATE TABLE IF NOT EXISTS room_bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_name TEXT NOT NULL,
            booked_by TEXT NOT NULL,
            purpose TEXT,
            booking_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            recurring INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Confirmed',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "assets": """
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_name TEXT NOT NULL,
            asset_type TEXT,
            serial_number TEXT,
            location TEXT,
            assigned_to TEXT,
            purchase_date TEXT,
            purchase_cost REAL,
            condition TEXT DEFAULT 'Good',
            notes TEXT,
            status TEXT DEFAULT 'In Use',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "visitors": """
        CREATE TABLE IF NOT EXISTS visitors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visitor_name TEXT NOT NULL,
            organisation TEXT,
            purpose TEXT NOT NULL,
            visiting TEXT,
            visit_date TEXT DEFAULT (date('now')),
            sign_in_time TEXT,
            sign_out_time TEXT,
            badge_number TEXT,
            dbs_checked INTEGER DEFAULT 0,
            safeguarding_briefing INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "incidents": """
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_type TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT,
            severity TEXT DEFAULT 'Minor',
            pupil_ids TEXT,
            staff_ids TEXT,
            reported_by TEXT NOT NULL,
            incident_date TEXT DEFAULT (date('now')),
            incident_time TEXT,
            action_taken TEXT,
            parent_notified INTEGER DEFAULT 0,
            first_aid_given INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Open',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "audit_log": """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            action TEXT NOT NULL,
            table_name TEXT,
            record_id TEXT,
            details TEXT,
            ip_address TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "policies": """
        CREATE TABLE IF NOT EXISTS policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT,
            content TEXT,
            version TEXT DEFAULT '1.0',
            approved_by TEXT,
            approval_date TEXT,
            review_date TEXT,
            status TEXT DEFAULT 'Active',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "documents": """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT,
            file_path TEXT,
            file_type TEXT,
            description TEXT,
            uploaded_by TEXT,
            access_level TEXT DEFAULT 'Staff',
            status TEXT DEFAULT 'Active',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "settings": """
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT,
            category TEXT DEFAULT 'General',
            description TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
}


def initialise_database(db_path):
    """Create all tables if they do not already exist."""
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        cursor = conn.cursor()
        for table_name, ddl in TABLES.items():
            cursor.execute(ddl)
        conn.commit()
        logger.info("Database initialised successfully at %s", db_path)
    finally:
        conn.close()


def seed_default_users(db_path):
    """Create default admin, teacher, and parent user accounts on first run."""
    from education_system.primary_school.core.defaults import (
        DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD,
        DEFAULT_TEACHER_USERNAME, DEFAULT_TEACHER_PASSWORD,
        DEFAULT_PARENT_USERNAME, DEFAULT_PARENT_PASSWORD,
    )

    conn = sqlite3.connect(db_path, timeout=30)
    try:
        cursor = conn.cursor()
        defaults = [
            (DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD, "admin", "Administrator"),
            (DEFAULT_TEACHER_USERNAME, DEFAULT_TEACHER_PASSWORD, "teacher", "Default Teacher"),
            (DEFAULT_PARENT_USERNAME, DEFAULT_PARENT_PASSWORD, "parent", "Default Parent"),
        ]
        for username, password, role, display_name in defaults:
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            if not cursor.fetchone():
                pw_hash = hash_password(password)
                cursor.execute(
                    "INSERT INTO users (username, password_hash, role, display_name) VALUES (?, ?, ?, ?)",
                    (username, pw_hash, role, display_name),
                )
                logger.info("Created default %s user: %s", role, username)
        conn.commit()
    finally:
        conn.close()
