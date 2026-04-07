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
            last_login TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
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
            dbs_number TEXT,
            qualifications TEXT,
            emergency_contact_name TEXT,
            emergency_contact_phone TEXT,
            notes TEXT,
            leaving_date TEXT,
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
            file_path TEXT,
            is_late INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "homework_feedback": """
        CREATE TABLE IF NOT EXISTS homework_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL REFERENCES homework_submissions(id),
            teacher_feedback TEXT,
            sticker TEXT,
            parent_comment TEXT,
            parent_id TEXT,
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
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
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
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
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
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
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
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
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
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
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
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
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
            available_copies INTEGER DEFAULT 1,
            status TEXT DEFAULT 'Available',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
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
            returned_date TEXT,
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
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
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
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
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
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
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
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
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
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
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
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
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
            status TEXT DEFAULT 'open',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
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
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT
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
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT
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
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT
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
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT,
            closed_at TEXT
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
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
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
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
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
    "payroll_records": """
        CREATE TABLE IF NOT EXISTS payroll_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            pay_period TEXT NOT NULL,
            gross_pay REAL NOT NULL DEFAULT 0,
            tax REAL NOT NULL DEFAULT 0,
            ni_contribution REAL NOT NULL DEFAULT 0,
            pension REAL NOT NULL DEFAULT 0,
            other_deductions REAL NOT NULL DEFAULT 0,
            net_pay REAL NOT NULL DEFAULT 0,
            status TEXT DEFAULT 'draft'
                CHECK(status IN ('draft','pending_approval','approved','processed','paid')),
            approved_by TEXT,
            processed_date TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (staff_id) REFERENCES staff(id)
        )
    """,
    "payroll_config": """
        CREATE TABLE IF NOT EXISTS payroll_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tax_year TEXT NOT NULL,
            tax_band_1 REAL DEFAULT 12570,
            tax_rate_1 REAL DEFAULT 0.20,
            tax_band_2 REAL DEFAULT 50270,
            tax_rate_2 REAL DEFAULT 0.40,
            ni_threshold REAL DEFAULT 12570,
            ni_rate REAL DEFAULT 0.12,
            pension_rate REAL DEFAULT 0.05,
            created_at TEXT DEFAULT (datetime('now'))
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
    # ── Pupil Wellbeing ──
    "pupil_wellbeing_concerns": """
        CREATE TABLE IF NOT EXISTS pupil_wellbeing_concerns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id TEXT NOT NULL,
            reported_by TEXT NOT NULL,
            concern_type TEXT NOT NULL,
            description TEXT NOT NULL,
            severity TEXT DEFAULT 'Low',
            status TEXT DEFAULT 'Open',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "pupil_wellbeing_checkins": """
        CREATE TABLE IF NOT EXISTS pupil_wellbeing_checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id TEXT NOT NULL,
            feeling TEXT NOT NULL,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "pupil_parent_meetings": """
        CREATE TABLE IF NOT EXISTS pupil_parent_meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id TEXT NOT NULL,
            staff_id TEXT NOT NULL,
            meeting_date TEXT NOT NULL,
            notes TEXT,
            actions TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Feedback & Complaints ──
    "feedback": """
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            category TEXT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            anonymous INTEGER DEFAULT 0,
            status TEXT DEFAULT 'open',
            votes INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "feedback_responses": """
        CREATE TABLE IF NOT EXISTS feedback_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feedback_id INTEGER NOT NULL,
            response TEXT NOT NULL,
            responded_by TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "complaints": """
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complainant_id TEXT,
            category TEXT,
            subject TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT DEFAULT 'open',
            priority TEXT DEFAULT 'normal',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "complaint_responses": """
        CREATE TABLE IF NOT EXISTS complaint_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id INTEGER NOT NULL,
            response TEXT NOT NULL,
            responded_by TEXT,
            action_taken TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── GDPR ──
    "gdpr_requests": """
        CREATE TABLE IF NOT EXISTS gdpr_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_name TEXT NOT NULL,
            requester_email TEXT,
            request_type TEXT NOT NULL,
            details TEXT,
            status TEXT DEFAULT 'pending',
            processed_by TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT
        )
    """,
    "gdpr_consent_records": """
        CREATE TABLE IF NOT EXISTS gdpr_consent_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            consent_type TEXT NOT NULL,
            consented INTEGER DEFAULT 0,
            consent_date TEXT,
            withdrawal_date TEXT
        )
    """,
    # ── Dashboard KPIs ──
    "dashboard_kpis": """
        CREATE TABLE IF NOT EXISTS dashboard_kpis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kpi_name TEXT NOT NULL,
            kpi_value TEXT,
            period TEXT,
            category TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Payroll (defined earlier with full constraints)
    # ── Staff Management ──
    "staff_appraisals": """
        CREATE TABLE IF NOT EXISTS staff_appraisals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id TEXT NOT NULL,
            appraiser_id TEXT,
            academic_year TEXT,
            status TEXT DEFAULT 'scheduled',
            overall_rating TEXT,
            summary TEXT,
            meeting_date TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "appraisal_objectives": """
        CREATE TABLE IF NOT EXISTS appraisal_objectives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appraisal_id INTEGER NOT NULL,
            objective TEXT NOT NULL,
            target TEXT,
            progress TEXT,
            status TEXT DEFAULT 'not_started',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "lesson_observations": """
        CREATE TABLE IF NOT EXISTS lesson_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id TEXT NOT NULL,
            observer_id TEXT,
            observation_date TEXT NOT NULL,
            subject TEXT,
            class_name TEXT,
            grade TEXT,
            strengths TEXT,
            areas_for_improvement TEXT,
            actions TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "staff_wellbeing_surveys": """
        CREATE TABLE IF NOT EXISTS staff_wellbeing_surveys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'draft',
            created_by TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "staff_wellbeing_responses": """
        CREATE TABLE IF NOT EXISTS staff_wellbeing_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER NOT NULL,
            staff_id TEXT,
            responses_json TEXT,
            submitted_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "staff_support_requests": """
        CREATE TABLE IF NOT EXISTS staff_support_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id TEXT NOT NULL,
            category TEXT,
            description TEXT,
            status TEXT DEFAULT 'open',
            assigned_to TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Lesson Plans ──
    "lesson_plans": """
        CREATE TABLE IF NOT EXISTS lesson_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id TEXT NOT NULL,
            subject TEXT,
            class_name TEXT,
            lesson_date TEXT,
            topic TEXT NOT NULL,
            objectives TEXT,
            activities TEXT,
            resources TEXT,
            assessment TEXT,
            differentiation TEXT,
            timing_notes TEXT,
            shared INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "lesson_plan_shares": """
        CREATE TABLE IF NOT EXISTS lesson_plan_shares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            shared_with_id TEXT NOT NULL,
            shared_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Portfolio & Skills ──
    "learning_portfolio": """
        CREATE TABLE IF NOT EXISTS learning_portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            subject TEXT,
            term TEXT,
            teacher_comment TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "pupil_skills": """
        CREATE TABLE IF NOT EXISTS pupil_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id TEXT NOT NULL,
            skill_area TEXT,
            skill_name TEXT NOT NULL,
            level TEXT DEFAULT 'beginning',
            assessed_by TEXT,
            assessed_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Homework Enhancements (homework_feedback defined earlier with FK constraints) ──
    # ── Student ID Cards ──
    "student_id_cards": """
        CREATE TABLE IF NOT EXISTS student_id_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            card_number TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            photo_path TEXT,
            qr_data TEXT,
            issue_date TEXT NOT NULL,
            expiry_date TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── LMS ──
    "lms_modules": """
        CREATE TABLE IF NOT EXISTS lms_modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id TEXT,
            title TEXT NOT NULL,
            description TEXT,
            order_index INTEGER DEFAULT 0,
            published INTEGER DEFAULT 0,
            created_by TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "lms_lessons": """
        CREATE TABLE IF NOT EXISTS lms_lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content_type TEXT DEFAULT 'text',
            content TEXT,
            order_index INTEGER DEFAULT 0,
            duration_mins INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "lms_progress": """
        CREATE TABLE IF NOT EXISTS lms_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            lesson_id INTEGER NOT NULL,
            completed INTEGER DEFAULT 0,
            completed_at TEXT
        )
    """,
    "lms_quizzes": """
        CREATE TABLE IF NOT EXISTS lms_quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            pass_mark INTEGER DEFAULT 50,
            time_limit_mins INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "lms_questions": """
        CREATE TABLE IF NOT EXISTS lms_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            question_type TEXT DEFAULT 'multiple_choice',
            options_json TEXT,
            correct_answer TEXT NOT NULL,
            marks INTEGER DEFAULT 1,
            order_index INTEGER DEFAULT 0
        )
    """,
    "lms_quiz_attempts": """
        CREATE TABLE IF NOT EXISTS lms_quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            answers_json TEXT,
            score INTEGER,
            passed INTEGER DEFAULT 0,
            attempted_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "lms_resources": """
        CREATE TABLE IF NOT EXISTS lms_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            file_path TEXT,
            resource_type TEXT DEFAULT 'document',
            course_id TEXT,
            uploaded_by TEXT,
            download_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Academics: academic_year ────────────────────────────────────────
    "academic_years": """
        CREATE TABLE IF NOT EXISTS academic_years (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            is_current INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "academic_terms": """
        CREATE TABLE IF NOT EXISTS academic_terms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            academic_year_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            term_number INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            FOREIGN KEY (academic_year_id) REFERENCES academic_years(id)
        )
    """,
    # ── Academics: assignments ──────────────────────────────────────────
    "assignments": """
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            subject_id INTEGER,
            teacher_id INTEGER,
            class_name TEXT,
            year_group TEXT,
            due_date TEXT,
            max_marks INTEGER DEFAULT 100,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        )
    """,
    "assignment_submissions": """
        CREATE TABLE IF NOT EXISTS assignment_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            pupil_id INTEGER NOT NULL,
            submitted_at TEXT DEFAULT (datetime('now')),
            marks INTEGER,
            feedback TEXT,
            status TEXT DEFAULT 'submitted',
            FOREIGN KEY (assignment_id) REFERENCES assignments(id),
            FOREIGN KEY (pupil_id) REFERENCES pupils(id)
        )
    """,
    # ── Academics: baseline_assessment ──────────────────────────────────
    "baseline_assessments": """
        CREATE TABLE IF NOT EXISTS baseline_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id INTEGER NOT NULL,
            subject_id INTEGER,
            assessment_type TEXT NOT NULL,
            score REAL,
            band TEXT,
            assessor_id INTEGER,
            assessed_date TEXT NOT NULL,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (pupil_id) REFERENCES pupils(id),
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        )
    """,
    # ── Academics: markbook ─────────────────────────────────────────────
    "markbook_entries": """
        CREATE TABLE IF NOT EXISTS markbook_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            teacher_id INTEGER,
            assessment_name TEXT NOT NULL,
            score REAL,
            max_score REAL DEFAULT 100,
            grade TEXT,
            term TEXT,
            date_recorded TEXT DEFAULT (date('now')),
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (pupil_id) REFERENCES pupils(id),
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        )
    """,
    # ── Academics: target_setting ───────────────────────────────────────
    "pupil_targets": """
        CREATE TABLE IF NOT EXISTS pupil_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id INTEGER NOT NULL,
            subject_id INTEGER,
            target_level TEXT,
            current_level TEXT,
            expected_level TEXT,
            set_by INTEGER,
            review_date TEXT,
            status TEXT DEFAULT 'active',
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (pupil_id) REFERENCES pupils(id),
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        )
    """,
    # ── Academics: question_analysis ────────────────────────────────────
    "question_analyses": """
        CREATE TABLE IF NOT EXISTS question_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id INTEGER NOT NULL,
            question_number INTEGER NOT NULL,
            topic TEXT,
            max_marks INTEGER NOT NULL,
            mean_score REAL,
            pass_rate REAL,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (assessment_id) REFERENCES assessments(id)
        )
    """,
    # ── Admin: health_safety ────────────────────────────────────────────
    "health_safety_incidents": """
        CREATE TABLE IF NOT EXISTS health_safety_incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            location TEXT,
            reported_by TEXT,
            reported_date TEXT DEFAULT (date('now')),
            severity TEXT DEFAULT 'low',
            status TEXT DEFAULT 'open',
            action_taken TEXT,
            resolved_date TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "health_safety_inspections": """
        CREATE TABLE IF NOT EXISTS health_safety_inspections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            area TEXT NOT NULL,
            inspector TEXT,
            inspection_date TEXT DEFAULT (date('now')),
            next_due TEXT,
            status TEXT DEFAULT 'scheduled',
            findings TEXT,
            actions_required TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Admin: risk_management ──────────────────────────────────────────
    "risk_assessments": """
        CREATE TABLE IF NOT EXISTS risk_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT,
            location TEXT,
            risk_level TEXT DEFAULT 'medium',
            likelihood INTEGER DEFAULT 3,
            impact INTEGER DEFAULT 3,
            control_measures TEXT,
            assessor TEXT,
            assessment_date TEXT DEFAULT (date('now')),
            review_date TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Admin: compliance ───────────────────────────────────────────────
    "compliance_checks": """
        CREATE TABLE IF NOT EXISTS compliance_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            area TEXT NOT NULL,
            requirement TEXT NOT NULL,
            description TEXT,
            responsible_person TEXT,
            check_date TEXT DEFAULT (date('now')),
            next_due TEXT,
            status TEXT DEFAULT 'compliant',
            evidence TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Admin: prevent_duty ─────────────────────────────────────────────
    "prevent_referrals": """
        CREATE TABLE IF NOT EXISTS prevent_referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id INTEGER,
            staff_reporter_id INTEGER,
            concern_type TEXT NOT NULL,
            description TEXT NOT NULL,
            risk_level TEXT DEFAULT 'low',
            action_taken TEXT,
            referral_date TEXT DEFAULT (date('now')),
            status TEXT DEFAULT 'open',
            outcome TEXT,
            resolved_date TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (pupil_id) REFERENCES pupils(id)
        )
    """,
    "prevent_training": """
        CREATE TABLE IF NOT EXISTS prevent_training (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            training_type TEXT NOT NULL,
            completion_date TEXT NOT NULL,
            expiry_date TEXT,
            certificate_ref TEXT,
            status TEXT DEFAULT 'valid',
            FOREIGN KEY (staff_id) REFERENCES staff(id)
        )
    """,
    # ── Admin: audit_reports ────────────────────────────────────────────
    "audit_reports": """
        CREATE TABLE IF NOT EXISTS audit_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            report_type TEXT NOT NULL,
            scope TEXT,
            auditor TEXT,
            audit_date TEXT DEFAULT (date('now')),
            findings TEXT,
            recommendations TEXT,
            status TEXT DEFAULT 'draft',
            follow_up_date TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Admin: bulk_operations ──────────────────────────────────────────
    "bulk_operations": """
        CREATE TABLE IF NOT EXISTS bulk_operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_type TEXT NOT NULL,
            description TEXT,
            initiated_by TEXT,
            total_records INTEGER DEFAULT 0,
            processed_records INTEGER DEFAULT 0,
            failed_records INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            error_log TEXT,
            started_at TEXT,
            completed_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Admin: census ───────────────────────────────────────────────────
    "census_returns": """
        CREATE TABLE IF NOT EXISTS census_returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            census_type TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            return_date TEXT,
            total_pupils INTEGER DEFAULT 0,
            total_staff INTEGER DEFAULT 0,
            fsm_count INTEGER DEFAULT 0,
            sen_count INTEGER DEFAULT 0,
            eal_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'draft',
            submission_ref TEXT,
            submitted_by TEXT,
            submitted_at TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Admin: quality_assurance ────────────────────────────────────────
    "qa_reviews": """
        CREATE TABLE IF NOT EXISTS qa_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_type TEXT NOT NULL,
            subject_area TEXT,
            reviewer TEXT,
            review_date TEXT DEFAULT (date('now')),
            rating TEXT,
            strengths TEXT,
            areas_for_improvement TEXT,
            action_plan TEXT,
            follow_up_date TEXT,
            status TEXT DEFAULT 'scheduled',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Admin: self_assessment ──────────────────────────────────────────
    "self_assessments": """
        CREATE TABLE IF NOT EXISTS self_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            academic_year TEXT NOT NULL,
            area TEXT NOT NULL,
            ofsted_grade TEXT,
            evidence TEXT,
            strengths TEXT,
            improvements TEXT,
            action_plan TEXT,
            assessor TEXT,
            assessment_date TEXT DEFAULT (date('now')),
            status TEXT DEFAULT 'draft',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Staff: dbs_checks ───────────────────────────────────────────────
    "dbs_checks": """
        CREATE TABLE IF NOT EXISTS dbs_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            check_type TEXT DEFAULT 'Enhanced',
            certificate_number TEXT,
            issue_date TEXT,
            expiry_date TEXT,
            status TEXT DEFAULT 'pending',
            verified_by TEXT,
            verified_date TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (staff_id) REFERENCES staff(id)
        )
    """,
    # ── Staff: first_aid ────────────────────────────────────────────────
    "first_aid_incidents": """
        CREATE TABLE IF NOT EXISTS first_aid_incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT NOT NULL,
            patient_type TEXT DEFAULT 'pupil',
            patient_id INTEGER,
            incident_date TEXT DEFAULT (date('now')),
            incident_time TEXT,
            location TEXT,
            description TEXT NOT NULL,
            treatment_given TEXT,
            treated_by TEXT,
            parent_notified INTEGER DEFAULT 0,
            ambulance_called INTEGER DEFAULT 0,
            follow_up_required INTEGER DEFAULT 0,
            follow_up_notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Staff: recruitment ──────────────────────────────────────────────
    "recruitment_vacancies": """
        CREATE TABLE IF NOT EXISTS recruitment_vacancies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            role_type TEXT,
            description TEXT,
            requirements TEXT,
            salary_range TEXT,
            closing_date TEXT,
            status TEXT DEFAULT 'open',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "recruitment_applications": """
        CREATE TABLE IF NOT EXISTS recruitment_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vacancy_id INTEGER NOT NULL,
            applicant_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            cv_path TEXT,
            cover_letter TEXT,
            status TEXT DEFAULT 'received',
            interview_date TEXT,
            interview_notes TEXT,
            offer_date TEXT,
            safeguarding_check TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (vacancy_id) REFERENCES recruitment_vacancies(id)
        )
    """,
    # ── Staff: staff_absence ────────────────────────────────────────────
    "staff_absences": """
        CREATE TABLE IF NOT EXISTS staff_absences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            absence_type TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT,
            reason TEXT,
            cover_required INTEGER DEFAULT 0,
            cover_arranged INTEGER DEFAULT 0,
            approved_by TEXT,
            status TEXT DEFAULT 'pending',
            return_date TEXT,
            return_notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (staff_id) REFERENCES staff(id)
        )
    """,
    # ── Pastoral: absence_requests ──────────────────────────────────────
    "absence_requests": """
        CREATE TABLE IF NOT EXISTS absence_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id INTEGER NOT NULL,
            requested_by TEXT,
            request_type TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            reason TEXT,
            supporting_evidence TEXT,
            status TEXT DEFAULT 'pending',
            reviewed_by TEXT,
            reviewed_date TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (pupil_id) REFERENCES pupils(id)
        )
    """,
    # ── Pastoral: early_warning ─────────────────────────────────────────
    "early_warning_alerts": """
        CREATE TABLE IF NOT EXISTS early_warning_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id INTEGER NOT NULL,
            alert_type TEXT NOT NULL,
            severity TEXT DEFAULT 'medium',
            description TEXT NOT NULL,
            raised_by TEXT,
            raised_date TEXT DEFAULT (date('now')),
            assigned_to TEXT,
            status TEXT DEFAULT 'open',
            resolution TEXT,
            resolved_date TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (pupil_id) REFERENCES pupils(id)
        )
    """,
    "early_warning_rules": """
        CREATE TABLE IF NOT EXISTS early_warning_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_name TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            threshold REAL,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Pastoral: accessibility ─────────────────────────────────────────
    "accessibility_provisions": """
        CREATE TABLE IF NOT EXISTS accessibility_provisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id INTEGER NOT NULL,
            provision_type TEXT NOT NULL,
            description TEXT NOT NULL,
            start_date TEXT DEFAULT (date('now')),
            review_date TEXT,
            provided_by TEXT,
            status TEXT DEFAULT 'active',
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (pupil_id) REFERENCES pupils(id)
        )
    """,
    # ── Pupil life: equality_diversity ──────────────────────────────────
    "equality_records": """
        CREATE TABLE IF NOT EXISTS equality_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_type TEXT NOT NULL,
            category TEXT,
            description TEXT NOT NULL,
            reported_by TEXT,
            reported_date TEXT DEFAULT (date('now')),
            action_taken TEXT,
            status TEXT DEFAULT 'open',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "diversity_monitoring": """
        CREATE TABLE IF NOT EXISTS diversity_monitoring (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            academic_year TEXT NOT NULL,
            category TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Pupil life: ilp ────────────────────────────────────────────────
    "individual_learning_plans": """
        CREATE TABLE IF NOT EXISTS individual_learning_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id INTEGER NOT NULL,
            created_by TEXT,
            start_date TEXT DEFAULT (date('now')),
            review_date TEXT,
            targets TEXT,
            strategies TEXT,
            support_required TEXT,
            progress_notes TEXT,
            parent_views TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (pupil_id) REFERENCES pupils(id)
        )
    """,
    # ── Pupil life: peer_mentoring ──────────────────────────────────────
    "peer_mentoring_pairs": """
        CREATE TABLE IF NOT EXISTS peer_mentoring_pairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mentor_id INTEGER NOT NULL,
            mentee_id INTEGER NOT NULL,
            subject_area TEXT,
            start_date TEXT DEFAULT (date('now')),
            end_date TEXT,
            status TEXT DEFAULT 'active',
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (mentor_id) REFERENCES pupils(id),
            FOREIGN KEY (mentee_id) REFERENCES pupils(id)
        )
    """,
    "mentoring_sessions": """
        CREATE TABLE IF NOT EXISTS mentoring_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair_id INTEGER NOT NULL,
            session_date TEXT DEFAULT (date('now')),
            duration_minutes INTEGER,
            topics_covered TEXT,
            mentor_notes TEXT,
            teacher_observations TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (pair_id) REFERENCES peer_mentoring_pairs(id)
        )
    """,
    # ── Pupil life: pupil_support ───────────────────────────────────────
    "support_referrals": """
        CREATE TABLE IF NOT EXISTS support_referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id INTEGER NOT NULL,
            referral_type TEXT NOT NULL,
            referred_by TEXT,
            referred_date TEXT DEFAULT (date('now')),
            description TEXT NOT NULL,
            urgency TEXT DEFAULT 'medium',
            assigned_to TEXT,
            status TEXT DEFAULT 'open',
            outcome TEXT,
            closed_date TEXT,
            parent_informed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (pupil_id) REFERENCES pupils(id)
        )
    """,
    # ── Communication: messaging ────────────────────────────────────────
    "messages": """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            sender_type TEXT DEFAULT 'staff',
            recipient_id INTEGER NOT NULL,
            recipient_type TEXT DEFAULT 'staff',
            subject TEXT,
            body TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            read_at TEXT,
            parent_message_id INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Communication: sms_email ────────────────────────────────────────
    "sms_email_log": """
        CREATE TABLE IF NOT EXISTS sms_email_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_type TEXT NOT NULL,
            recipient TEXT NOT NULL,
            recipient_name TEXT,
            subject TEXT,
            body TEXT,
            status TEXT DEFAULT 'pending',
            sent_at TEXT,
            error_message TEXT,
            template_id INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "communication_templates": """
        CREATE TABLE IF NOT EXISTS communication_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            message_type TEXT NOT NULL,
            subject_template TEXT,
            body_template TEXT NOT NULL,
            category TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Communication: surveys ──────────────────────────────────────────
    "surveys": """
        CREATE TABLE IF NOT EXISTS surveys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            target_audience TEXT,
            created_by TEXT,
            start_date TEXT,
            end_date TEXT,
            is_anonymous INTEGER DEFAULT 0,
            status TEXT DEFAULT 'draft',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "survey_questions": """
        CREATE TABLE IF NOT EXISTS survey_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            question_type TEXT DEFAULT 'text',
            options TEXT,
            sort_order INTEGER DEFAULT 0,
            is_required INTEGER DEFAULT 1,
            FOREIGN KEY (survey_id) REFERENCES surveys(id)
        )
    """,
    "survey_responses": """
        CREATE TABLE IF NOT EXISTS survey_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            respondent_id TEXT,
            response_text TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (survey_id) REFERENCES surveys(id),
            FOREIGN KEY (question_id) REFERENCES survey_questions(id)
        )
    """,
    # ── Communication: activity_feed ────────────────────────────────────
    "activity_feed": """
        CREATE TABLE IF NOT EXISTS activity_feed (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id INTEGER NOT NULL,
            actor_type TEXT DEFAULT 'staff',
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id INTEGER,
            description TEXT,
            metadata TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Facilities: resource_booking ────────────────────────────────────
    "resources": """
        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            description TEXT,
            location TEXT,
            is_available INTEGER DEFAULT 1,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "resource_bookings": """
        CREATE TABLE IF NOT EXISTS resource_bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_id INTEGER NOT NULL,
            booked_by TEXT NOT NULL,
            booking_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            purpose TEXT,
            status TEXT DEFAULT 'confirmed',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (resource_id) REFERENCES resources(id)
        )
    """,
    # ── Facilities: departments ─────────────────────────────────────────
    "departments": """
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            head_of_department TEXT,
            description TEXT,
            budget REAL DEFAULT 0,
            email TEXT,
            room TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Facilities: emergency ───────────────────────────────────────────
    "emergency_procedures": """
        CREATE TABLE IF NOT EXISTS emergency_procedures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            procedure_type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            steps TEXT,
            responsible_person TEXT,
            last_drill_date TEXT,
            next_drill_date TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "emergency_contacts": """
        CREATE TABLE IF NOT EXISTS emergency_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            role TEXT,
            phone TEXT NOT NULL,
            email TEXT,
            priority_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "emergency_drills": """
        CREATE TABLE IF NOT EXISTS emergency_drills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            procedure_id INTEGER NOT NULL,
            drill_date TEXT NOT NULL,
            duration_minutes INTEGER,
            participants INTEGER,
            observations TEXT,
            issues_found TEXT,
            follow_up_actions TEXT,
            conducted_by TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (procedure_id) REFERENCES emergency_procedures(id)
        )
    """,
    # ── Facilities: lettings ────────────────────────────────────────────
    "lettings": """
        CREATE TABLE IF NOT EXISTS lettings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            facility TEXT NOT NULL,
            hirer_name TEXT NOT NULL,
            hirer_email TEXT,
            hirer_phone TEXT,
            organisation TEXT,
            event_type TEXT,
            booking_date TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            recurring INTEGER DEFAULT 0,
            fee REAL DEFAULT 0,
            payment_status TEXT DEFAULT 'unpaid',
            insurance_verified INTEGER DEFAULT 0,
            risk_assessment INTEGER DEFAULT 0,
            dbs_checked INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Portals: parent_portal ──────────────────────────────────────────
    "parent_portal_accounts": """
        CREATE TABLE IF NOT EXISTS parent_portal_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            pupil_ids TEXT,
            access_level TEXT DEFAULT 'standard',
            last_login TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Portals: pupil_portal ───────────────────────────────────────────
    "pupil_portal_preferences": """
        CREATE TABLE IF NOT EXISTS pupil_portal_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id INTEGER NOT NULL UNIQUE,
            theme TEXT DEFAULT 'default',
            notifications_enabled INTEGER DEFAULT 1,
            dashboard_widgets TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (pupil_id) REFERENCES pupils(id)
        )
    """,
    # ── Portals: document_hub ───────────────────────────────────────────
    "document_hub_files": """
        CREATE TABLE IF NOT EXISTS document_hub_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            file_path TEXT NOT NULL,
            file_type TEXT,
            file_size INTEGER,
            category TEXT,
            uploaded_by TEXT,
            access_level TEXT DEFAULT 'staff',
            tags TEXT,
            download_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Portals: kpi_dashboard ──────────────────────────────────────────
    "kpi_metrics": """
        CREATE TABLE IF NOT EXISTS kpi_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT NOT NULL,
            category TEXT NOT NULL,
            current_value REAL,
            target_value REAL,
            unit TEXT,
            trend TEXT,
            period TEXT,
            last_updated TEXT DEFAULT (datetime('now')),
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Portals: mobile_dashboard ───────────────────────────────────────
    "mobile_dashboard_widgets": """
        CREATE TABLE IF NOT EXISTS mobile_dashboard_widgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            widget_type TEXT NOT NULL,
            position INTEGER DEFAULT 0,
            config TEXT,
            is_visible INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Portals: progress_dashboard ─────────────────────────────────────
    "progress_snapshots": """
        CREATE TABLE IF NOT EXISTS progress_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pupil_id INTEGER NOT NULL,
            subject_id INTEGER,
            snapshot_date TEXT DEFAULT (date('now')),
            current_level TEXT,
            target_level TEXT,
            expected_level TEXT,
            attendance_pct REAL,
            behaviour_points INTEGER DEFAULT 0,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (pupil_id) REFERENCES pupils(id),
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        )
    """,
    # ── Admin: helpdesk ─────────────────────────────────────────────────
    "helpdesk_tickets": """
        CREATE TABLE IF NOT EXISTS helpdesk_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT,
            priority TEXT DEFAULT 'medium',
            submitted_by TEXT,
            assigned_to TEXT,
            status TEXT DEFAULT 'open',
            resolution TEXT,
            resolved_date TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Admin: letter_templates ─────────────────────────────────────────
    "letter_templates": """
        CREATE TABLE IF NOT EXISTS letter_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            subject TEXT,
            body_template TEXT NOT NULL,
            placeholders TEXT,
            created_by TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Admin: onboarding ───────────────────────────────────────────────
    "onboarding_checklists": """
        CREATE TABLE IF NOT EXISTS onboarding_checklists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            checklist_type TEXT NOT NULL,
            person_id INTEGER NOT NULL,
            person_type TEXT NOT NULL,
            item_name TEXT NOT NULL,
            description TEXT,
            is_completed INTEGER DEFAULT 0,
            completed_date TEXT,
            completed_by TEXT,
            due_date TEXT,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Admin: todo ─────────────────────────────────────────────────────
    "todos": """
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            priority TEXT DEFAULT 'medium',
            due_date TEXT,
            category TEXT,
            is_completed INTEGER DEFAULT 0,
            completed_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Admin: multi_language ───────────────────────────────────────────
    "translations": """
        CREATE TABLE IF NOT EXISTS translations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            language_code TEXT NOT NULL,
            translation_key TEXT NOT NULL,
            translation_value TEXT NOT NULL,
            context TEXT,
            is_verified INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "supported_languages": """
        CREATE TABLE IF NOT EXISTS supported_languages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            language_code TEXT NOT NULL UNIQUE,
            language_name TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            is_default INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
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

        # Migration: add new columns to homework_submissions if missing
        hw_sub_cols = {r[1] for r in cursor.execute("PRAGMA table_info(homework_submissions)").fetchall()}
        if "file_path" not in hw_sub_cols:
            cursor.execute("ALTER TABLE homework_submissions ADD COLUMN file_path TEXT")
        if "is_late" not in hw_sub_cols:
            cursor.execute("ALTER TABLE homework_submissions ADD COLUMN is_late INTEGER DEFAULT 0")

        # Shared LMS tables
        from education_system.shared.lms.schema import create_lms_tables
        create_lms_tables(conn)

        conn.commit()
        logger.info("Database initialised successfully at %s", db_path)
    finally:
        conn.close()


def seed_default_staff(db_path):
    """Seed default staff records into the staff table (primary school)."""
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        cursor = conn.cursor()
        staff_records = [
            ("STF0001", None, "Margaret", "Henderson", "Head Teacher",
             "m.henderson@primary.school.uk", None, "Senior Leadership", "Active"),
            ("STF0002", None, "Claire", "Barton", "Teacher",
             "c.barton@primary.school.uk", "Year 1", "Key Stage 1", "Active"),
            ("STF0003", None, "David", "Okonkwo", "Teacher",
             "d.okonkwo@primary.school.uk", "Year 3", "Key Stage 2", "Active"),
            ("STF0004", None, "Sophie", "Marsh", "Teaching Assistant",
             "s.marsh@primary.school.uk", None, "Key Stage 1", "Active"),
            ("STF0005", None, "Rebecca", "Thornton", "SENCO",
             "r.thornton@primary.school.uk", None, "Inclusion", "Active"),
        ]
        for sid, uid, fn, ln, role, email, class_of, dept, status in staff_records:
            cursor.execute(
                """INSERT OR IGNORE INTO staff
                   (staff_id, user_id, first_name, last_name, role, email,
                    class_teacher_of, department, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sid, uid, fn, ln, role, email, class_of, dept, status),
            )
        conn.commit()
        logger.info("Default staff records seeded for primary school")
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
