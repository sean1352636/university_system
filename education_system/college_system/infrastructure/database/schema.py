"""Database schema definitions and initialization."""

import sqlite3
import logging
from datetime import datetime

from education_system.college_system.infrastructure.database.db import connect, get_db_path

logger = logging.getLogger(__name__)

TABLES = {
    "users": """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student',
            email TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            failed_login_attempts INTEGER NOT NULL DEFAULT 0,
            locked_until TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "sessions": """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """,
    "students": """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE NOT NULL,
            user_id INTEGER,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            date_of_birth TEXT,
            address TEXT,
            major TEXT,
            year_group TEXT DEFAULT '12',
            form_group TEXT,
            form_tutor TEXT,
            enrollment_date TEXT NOT NULL DEFAULT (date('now')),
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """,
    "courses": """
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_code TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            credits INTEGER NOT NULL DEFAULT 3,
            capacity INTEGER NOT NULL DEFAULT 30,
            department TEXT,
            instructor TEXT,
            semester TEXT,
            schedule TEXT,
            qualification_type TEXT DEFAULT 'A-Level',
            subject_area TEXT,
            teacher TEXT,
            term TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "prerequisites": """
        CREATE TABLE IF NOT EXISTS prerequisites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            prerequisite_id INTEGER NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses(id),
            FOREIGN KEY (prerequisite_id) REFERENCES courses(id),
            UNIQUE(course_id, prerequisite_id)
        )
    """,
    "enrollments": """
        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'enrolled',
            enrolled_at TEXT NOT NULL DEFAULT (datetime('now')),
            dropped_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (course_id) REFERENCES courses(id),
            UNIQUE(student_id, course_id)
        )
    """,
    "waitlist": """
        CREATE TABLE IF NOT EXISTS waitlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            added_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (course_id) REFERENCES courses(id),
            UNIQUE(student_id, course_id)
        )
    """,
    "grades": """
        CREATE TABLE IF NOT EXISTS grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            score REAL,
            letter_grade TEXT,
            semester TEXT,
            grade_type TEXT DEFAULT 'actual',
            predicted_grade TEXT,
            term TEXT,
            recorded_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            recorded_by TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (course_id) REFERENCES courses(id),
            UNIQUE(student_id, course_id, grade_type)
        )
    """,
    "attendance_sessions": """
        CREATE TABLE IF NOT EXISTS attendance_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            session_date TEXT NOT NULL,
            topic TEXT,
            created_by TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (course_id) REFERENCES courses(id)
        )
    """,
    "attendance_records": """
        CREATE TABLE IF NOT EXISTS attendance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'absent',
            notes TEXT,
            recorded_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (session_id) REFERENCES attendance_sessions(id),
            FOREIGN KEY (student_id) REFERENCES students(id),
            UNIQUE(session_id, student_id)
        )
    """,
    "roles": """
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            level INTEGER NOT NULL DEFAULT 0
        )
    """,
    "permissions": """
        CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_id INTEGER NOT NULL,
            resource TEXT NOT NULL,
            action TEXT NOT NULL,
            FOREIGN KEY (role_id) REFERENCES roles(id),
            UNIQUE(role_id, resource, action)
        )
    """,
    "audit_log": """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            action TEXT NOT NULL,
            resource TEXT,
            details TEXT,
            ip_address TEXT,
            timestamp TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "timetable_slots": """
        CREATE TABLE IF NOT EXISTS timetable_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            day_of_week TEXT NOT NULL CHECK(day_of_week IN ('Mon','Tue','Wed','Thu','Fri')),
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            room TEXT,
            instructor_name TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (course_id) REFERENCES courses(id)
        )
    """,
    "assignments": """
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            due_date TEXT NOT NULL,
            max_score REAL NOT NULL DEFAULT 100,
            allow_late INTEGER NOT NULL DEFAULT 0,
            created_by INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (course_id) REFERENCES courses(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """,
    "submissions": """
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            content TEXT,
            submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
            is_late INTEGER NOT NULL DEFAULT 0,
            score REAL,
            feedback TEXT,
            graded_by INTEGER,
            graded_at TEXT,
            FOREIGN KEY (assignment_id) REFERENCES assignments(id),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (graded_by) REFERENCES users(id)
        )
    """,
    "notifications": """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT,
            type TEXT NOT NULL DEFAULT 'info' CHECK(type IN ('info','success','warning','alert')),
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """,
    "mfa_secrets": """
        CREATE TABLE IF NOT EXISTS mfa_secrets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            totp_secret TEXT NOT NULL,
            is_enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """,
    "mfa_recovery_codes": """
        CREATE TABLE IF NOT EXISTS mfa_recovery_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            code_hash TEXT NOT NULL,
            is_used INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """,
    "staff": """
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id TEXT UNIQUE NOT NULL,
            user_id INTEGER,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            title TEXT DEFAULT '',
            email TEXT,
            phone TEXT,
            subject_area TEXT,
            form_group TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """,
    "messages": """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            recipient_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            body TEXT,
            is_read INTEGER NOT NULL DEFAULT 0,
            sender_deleted INTEGER NOT NULL DEFAULT 0,
            recipient_deleted INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (sender_id) REFERENCES users(id),
            FOREIGN KEY (recipient_id) REFERENCES users(id)
        )
    """,
    "todo_items": """
        CREATE TABLE IF NOT EXISTS todo_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            priority TEXT NOT NULL DEFAULT 'medium' CHECK(priority IN ('low','medium','high')),
            due_date TEXT,
            is_completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """,
    "calendar_events": """
        CREATE TABLE IF NOT EXISTS calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            event_date TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            event_type TEXT NOT NULL DEFAULT 'personal' CHECK(event_type IN ('personal','academic','college','deadline')),
            is_all_day INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """,
    "first_aid_incidents": """
        CREATE TABLE IF NOT EXISTS first_aid_incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reported_by INTEGER NOT NULL,
            student_id INTEGER,
            incident_date TEXT NOT NULL DEFAULT (date('now')),
            incident_time TEXT,
            location TEXT,
            description TEXT NOT NULL,
            treatment TEXT,
            severity TEXT NOT NULL DEFAULT 'minor' CHECK(severity IN ('minor','moderate','severe','emergency')),
            status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','treated','referred','closed')),
            treated_by TEXT,
            parent_notified INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (reported_by) REFERENCES users(id),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "helpdesk_tickets": """
        CREATE TABLE IF NOT EXISTS helpdesk_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general' CHECK(category IN ('general','it','facilities','academic','finance','other')),
            priority TEXT NOT NULL DEFAULT 'medium' CHECK(priority IN ('low','medium','high','urgent')),
            status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','in_progress','resolved','closed')),
            assigned_to INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (assigned_to) REFERENCES users(id)
        )
    """,
    "helpdesk_responses": """
        CREATE TABLE IF NOT EXISTS helpdesk_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (ticket_id) REFERENCES helpdesk_tickets(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """,
    "parent_links": """
        CREATE TABLE IF NOT EXISTS parent_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_user_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            relationship TEXT DEFAULT 'parent',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (parent_user_id) REFERENCES users(id),
            FOREIGN KEY (student_id) REFERENCES students(id),
            UNIQUE(parent_user_id, student_id)
        )
    """,
    "user_settings": """
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            setting_key TEXT NOT NULL,
            setting_value TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, setting_key)
        )
    """,
    "system_settings": """
        CREATE TABLE IF NOT EXISTS system_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_key TEXT UNIQUE NOT NULL,
            setting_value TEXT,
            updated_by INTEGER,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (updated_by) REFERENCES users(id)
        )
    """,
    # ---- Student Lifecycle ----
    "applications": """
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            applicant_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            date_of_birth TEXT,
            address TEXT,
            previous_school TEXT,
            course_preferences TEXT,
            gcse_results TEXT,
            personal_statement TEXT,
            status TEXT NOT NULL DEFAULT 'enquiry'
                CHECK(status IN ('enquiry','applied','conditional_offer',
                      'unconditional_offer','accepted','enrolled','rejected','withdrawn')),
            notes TEXT,
            applied_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "inductions": """
        CREATE TABLE IF NOT EXISTS inductions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            consent_form INTEGER NOT NULL DEFAULT 0,
            learning_agreement INTEGER NOT NULL DEFAULT 0,
            photo_id INTEGER NOT NULL DEFAULT 0,
            ict_acceptable_use INTEGER NOT NULL DEFAULT 0,
            emergency_contact TEXT,
            medical_info TEXT,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK(status IN ('pending','in_progress','completed')),
            completed_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "withdrawals": """
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            withdrawal_date TEXT NOT NULL DEFAULT (date('now')),
            reason TEXT,
            destination TEXT,
            destination_type TEXT DEFAULT 'unknown'
                CHECK(destination_type IN ('employment','another_provider',
                      'university','apprenticeship','neet','unknown','other')),
            exit_interview INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            recorded_by INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (recorded_by) REFERENCES users(id)
        )
    """,
    # ---- Pastoral ----
    "safeguarding_concerns": """
        CREATE TABLE IF NOT EXISTS safeguarding_concerns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            reported_by INTEGER NOT NULL,
            concern_date TEXT NOT NULL DEFAULT (date('now')),
            category TEXT NOT NULL DEFAULT 'other'
                CHECK(category IN ('abuse','neglect','exploitation',
                      'self_harm','radicalisation','other')),
            description TEXT NOT NULL,
            risk_level TEXT NOT NULL DEFAULT 'low'
                CHECK(risk_level IN ('low','medium','high','critical')),
            status TEXT NOT NULL DEFAULT 'reported'
                CHECK(status IN ('reported','under_review','action_taken',
                      'referred','closed')),
            assigned_to INTEGER,
            actions_taken TEXT,
            referral_agency TEXT,
            parent_informed INTEGER NOT NULL DEFAULT 0,
            confidential INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (reported_by) REFERENCES users(id),
            FOREIGN KEY (assigned_to) REFERENCES users(id)
        )
    """,
    "behaviour_records": """
        CREATE TABLE IF NOT EXISTS behaviour_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            recorded_by INTEGER NOT NULL,
            incident_date TEXT NOT NULL DEFAULT (date('now')),
            type TEXT NOT NULL DEFAULT 'concern'
                CHECK(type IN ('detention','sanction','reward','exclusion','concern')),
            category TEXT NOT NULL DEFAULT 'other'
                CHECK(category IN ('punctuality','uniform','disruption',
                      'achievement','community','other')),
            points INTEGER NOT NULL DEFAULT 0,
            description TEXT,
            action_taken TEXT,
            parent_notified INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'recorded'
                CHECK(status IN ('recorded','actioned','resolved')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (recorded_by) REFERENCES users(id)
        )
    """,
    "pastoral_notes": """
        CREATE TABLE IF NOT EXISTS pastoral_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            author_id INTEGER NOT NULL,
            note_date TEXT NOT NULL DEFAULT (date('now')),
            category TEXT NOT NULL DEFAULT 'general'
                CHECK(category IN ('general','academic','welfare',
                      'behaviour','attendance','family')),
            content TEXT NOT NULL,
            is_confidential INTEGER NOT NULL DEFAULT 0,
            follow_up_required INTEGER NOT NULL DEFAULT 0,
            follow_up_date TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (author_id) REFERENCES users(id)
        )
    """,
    "wellbeing_records": """
        CREATE TABLE IF NOT EXISTS wellbeing_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            recorded_by INTEGER NOT NULL,
            record_date TEXT NOT NULL DEFAULT (date('now')),
            type TEXT NOT NULL DEFAULT 'check_in'
                CHECK(type IN ('check_in','support_plan','referral','review')),
            wellbeing_score INTEGER,
            concerns TEXT,
            actions TEXT,
            referral_to TEXT,
            next_review_date TEXT,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK(status IN ('active','monitoring','closed')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (recorded_by) REFERENCES users(id)
        )
    """,
    "lac_records": """
        CREATE TABLE IF NOT EXISTS lac_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'lac'
                CHECK(status IN ('lac','care_leaver','previously_lac','child_in_need')),
            social_worker_name TEXT,
            social_worker_contact TEXT,
            virtual_school_contact TEXT,
            pep_date TEXT,
            pupil_premium_plus INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    # ---- Learning Support ----
    "send_records": """
        CREATE TABLE IF NOT EXISTS send_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL UNIQUE,
            send_status TEXT NOT NULL DEFAULT 'none'
                CHECK(send_status IN ('none','send_support','ehcp','monitoring')),
            primary_need TEXT DEFAULT 'other'
                CHECK(primary_need IN ('cognition','communication','semh',
                      'sensory_physical','other')),
            ehcp_review_date TEXT,
            support_plan TEXT,
            exam_access TEXT,
            extra_time_percent INTEGER NOT NULL DEFAULT 0,
            reader INTEGER NOT NULL DEFAULT 0,
            scribe INTEGER NOT NULL DEFAULT 0,
            rest_breaks INTEGER NOT NULL DEFAULT 0,
            funding_band TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "interventions": """
        CREATE TABLE IF NOT EXISTS interventions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            staff_id INTEGER NOT NULL,
            intervention_type TEXT NOT NULL DEFAULT 'academic'
                CHECK(intervention_type IN ('academic','attendance',
                      'behaviour','wellbeing')),
            subject_area TEXT,
            description TEXT NOT NULL,
            start_date TEXT,
            end_date TEXT,
            sessions_planned INTEGER NOT NULL DEFAULT 0,
            sessions_attended INTEGER NOT NULL DEFAULT 0,
            outcome TEXT,
            status TEXT NOT NULL DEFAULT 'planned'
                CHECK(status IN ('planned','active','completed','cancelled')),
            impact_rating TEXT
                CHECK(impact_rating IN ('no_impact','some_impact',
                      'significant_impact') OR impact_rating IS NULL),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (staff_id) REFERENCES users(id)
        )
    """,
    # ---- Exams & Assessment ----
    "exam_entries": """
        CREATE TABLE IF NOT EXISTS exam_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            exam_board TEXT,
            qualification TEXT,
            unit_code TEXT,
            entry_date TEXT,
            exam_series TEXT,
            tier TEXT,
            fee REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'planned'
                CHECK(status IN ('planned','entered','amended','withdrawn')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (course_id) REFERENCES courses(id)
        )
    """,
    "exam_timetable": """
        CREATE TABLE IF NOT EXISTS exam_timetable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_entry_id INTEGER NOT NULL,
            exam_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            room TEXT,
            seat_number TEXT,
            invigilator TEXT,
            clash_resolved INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (exam_entry_id) REFERENCES exam_entries(id)
        )
    """,
    "exam_access": """
        CREATE TABLE IF NOT EXISTS exam_access (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            arrangement_type TEXT NOT NULL
                CHECK(arrangement_type IN ('extra_time','reader','scribe',
                      'rest_breaks','word_processor','separate_room','other')),
            detail TEXT,
            percentage INTEGER,
            approved_by TEXT,
            evidence_held INTEGER NOT NULL DEFAULT 0,
            valid_from TEXT,
            valid_until TEXT,
            jcq_form_complete INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            UNIQUE(student_id, arrangement_type)
        )
    """,
    "exam_results": """
        CREATE TABLE IF NOT EXISTS exam_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            exam_board TEXT,
            qualification TEXT,
            unit_code TEXT,
            grade TEXT,
            ums_score REAL,
            raw_mark REAL,
            max_mark REAL,
            series TEXT,
            result_date TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (course_id) REFERENCES courses(id)
        )
    """,
    # ---- Compliance / Funding ----
    "funding_records": """
        CREATE TABLE IF NOT EXISTS funding_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            learning_aim TEXT,
            aim_type TEXT,
            funding_model TEXT DEFAULT '16-19',
            planned_hours INTEGER NOT NULL DEFAULT 0,
            actual_hours INTEGER NOT NULL DEFAULT 0,
            start_date TEXT,
            planned_end_date TEXT,
            actual_end_date TEXT,
            completion_status TEXT NOT NULL DEFAULT 'in_progress'
                CHECK(completion_status IN ('in_progress','completed',
                      'withdrawn','transferred')),
            outcome TEXT
                CHECK(outcome IN ('achieved','not_achieved','partial')
                      OR outcome IS NULL),
            withdrawal_reason TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "resit_tracking": """
        CREATE TABLE IF NOT EXISTS resit_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject TEXT NOT NULL CHECK(subject IN ('english','maths')),
            gcse_grade_on_entry TEXT,
            current_level TEXT,
            target_grade TEXT,
            resit_required INTEGER NOT NULL DEFAULT 1,
            exam_entries_count INTEGER NOT NULL DEFAULT 0,
            latest_result TEXT,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK(status IN ('active','achieved','exempt','continuing')),
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            UNIQUE(student_id, subject)
        )
    """,
    "destinations": """
        CREATE TABLE IF NOT EXISTS destinations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            academic_year TEXT,
            intended_destination TEXT,
            confirmed_destination TEXT,
            destination_type TEXT DEFAULT 'unknown'
                CHECK(destination_type IN ('university','apprenticeship',
                      'employment','further_education','gap_year','neet','unknown')),
            institution_name TEXT,
            course_title TEXT,
            neet_risk INTEGER NOT NULL DEFAULT 0,
            contact_made INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    # ---- Reports ----
    "progress_reports": """
        CREATE TABLE IF NOT EXISTS progress_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            report_type TEXT NOT NULL DEFAULT 'interim'
                CHECK(report_type IN ('interim','full','final')),
            academic_year TEXT,
            term TEXT,
            overall_comment TEXT,
            tutor_comment TEXT,
            status TEXT NOT NULL DEFAULT 'draft'
                CHECK(status IN ('draft','published','sent')),
            published_at TEXT,
            created_by INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """,
    "report_entries": """
        CREATE TABLE IF NOT EXISTS report_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            effort_grade TEXT,
            attainment_grade TEXT,
            target_grade TEXT,
            teacher_comment TEXT,
            attendance_rate REAL,
            FOREIGN KEY (report_id) REFERENCES progress_reports(id),
            FOREIGN KEY (course_id) REFERENCES courses(id)
        )
    """,
    # ---- Parents Evening ----
    "parents_evenings": """
        CREATE TABLE IF NOT EXISTS parents_evenings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            academic_year TEXT,
            term TEXT,
            event_date TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            slot_duration INTEGER NOT NULL DEFAULT 5,
            status TEXT NOT NULL DEFAULT 'scheduled'
                CHECK(status IN ('scheduled','open','closed','completed')),
            created_by INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """,
    "parents_evening_slots": """
        CREATE TABLE IF NOT EXISTS parents_evening_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evening_id INTEGER NOT NULL,
            staff_id INTEGER NOT NULL,
            parent_user_id INTEGER,
            student_id INTEGER,
            slot_time TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'available'
                CHECK(status IN ('available','booked','completed','cancelled')),
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (evening_id) REFERENCES parents_evenings(id),
            FOREIGN KEY (staff_id) REFERENCES users(id),
            FOREIGN KEY (parent_user_id) REFERENCES users(id),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    # ---- Careers / Progression ----
    "careers_activities": """
        CREATE TABLE IF NOT EXISTS careers_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            activity_date TEXT NOT NULL DEFAULT (date('now')),
            activity_type TEXT NOT NULL DEFAULT 'encounter'
                CHECK(activity_type IN ('encounter','workshop','talk','fair',
                      'guidance','mentoring','workplace_visit')),
            gatsby_benchmark INTEGER,
            provider TEXT,
            description TEXT,
            duration_minutes INTEGER,
            recorded_by INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (recorded_by) REFERENCES users(id)
        )
    """,
    "ucas_records": """
        CREATE TABLE IF NOT EXISTS ucas_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL UNIQUE,
            ucas_id TEXT,
            personal_statement TEXT,
            reference_text TEXT,
            referee_id INTEGER,
            predicted_grades TEXT,
            choices TEXT,
            application_status TEXT NOT NULL DEFAULT 'not_started'
                CHECK(application_status IN ('not_started','in_progress',
                      'submitted','offers_received','firm_choice_made')),
            firm_choice TEXT,
            insurance_choice TEXT,
            deadline_date TEXT,
            submitted_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (referee_id) REFERENCES users(id)
        )
    """,
    "work_experience": """
        CREATE TABLE IF NOT EXISTS work_experience (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            employer_name TEXT NOT NULL,
            employer_contact TEXT,
            placement_address TEXT,
            start_date TEXT,
            end_date TEXT,
            hours_per_week REAL,
            role TEXT,
            dbs_checked INTEGER NOT NULL DEFAULT 0,
            risk_assessment INTEGER NOT NULL DEFAULT 0,
            insurance_confirmed INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'planned'
                CHECK(status IN ('planned','approved','in_progress',
                      'completed','cancelled')),
            student_evaluation TEXT,
            employer_evaluation TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    # ---- Ops ----
    "bursary_records": """
        CREATE TABLE IF NOT EXISTS bursary_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            bursary_type TEXT NOT NULL DEFAULT 'discretionary'
                CHECK(bursary_type IN ('vulnerable','discretionary',
                      'free_meals','in_kind')),
            amount REAL NOT NULL DEFAULT 0,
            evidence_type TEXT,
            evidence_verified INTEGER NOT NULL DEFAULT 0,
            award_date TEXT,
            academic_year TEXT,
            payment_frequency TEXT DEFAULT 'one_off'
                CHECK(payment_frequency IN ('one_off','weekly','termly')),
            status TEXT NOT NULL DEFAULT 'applied'
                CHECK(status IN ('applied','approved','active',
                      'expired','rejected')),
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "meal_eligibility": """
        CREATE TABLE IF NOT EXISTS meal_eligibility (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL UNIQUE,
            eligible INTEGER NOT NULL DEFAULT 0,
            eligibility_type TEXT DEFAULT 'fsm'
                CHECK(eligibility_type IN ('fsm','fsm_ever6','universal')),
            evidence_checked INTEGER NOT NULL DEFAULT 0,
            start_date TEXT,
            end_date TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "transport_records": """
        CREATE TABLE IF NOT EXISTS transport_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            transport_type TEXT NOT NULL DEFAULT 'bus_pass'
                CHECK(transport_type IN ('bus_pass','train_pass','taxi',
                      'walking','cycling','driving')),
            route TEXT,
            pass_number TEXT,
            provider TEXT,
            eligible INTEGER NOT NULL DEFAULT 0,
            start_date TEXT,
            end_date TEXT,
            cost REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK(status IN ('active','expired','cancelled')),
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "asset_loans": """
        CREATE TABLE IF NOT EXISTS asset_loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            asset_type TEXT NOT NULL DEFAULT 'other'
                CHECK(asset_type IN ('chromebook','laptop','calculator',
                      'textbook','other')),
            asset_tag TEXT,
            description TEXT NOT NULL,
            loaned_date TEXT NOT NULL DEFAULT (date('now')),
            due_date TEXT,
            returned_date TEXT,
            condition_out TEXT NOT NULL DEFAULT 'good',
            condition_in TEXT,
            status TEXT NOT NULL DEFAULT 'on_loan'
                CHECK(status IN ('on_loan','returned','overdue','lost','damaged')),
            recorded_by INTEGER,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (recorded_by) REFERENCES users(id)
        )
    """,
    "library_items": """
        CREATE TABLE IF NOT EXISTS library_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT,
            isbn TEXT,
            category TEXT DEFAULT 'textbook'
                CHECK(category IN ('textbook','reference','fiction','periodical')),
            location TEXT,
            total_copies INTEGER NOT NULL DEFAULT 1,
            available_copies INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "library_loans": """
        CREATE TABLE IF NOT EXISTS library_loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            loaned_date TEXT NOT NULL DEFAULT (date('now')),
            due_date TEXT NOT NULL,
            returned_date TEXT,
            status TEXT NOT NULL DEFAULT 'on_loan'
                CHECK(status IN ('on_loan','returned','overdue','lost')),
            recorded_by INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (item_id) REFERENCES library_items(id),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (recorded_by) REFERENCES users(id)
        )
    """,
    # ---- Staff / Admin ----
    "staff_hr": """
        CREATE TABLE IF NOT EXISTS staff_hr (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL UNIQUE,
            contract_type TEXT DEFAULT 'full_time'
                CHECK(contract_type IN ('full_time','part_time','fixed_term',
                      'agency','volunteer')),
            contract_start TEXT,
            contract_end TEXT,
            dbs_number TEXT,
            dbs_date TEXT,
            dbs_status TEXT DEFAULT 'pending'
                CHECK(dbs_status IN ('clear','pending','expired')),
            safeguarding_training_date TEXT,
            safeguarding_training_expiry TEXT,
            first_aid_trained INTEGER NOT NULL DEFAULT 0,
            prevent_trained INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (staff_id) REFERENCES staff(id)
        )
    """,
    "cover_arrangements": """
        CREATE TABLE IF NOT EXISTS cover_arrangements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            absent_staff_id INTEGER NOT NULL,
            cover_staff_id INTEGER,
            timetable_slot_id INTEGER,
            cover_date TEXT NOT NULL,
            reason TEXT,
            status TEXT NOT NULL DEFAULT 'requested'
                CHECK(status IN ('requested','confirmed','completed','cancelled')),
            notes TEXT,
            arranged_by INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (absent_staff_id) REFERENCES users(id),
            FOREIGN KEY (cover_staff_id) REFERENCES users(id),
            FOREIGN KEY (timetable_slot_id) REFERENCES timetable_slots(id),
            FOREIGN KEY (arranged_by) REFERENCES users(id)
        )
    """,
    # ---- Student Support ----
    "support_interventions": """
        CREATE TABLE IF NOT EXISTS support_interventions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            staff_id INTEGER NOT NULL,
            intervention_type TEXT NOT NULL DEFAULT 'academic'
                CHECK(intervention_type IN ('academic','attendance','behaviour',
                      'wellbeing','mentoring')),
            targets TEXT,
            sessions_planned INTEGER NOT NULL DEFAULT 0,
            sessions_attended INTEGER NOT NULL DEFAULT 0,
            outcome TEXT,
            impact_rating TEXT
                CHECK(impact_rating IN ('none','some','significant')
                      OR impact_rating IS NULL),
            status TEXT NOT NULL DEFAULT 'planned'
                CHECK(status IN ('planned','active','completed','cancelled')),
            review_date TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (staff_id) REFERENCES users(id)
        )
    """,
    "risk_register": """
        CREATE TABLE IF NOT EXISTS risk_register (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            risk_type TEXT NOT NULL DEFAULT 'academic'
                CHECK(risk_type IN ('academic','attendance','behaviour',
                      'wellbeing','safeguarding','financial','neet')),
            risk_level TEXT NOT NULL DEFAULT 'low'
                CHECK(risk_level IN ('low','medium','high','critical')),
            identified_by INTEGER NOT NULL,
            mitigations TEXT,
            status TEXT NOT NULL DEFAULT 'open'
                CHECK(status IN ('open','monitoring','escalated','resolved')),
            resolved_date TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (identified_by) REFERENCES users(id)
        )
    """,
    "student_documents": """
        CREATE TABLE IF NOT EXISTS student_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            document_type TEXT NOT NULL DEFAULT 'other'
                CHECK(document_type IN ('consent_form','id_document','ehcp',
                      'medical','reference','other')),
            title TEXT NOT NULL,
            file_path TEXT,
            uploaded_by INTEGER NOT NULL,
            expiry_date TEXT,
            verified INTEGER NOT NULL DEFAULT 0,
            verified_by INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (uploaded_by) REFERENCES users(id),
            FOREIGN KEY (verified_by) REFERENCES users(id)
        )
    """,
    # ---- Finance ----
    "fee_items": """
        CREATE TABLE IF NOT EXISTS fee_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            fee_type TEXT NOT NULL DEFAULT 'tuition'
                CHECK(fee_type IN ('tuition','exam','trip','materials','other')),
            amount REAL NOT NULL DEFAULT 0,
            academic_year TEXT,
            mandatory INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "invoices": """
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            fee_item_id INTEGER NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            due_date TEXT,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK(status IN ('pending','paid','overdue','cancelled','partial')),
            paid_amount REAL NOT NULL DEFAULT 0,
            paid_date TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (fee_item_id) REFERENCES fee_items(id)
        )
    """,
    "payments": """
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            payment_method TEXT NOT NULL DEFAULT 'cash'
                CHECK(payment_method IN ('cash','card','bank_transfer',
                      'bursary_offset')),
            reference TEXT,
            recorded_by INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (invoice_id) REFERENCES invoices(id),
            FOREIGN KEY (recorded_by) REFERENCES users(id)
        )
    """,
    "payroll_records": """
        CREATE TABLE IF NOT EXISTS payroll_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            pay_period TEXT NOT NULL,
            gross_pay REAL NOT NULL DEFAULT 0,
            deductions REAL NOT NULL DEFAULT 0,
            net_pay REAL NOT NULL DEFAULT 0,
            payment_date TEXT,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK(status IN ('pending','processed','paid')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (staff_id) REFERENCES staff(id)
        )
    """,
    # ---- Rooms ----
    "rooms": """
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_code TEXT UNIQUE NOT NULL,
            building TEXT,
            floor TEXT,
            room_type TEXT NOT NULL DEFAULT 'classroom'
                CHECK(room_type IN ('classroom','lab','workshop','lecture_hall',
                      'it_suite','office','other')),
            capacity INTEGER NOT NULL DEFAULT 30,
            has_projector INTEGER NOT NULL DEFAULT 0,
            has_whiteboard INTEGER NOT NULL DEFAULT 1,
            has_computers INTEGER NOT NULL DEFAULT 0,
            wheelchair_accessible INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK(status IN ('active','maintenance','decommissioned')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "room_resources": """
        CREATE TABLE IF NOT EXISTS room_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            resource_name TEXT NOT NULL,
            resource_type TEXT NOT NULL DEFAULT 'equipment'
                CHECK(resource_type IN ('equipment','software','furniture')),
            quantity INTEGER NOT NULL DEFAULT 1,
            condition TEXT NOT NULL DEFAULT 'good'
                CHECK(condition IN ('good','fair','poor','broken')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (room_id) REFERENCES rooms(id)
        )
    """,
    # ---- Departments ----
    "departments": """
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            faculty TEXT,
            head_of_department INTEGER,
            curriculum_area TEXT,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK(status IN ('active','inactive')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (head_of_department) REFERENCES users(id)
        )
    """,
    # ---- Groups ----
    "tutor_groups": """
        CREATE TABLE IF NOT EXISTS tutor_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            year_group TEXT,
            tutor_id INTEGER,
            room_id INTEGER,
            max_size INTEGER NOT NULL DEFAULT 30,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (tutor_id) REFERENCES users(id),
            FOREIGN KEY (room_id) REFERENCES rooms(id)
        )
    """,
    "teaching_groups": """
        CREATE TABLE IF NOT EXISTS teaching_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            course_id INTEGER NOT NULL,
            academic_year TEXT,
            max_size INTEGER NOT NULL DEFAULT 30,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (course_id) REFERENCES courses(id)
        )
    """,
    "group_members": """
        CREATE TABLE IF NOT EXISTS group_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            group_type TEXT NOT NULL CHECK(group_type IN ('tutor','teaching')),
            student_id INTEGER NOT NULL,
            joined_date TEXT NOT NULL DEFAULT (date('now')),
            left_date TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    # ---- Compliance Enhancement ----
    "funding_evidence": """
        CREATE TABLE IF NOT EXISTS funding_evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            funding_record_id INTEGER NOT NULL,
            evidence_type TEXT NOT NULL DEFAULT 'other'
                CHECK(evidence_type IN ('enrollment_form','learning_agreement',
                      'attendance_evidence','completion_evidence','other')),
            file_path TEXT,
            verified INTEGER NOT NULL DEFAULT 0,
            verified_by INTEGER,
            verified_date TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (funding_record_id) REFERENCES funding_records(id),
            FOREIGN KEY (verified_by) REFERENCES users(id)
        )
    """,
    "funding_rules": """
        CREATE TABLE IF NOT EXISTS funding_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_code TEXT UNIQUE NOT NULL,
            description TEXT,
            rule_type TEXT NOT NULL DEFAULT 'eligibility'
                CHECK(rule_type IN ('eligibility','hours','completion','withdrawal')),
            applies_to TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ================================================================
    # NEW FEATURE TABLES (40 modules, 84 tables)
    # ================================================================
    # ---- CPD ----
    "cpd_records": """
        CREATE TABLE IF NOT EXISTS cpd_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            provider TEXT,
            cpd_type TEXT NOT NULL DEFAULT 'course',
            hours REAL NOT NULL DEFAULT 0,
            certification TEXT,
            expiry_date TEXT,
            evidence TEXT,
            reflection TEXT,
            status TEXT NOT NULL DEFAULT 'completed',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "cpd_targets": """
        CREATE TABLE IF NOT EXISTS cpd_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            academic_year TEXT NOT NULL,
            target_hours REAL NOT NULL DEFAULT 30,
            achieved_hours REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Observations ----
    "teaching_observations": """
        CREATE TABLE IF NOT EXISTS teaching_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            observer_id INTEGER,
            scheduled_date TEXT,
            course_id INTEGER,
            observation_type TEXT NOT NULL DEFAULT 'formal',
            grade TEXT,
            strengths TEXT,
            areas_for_development TEXT,
            action_points TEXT,
            status TEXT NOT NULL DEFAULT 'scheduled',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Appraisals ----
    "appraisals": """
        CREATE TABLE IF NOT EXISTS appraisals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            appraiser_id INTEGER,
            academic_year TEXT NOT NULL,
            appraisal_type TEXT NOT NULL DEFAULT 'annual',
            overall_rating TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "appraisal_objectives": """
        CREATE TABLE IF NOT EXISTS appraisal_objectives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appraisal_id INTEGER NOT NULL REFERENCES appraisals(id),
            objective_text TEXT NOT NULL,
            success_criteria TEXT,
            progress_notes TEXT,
            status TEXT NOT NULL DEFAULT 'in_progress',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Resource Booking ----
    "bookable_resources": """
        CREATE TABLE IF NOT EXISTS bookable_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            resource_type TEXT NOT NULL DEFAULT 'room',
            location TEXT,
            capacity INTEGER,
            is_available INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "resource_bookings": """
        CREATE TABLE IF NOT EXISTS resource_bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_id INTEGER NOT NULL REFERENCES bookable_resources(id),
            booked_by INTEGER NOT NULL,
            booking_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            purpose TEXT,
            status TEXT NOT NULL DEFAULT 'confirmed',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Markbook ----
    "markbook_columns": """
        CREATE TABLE IF NOT EXISTS markbook_columns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            column_name TEXT NOT NULL,
            column_type TEXT NOT NULL DEFAULT 'score',
            max_score REAL,
            weight REAL NOT NULL DEFAULT 1.0,
            due_date TEXT,
            display_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "markbook_entries": """
        CREATE TABLE IF NOT EXISTS markbook_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            column_id INTEGER NOT NULL REFERENCES markbook_columns(id),
            student_id INTEGER NOT NULL,
            value TEXT,
            score REAL,
            comment TEXT,
            entered_by INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Staff Wellbeing ----
    "wellbeing_checkins": """
        CREATE TABLE IF NOT EXISTS wellbeing_checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            checkin_date TEXT NOT NULL DEFAULT (date('now')),
            mood_rating INTEGER NOT NULL DEFAULT 3,
            workload_rating INTEGER NOT NULL DEFAULT 3,
            stress_level TEXT,
            notes TEXT,
            confidential INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "rtw_interviews": """
        CREATE TABLE IF NOT EXISTS rtw_interviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            absence_start TEXT NOT NULL,
            absence_end TEXT NOT NULL,
            return_date TEXT NOT NULL,
            interviewer_id INTEGER,
            reason_category TEXT,
            adjustments TEXT,
            oh_referral INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Lesson Plans ----
    "lesson_plans": """
        CREATE TABLE IF NOT EXISTS lesson_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            lesson_date TEXT NOT NULL,
            topic TEXT NOT NULL,
            learning_objectives TEXT,
            starter_activity TEXT,
            main_activity TEXT,
            plenary TEXT,
            differentiation TEXT,
            resources TEXT,
            homework TEXT,
            reflection TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Data Dashboard ----
    "dashboard_widgets": """
        CREATE TABLE IF NOT EXISTS dashboard_widgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            widget_type TEXT NOT NULL,
            config TEXT,
            display_order INTEGER NOT NULL DEFAULT 0,
            is_visible INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "saved_reports": """
        CREATE TABLE IF NOT EXISTS saved_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            report_name TEXT NOT NULL,
            report_type TEXT NOT NULL,
            parameters TEXT,
            last_run TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Absence Requests ----
    "absence_requests": """
        CREATE TABLE IF NOT EXISTS absence_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            absence_type TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            reason TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            approved_by INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "swap_requests": """
        CREATE TABLE IF NOT EXISTS swap_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            original_slot_id INTEGER,
            swap_slot_id INTEGER,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Intervention Tracking ----
    "academic_interventions": """
        CREATE TABLE IF NOT EXISTS academic_interventions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            staff_id INTEGER NOT NULL,
            intervention_type TEXT NOT NULL,
            subject_area TEXT,
            sessions_total INTEGER NOT NULL DEFAULT 0,
            sessions_completed INTEGER NOT NULL DEFAULT 0,
            pre_assessment_score REAL,
            post_assessment_score REAL,
            value_added REAL,
            impact_notes TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "intervention_sessions": """
        CREATE TABLE IF NOT EXISTS intervention_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intervention_id INTEGER NOT NULL REFERENCES academic_interventions(id),
            session_date TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL DEFAULT 30,
            attended INTEGER NOT NULL DEFAULT 1,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Visitors ----
    "visitors": """
        CREATE TABLE IF NOT EXISTS visitors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            organization TEXT,
            purpose TEXT NOT NULL,
            visiting_staff_id INTEGER,
            dbs_checked INTEGER NOT NULL DEFAULT 0,
            safeguarding_briefed INTEGER NOT NULL DEFAULT 0,
            badge_number TEXT,
            sign_in_time TEXT,
            sign_out_time TEXT,
            vehicle_reg TEXT,
            status TEXT NOT NULL DEFAULT 'signed_in',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Policies ----
    "policies": """
        CREATE TABLE IF NOT EXISTS policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            version TEXT NOT NULL DEFAULT '1.0',
            author_id INTEGER,
            content TEXT,
            file_path TEXT,
            review_date TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            approved_by INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "policy_acknowledgements": """
        CREATE TABLE IF NOT EXISTS policy_acknowledgements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            policy_id INTEGER NOT NULL REFERENCES policies(id),
            user_id INTEGER NOT NULL,
            acknowledged_at TEXT NOT NULL DEFAULT (datetime('now')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- GDPR ----
    "data_subjects": """
        CREATE TABLE IF NOT EXISTS data_subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            consent_marketing INTEGER NOT NULL DEFAULT 0,
            consent_analytics INTEGER NOT NULL DEFAULT 0,
            consent_third_party INTEGER NOT NULL DEFAULT 0,
            erasure_requested INTEGER NOT NULL DEFAULT 0,
            erasure_completed_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "subject_access_requests": """
        CREATE TABLE IF NOT EXISTS subject_access_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_name TEXT NOT NULL,
            subject_user_id INTEGER,
            request_date TEXT NOT NULL DEFAULT (date('now')),
            due_date TEXT,
            response_date TEXT,
            status TEXT NOT NULL DEFAULT 'received',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "data_breaches": """
        CREATE TABLE IF NOT EXISTS data_breaches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reported_by INTEGER NOT NULL,
            breach_date TEXT NOT NULL,
            description TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'low',
            individuals_affected INTEGER NOT NULL DEFAULT 0,
            ico_notified INTEGER NOT NULL DEFAULT 0,
            remedial_actions TEXT,
            status TEXT NOT NULL DEFAULT 'investigating',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Quality Assurance ----
    "quality_reviews": """
        CREATE TABLE IF NOT EXISTS quality_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_type TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            title TEXT NOT NULL,
            lead_reviewer_id INTEGER,
            overall_grade TEXT,
            key_findings TEXT,
            status TEXT NOT NULL DEFAULT 'planned',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "qip_actions": """
        CREATE TABLE IF NOT EXISTS qip_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id INTEGER NOT NULL REFERENCES quality_reviews(id),
            action_text TEXT NOT NULL,
            responsible_id INTEGER,
            target_date TEXT,
            evidence TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Bulk Operations ----
    "bulk_jobs": """
        CREATE TABLE IF NOT EXISTS bulk_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_type TEXT NOT NULL,
            initiated_by INTEGER NOT NULL,
            file_path TEXT,
            total_rows INTEGER NOT NULL DEFAULT 0,
            processed_rows INTEGER NOT NULL DEFAULT 0,
            success_count INTEGER NOT NULL DEFAULT 0,
            error_count INTEGER NOT NULL DEFAULT 0,
            error_log TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Emergency ----
    "emergency_drills": """
        CREATE TABLE IF NOT EXISTS emergency_drills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drill_type TEXT NOT NULL,
            scheduled_date TEXT NOT NULL,
            actual_date TEXT,
            duration_minutes INTEGER,
            outcome TEXT,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'planned',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "emergency_protocols": """
        CREATE TABLE IF NOT EXISTS emergency_protocols (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            protocol_type TEXT NOT NULL,
            title TEXT NOT NULL,
            procedure TEXT,
            assembly_point TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "evacuation_registers": """
        CREATE TABLE IF NOT EXISTS evacuation_registers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drill_id INTEGER NOT NULL REFERENCES emergency_drills(id),
            area TEXT NOT NULL,
            headcount_expected INTEGER NOT NULL DEFAULT 0,
            headcount_actual INTEGER NOT NULL DEFAULT 0,
            staff_responsible INTEGER,
            all_accounted INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Academic Year ----
    "academic_years": """
        CREATE TABLE IF NOT EXISTS academic_years (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            is_current INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'planned',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "terms": """
        CREATE TABLE IF NOT EXISTS terms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            academic_year_id INTEGER NOT NULL REFERENCES academic_years(id),
            term_name TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            half_term_start TEXT,
            half_term_end TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "year_rollover_log": """
        CREATE TABLE IF NOT EXISTS year_rollover_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_year_id INTEGER NOT NULL,
            to_year_id INTEGER NOT NULL,
            students_promoted INTEGER NOT NULL DEFAULT 0,
            courses_copied INTEGER NOT NULL DEFAULT 0,
            rolled_at TEXT NOT NULL DEFAULT (datetime('now')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- KPI Dashboard ----
    "kpi_targets": """
        CREATE TABLE IF NOT EXISTS kpi_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            academic_year TEXT NOT NULL,
            kpi_name TEXT NOT NULL,
            kpi_category TEXT NOT NULL DEFAULT 'academic',
            target_value REAL,
            actual_value REAL,
            national_benchmark REAL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "kpi_snapshots": """
        CREATE TABLE IF NOT EXISTS kpi_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            academic_year TEXT NOT NULL,
            snapshot_date TEXT NOT NULL DEFAULT (date('now')),
            kpi_data TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Audit Reports ----
    "audit_report_records": """
        CREATE TABLE IF NOT EXISTS audit_report_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_type TEXT NOT NULL,
            title TEXT NOT NULL,
            generated_by INTEGER,
            result_summary TEXT,
            findings TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "compliance_checks": """
        CREATE TABLE IF NOT EXISTS compliance_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            check_type TEXT NOT NULL,
            staff_id INTEGER,
            check_date TEXT NOT NULL DEFAULT (date('now')),
            expiry_date TEXT,
            is_compliant INTEGER NOT NULL DEFAULT 1,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- User Management ----
    "permission_templates": """
        CREATE TABLE IF NOT EXISTS permission_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name TEXT NOT NULL,
            role TEXT NOT NULL,
            permissions TEXT,
            description TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "user_creation_log": """
        CREATE TABLE IF NOT EXISTS user_creation_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_by INTEGER NOT NULL,
            batch_id TEXT,
            username TEXT NOT NULL,
            role TEXT NOT NULL,
            method TEXT NOT NULL DEFAULT 'manual',
            status TEXT NOT NULL DEFAULT 'success',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Portfolio ----
    "portfolio_items": """
        CREATE TABLE IF NOT EXISTS portfolio_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            item_type TEXT NOT NULL DEFAULT 'work',
            description TEXT,
            file_path TEXT,
            subject_area TEXT,
            is_public INTEGER NOT NULL DEFAULT 0,
            tags TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "portfolio_shares": """
        CREATE TABLE IF NOT EXISTS portfolio_shares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_item_id INTEGER NOT NULL REFERENCES portfolio_items(id),
            shared_with_user_id INTEGER NOT NULL,
            expires_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Study Planner ----
    "study_sessions": """
        CREATE TABLE IF NOT EXISTS study_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT,
            planned_date TEXT NOT NULL,
            planned_duration INTEGER NOT NULL DEFAULT 30,
            actual_duration INTEGER,
            session_type TEXT NOT NULL DEFAULT 'revision',
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "study_goals": """
        CREATE TABLE IF NOT EXISTS study_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            target_date TEXT,
            target_hours REAL NOT NULL DEFAULT 0,
            achieved_hours REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "pomodoro_sessions": """
        CREATE TABLE IF NOT EXISTS pomodoro_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            study_session_id INTEGER REFERENCES study_sessions(id),
            start_time TEXT NOT NULL,
            end_time TEXT,
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Enrichment ----
    "enrichment_activities": """
        CREATE TABLE IF NOT EXISTS enrichment_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            activity_type TEXT NOT NULL DEFAULT 'club',
            lead_staff_id INTEGER,
            day_of_week TEXT,
            time_slot TEXT,
            location TEXT,
            capacity INTEGER,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "enrichment_enrollments": """
        CREATE TABLE IF NOT EXISTS enrichment_enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL REFERENCES enrichment_activities(id),
            student_id INTEGER NOT NULL,
            enrolled_at TEXT NOT NULL DEFAULT (datetime('now')),
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "enrichment_attendance": """
        CREATE TABLE IF NOT EXISTS enrichment_attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment_id INTEGER NOT NULL REFERENCES enrichment_enrollments(id),
            session_date TEXT NOT NULL,
            attended INTEGER NOT NULL DEFAULT 1,
            hours REAL NOT NULL DEFAULT 1.0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Peer Mentoring ----
    "mentoring_pairs": """
        CREATE TABLE IF NOT EXISTS mentoring_pairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mentor_id INTEGER NOT NULL,
            mentee_id INTEGER NOT NULL,
            matched_by INTEGER,
            subject_area TEXT,
            start_date TEXT NOT NULL DEFAULT (date('now')),
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "mentoring_goals": """
        CREATE TABLE IF NOT EXISTS mentoring_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair_id INTEGER NOT NULL REFERENCES mentoring_pairs(id),
            goal_text TEXT NOT NULL,
            target_date TEXT,
            status TEXT NOT NULL DEFAULT 'in_progress',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "mentoring_logs": """
        CREATE TABLE IF NOT EXISTS mentoring_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair_id INTEGER NOT NULL REFERENCES mentoring_pairs(id),
            meeting_date TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL DEFAULT 30,
            mentor_notes TEXT,
            mentee_notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Surveys ----
    "surveys": """
        CREATE TABLE IF NOT EXISTS surveys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            survey_type TEXT NOT NULL DEFAULT 'feedback',
            is_anonymous INTEGER NOT NULL DEFAULT 0,
            target_role TEXT,
            open_date TEXT,
            close_date TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "survey_questions": """
        CREATE TABLE IF NOT EXISTS survey_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER NOT NULL REFERENCES surveys(id),
            question_text TEXT NOT NULL,
            question_type TEXT NOT NULL DEFAULT 'text',
            options TEXT,
            is_required INTEGER NOT NULL DEFAULT 1,
            display_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "survey_responses": """
        CREATE TABLE IF NOT EXISTS survey_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER NOT NULL REFERENCES surveys(id),
            respondent_id INTEGER,
            started_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT,
            is_complete INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "survey_answers": """
        CREATE TABLE IF NOT EXISTS survey_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            response_id INTEGER NOT NULL REFERENCES survey_responses(id),
            question_id INTEGER NOT NULL REFERENCES survey_questions(id),
            answer_text TEXT,
            rating INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Skills Passport ----
    "skill_categories": """
        CREATE TABLE IF NOT EXISTS skill_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            display_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "skill_assessments": """
        CREATE TABLE IF NOT EXISTS skill_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            skill_category_id INTEGER NOT NULL REFERENCES skill_categories(id),
            self_rating INTEGER,
            teacher_rating INTEGER,
            endorsed_by INTEGER,
            evidence TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "skill_endorsements": """
        CREATE TABLE IF NOT EXISTS skill_endorsements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id INTEGER NOT NULL REFERENCES skill_assessments(id),
            endorsed_by INTEGER NOT NULL,
            endorsement_text TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Progress Dashboard ----
    "progress_snapshots": """
        CREATE TABLE IF NOT EXISTS progress_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            snapshot_date TEXT NOT NULL DEFAULT (date('now')),
            attendance_percent REAL,
            average_grade TEXT,
            assignments_due INTEGER NOT NULL DEFAULT 0,
            assignments_overdue INTEGER NOT NULL DEFAULT 0,
            trajectory TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Meal Ordering ----
    "menu_items": """
        CREATE TABLE IF NOT EXISTS menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'main',
            price REAL NOT NULL DEFAULT 0,
            dietary_tags TEXT,
            description TEXT,
            is_available INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "meal_orders": """
        CREATE TABLE IF NOT EXISTS meal_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            order_date TEXT NOT NULL DEFAULT (date('now')),
            collection_time TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            total_price REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "meal_order_items": """
        CREATE TABLE IF NOT EXISTS meal_order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL REFERENCES meal_orders(id),
            menu_item_id INTEGER NOT NULL REFERENCES menu_items(id),
            quantity INTEGER NOT NULL DEFAULT 1,
            price REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "free_meal_balances": """
        CREATE TABLE IF NOT EXISTS free_meal_balances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            daily_allowance REAL NOT NULL DEFAULT 2.50,
            balance REAL NOT NULL DEFAULT 0,
            eligibility_type TEXT NOT NULL DEFAULT 'fsm',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "dietary_preferences": """
        CREATE TABLE IF NOT EXISTS dietary_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            vegetarian INTEGER NOT NULL DEFAULT 0,
            vegan INTEGER NOT NULL DEFAULT 0,
            halal INTEGER NOT NULL DEFAULT 0,
            kosher INTEGER NOT NULL DEFAULT 0,
            gluten_free INTEGER NOT NULL DEFAULT 0,
            nut_allergy INTEGER NOT NULL DEFAULT 0,
            dairy_free INTEGER NOT NULL DEFAULT 0,
            other_allergies TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Print Credits ----
    "print_accounts": """
        CREATE TABLE IF NOT EXISTS print_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            balance REAL NOT NULL DEFAULT 0,
            quota_remaining INTEGER NOT NULL DEFAULT 100,
            quota_reset_date TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "print_transactions": """
        CREATE TABLE IF NOT EXISTS print_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL REFERENCES print_accounts(id),
            transaction_type TEXT NOT NULL DEFAULT 'print',
            amount REAL NOT NULL DEFAULT 0,
            pages INTEGER NOT NULL DEFAULT 0,
            print_type TEXT NOT NULL DEFAULT 'mono',
            description TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Work Journal ----
    "work_placements": """
        CREATE TABLE IF NOT EXISTS work_placements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            employer_name TEXT NOT NULL,
            role_title TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT,
            supervisor_name TEXT,
            dbs_confirmed INTEGER NOT NULL DEFAULT 0,
            risk_assessment TEXT,
            status TEXT NOT NULL DEFAULT 'planned',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "journal_entries": """
        CREATE TABLE IF NOT EXISTS journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            placement_id INTEGER NOT NULL REFERENCES work_placements(id),
            entry_date TEXT NOT NULL,
            daily_reflection TEXT,
            skills_developed TEXT,
            challenges TEXT,
            employer_feedback TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Announcements ----
    "announcements": """
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            author_id INTEGER NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            target_role TEXT,
            is_pinned INTEGER NOT NULL DEFAULT 0,
            publish_date TEXT NOT NULL DEFAULT (date('now')),
            expiry_date TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "announcement_reads": """
        CREATE TABLE IF NOT EXISTS announcement_reads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            announcement_id INTEGER NOT NULL REFERENCES announcements(id),
            user_id INTEGER NOT NULL,
            read_at TEXT NOT NULL DEFAULT (datetime('now')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Document Hub ----
    "documents": """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            file_path TEXT,
            file_type TEXT,
            file_size INTEGER,
            version INTEGER NOT NULL DEFAULT 1,
            uploaded_by INTEGER NOT NULL,
            target_role TEXT,
            download_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "document_versions": """
        CREATE TABLE IF NOT EXISTS document_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL REFERENCES documents(id),
            version INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            change_notes TEXT,
            uploaded_by INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Advanced Search ----
    "search_history": """
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            query TEXT NOT NULL,
            module_filter TEXT,
            result_count INTEGER NOT NULL DEFAULT 0,
            searched_at TEXT NOT NULL DEFAULT (datetime('now')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "saved_searches": """
        CREATE TABLE IF NOT EXISTS saved_searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            query TEXT NOT NULL,
            filters TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Feedback ----
    "feedback_items": """
        CREATE TABLE IF NOT EXISTS feedback_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submitted_by INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT NOT NULL DEFAULT 'suggestion',
            is_anonymous INTEGER NOT NULL DEFAULT 0,
            upvote_count INTEGER NOT NULL DEFAULT 0,
            admin_response TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "feedback_votes": """
        CREATE TABLE IF NOT EXISTS feedback_votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feedback_id INTEGER NOT NULL REFERENCES feedback_items(id),
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Accessibility ----
    "accessibility_preferences": """
        CREATE TABLE IF NOT EXISTS accessibility_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            theme TEXT NOT NULL DEFAULT 'default',
            font_size TEXT NOT NULL DEFAULT 'medium',
            font_family TEXT NOT NULL DEFAULT 'system',
            reduce_animations INTEGER NOT NULL DEFAULT 0,
            screen_reader_mode INTEGER NOT NULL DEFAULT 0,
            high_contrast INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Mobile Dashboard ----
    "mobile_widget_config": """
        CREATE TABLE IF NOT EXISTS mobile_widget_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            widget_type TEXT NOT NULL,
            display_order INTEGER NOT NULL DEFAULT 0,
            is_visible INTEGER NOT NULL DEFAULT 1,
            config TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "quick_actions": """
        CREATE TABLE IF NOT EXISTS quick_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action_name TEXT NOT NULL,
            action_target TEXT NOT NULL,
            display_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Attachments ----
    "attachments": """
        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uploaded_by INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT,
            file_size INTEGER NOT NULL DEFAULT 0,
            entity_type TEXT,
            entity_id INTEGER,
            is_public INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Activity Feed ----
    "activity_feed_items": """
        CREATE TABLE IF NOT EXISTS activity_feed_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            entity_type TEXT,
            entity_id INTEGER,
            target_role TEXT,
            target_user_id INTEGER,
            is_read INTEGER NOT NULL DEFAULT 0,
            dismissed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- SMS/Email ----
    "notification_preferences": """
        CREATE TABLE IF NOT EXISTS notification_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            email_enabled INTEGER NOT NULL DEFAULT 1,
            sms_enabled INTEGER NOT NULL DEFAULT 0,
            phone_number TEXT,
            attendance_alerts INTEGER NOT NULL DEFAULT 1,
            grade_alerts INTEGER NOT NULL DEFAULT 1,
            assignment_alerts INTEGER NOT NULL DEFAULT 1,
            digest_frequency TEXT NOT NULL DEFAULT 'daily',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "notification_templates": """
        CREATE TABLE IF NOT EXISTS notification_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name TEXT NOT NULL UNIQUE,
            template_type TEXT NOT NULL DEFAULT 'email',
            subject TEXT,
            body TEXT NOT NULL,
            variables TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "notification_log": """
        CREATE TABLE IF NOT EXISTS notification_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_id INTEGER NOT NULL,
            channel TEXT NOT NULL DEFAULT 'email',
            template_id INTEGER REFERENCES notification_templates(id),
            subject TEXT,
            body TEXT,
            status TEXT NOT NULL DEFAULT 'sent',
            sent_at TEXT NOT NULL DEFAULT (datetime('now')),
            error_message TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Multi-Language ----
    "translation_overrides": """
        CREATE TABLE IF NOT EXISTS translation_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            locale TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(locale, key)
        )
    """,
    # ---- Individual Learning Plans ----
    "ilp_plans": """
        CREATE TABLE IF NOT EXISTS ilp_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            academic_year TEXT,
            plan_type TEXT DEFAULT 'standard',
            status TEXT DEFAULT 'active',
            created_by INTEGER,
            long_term_goal TEXT,
            support_needs TEXT,
            review_frequency TEXT DEFAULT 'half-termly',
            next_review_date TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """,
    "ilp_targets": """
        CREATE TABLE IF NOT EXISTS ilp_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            subject_area TEXT,
            target_description TEXT NOT NULL,
            success_criteria TEXT,
            current_grade TEXT,
            target_grade TEXT,
            status TEXT DEFAULT 'in_progress',
            evidence TEXT,
            completed_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (plan_id) REFERENCES ilp_plans(id)
        )
    """,
    "ilp_reviews": """
        CREATE TABLE IF NOT EXISTS ilp_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            reviewer_id INTEGER,
            review_date TEXT NOT NULL,
            summary TEXT,
            student_voice TEXT,
            actions_agreed TEXT,
            next_review_date TEXT,
            attendance_status TEXT DEFAULT 'attended',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (plan_id) REFERENCES ilp_plans(id),
            FOREIGN KEY (reviewer_id) REFERENCES users(id)
        )
    """,
    # ---- UCAS Applications ----
    "ucas_applications": """
        CREATE TABLE IF NOT EXISTS ucas_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            academic_year TEXT,
            ucas_id TEXT,
            personal_statement_status TEXT DEFAULT 'not_started',
            reference_status TEXT DEFAULT 'not_requested',
            reference_author_id INTEGER,
            predicted_tariff INTEGER DEFAULT 0,
            application_status TEXT DEFAULT 'draft',
            submitted_at TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (reference_author_id) REFERENCES users(id)
        )
    """,
    "ucas_choices": """
        CREATE TABLE IF NOT EXISTS ucas_choices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            university_name TEXT NOT NULL,
            course_title TEXT NOT NULL,
            ucas_code TEXT,
            choice_number INTEGER,
            offer_type TEXT,
            offer_conditions TEXT,
            offer_status TEXT DEFAULT 'pending',
            is_firm INTEGER DEFAULT 0,
            is_insurance INTEGER DEFAULT 0,
            reply_deadline TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (application_id) REFERENCES ucas_applications(id)
        )
    """,
    "ucas_references": """
        CREATE TABLE IF NOT EXISTS ucas_references (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            author_id INTEGER,
            draft_text TEXT,
            status TEXT DEFAULT 'draft',
            submitted_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (application_id) REFERENCES ucas_applications(id),
            FOREIGN KEY (author_id) REFERENCES users(id)
        )
    """,
    # ---- T-Level Pathways ----
    "tlevel_routes": """
        CREATE TABLE IF NOT EXISTS tlevel_routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route_name TEXT NOT NULL,
            pathway TEXT,
            awarding_body TEXT,
            glh_total INTEGER DEFAULT 1800,
            industry_placement_hours INTEGER DEFAULT 315,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "tlevel_enrollments": """
        CREATE TABLE IF NOT EXISTS tlevel_enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            route_id INTEGER NOT NULL,
            academic_year TEXT,
            core_grade TEXT,
            occupational_specialism TEXT,
            specialism_grade TEXT,
            placement_hours_completed INTEGER DEFAULT 0,
            placement_employer TEXT,
            placement_start_date TEXT,
            placement_end_date TEXT,
            placement_status TEXT DEFAULT 'not_started',
            overall_grade TEXT,
            status TEXT DEFAULT 'active',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (route_id) REFERENCES tlevel_routes(id)
        )
    """,
    "tlevel_placement_logs": """
        CREATE TABLE IF NOT EXISTS tlevel_placement_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment_id INTEGER NOT NULL,
            log_date TEXT NOT NULL,
            hours REAL NOT NULL,
            activity TEXT,
            supervisor_feedback TEXT,
            student_reflection TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (enrollment_id) REFERENCES tlevel_enrollments(id)
        )
    """,
    # ---- Apprenticeships ----
    "apprenticeship_standards": """
        CREATE TABLE IF NOT EXISTS apprenticeship_standards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            standard_name TEXT NOT NULL,
            level INTEGER NOT NULL,
            sector TEXT,
            duration_months INTEGER DEFAULT 12,
            epa_provider TEXT,
            off_the_job_hours INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "apprenticeship_enrollments": """
        CREATE TABLE IF NOT EXISTS apprenticeship_enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            standard_id INTEGER NOT NULL,
            employer_name TEXT NOT NULL,
            employer_contact TEXT,
            start_date TEXT,
            expected_end_date TEXT,
            actual_end_date TEXT,
            otj_hours_target INTEGER DEFAULT 0,
            otj_hours_completed INTEGER DEFAULT 0,
            epa_status TEXT DEFAULT 'not_started',
            epa_grade TEXT,
            gateway_met INTEGER DEFAULT 0,
            progress_review_date TEXT,
            status TEXT DEFAULT 'active',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (standard_id) REFERENCES apprenticeship_standards(id)
        )
    """,
    "apprenticeship_otj_log": """
        CREATE TABLE IF NOT EXISTS apprenticeship_otj_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment_id INTEGER NOT NULL,
            log_date TEXT NOT NULL,
            hours REAL NOT NULL,
            activity_type TEXT,
            description TEXT,
            evidence TEXT,
            verified INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (enrollment_id) REFERENCES apprenticeship_enrollments(id)
        )
    """,
    "apprenticeship_reviews": """
        CREATE TABLE IF NOT EXISTS apprenticeship_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment_id INTEGER NOT NULL,
            review_date TEXT NOT NULL,
            reviewer_id INTEGER,
            employer_present INTEGER DEFAULT 0,
            progress_summary TEXT,
            targets_set TEXT,
            concerns TEXT,
            next_review_date TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (enrollment_id) REFERENCES apprenticeship_enrollments(id)
        )
    """,
    # ---- Value-Added Analysis ----
    "value_added_baselines": """
        CREATE TABLE IF NOT EXISTS value_added_baselines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            academic_year TEXT,
            gcse_average REAL,
            gcse_english INTEGER,
            gcse_maths INTEGER,
            baseline_score REAL,
            data_source TEXT DEFAULT 'gcse',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "value_added_predictions": """
        CREATE TABLE IF NOT EXISTS value_added_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            academic_year TEXT,
            predicted_grade TEXT,
            target_grade TEXT,
            actual_grade TEXT,
            value_added_score REAL,
            alps_grade TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (course_id) REFERENCES courses(id)
        )
    """,
    "value_added_benchmarks": """
        CREATE TABLE IF NOT EXISTS value_added_benchmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            academic_year TEXT NOT NULL,
            subject_area TEXT,
            qualification_type TEXT DEFAULT 'A-Level',
            baseline_band TEXT,
            national_average REAL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Governance & Board ----
    "governors": """
        CREATE TABLE IF NOT EXISTS governors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            governor_type TEXT DEFAULT 'community',
            role_on_board TEXT,
            appointed_date TEXT,
            term_end_date TEXT,
            dbs_checked INTEGER DEFAULT 0,
            dbs_date TEXT,
            skills TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "board_meetings": """
        CREATE TABLE IF NOT EXISTS board_meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_date TEXT NOT NULL,
            meeting_type TEXT DEFAULT 'full_board',
            location TEXT,
            chair_id INTEGER,
            clerk_id INTEGER,
            agenda TEXT,
            minutes TEXT,
            status TEXT DEFAULT 'scheduled',
            quorate INTEGER DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (chair_id) REFERENCES governors(id)
        )
    """,
    "board_actions": """
        CREATE TABLE IF NOT EXISTS board_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER NOT NULL,
            action_description TEXT NOT NULL,
            assigned_to INTEGER,
            due_date TEXT,
            status TEXT DEFAULT 'open',
            completion_notes TEXT,
            completed_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (meeting_id) REFERENCES board_meetings(id),
            FOREIGN KEY (assigned_to) REFERENCES governors(id)
        )
    """,
    "strategic_plans": """
        CREATE TABLE IF NOT EXISTS strategic_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            academic_year TEXT,
            priority_area TEXT,
            objective TEXT,
            success_measure TEXT,
            responsible_person TEXT,
            progress TEXT,
            status TEXT DEFAULT 'active',
            review_date TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- DBS Checks ----
    "dbs_checks": """
        CREATE TABLE IF NOT EXISTS dbs_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER,
            governor_id INTEGER,
            volunteer_name TEXT,
            check_type TEXT DEFAULT 'enhanced',
            certificate_number TEXT,
            issue_date TEXT,
            expiry_date TEXT,
            update_service INTEGER DEFAULT 0,
            update_service_id TEXT,
            barred_list_checked INTEGER DEFAULT 0,
            children_workforce INTEGER DEFAULT 1,
            status TEXT DEFAULT 'valid',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Risk Management ----
    "institutional_risks": """
        CREATE TABLE IF NOT EXISTS institutional_risks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            risk_title TEXT NOT NULL,
            category TEXT DEFAULT 'operational',
            description TEXT,
            likelihood INTEGER DEFAULT 3,
            impact INTEGER DEFAULT 3,
            risk_score INTEGER,
            current_controls TEXT,
            mitigation_strategy TEXT,
            risk_owner TEXT,
            review_date TEXT,
            status TEXT DEFAULT 'open',
            residual_likelihood INTEGER,
            residual_impact INTEGER,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "risk_reviews": """
        CREATE TABLE IF NOT EXISTS risk_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            risk_id INTEGER NOT NULL,
            review_date TEXT NOT NULL,
            reviewer TEXT,
            previous_score INTEGER,
            new_score INTEGER,
            commentary TEXT,
            actions_taken TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (risk_id) REFERENCES institutional_risks(id)
        )
    """,
    # ---- Prevent Duty ----
    "prevent_referrals": """
        CREATE TABLE IF NOT EXISTS prevent_referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reported_by INTEGER,
            subject_name TEXT NOT NULL,
            subject_type TEXT DEFAULT 'student',
            subject_id INTEGER,
            concern_type TEXT,
            concern_details TEXT NOT NULL,
            risk_level TEXT DEFAULT 'low',
            channel_referral INTEGER DEFAULT 0,
            channel_reference TEXT,
            actions_taken TEXT,
            outcome TEXT,
            status TEXT DEFAULT 'open',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (reported_by) REFERENCES users(id)
        )
    """,
    "prevent_training": """
        CREATE TABLE IF NOT EXISTS prevent_training (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            training_type TEXT DEFAULT 'basic',
            completed_date TEXT,
            expiry_date TEXT,
            certificate_ref TEXT,
            status TEXT DEFAULT 'completed',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (staff_id) REFERENCES staff(id)
        )
    """,
    # ---- Complaints ----
    "complaints": """
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complainant_name TEXT NOT NULL,
            complainant_type TEXT DEFAULT 'parent',
            complainant_email TEXT,
            complainant_phone TEXT,
            complaint_date TEXT NOT NULL DEFAULT (date('now')),
            category TEXT DEFAULT 'general',
            subject TEXT NOT NULL,
            description TEXT NOT NULL,
            stage TEXT DEFAULT 'informal',
            assigned_to INTEGER,
            investigation_notes TEXT,
            outcome TEXT,
            resolution TEXT,
            resolved_date TEXT,
            appeal_lodged INTEGER DEFAULT 0,
            status TEXT DEFAULT 'open',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (assigned_to) REFERENCES users(id)
        )
    """,
    "complaint_responses": """
        CREATE TABLE IF NOT EXISTS complaint_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id INTEGER NOT NULL,
            responder_id INTEGER,
            response_date TEXT NOT NULL DEFAULT (date('now')),
            response_text TEXT NOT NULL,
            response_type TEXT DEFAULT 'investigation',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (complaint_id) REFERENCES complaints(id),
            FOREIGN KEY (responder_id) REFERENCES users(id)
        )
    """,
    # ---- Equality & Diversity ----
    "protected_characteristics": """
        CREATE TABLE IF NOT EXISTS protected_characteristics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_type TEXT NOT NULL DEFAULT 'student',
            person_id INTEGER NOT NULL,
            ethnicity TEXT,
            religion TEXT,
            sexual_orientation TEXT,
            gender_identity TEXT,
            disability_status TEXT,
            disability_details TEXT,
            marital_status TEXT,
            pregnancy_maternity TEXT,
            preferred_pronouns TEXT,
            collection_date TEXT NOT NULL DEFAULT (date('now')),
            consent_given INTEGER DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "equality_impact_assessments": """
        CREATE TABLE IF NOT EXISTS equality_impact_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            policy_or_practice TEXT NOT NULL,
            assessor TEXT,
            assessment_date TEXT NOT NULL DEFAULT (date('now')),
            protected_group TEXT,
            potential_impact TEXT,
            impact_type TEXT DEFAULT 'neutral',
            mitigating_actions TEXT,
            review_date TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "equality_objectives": """
        CREATE TABLE IF NOT EXISTS equality_objectives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            objective TEXT NOT NULL,
            protected_group TEXT,
            target TEXT,
            progress TEXT,
            academic_year TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Staff Absence ----
    "staff_absences": """
        CREATE TABLE IF NOT EXISTS staff_absences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            absence_type TEXT DEFAULT 'sickness',
            start_date TEXT NOT NULL,
            end_date TEXT,
            days_lost REAL DEFAULT 0,
            reason TEXT,
            self_certified INTEGER DEFAULT 0,
            fit_note_received INTEGER DEFAULT 0,
            fit_note_expiry TEXT,
            return_to_work_done INTEGER DEFAULT 0,
            rtw_date TEXT,
            rtw_notes TEXT,
            occupational_health_referral INTEGER DEFAULT 0,
            trigger_point_reached INTEGER DEFAULT 0,
            status TEXT DEFAULT 'current',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (staff_id) REFERENCES staff(id)
        )
    """,
    "staff_absence_triggers": """
        CREATE TABLE IF NOT EXISTS staff_absence_triggers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger_name TEXT NOT NULL,
            trigger_type TEXT DEFAULT 'days',
            threshold INTEGER NOT NULL,
            period_months INTEGER DEFAULT 12,
            action_required TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Staff Recruitment ----
    "job_vacancies": """
        CREATE TABLE IF NOT EXISTS job_vacancies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_title TEXT NOT NULL,
            department TEXT,
            contract_type TEXT DEFAULT 'permanent',
            hours TEXT DEFAULT 'full-time',
            salary_range TEXT,
            closing_date TEXT,
            start_date TEXT,
            description TEXT,
            person_spec TEXT,
            hiring_manager_id INTEGER,
            status TEXT DEFAULT 'draft',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "job_applications": """
        CREATE TABLE IF NOT EXISTS job_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vacancy_id INTEGER NOT NULL,
            applicant_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            cv_path TEXT,
            cover_letter TEXT,
            application_date TEXT NOT NULL DEFAULT (date('now')),
            shortlisted INTEGER DEFAULT 0,
            interview_date TEXT,
            interview_score REAL,
            interview_notes TEXT,
            references_received INTEGER DEFAULT 0,
            offer_made INTEGER DEFAULT 0,
            offer_accepted INTEGER DEFAULT 0,
            status TEXT DEFAULT 'received',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (vacancy_id) REFERENCES job_vacancies(id)
        )
    """,
    # ---- Marketing & Open Days ----
    "open_days": """
        CREATE TABLE IF NOT EXISTS open_days (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name TEXT NOT NULL,
            event_date TEXT NOT NULL,
            event_type TEXT DEFAULT 'open_day',
            start_time TEXT,
            end_time TEXT,
            capacity INTEGER,
            registrations INTEGER DEFAULT 0,
            attendees INTEGER DEFAULT 0,
            location TEXT,
            description TEXT,
            target_audience TEXT,
            status TEXT DEFAULT 'planned',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "open_day_registrations": """
        CREATE TABLE IF NOT EXISTS open_day_registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            student_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            school TEXT,
            year_group TEXT,
            interests TEXT,
            attended INTEGER DEFAULT 0,
            follow_up_sent INTEGER DEFAULT 0,
            applied INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (event_id) REFERENCES open_days(id)
        )
    """,
    "marketing_campaigns": """
        CREATE TABLE IF NOT EXISTS marketing_campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_name TEXT NOT NULL,
            campaign_type TEXT DEFAULT 'digital',
            start_date TEXT,
            end_date TEXT,
            budget REAL DEFAULT 0,
            spend REAL DEFAULT 0,
            target_audience TEXT,
            channels TEXT,
            impressions INTEGER DEFAULT 0,
            enquiries INTEGER DEFAULT 0,
            applications INTEGER DEFAULT 0,
            notes TEXT,
            status TEXT DEFAULT 'planned',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Early Warning System ----
    "early_warning_alerts": """
        CREATE TABLE IF NOT EXISTS early_warning_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            alert_type TEXT NOT NULL,
            severity TEXT DEFAULT 'medium',
            trigger_source TEXT,
            trigger_detail TEXT,
            attendance_pct REAL,
            grade_trend TEXT,
            behaviour_count INTEGER,
            recommended_action TEXT,
            assigned_to INTEGER,
            action_taken TEXT,
            resolved INTEGER DEFAULT 0,
            resolved_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (assigned_to) REFERENCES users(id)
        )
    """,
    "early_warning_rules": """
        CREATE TABLE IF NOT EXISTS early_warning_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_name TEXT NOT NULL,
            rule_type TEXT NOT NULL,
            threshold REAL NOT NULL,
            comparison TEXT DEFAULT 'less_than',
            severity TEXT DEFAULT 'medium',
            auto_assign_role TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Self-Assessment & Ofsted ----
    "sef_sections": """
        CREATE TABLE IF NOT EXISTS sef_sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            academic_year TEXT,
            section_name TEXT NOT NULL,
            section_number TEXT,
            self_grade TEXT,
            strengths TEXT,
            areas_for_improvement TEXT,
            evidence TEXT,
            last_updated_by INTEGER,
            status TEXT DEFAULT 'draft',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "improvement_actions": """
        CREATE TABLE IF NOT EXISTS improvement_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sef_section_id INTEGER,
            action_description TEXT NOT NULL,
            responsible_person TEXT,
            start_date TEXT,
            target_date TEXT,
            success_criteria TEXT,
            progress TEXT,
            impact TEXT,
            cost REAL DEFAULT 0,
            status TEXT DEFAULT 'not_started',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (sef_section_id) REFERENCES sef_sections(id)
        )
    """,
    "ofsted_prep_checklist": """
        CREATE TABLE IF NOT EXISTS ofsted_prep_checklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            item TEXT NOT NULL,
            responsible_person TEXT,
            document_location TEXT,
            is_ready INTEGER DEFAULT 0,
            notes TEXT,
            last_checked TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Alumni Network ----
    "alumni_records": """
        CREATE TABLE IF NOT EXISTS alumni_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            graduation_year TEXT,
            courses_studied TEXT,
            current_employer TEXT,
            current_role TEXT,
            further_education TEXT,
            university_attended TEXT,
            degree_achieved TEXT,
            willing_to_mentor INTEGER DEFAULT 0,
            willing_to_speak INTEGER DEFAULT 0,
            consent_to_contact INTEGER DEFAULT 1,
            last_contacted TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "alumni_events": """
        CREATE TABLE IF NOT EXISTS alumni_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name TEXT NOT NULL,
            event_date TEXT NOT NULL,
            event_type TEXT DEFAULT 'reunion',
            description TEXT,
            location TEXT,
            attendee_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'planned',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "alumni_surveys": """
        CREATE TABLE IF NOT EXISTS alumni_surveys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_id INTEGER NOT NULL,
            survey_year TEXT,
            employment_status TEXT,
            satisfaction_rating INTEGER,
            would_recommend INTEGER DEFAULT 1,
            feedback TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (alumni_id) REFERENCES alumni_records(id)
        )
    """,
    # ---- Student Portal ----
    "portal_pages": """
        CREATE TABLE IF NOT EXISTS portal_pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_title TEXT NOT NULL,
            page_slug TEXT UNIQUE NOT NULL,
            content TEXT,
            category TEXT DEFAULT 'general',
            is_published INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_by INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "portal_links": """
        CREATE TABLE IF NOT EXISTS portal_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link_title TEXT NOT NULL,
            url TEXT NOT NULL,
            category TEXT DEFAULT 'useful_links',
            description TEXT,
            icon TEXT,
            sort_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Discussion Forums ----
    "forum_categories": """
        CREATE TABLE IF NOT EXISTS forum_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            sort_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "forum_threads": """
        CREATE TABLE IF NOT EXISTS forum_threads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            author_id INTEGER NOT NULL,
            is_pinned INTEGER DEFAULT 0,
            is_locked INTEGER DEFAULT 0,
            view_count INTEGER DEFAULT 0,
            reply_count INTEGER DEFAULT 0,
            last_reply_at TEXT,
            status TEXT DEFAULT 'open',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (category_id) REFERENCES forum_categories(id),
            FOREIGN KEY (author_id) REFERENCES users(id)
        )
    """,
    "forum_posts": """
        CREATE TABLE IF NOT EXISTS forum_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id INTEGER NOT NULL,
            author_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            is_solution INTEGER DEFAULT 0,
            edited_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (thread_id) REFERENCES forum_threads(id),
            FOREIGN KEY (author_id) REFERENCES users(id)
        )
    """,
    # ---- Internal Verification ----
    "iv_plans": """
        CREATE TABLE IF NOT EXISTS iv_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            academic_year TEXT,
            lead_iv_id INTEGER,
            sampling_strategy TEXT,
            sample_size_pct INTEGER DEFAULT 25,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (course_id) REFERENCES courses(id),
            FOREIGN KEY (lead_iv_id) REFERENCES staff(id)
        )
    """,
    "iv_samples": """
        CREATE TABLE IF NOT EXISTS iv_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            assignment_title TEXT NOT NULL,
            assessor_id INTEGER,
            verifier_id INTEGER,
            sample_date TEXT,
            student_ids TEXT,
            assessment_decisions_agreed INTEGER DEFAULT 1,
            feedback_quality TEXT,
            grading_accurate INTEGER DEFAULT 1,
            action_required TEXT,
            action_completed INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (plan_id) REFERENCES iv_plans(id)
        )
    """,
    "iv_observations": """
        CREATE TABLE IF NOT EXISTS iv_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            assessor_id INTEGER,
            observer_id INTEGER,
            observation_date TEXT,
            assessment_type TEXT,
            feedback TEXT,
            actions TEXT,
            grade TEXT,
            status TEXT DEFAULT 'scheduled',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (plan_id) REFERENCES iv_plans(id)
        )
    """,
    # ---- Functional Skills & GCSE Resits ----
    "functional_skills_enrollments": """
        CREATE TABLE IF NOT EXISTS functional_skills_enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            qualification_type TEXT DEFAULT 'gcse_resit',
            level TEXT DEFAULT '2',
            entry_grade TEXT,
            target_grade TEXT,
            current_grade TEXT,
            exam_board TEXT,
            exam_series TEXT,
            exam_date TEXT,
            result TEXT,
            attendance_pct REAL,
            status TEXT DEFAULT 'enrolled',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "functional_skills_assessments": """
        CREATE TABLE IF NOT EXISTS functional_skills_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment_id INTEGER NOT NULL,
            assessment_type TEXT DEFAULT 'mock',
            assessment_date TEXT,
            score REAL,
            grade TEXT,
            feedback TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (enrollment_id) REFERENCES functional_skills_enrollments(id)
        )
    """,
    # ---- Study Programmes ----
    "study_programmes": """
        CREATE TABLE IF NOT EXISTS study_programmes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            academic_year TEXT,
            programme_type TEXT DEFAULT 'level3',
            substantive_qualification TEXT,
            maths_requirement TEXT DEFAULT 'not_met',
            maths_enrollment_id INTEGER,
            english_requirement TEXT DEFAULT 'not_met',
            english_enrollment_id INTEGER,
            work_experience_completed INTEGER DEFAULT 0,
            work_experience_hours INTEGER DEFAULT 0,
            enrichment_hours INTEGER DEFAULT 0,
            tutorial_hours INTEGER DEFAULT 0,
            total_planned_hours INTEGER DEFAULT 0,
            total_delivered_hours INTEGER DEFAULT 0,
            is_valid INTEGER DEFAULT 0,
            validation_notes TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "study_programme_components": """
        CREATE TABLE IF NOT EXISTS study_programme_components (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            programme_id INTEGER NOT NULL,
            component_type TEXT NOT NULL,
            component_name TEXT NOT NULL,
            planned_hours INTEGER DEFAULT 0,
            delivered_hours INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (programme_id) REFERENCES study_programmes(id)
        )
    """,
    # ---- Tutorial System ----
    "tutor_assignments": """
        CREATE TABLE IF NOT EXISTS tutor_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            tutor_id INTEGER NOT NULL,
            academic_year TEXT,
            tutor_group TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (tutor_id) REFERENCES staff(id)
        )
    """,
    "tutorial_sessions": """
        CREATE TABLE IF NOT EXISTS tutorial_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tutor_id INTEGER NOT NULL,
            tutor_group TEXT,
            session_date TEXT NOT NULL,
            session_type TEXT DEFAULT 'group',
            topic TEXT,
            resources TEXT,
            notes TEXT,
            status TEXT DEFAULT 'scheduled',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (tutor_id) REFERENCES staff(id)
        )
    """,
    "tutorial_records": """
        CREATE TABLE IF NOT EXISTS tutorial_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            student_id INTEGER NOT NULL,
            tutor_id INTEGER NOT NULL,
            meeting_date TEXT NOT NULL,
            meeting_type TEXT DEFAULT '1to1',
            discussion_notes TEXT,
            targets_set TEXT,
            student_concerns TEXT,
            follow_up_required INTEGER DEFAULT 0,
            follow_up_notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (tutor_id) REFERENCES staff(id)
        )
    """,
    # ---- Student Wellbeing ----
    "wellbeing_referrals": """
        CREATE TABLE IF NOT EXISTS wellbeing_referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            referred_by INTEGER,
            referral_type TEXT DEFAULT 'internal',
            concern_category TEXT,
            concern_details TEXT NOT NULL,
            risk_level TEXT DEFAULT 'low',
            service_referred_to TEXT,
            external_agency TEXT,
            consent_obtained INTEGER DEFAULT 0,
            appointment_date TEXT,
            outcome TEXT,
            status TEXT DEFAULT 'open',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (referred_by) REFERENCES users(id)
        )
    """,
    "wellbeing_logs": """
        CREATE TABLE IF NOT EXISTS wellbeing_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            logged_by INTEGER,
            log_date TEXT NOT NULL DEFAULT (date('now')),
            mood_rating INTEGER,
            anxiety_level INTEGER,
            sleep_quality TEXT,
            notes TEXT,
            follow_up_needed INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "counselling_sessions": """
        CREATE TABLE IF NOT EXISTS counselling_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            counsellor_id INTEGER,
            session_date TEXT NOT NULL,
            session_number INTEGER DEFAULT 1,
            session_type TEXT DEFAULT 'individual',
            presenting_issues TEXT,
            session_notes TEXT,
            risk_assessment TEXT,
            next_appointment TEXT,
            status TEXT DEFAULT 'completed',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    # ---- Student Council ----
    "council_members": """
        CREATE TABLE IF NOT EXISTS council_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            role TEXT DEFAULT 'representative',
            year_group TEXT,
            department TEXT,
            elected_date TEXT,
            term_end_date TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "council_meetings": """
        CREATE TABLE IF NOT EXISTS council_meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_date TEXT NOT NULL,
            chair_id INTEGER,
            agenda TEXT,
            minutes TEXT,
            attendees TEXT,
            status TEXT DEFAULT 'scheduled',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (chair_id) REFERENCES council_members(id)
        )
    """,
    "council_proposals": """
        CREATE TABLE IF NOT EXISTS council_proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            proposed_by INTEGER,
            meeting_id INTEGER,
            description TEXT,
            category TEXT DEFAULT 'general',
            vote_for INTEGER DEFAULT 0,
            vote_against INTEGER DEFAULT 0,
            vote_abstain INTEGER DEFAULT 0,
            outcome TEXT,
            management_response TEXT,
            implementation_status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (proposed_by) REFERENCES council_members(id)
        )
    """,
    # ---- Facility Lettings ----
    "lettings_bookings": """
        CREATE TABLE IF NOT EXISTS lettings_bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hirer_name TEXT NOT NULL,
            organisation TEXT,
            contact_email TEXT,
            contact_phone TEXT,
            facility TEXT NOT NULL,
            booking_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            recurrence TEXT DEFAULT 'one-off',
            purpose TEXT,
            attendee_count INTEGER DEFAULT 0,
            dbs_required INTEGER DEFAULT 0,
            dbs_verified INTEGER DEFAULT 0,
            insurance_verified INTEGER DEFAULT 0,
            risk_assessment_done INTEGER DEFAULT 0,
            fee REAL DEFAULT 0,
            payment_status TEXT DEFAULT 'unpaid',
            invoice_number TEXT,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "lettings_contracts": """
        CREATE TABLE IF NOT EXISTS lettings_contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hirer_name TEXT NOT NULL,
            organisation TEXT,
            contract_start TEXT,
            contract_end TEXT,
            terms TEXT,
            agreed_fee REAL DEFAULT 0,
            signed_date TEXT,
            status TEXT DEFAULT 'draft',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Health & Safety ----
    "hs_incidents": """
        CREATE TABLE IF NOT EXISTS hs_incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_date TEXT NOT NULL,
            reported_by TEXT,
            location TEXT,
            incident_type TEXT DEFAULT 'accident',
            description TEXT NOT NULL,
            persons_involved TEXT,
            injury_details TEXT,
            first_aid_given INTEGER DEFAULT 0,
            riddor_reportable INTEGER DEFAULT 0,
            riddor_reference TEXT,
            investigation_notes TEXT,
            root_cause TEXT,
            corrective_actions TEXT,
            status TEXT DEFAULT 'open',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "hs_inspections": """
        CREATE TABLE IF NOT EXISTS hs_inspections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inspection_type TEXT NOT NULL,
            area TEXT,
            inspector TEXT,
            inspection_date TEXT NOT NULL,
            next_due_date TEXT,
            findings TEXT,
            actions_required TEXT,
            certificate_ref TEXT,
            status TEXT DEFAULT 'passed',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "hs_risk_assessments": """
        CREATE TABLE IF NOT EXISTS hs_risk_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity TEXT NOT NULL,
            location TEXT,
            assessor TEXT,
            assessment_date TEXT NOT NULL,
            hazards TEXT,
            persons_at_risk TEXT,
            existing_controls TEXT,
            risk_rating TEXT DEFAULT 'medium',
            additional_controls TEXT,
            review_date TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "hs_compliance_checks": """
        CREATE TABLE IF NOT EXISTS hs_compliance_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            check_type TEXT NOT NULL,
            description TEXT,
            responsible_person TEXT,
            frequency TEXT DEFAULT 'annual',
            last_completed TEXT,
            next_due TEXT,
            certificate_ref TEXT,
            provider TEXT,
            status TEXT DEFAULT 'current',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- Letter Templates ----
    "letter_templates": """
        CREATE TABLE IF NOT EXISTS letter_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            subject_line TEXT,
            body_template TEXT NOT NULL,
            merge_fields TEXT,
            is_active INTEGER DEFAULT 1,
            created_by INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "generated_letters": """
        CREATE TABLE IF NOT EXISTS generated_letters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            recipient_type TEXT DEFAULT 'student',
            recipient_id INTEGER,
            recipient_name TEXT,
            subject TEXT,
            body TEXT NOT NULL,
            sent_via TEXT DEFAULT 'email',
            sent_at TEXT,
            status TEXT DEFAULT 'draft',
            created_by INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (template_id) REFERENCES letter_templates(id)
        )
    """,
    # ---- Disciplinary & Appeals ----
    "disciplinary_cases": """
        CREATE TABLE IF NOT EXISTS disciplinary_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_type TEXT DEFAULT 'student',
            person_id INTEGER NOT NULL,
            case_reference TEXT UNIQUE,
            case_type TEXT DEFAULT 'misconduct',
            allegation TEXT NOT NULL,
            reported_by INTEGER,
            reported_date TEXT NOT NULL DEFAULT (date('now')),
            investigating_officer INTEGER,
            hearing_date TEXT,
            hearing_panel TEXT,
            hearing_outcome TEXT,
            sanction TEXT,
            sanction_start_date TEXT,
            sanction_end_date TEXT,
            appeal_deadline TEXT,
            status TEXT DEFAULT 'under_investigation',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "disciplinary_evidence": """
        CREATE TABLE IF NOT EXISTS disciplinary_evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            evidence_type TEXT DEFAULT 'document',
            description TEXT,
            file_path TEXT,
            submitted_by INTEGER,
            submitted_date TEXT NOT NULL DEFAULT (date('now')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (case_id) REFERENCES disciplinary_cases(id)
        )
    """,
    "disciplinary_appeals": """
        CREATE TABLE IF NOT EXISTS disciplinary_appeals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            appellant_id INTEGER,
            appeal_date TEXT NOT NULL,
            grounds TEXT NOT NULL,
            panel_members TEXT,
            hearing_date TEXT,
            outcome TEXT,
            status TEXT DEFAULT 'submitted',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (case_id) REFERENCES disciplinary_cases(id)
        )
    """,
    # ---- Staff Onboarding ----
    "onboarding_checklists": """
        CREATE TABLE IF NOT EXISTS onboarding_checklists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            start_date TEXT,
            mentor_id INTEGER,
            probation_end_date TEXT,
            probation_outcome TEXT,
            overall_status TEXT DEFAULT 'in_progress',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (staff_id) REFERENCES staff(id)
        )
    """,
    "onboarding_tasks": """
        CREATE TABLE IF NOT EXISTS onboarding_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            checklist_id INTEGER NOT NULL,
            task_name TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            assigned_to INTEGER,
            due_date TEXT,
            completed INTEGER DEFAULT 0,
            completed_date TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (checklist_id) REFERENCES onboarding_checklists(id)
        )
    """,
    "probation_reviews": """
        CREATE TABLE IF NOT EXISTS probation_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            checklist_id INTEGER NOT NULL,
            review_date TEXT NOT NULL,
            reviewer_id INTEGER,
            review_number INTEGER DEFAULT 1,
            performance_rating TEXT,
            areas_of_strength TEXT,
            areas_for_development TEXT,
            targets TEXT,
            recommendation TEXT DEFAULT 'continue',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (checklist_id) REFERENCES onboarding_checklists(id)
        )
    """,
    # ---- Expense Claims ----
    "expense_claims": """
        CREATE TABLE IF NOT EXISTS expense_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            claimant_id INTEGER NOT NULL,
            claim_date TEXT NOT NULL DEFAULT (date('now')),
            description TEXT NOT NULL,
            category TEXT DEFAULT 'travel',
            amount REAL NOT NULL,
            mileage REAL,
            mileage_rate REAL DEFAULT 0.45,
            receipt_path TEXT,
            approved_by INTEGER,
            approved_date TEXT,
            paid INTEGER DEFAULT 0,
            paid_date TEXT,
            status TEXT DEFAULT 'submitted',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (claimant_id) REFERENCES staff(id)
        )
    """,
    # ---- Baseline Assessment ----
    "baseline_assessments": """
        CREATE TABLE IF NOT EXISTS baseline_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            academic_year TEXT,
            assessment_type TEXT DEFAULT 'initial',
            assessment_date TEXT NOT NULL DEFAULT (date('now')),
            english_score REAL,
            maths_score REAL,
            ict_score REAL,
            learning_style TEXT,
            prior_attainment TEXT,
            gcse_english_grade TEXT,
            gcse_maths_grade TEXT,
            overall_baseline TEXT,
            additional_needs_identified TEXT,
            assessor_id INTEGER,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "progress_checkpoints": """
        CREATE TABLE IF NOT EXISTS progress_checkpoints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER,
            checkpoint_number INTEGER DEFAULT 1,
            checkpoint_date TEXT NOT NULL,
            current_grade TEXT,
            target_grade TEXT,
            effort_grade TEXT,
            attendance_pct REAL,
            concerns TEXT,
            actions TEXT,
            reviewer_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    # ---- Data Export & ILR ----
    "export_jobs": """
        CREATE TABLE IF NOT EXISTS export_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            export_type TEXT NOT NULL,
            academic_year TEXT,
            description TEXT,
            parameters TEXT,
            file_path TEXT,
            record_count INTEGER DEFAULT 0,
            validation_errors INTEGER DEFAULT 0,
            validation_warnings INTEGER DEFAULT 0,
            validation_log TEXT,
            started_at TEXT,
            completed_at TEXT,
            created_by INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "export_templates": """
        CREATE TABLE IF NOT EXISTS export_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name TEXT NOT NULL,
            export_type TEXT NOT NULL,
            field_mapping TEXT,
            filters TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "academic_transfer_history": """
        CREATE TABLE IF NOT EXISTS academic_transfer_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            source_system TEXT NOT NULL,
            source_student_id TEXT NOT NULL,
            transfer_date TEXT NOT NULL DEFAULT (datetime('now')),
            data_json TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "certificates": """
        CREATE TABLE IF NOT EXISTS certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            certificate_number TEXT UNIQUE NOT NULL,
            certificate_type TEXT NOT NULL,
            course_name TEXT NOT NULL,
            award_date TEXT NOT NULL,
            grade TEXT,
            additional_info TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            issued_by TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "transcript_requests": """
        CREATE TABLE IF NOT EXISTS transcript_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            requested_by TEXT,
            academic_year TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            generated_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ================================================================
    # FEATURES 31-40
    # ================================================================
    # ---- 31. Census / ILR ----
    "census_returns": """
        CREATE TABLE IF NOT EXISTS census_returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            return_type TEXT NOT NULL DEFAULT 'census'
                CHECK(return_type IN ('census','ilr','hesa')),
            academic_year TEXT,
            term TEXT,
            collection_period TEXT,
            submission_deadline TEXT,
            status TEXT NOT NULL DEFAULT 'draft'
                CHECK(status IN ('draft','validated','submitted','accepted','rejected')),
            validation_errors TEXT,
            record_count INTEGER NOT NULL DEFAULT 0,
            submitted_by INTEGER,
            submitted_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (submitted_by) REFERENCES users(id)
        )
    """,
    "census_student_records": """
        CREATE TABLE IF NOT EXISTS census_student_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            census_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            uln TEXT,
            upn TEXT,
            ethnicity TEXT,
            fsm_eligible INTEGER NOT NULL DEFAULT 0,
            send_provision TEXT,
            ehcp INTEGER NOT NULL DEFAULT 0,
            hours_at_provider REAL,
            hours_at_employer REAL,
            planned_hours REAL,
            funding_model TEXT,
            programme_type TEXT,
            valid INTEGER NOT NULL DEFAULT 1,
            validation_notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (census_id) REFERENCES census_returns(id),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "ilr_learning_aims": """
        CREATE TABLE IF NOT EXISTS ilr_learning_aims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            census_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            learning_aim_ref TEXT NOT NULL,
            aim_type TEXT,
            start_date TEXT,
            planned_end_date TEXT,
            actual_end_date TEXT,
            completion_status TEXT,
            outcome TEXT,
            funding_model TEXT,
            delivery_location TEXT,
            partner_ukprn TEXT,
            valid INTEGER NOT NULL DEFAULT 1,
            validation_notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (census_id) REFERENCES census_returns(id),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    # ---- 32. UCAS Export ----
    "ucas_export_batches": """
        CREATE TABLE IF NOT EXISTS ucas_export_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            academic_year TEXT,
            export_type TEXT NOT NULL DEFAULT 'applications'
                CHECK(export_type IN ('applications','references','predictions')),
            record_count INTEGER NOT NULL DEFAULT 0,
            exported_by INTEGER,
            status TEXT NOT NULL DEFAULT 'draft'
                CHECK(status IN ('draft','generated','exported','sent')),
            xml_data TEXT,
            export_date TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (exported_by) REFERENCES users(id)
        )
    """,
    "ucas_export_records": """
        CREATE TABLE IF NOT EXISTS ucas_export_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            ucas_id TEXT,
            personal_id TEXT,
            course_choices TEXT,
            predicted_grades TEXT,
            reference_text TEXT,
            personal_statement_hash TEXT,
            export_status TEXT NOT NULL DEFAULT 'pending'
                CHECK(export_status IN ('pending','included','excluded','error')),
            error_notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (batch_id) REFERENCES ucas_export_batches(id),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    # ---- 33. Destination Outcomes ----
    "destination_outcomes": """
        CREATE TABLE IF NOT EXISTS destination_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            academic_year TEXT,
            leaving_date TEXT,
            outcome_type TEXT DEFAULT 'unknown'
                CHECK(outcome_type IN ('university','apprenticeship','employment',
                      'further_education','gap_year','neet','unknown','volunteering')),
            institution_name TEXT,
            course_title TEXT,
            employer_name TEXT,
            job_title TEXT,
            sustained_at_3m INTEGER NOT NULL DEFAULT 0,
            sustained_at_6m INTEGER NOT NULL DEFAULT 0,
            contact_date TEXT,
            contact_method TEXT,
            verified INTEGER NOT NULL DEFAULT 0,
            verified_by INTEGER,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (verified_by) REFERENCES users(id)
        )
    """,
    "outcome_surveys": """
        CREATE TABLE IF NOT EXISTS outcome_surveys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            academic_year TEXT,
            survey_type TEXT DEFAULT '3_month'
                CHECK(survey_type IN ('3_month','6_month','12_month')),
            sent_date TEXT,
            response_date TEXT,
            current_status TEXT,
            satisfaction_rating INTEGER,
            would_recommend INTEGER NOT NULL DEFAULT 1,
            comments TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    # ---- 34. IQR Manager ----
    "iqr_cycles": """
        CREATE TABLE IF NOT EXISTS iqr_cycles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            academic_year TEXT,
            cycle_name TEXT NOT NULL,
            start_date TEXT,
            end_date TEXT,
            focus_areas TEXT,
            status TEXT NOT NULL DEFAULT 'planned'
                CHECK(status IN ('planned','active','completed')),
            created_by INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """,
    "iqr_visits": """
        CREATE TABLE IF NOT EXISTS iqr_visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle_id INTEGER NOT NULL,
            department TEXT,
            course_id INTEGER,
            visit_date TEXT,
            reviewer_id INTEGER,
            visit_type TEXT NOT NULL DEFAULT 'learning_walk'
                CHECK(visit_type IN ('learning_walk','deep_dive','work_scrutiny',
                      'student_voice','staff_interview')),
            duration_minutes INTEGER NOT NULL DEFAULT 60,
            findings TEXT,
            strengths TEXT,
            areas_for_improvement TEXT,
            overall_judgement TEXT
                CHECK(overall_judgement IN ('outstanding','good',
                      'requires_improvement','inadequate') OR overall_judgement IS NULL),
            status TEXT NOT NULL DEFAULT 'scheduled'
                CHECK(status IN ('scheduled','completed','cancelled')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (cycle_id) REFERENCES iqr_cycles(id),
            FOREIGN KEY (course_id) REFERENCES courses(id),
            FOREIGN KEY (reviewer_id) REFERENCES users(id)
        )
    """,
    "iqr_action_plans": """
        CREATE TABLE IF NOT EXISTS iqr_action_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visit_id INTEGER NOT NULL,
            action_description TEXT NOT NULL,
            responsible_person TEXT,
            target_date TEXT,
            success_criteria TEXT,
            progress TEXT,
            evidence TEXT,
            status TEXT NOT NULL DEFAULT 'not_started'
                CHECK(status IN ('not_started','in_progress','completed','overdue')),
            reviewed_date TEXT,
            reviewed_by INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (visit_id) REFERENCES iqr_visits(id),
            FOREIGN KEY (reviewed_by) REFERENCES users(id)
        )
    """,
    # ---- 35. SEF Builder ----
    "sef_documents": """
        CREATE TABLE IF NOT EXISTS sef_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            academic_year TEXT,
            title TEXT NOT NULL,
            version TEXT NOT NULL DEFAULT '1.0',
            overall_effectiveness TEXT,
            status TEXT NOT NULL DEFAULT 'draft'
                CHECK(status IN ('draft','review','approved','archived')),
            created_by INTEGER,
            approved_by INTEGER,
            approved_date TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (created_by) REFERENCES users(id),
            FOREIGN KEY (approved_by) REFERENCES users(id)
        )
    """,
    "sef_judgement_areas": """
        CREATE TABLE IF NOT EXISTS sef_judgement_areas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sef_id INTEGER NOT NULL,
            area_name TEXT NOT NULL,
            area_number TEXT,
            self_grade TEXT
                CHECK(self_grade IN ('outstanding','good',
                      'requires_improvement','inadequate') OR self_grade IS NULL),
            narrative TEXT,
            strengths TEXT,
            areas_for_improvement TEXT,
            key_actions TEXT,
            display_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (sef_id) REFERENCES sef_documents(id)
        )
    """,
    "sef_evidence_links": """
        CREATE TABLE IF NOT EXISTS sef_evidence_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            judgement_area_id INTEGER NOT NULL,
            evidence_type TEXT NOT NULL DEFAULT 'data'
                CHECK(evidence_type IN ('data','document','observation',
                      'survey','outcome','external')),
            evidence_description TEXT NOT NULL,
            data_source TEXT,
            data_query TEXT,
            data_value TEXT,
            document_path TEXT,
            linked_at TEXT NOT NULL DEFAULT (datetime('now')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (judgement_area_id) REFERENCES sef_judgement_areas(id)
        )
    """,
    # ---- 36. Question-Level Analysis ----
    "assessment_papers": """
        CREATE TABLE IF NOT EXISTS assessment_papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER,
            title TEXT NOT NULL,
            exam_board TEXT,
            paper_code TEXT,
            total_marks INTEGER NOT NULL,
            assessment_date TEXT,
            academic_year TEXT,
            created_by INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (course_id) REFERENCES courses(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """,
    "paper_questions": """
        CREATE TABLE IF NOT EXISTS paper_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id INTEGER NOT NULL,
            question_number TEXT NOT NULL,
            topic TEXT,
            subtopic TEXT,
            max_marks INTEGER NOT NULL,
            skill_type TEXT
                CHECK(skill_type IN ('knowledge','application','analysis','evaluation')
                      OR skill_type IS NULL),
            difficulty TEXT
                CHECK(difficulty IN ('easy','medium','hard') OR difficulty IS NULL),
            specification_ref TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (paper_id) REFERENCES assessment_papers(id)
        )
    """,
    "student_question_scores": """
        CREATE TABLE IF NOT EXISTS student_question_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            marks_awarded INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (question_id) REFERENCES paper_questions(id),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    # ---- 37. Target Setting ----
    "prior_attainment": """
        CREATE TABLE IF NOT EXISTS prior_attainment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            qualification_type TEXT DEFAULT 'gcse'
                CHECK(qualification_type IN ('gcse','btec','other')),
            subject TEXT,
            grade TEXT,
            points REAL,
            academic_year TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "target_grades": """
        CREATE TABLE IF NOT EXISTS target_grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            prior_average_points REAL,
            meg_grade TEXT,
            target_grade TEXT,
            aspirational_grade TEXT,
            current_grade TEXT,
            alps_score REAL,
            value_added REAL,
            setting_method TEXT NOT NULL DEFAULT 'alps'
                CHECK(setting_method IN ('alps','fft','internal','manual')),
            academic_year TEXT,
            generated_at TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (course_id) REFERENCES courses(id)
        )
    """,
    "alps_benchmarks": """
        CREATE TABLE IF NOT EXISTS alps_benchmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            qualification_type TEXT NOT NULL,
            prior_points_min REAL,
            prior_points_max REAL,
            subject_group TEXT,
            meg_grade TEXT,
            target_grade TEXT,
            aspirational_grade TEXT,
            academic_year TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    # ---- 38. Cover Agency ----
    "cover_agencies": """
        CREATE TABLE IF NOT EXISTS cover_agencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agency_name TEXT NOT NULL,
            contact_name TEXT,
            contact_email TEXT,
            contact_phone TEXT,
            address TEXT,
            specialisms TEXT,
            day_rate REAL NOT NULL DEFAULT 0,
            preferred_rank INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            contract_start TEXT,
            contract_end TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "agency_cover_requests": """
        CREATE TABLE IF NOT EXISTS agency_cover_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cover_arrangement_id INTEGER,
            agency_id INTEGER NOT NULL,
            subject_area TEXT,
            date_required TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            year_group TEXT,
            special_requirements TEXT,
            request_sent_at TEXT,
            agency_response TEXT NOT NULL DEFAULT 'pending'
                CHECK(agency_response IN ('pending','accepted','declined','no_response')),
            teacher_name TEXT,
            teacher_confirmed INTEGER NOT NULL DEFAULT 0,
            day_rate REAL,
            status TEXT NOT NULL DEFAULT 'draft'
                CHECK(status IN ('draft','sent','confirmed','cancelled')),
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (cover_arrangement_id) REFERENCES cover_arrangements(id),
            FOREIGN KEY (agency_id) REFERENCES cover_agencies(id)
        )
    """,
    "agency_invoices": """
        CREATE TABLE IF NOT EXISTS agency_invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agency_id INTEGER NOT NULL,
            invoice_number TEXT,
            invoice_date TEXT,
            period_start TEXT,
            period_end TEXT,
            days_covered INTEGER NOT NULL DEFAULT 0,
            total_amount REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'received'
                CHECK(status IN ('received','approved','paid','disputed')),
            approved_by INTEGER,
            paid_date TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (agency_id) REFERENCES cover_agencies(id),
            FOREIGN KEY (approved_by) REFERENCES users(id)
        )
    """,
    # ---- 39. Lettings Portal ----
    "lettings_hirers": """
        CREATE TABLE IF NOT EXISTS lettings_hirers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organisation_name TEXT NOT NULL,
            contact_name TEXT NOT NULL,
            contact_email TEXT,
            contact_phone TEXT,
            address TEXT,
            account_type TEXT NOT NULL DEFAULT 'occasional'
                CHECK(account_type IN ('regular','occasional','community','commercial')),
            discount_rate REAL NOT NULL DEFAULT 0,
            credit_limit REAL NOT NULL DEFAULT 0,
            dbs_on_file INTEGER NOT NULL DEFAULT 0,
            insurance_verified INTEGER NOT NULL DEFAULT 0,
            insurance_expiry TEXT,
            terms_agreed INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "lettings_invoices": """
        CREATE TABLE IF NOT EXISTS lettings_invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER,
            hirer_id INTEGER NOT NULL,
            invoice_number TEXT UNIQUE,
            invoice_date TEXT,
            subtotal REAL NOT NULL DEFAULT 0,
            vat_amount REAL NOT NULL DEFAULT 0,
            discount_amount REAL NOT NULL DEFAULT 0,
            total_amount REAL NOT NULL DEFAULT 0,
            due_date TEXT,
            payment_terms TEXT NOT NULL DEFAULT '30 days',
            status TEXT NOT NULL DEFAULT 'draft'
                CHECK(status IN ('draft','sent','paid','overdue','cancelled','credit_note')),
            paid_amount REAL NOT NULL DEFAULT 0,
            paid_date TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (booking_id) REFERENCES lettings_bookings(id),
            FOREIGN KEY (hirer_id) REFERENCES lettings_hirers(id)
        )
    """,
    "lettings_facilities": """
        CREATE TABLE IF NOT EXISTS lettings_facilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            facility_name TEXT NOT NULL,
            facility_type TEXT DEFAULT 'classroom'
                CHECK(facility_type IN ('hall','sports_hall','classroom','field',
                      'studio','meeting_room','other')),
            capacity INTEGER,
            hourly_rate REAL NOT NULL DEFAULT 0,
            half_day_rate REAL NOT NULL DEFAULT 0,
            full_day_rate REAL NOT NULL DEFAULT 0,
            community_rate REAL NOT NULL DEFAULT 0,
            available_days TEXT NOT NULL DEFAULT 'Mon,Tue,Wed,Thu,Fri',
            available_from TEXT NOT NULL DEFAULT '17:00',
            available_until TEXT NOT NULL DEFAULT '22:00',
            weekend_available INTEGER NOT NULL DEFAULT 1,
            equipment_included TEXT,
            special_conditions TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "lettings_availability": """
        CREATE TABLE IF NOT EXISTS lettings_availability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            facility_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            is_blocked INTEGER NOT NULL DEFAULT 0,
            block_reason TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (facility_id) REFERENCES lettings_facilities(id)
        )
    """,
    # ---- 40. Employer Portal ----
    "employer_accounts": """
        CREATE TABLE IF NOT EXISTS employer_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            contact_name TEXT NOT NULL,
            contact_email TEXT,
            contact_phone TEXT,
            address TEXT,
            sector TEXT,
            company_size TEXT DEFAULT 'small'
                CHECK(company_size IN ('small','medium','large')),
            levy_payer INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            portal_access_enabled INTEGER NOT NULL DEFAULT 0,
            last_login TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "employer_learner_links": """
        CREATE TABLE IF NOT EXISTS employer_learner_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employer_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            apprenticeship_standard TEXT,
            start_date TEXT,
            expected_end_date TEXT,
            actual_end_date TEXT,
            mentor_name TEXT,
            mentor_email TEXT,
            training_plan TEXT,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK(status IN ('active','completed','withdrawn','break_in_learning')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (employer_id) REFERENCES employer_accounts(id),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "progress_reviews": """
        CREATE TABLE IF NOT EXISTS progress_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            learner_link_id INTEGER NOT NULL,
            review_date TEXT NOT NULL,
            review_type TEXT NOT NULL DEFAULT 'monthly'
                CHECK(review_type IN ('monthly','tripartite','gateway','epa_readiness')),
            reviewer_name TEXT,
            on_track INTEGER NOT NULL DEFAULT 1,
            ksbm_progress TEXT,
            off_the_job_hours REAL NOT NULL DEFAULT 0,
            off_the_job_target REAL NOT NULL DEFAULT 0,
            employer_feedback TEXT,
            learner_feedback TEXT,
            assessor_feedback TEXT,
            actions TEXT,
            employer_signed INTEGER NOT NULL DEFAULT 0,
            learner_signed INTEGER NOT NULL DEFAULT 0,
            assessor_signed INTEGER NOT NULL DEFAULT 0,
            next_review_date TEXT,
            status TEXT NOT NULL DEFAULT 'scheduled'
                CHECK(status IN ('scheduled','completed','missed')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (learner_link_id) REFERENCES employer_learner_links(id)
        )
    """,
    "employer_sign_offs": """
        CREATE TABLE IF NOT EXISTS employer_sign_offs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id INTEGER NOT NULL,
            signer_type TEXT NOT NULL
                CHECK(signer_type IN ('employer','learner','assessor')),
            signer_name TEXT,
            signed_at TEXT,
            comments TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (review_id) REFERENCES progress_reviews(id)
        )
    """,
}


def init_db(db_path: str | None = None):
    """Initialize the database with all tables."""
    conn = connect(db_path)
    try:
        for table_sql in TABLES.values():
            conn.execute(table_sql)

        # Migration: add timetable_slot_id to attendance_sessions if missing
        cursor = conn.execute("PRAGMA table_info(attendance_sessions)")
        columns = [row[1] for row in cursor.fetchall()]
        if "timetable_slot_id" not in columns:
            conn.execute(
                "ALTER TABLE attendance_sessions ADD COLUMN timetable_slot_id INTEGER"
            )

        # Migration: add previous_system columns to students if missing
        cols = {r[1] for r in conn.execute("PRAGMA table_info(students)").fetchall()}
        if "previous_system" not in cols:
            conn.execute("ALTER TABLE students ADD COLUMN previous_system TEXT")
        if "previous_system_id" not in cols:
            conn.execute("ALTER TABLE students ADD COLUMN previous_system_id TEXT")

        # Shared LMS tables
        from education_system.shared.lms.schema import create_lms_tables
        create_lms_tables(conn)

        conn.commit()
        logger.info("Database initialized successfully")
    finally:
        conn.close()


def seed_default_data(db_path: str | None = None):
    """Seed the database with default roles and admin user."""
    from education_system.college_system.infrastructure.auth.password_manager import hash_password
    from education_system.college_system.core.defaults import (
        DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD,
        DEFAULT_TEACHER_USERNAME, DEFAULT_TEACHER_PASSWORD,
        DEFAULT_STUDENT_USERNAME, DEFAULT_STUDENT_PASSWORD,
    )

    conn = connect(db_path)
    try:
        # Seed roles
        roles = [
            ("admin", "System administrator", 100),
            ("staff", "Staff member", 75),
            ("instructor", "Course instructor", 50),
            ("teacher", "Subject teacher", 50),
            ("parent", "Parent/Guardian", 30),
            ("student", "Student", 25),
        ]
        for name, desc, level in roles:
            conn.execute(
                "INSERT OR IGNORE INTO roles (name, description, level) VALUES (?, ?, ?)",
                (name, desc, level),
            )

        # Seed default permissions
        admin_perms = [
            ("users", "create"), ("users", "read"), ("users", "update"), ("users", "delete"),
            ("students", "create"), ("students", "read"), ("students", "update"), ("students", "delete"),
            ("courses", "create"), ("courses", "read"), ("courses", "update"), ("courses", "delete"),
            ("enrollments", "create"), ("enrollments", "read"), ("enrollments", "update"), ("enrollments", "delete"),
            ("grades", "create"), ("grades", "read"), ("grades", "update"), ("grades", "delete"),
            ("attendance", "create"), ("attendance", "read"), ("attendance", "update"), ("attendance", "delete"),
        ]
        admin_role = conn.execute("SELECT id FROM roles WHERE name = 'admin'").fetchone()
        if admin_role:
            for resource, action in admin_perms:
                conn.execute(
                    "INSERT OR IGNORE INTO permissions (role_id, resource, action) VALUES (?, ?, ?)",
                    (admin_role["id"], resource, action),
                )

        # Seed instructor permissions
        instructor_role = conn.execute("SELECT id FROM roles WHERE name = 'instructor'").fetchone()
        if instructor_role:
            instructor_perms = [
                ("students", "read"), ("courses", "read"), ("courses", "update"),
                ("enrollments", "read"), ("grades", "create"), ("grades", "read"),
                ("grades", "update"), ("attendance", "create"), ("attendance", "read"),
                ("attendance", "update"),
            ]
            for resource, action in instructor_perms:
                conn.execute(
                    "INSERT OR IGNORE INTO permissions (role_id, resource, action) VALUES (?, ?, ?)",
                    (instructor_role["id"], resource, action),
                )

        # Seed teacher permissions (same as instructor)
        teacher_role = conn.execute("SELECT id FROM roles WHERE name = 'teacher'").fetchone()
        if teacher_role:
            teacher_perms = [
                ("students", "read"), ("courses", "read"), ("courses", "update"),
                ("enrollments", "read"), ("grades", "create"), ("grades", "read"),
                ("grades", "update"), ("attendance", "create"), ("attendance", "read"),
                ("attendance", "update"),
            ]
            for resource, action in teacher_perms:
                conn.execute(
                    "INSERT OR IGNORE INTO permissions (role_id, resource, action) VALUES (?, ?, ?)",
                    (teacher_role["id"], resource, action),
                )

        # Seed student permissions
        student_role = conn.execute("SELECT id FROM roles WHERE name = 'student'").fetchone()
        if student_role:
            student_perms = [
                ("students", "read"), ("courses", "read"),
                ("enrollments", "read"), ("grades", "read"), ("attendance", "read"),
            ]
            for resource, action in student_perms:
                conn.execute(
                    "INSERT OR IGNORE INTO permissions (role_id, resource, action) VALUES (?, ?, ?)",
                    (student_role["id"], resource, action),
                )

        # Seed admin user
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (DEFAULT_ADMIN_USERNAME,)
        ).fetchone()
        if not existing:
            pw_hash = hash_password(DEFAULT_ADMIN_PASSWORD)
            conn.execute(
                "INSERT INTO users (username, password_hash, role, email) VALUES (?, ?, ?, ?)",
                (DEFAULT_ADMIN_USERNAME, pw_hash, "admin", "admin@sixthform.ac.uk"),
            )

        # Seed default teacher user
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (DEFAULT_TEACHER_USERNAME,)
        ).fetchone()
        if not existing:
            pw_hash = hash_password(DEFAULT_TEACHER_PASSWORD)
            conn.execute(
                "INSERT INTO users (username, password_hash, role, email) VALUES (?, ?, ?, ?)",
                (DEFAULT_TEACHER_USERNAME, pw_hash, "teacher", "teacher@sixthform.ac.uk"),
            )

        # Seed default student user (with linked student record)
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (DEFAULT_STUDENT_USERNAME,)
        ).fetchone()
        if not existing:
            pw_hash = hash_password(DEFAULT_STUDENT_PASSWORD)
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, role, email) VALUES (?, ?, ?, ?)",
                (DEFAULT_STUDENT_USERNAME, pw_hash, "student", "student@sixthform.ac.uk"),
            )
            student_user_id = cursor.lastrowid

            # Create a linked student record
            existing_student = conn.execute(
                "SELECT id FROM students WHERE student_id = ?", ("SFC0001",)
            ).fetchone()
            if not existing_student:
                conn.execute(
                    """INSERT INTO students
                       (student_id, user_id, first_name, last_name, email, year_group, form_group)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    ("SFC0001", student_user_id, "Demo", "Student",
                     "student@sixthform.ac.uk", "12", "12A"),
                )

        # Seed default courses
        default_courses = [
            # (course_code, title, GLH, capacity, qualification_type, subject_area, teacher, term)
            ("MATH101", "Mathematics", 360, 30, "A-Level", "Mathematics", "Dr S. Patel", "Autumn"),
            ("MATH102", "Further Mathematics", 360, 25, "A-Level", "Mathematics", "Dr S. Patel", "Autumn"),
            ("PHYS101", "Physics", 360, 30, "A-Level", "Science", "Mr R. Thompson", "Autumn"),
            ("CHEM101", "Chemistry", 360, 30, "A-Level", "Science", "Dr L. Chen", "Autumn"),
            ("BIO101", "Biology", 360, 30, "A-Level", "Science", "Mrs K. Williams", "Autumn"),
            ("CS101", "Computer Science", 360, 28, "A-Level", "Technology", "Mr J. Ahmed", "Autumn"),
            ("ENG101", "English Literature", 360, 30, "A-Level", "English", "Ms H. Clarke", "Autumn"),
            ("ENG102", "English Language", 360, 30, "A-Level", "English", "Ms H. Clarke", "Spring"),
            ("HIST101", "History", 360, 30, "A-Level", "Humanities", "Mr D. Evans", "Autumn"),
            ("GEOG101", "Geography", 360, 30, "A-Level", "Humanities", "Mrs F. Taylor", "Autumn"),
            ("PSYCH101", "Psychology", 360, 32, "A-Level", "Social Sciences", "Dr M. Brooks", "Autumn"),
            ("SOC101", "Sociology", 360, 30, "A-Level", "Social Sciences", "Ms N. Okafor", "Spring"),
            ("ECON101", "Economics", 360, 30, "A-Level", "Business", "Mr A. Shah", "Autumn"),
            ("BUS101", "Business Studies", 360, 30, "A-Level", "Business", "Mr A. Shah", "Spring"),
            ("ART101", "Art and Design", 360, 24, "A-Level", "Creative Arts", "Mrs P. Reynolds", "Autumn"),
            ("MUS101", "Music", 360, 20, "A-Level", "Creative Arts", "Mr G. Foster", "Autumn"),
            ("FREN101", "French", 360, 25, "A-Level", "Modern Languages", "Mme C. Dubois", "Autumn"),
            ("SPAN101", "Spanish", 360, 25, "A-Level", "Modern Languages", "Sr B. Garcia", "Autumn"),
            ("BTEC_BUS", "Business", 360, 28, "BTEC", "Business", "Ms R. Hughes", "Autumn"),
            ("BTEC_HSC", "Health and Social Care", 360, 26, "BTEC", "Health", "Mrs J. Morgan", "Autumn"),
        ]
        for code, title, glh, cap, qual, area, tch, trm in default_courses:
            conn.execute(
                """INSERT OR IGNORE INTO courses
                   (course_code, title, credits, capacity, qualification_type, subject_area, teacher, term)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (code, title, glh, cap, qual, area, tch, trm),
            )

        # Seed default staff records
        staff_records = [
            ("STF0001", None, "Mrs", "Linda", "Patel", "l.patel@sixthform.ac.uk",
             "A-Level Sciences", None, "active"),
            ("STF0002", None, "Dr", "Simon", "Whitaker", "s.whitaker@sixthform.ac.uk",
             "A-Level Mathematics", None, "active"),
            ("STF0003", None, "Mr", "Andrew", "Mensah", "a.mensah@sixthform.ac.uk",
             "BTEC Business", None, "active"),
            ("STF0004", None, "Ms", "Fiona", "Campbell", "f.campbell@sixthform.ac.uk",
             "Student Services", None, "active"),
            ("STF0005", None, "Mrs", "Janet", "Riley", "j.riley@sixthform.ac.uk",
             "Careers", None, "active"),
        ]
        for sid, uid, title, fn, ln, email, subj, fg, status in staff_records:
            conn.execute(
                """INSERT OR IGNORE INTO staff
                   (staff_id, user_id, title, first_name, last_name, email,
                    subject_area, form_group, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sid, uid, title, fn, ln, email, subj, fg, status),
            )

        conn.commit()
        logger.info("Default data seeded successfully")
    finally:
        conn.close()
