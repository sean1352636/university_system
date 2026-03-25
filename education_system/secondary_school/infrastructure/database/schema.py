"""Database schema definitions and initialization for the Secondary School system."""

import sqlite3
import logging
from datetime import datetime

from education_system.secondary_school.infrastructure.database.db import connect, get_db_path

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
            date_of_birth TEXT,
            address TEXT,
            year_group TEXT DEFAULT '7',
            form_group TEXT,
            form_tutor TEXT,
            key_stage TEXT DEFAULT 'KS3',
            sen_status TEXT DEFAULT 'none',
            pupil_premium INTEGER NOT NULL DEFAULT 0,
            parent_name TEXT,
            parent_email TEXT,
            parent_phone TEXT,
            emergency_contact_name TEXT,
            emergency_contact_phone TEXT,
            enrollment_date TEXT NOT NULL DEFAULT (date('now')),
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
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
            title TEXT DEFAULT 'Mr',
            email TEXT,
            phone TEXT,
            department TEXT,
            role TEXT DEFAULT 'teacher',
            is_form_tutor INTEGER NOT NULL DEFAULT 0,
            form_group TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """,
    "subjects": """
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_code TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            department TEXT,
            key_stage TEXT DEFAULT 'KS3',
            is_core INTEGER NOT NULL DEFAULT 0,
            capacity INTEGER NOT NULL DEFAULT 30,
            teacher TEXT,
            room TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "enrollments": """
        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'enrolled',
            enrolled_at TEXT NOT NULL DEFAULT (datetime('now')),
            dropped_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (subject_id) REFERENCES subjects(id),
            UNIQUE(student_id, subject_id)
        )
    """,
    "grades": """
        CREATE TABLE IF NOT EXISTS grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            assessment_type TEXT NOT NULL DEFAULT 'classwork',
            assessment_name TEXT,
            score REAL,
            grade TEXT,
            term TEXT,
            academic_year TEXT,
            teacher_comment TEXT,
            graded_at TEXT NOT NULL DEFAULT (datetime('now')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        )
    """,
    "attendance_records": """
        CREATE TABLE IF NOT EXISTS attendance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject_id INTEGER,
            date TEXT NOT NULL,
            period TEXT,
            status TEXT NOT NULL DEFAULT 'present',
            note TEXT,
            recorded_by TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        )
    """,
    "timetable_slots": """
        CREATE TABLE IF NOT EXISTS timetable_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            day_of_week TEXT NOT NULL,
            period INTEGER NOT NULL,
            room TEXT,
            teacher TEXT,
            year_group TEXT,
            form_group TEXT,
            term TEXT DEFAULT 'Autumn',
            academic_year TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        )
    """,
    "behaviour_records": """
        CREATE TABLE IF NOT EXISTS behaviour_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            type TEXT NOT NULL DEFAULT 'positive',
            category TEXT NOT NULL,
            description TEXT,
            points INTEGER NOT NULL DEFAULT 0,
            sanction TEXT,
            recorded_by TEXT,
            incident_date TEXT NOT NULL DEFAULT (date('now')),
            resolved INTEGER NOT NULL DEFAULT 0,
            parent_notified INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "notifications": """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """,
    "exams": """
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            exam_type TEXT NOT NULL DEFAULT 'end_of_term',
            year_group TEXT,
            date TEXT,
            start_time TEXT,
            duration_minutes INTEGER NOT NULL DEFAULT 60,
            room TEXT,
            invigilator TEXT,
            total_marks INTEGER NOT NULL DEFAULT 100,
            status TEXT NOT NULL DEFAULT 'scheduled',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        )
    """,
    "exam_results": """
        CREATE TABLE IF NOT EXISTS exam_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            marks_obtained REAL,
            grade TEXT,
            absent INTEGER NOT NULL DEFAULT 0,
            special_consideration TEXT,
            comment TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (exam_id) REFERENCES exams(id),
            FOREIGN KEY (student_id) REFERENCES students(id),
            UNIQUE(exam_id, student_id)
        )
    """,
    "staff_hr": """
        CREATE TABLE IF NOT EXISTS staff_hr (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id TEXT UNIQUE NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            title TEXT DEFAULT 'Mr',
            email TEXT,
            phone TEXT,
            address TEXT,
            department TEXT,
            job_title TEXT DEFAULT 'Teacher',
            contract_type TEXT DEFAULT 'permanent',
            salary REAL,
            start_date TEXT,
            end_date TEXT,
            dbs_check_date TEXT,
            dbs_certificate TEXT,
            emergency_contact_name TEXT,
            emergency_contact_phone TEXT,
            sick_days_used INTEGER NOT NULL DEFAULT 0,
            annual_leave_used INTEGER NOT NULL DEFAULT 0,
            annual_leave_entitlement INTEGER NOT NULL DEFAULT 25,
            status TEXT NOT NULL DEFAULT 'active',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "staff_leave": """
        CREATE TABLE IF NOT EXISTS staff_leave (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_hr_id INTEGER NOT NULL,
            leave_type TEXT NOT NULL DEFAULT 'annual',
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            days INTEGER NOT NULL DEFAULT 1,
            reason TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            approved_by TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (staff_hr_id) REFERENCES staff_hr(id)
        )
    """,
    "finance_transactions": """
        CREATE TABLE IF NOT EXISTS finance_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_type TEXT NOT NULL DEFAULT 'income',
            category TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL DEFAULT 0.0,
            reference TEXT,
            student_id INTEGER,
            staff_hr_id INTEGER,
            date TEXT NOT NULL DEFAULT (date('now')),
            status TEXT NOT NULL DEFAULT 'completed',
            recorded_by TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (staff_hr_id) REFERENCES staff_hr(id)
        )
    """,
    "finance_budgets": """
        CREATE TABLE IF NOT EXISTS finance_budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department TEXT NOT NULL,
            academic_year TEXT NOT NULL DEFAULT '2025/2026',
            allocated REAL NOT NULL DEFAULT 0.0,
            spent REAL NOT NULL DEFAULT 0.0,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(department, academic_year)
        )
    """,
    "send_records": """
        CREATE TABLE IF NOT EXISTS send_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            sen_type TEXT NOT NULL DEFAULT 'SEN Support',
            primary_need TEXT,
            ehcp INTEGER NOT NULL DEFAULT 0,
            ehcp_review_date TEXT,
            key_worker TEXT,
            external_agencies TEXT,
            diagnosis TEXT,
            strategies TEXT,
            access_arrangements TEXT,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "send_provisions": """
        CREATE TABLE IF NOT EXISTS send_provisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            send_record_id INTEGER NOT NULL,
            provision_type TEXT NOT NULL,
            description TEXT,
            frequency TEXT,
            staff_responsible TEXT,
            start_date TEXT,
            end_date TEXT,
            outcome TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (send_record_id) REFERENCES send_records(id)
        )
    """,
    "safeguarding_concerns": """
        CREATE TABLE IF NOT EXISTS safeguarding_concerns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            reported_by TEXT NOT NULL,
            concern_type TEXT NOT NULL DEFAULT 'welfare',
            severity TEXT NOT NULL DEFAULT 'low',
            description TEXT NOT NULL,
            action_taken TEXT,
            referred_to TEXT,
            outcome TEXT,
            is_resolved INTEGER NOT NULL DEFAULT 0,
            confidential INTEGER NOT NULL DEFAULT 1,
            incident_date TEXT NOT NULL DEFAULT (date('now')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "parents_evening_events": """
        CREATE TABLE IF NOT EXISTS parents_evening_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            year_group TEXT,
            date TEXT NOT NULL,
            start_time TEXT NOT NULL DEFAULT '16:00',
            end_time TEXT NOT NULL DEFAULT '19:00',
            slot_duration_minutes INTEGER NOT NULL DEFAULT 5,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "parents_evening_slots": """
        CREATE TABLE IF NOT EXISTS parents_evening_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            teacher TEXT NOT NULL,
            student_id INTEGER NOT NULL,
            time_slot TEXT NOT NULL,
            parent_name TEXT,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'booked',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (event_id) REFERENCES parents_evening_events(id),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "cover_lessons": """
        CREATE TABLE IF NOT EXISTS cover_lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            absent_teacher TEXT NOT NULL,
            cover_teacher TEXT,
            subject_id INTEGER,
            year_group TEXT,
            date TEXT NOT NULL,
            period INTEGER NOT NULL,
            room TEXT,
            work_set TEXT,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        )
    """,
    "homework": """
        CREATE TABLE IF NOT EXISTS homework (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            year_group TEXT,
            title TEXT NOT NULL,
            description TEXT,
            set_by TEXT,
            set_date TEXT NOT NULL DEFAULT (date('now')),
            due_date TEXT NOT NULL,
            max_marks INTEGER,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        )
    """,
    "homework_submissions": """
        CREATE TABLE IF NOT EXISTS homework_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            homework_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            submitted_at TEXT,
            marks INTEGER,
            feedback TEXT,
            file_path TEXT,
            is_late INTEGER NOT NULL DEFAULT 0,
            resubmission_of INTEGER,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (homework_id) REFERENCES homework(id),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (resubmission_of) REFERENCES homework_submissions(id)
        )
    """,
    "homework_rubrics": """
        CREATE TABLE IF NOT EXISTS homework_rubrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            homework_id INTEGER NOT NULL,
            criteria TEXT NOT NULL,
            max_marks INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (homework_id) REFERENCES homework(id)
        )
    """,
    "homework_feedback": """
        CREATE TABLE IF NOT EXISTS homework_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            feedback_text TEXT NOT NULL,
            marked_by TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (submission_id) REFERENCES homework_submissions(id)
        )
    """,
    "homework_drafts": """
        CREATE TABLE IF NOT EXISTS homework_drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            homework_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            draft_text TEXT,
            saved_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (homework_id) REFERENCES homework(id),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "school_events": """
        CREATE TABLE IF NOT EXISTS school_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            event_type TEXT NOT NULL DEFAULT 'general',
            date TEXT NOT NULL,
            end_date TEXT,
            start_time TEXT,
            end_time TEXT,
            location TEXT,
            year_group TEXT,
            is_whole_school INTEGER NOT NULL DEFAULT 0,
            created_by TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "announcements": """
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            audience TEXT NOT NULL DEFAULT 'all',
            year_group TEXT,
            priority TEXT NOT NULL DEFAULT 'normal',
            published INTEGER NOT NULL DEFAULT 1,
            expires_at TEXT,
            created_by TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "pastoral_notes": """
        CREATE TABLE IF NOT EXISTS pastoral_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            note_type TEXT NOT NULL DEFAULT 'general',
            content TEXT NOT NULL,
            recorded_by TEXT,
            is_confidential INTEGER NOT NULL DEFAULT 0,
            follow_up_date TEXT,
            follow_up_done INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "house_points": """
        CREATE TABLE IF NOT EXISTS house_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            house TEXT NOT NULL,
            points INTEGER NOT NULL DEFAULT 1,
            reason TEXT,
            awarded_by TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "library_books": """
        CREATE TABLE IF NOT EXISTS library_books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isbn TEXT,
            title TEXT NOT NULL,
            author TEXT,
            category TEXT,
            location TEXT,
            copies_total INTEGER NOT NULL DEFAULT 1,
            copies_available INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'available',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "library_loans": """
        CREATE TABLE IF NOT EXISTS library_loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            borrowed_at TEXT NOT NULL DEFAULT (datetime('now')),
            due_date TEXT NOT NULL,
            returned_at TEXT,
            status TEXT NOT NULL DEFAULT 'borrowed',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (book_id) REFERENCES library_books(id),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "medical_conditions": """
        CREATE TABLE IF NOT EXISTS medical_conditions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            condition_name TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'low',
            medications TEXT,
            allergies TEXT,
            care_plan TEXT,
            emergency_protocol TEXT,
            doctor_name TEXT,
            doctor_phone TEXT,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "first_aid_log": """
        CREATE TABLE IF NOT EXISTS first_aid_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            incident_date TEXT NOT NULL DEFAULT (date('now')),
            incident_time TEXT,
            location TEXT,
            description TEXT NOT NULL,
            treatment TEXT,
            treated_by TEXT,
            parent_notified INTEGER NOT NULL DEFAULT 0,
            sent_home INTEGER NOT NULL DEFAULT 0,
            ambulance_called INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "meal_registrations": """
        CREATE TABLE IF NOT EXISTS meal_registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            free_school_meals INTEGER NOT NULL DEFAULT 0,
            dietary_requirements TEXT,
            allergies TEXT,
            meal_preference TEXT NOT NULL DEFAULT 'standard',
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            UNIQUE(student_id)
        )
    """,
    "meal_bookings": """
        CREATE TABLE IF NOT EXISTS meal_bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            meal_type TEXT NOT NULL DEFAULT 'lunch',
            menu_choice TEXT,
            status TEXT NOT NULL DEFAULT 'booked',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "trips": """
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            destination TEXT,
            date TEXT NOT NULL,
            return_date TEXT,
            departure_time TEXT,
            return_time TEXT,
            year_group TEXT,
            lead_teacher TEXT,
            max_students INTEGER,
            cost_per_student REAL DEFAULT 0.0,
            transport TEXT,
            risk_assessment_done INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'planned',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "trip_students": """
        CREATE TABLE IF NOT EXISTS trip_students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            consent_received INTEGER NOT NULL DEFAULT 0,
            paid INTEGER NOT NULL DEFAULT 0,
            medical_notes TEXT,
            emergency_contact TEXT,
            emergency_phone TEXT,
            status TEXT NOT NULL DEFAULT 'registered',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (trip_id) REFERENCES trips(id),
            FOREIGN KEY (student_id) REFERENCES students(id),
            UNIQUE(trip_id, student_id)
        )
    """,
    "clubs": """
        CREATE TABLE IF NOT EXISTS clubs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT NOT NULL DEFAULT 'general',
            day_of_week TEXT,
            start_time TEXT,
            end_time TEXT,
            location TEXT,
            teacher TEXT,
            max_members INTEGER,
            year_groups TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "club_members": """
        CREATE TABLE IF NOT EXISTS club_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            joined_at TEXT NOT NULL DEFAULT (datetime('now')),
            status TEXT NOT NULL DEFAULT 'active',
            FOREIGN KEY (club_id) REFERENCES clubs(id),
            FOREIGN KEY (student_id) REFERENCES students(id),
            UNIQUE(club_id, student_id)
        )
    """,
    "detentions": """
        CREATE TABLE IF NOT EXISTS detentions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            behaviour_record_id INTEGER,
            detention_type TEXT NOT NULL DEFAULT 'lunchtime',
            date TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            room TEXT,
            supervisor TEXT,
            reason TEXT NOT NULL,
            attended INTEGER,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'scheduled',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (behaviour_record_id) REFERENCES behaviour_records(id)
        )
    """,
    "documents": """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'policy',
            description TEXT,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            uploaded_by TEXT,
            version TEXT DEFAULT '1.0',
            requires_acknowledgement INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "document_acknowledgements": """
        CREATE TABLE IF NOT EXISTS document_acknowledgements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            acknowledged_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (document_id) REFERENCES documents(id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(document_id, user_id)
        )
    """,
    "visitors": """
        CREATE TABLE IF NOT EXISTS visitors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visitor_name TEXT NOT NULL,
            organisation TEXT,
            purpose TEXT NOT NULL,
            visiting TEXT,
            badge_number TEXT,
            dbs_checked INTEGER NOT NULL DEFAULT 0,
            sign_in_time TEXT NOT NULL DEFAULT (datetime('now')),
            sign_out_time TEXT,
            car_registration TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "room_bookings": """
        CREATE TABLE IF NOT EXISTS room_bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room TEXT NOT NULL,
            date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            purpose TEXT NOT NULL,
            booked_by TEXT,
            recurring INTEGER NOT NULL DEFAULT 0,
            equipment_needed TEXT,
            status TEXT NOT NULL DEFAULT 'confirmed',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "staff_directory": """
        CREATE TABLE IF NOT EXISTS staff_directory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id TEXT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            title TEXT DEFAULT 'Mr',
            role TEXT DEFAULT 'Teacher',
            department TEXT,
            email TEXT,
            phone_ext TEXT,
            room TEXT,
            subjects TEXT,
            responsibilities TEXT,
            photo_path TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "assets": """
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_tag TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'IT',
            description TEXT,
            serial_number TEXT,
            location TEXT,
            assigned_to TEXT,
            department TEXT,
            purchase_date TEXT,
            purchase_cost REAL,
            warranty_expiry TEXT,
            condition TEXT NOT NULL DEFAULT 'good',
            status TEXT NOT NULL DEFAULT 'in_use',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "school_settings": """
        CREATE TABLE IF NOT EXISTS school_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT,
            category TEXT NOT NULL DEFAULT 'general',
            description TEXT,
            updated_by TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "admissions_applications": """
        CREATE TABLE IF NOT EXISTS admissions_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            applicant_first_name TEXT NOT NULL,
            applicant_last_name TEXT NOT NULL,
            date_of_birth TEXT,
            gender TEXT,
            address TEXT,
            year_group_applying TEXT NOT NULL,
            parent_name TEXT NOT NULL,
            parent_email TEXT,
            parent_phone TEXT,
            previous_school TEXT,
            sen_needs TEXT,
            medical_info TEXT,
            additional_info TEXT,
            application_date TEXT NOT NULL DEFAULT (date('now')),
            status TEXT NOT NULL DEFAULT 'received',
            decision_date TEXT,
            decision_by TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "intervention_groups": """
        CREATE TABLE IF NOT EXISTS intervention_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            subject_id INTEGER,
            year_group TEXT,
            lead_teacher TEXT,
            target TEXT,
            start_date TEXT,
            end_date TEXT,
            meeting_frequency TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        )
    """,
    "intervention_members": """
        CREATE TABLE IF NOT EXISTS intervention_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            baseline_grade TEXT,
            target_grade TEXT,
            current_grade TEXT,
            progress_notes TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (group_id) REFERENCES intervention_groups(id),
            FOREIGN KEY (student_id) REFERENCES students(id),
            UNIQUE(group_id, student_id)
        )
    """,
    "cpd_records": """
        CREATE TABLE IF NOT EXISTS cpd_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_name TEXT NOT NULL,
            training_title TEXT NOT NULL,
            provider TEXT,
            category TEXT NOT NULL DEFAULT 'general',
            date TEXT NOT NULL,
            duration_hours REAL,
            cost REAL DEFAULT 0.0,
            certificate INTEGER NOT NULL DEFAULT 0,
            impact TEXT,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'completed',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "transport_routes": """
        CREATE TABLE IF NOT EXISTS transport_routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route_name TEXT NOT NULL,
            operator TEXT,
            vehicle_type TEXT DEFAULT 'bus',
            capacity INTEGER,
            driver_name TEXT,
            driver_phone TEXT,
            departure_time TEXT,
            return_time TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "transport_stops": """
        CREATE TABLE IF NOT EXISTS transport_stops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route_id INTEGER NOT NULL,
            stop_name TEXT NOT NULL,
            pickup_time TEXT,
            dropoff_time TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (route_id) REFERENCES transport_routes(id)
        )
    """,
    "transport_students": """
        CREATE TABLE IF NOT EXISTS transport_students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            stop_id INTEGER,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (route_id) REFERENCES transport_routes(id),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (stop_id) REFERENCES transport_stops(id),
            UNIQUE(route_id, student_id)
        )
    """,
    "rewards": """
        CREATE TABLE IF NOT EXISTS rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            reward_type TEXT NOT NULL DEFAULT 'merit',
            category TEXT NOT NULL DEFAULT 'general',
            points INTEGER NOT NULL DEFAULT 1,
            reason TEXT NOT NULL,
            awarded_by TEXT,
            awarded_date TEXT NOT NULL DEFAULT (date('now')),
            certificate_issued INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "careers_records": """
        CREATE TABLE IF NOT EXISTS careers_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            meeting_date TEXT NOT NULL,
            adviser TEXT,
            career_interests TEXT,
            action_points TEXT,
            destination TEXT,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "work_experience": """
        CREATE TABLE IF NOT EXISTS work_experience (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            employer TEXT NOT NULL,
            contact_name TEXT,
            contact_phone TEXT,
            contact_email TEXT,
            address TEXT,
            role TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            risk_assessment_done INTEGER NOT NULL DEFAULT 0,
            parent_consent INTEGER NOT NULL DEFAULT 0,
            insurance_confirmed INTEGER NOT NULL DEFAULT 0,
            feedback TEXT,
            status TEXT NOT NULL DEFAULT 'planned',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "form_groups": """
        CREATE TABLE IF NOT EXISTS form_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            year_group TEXT NOT NULL,
            form_tutor TEXT,
            room TEXT,
            max_students INTEGER DEFAULT 30,
            registration_time TEXT DEFAULT '08:40',
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "form_group_students": """
        CREATE TABLE IF NOT EXISTS form_group_students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            form_group_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            joined_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (form_group_id) REFERENCES form_groups(id),
            FOREIGN KEY (student_id) REFERENCES students(id),
            UNIQUE(student_id)
        )
    """,
    "audit_log": """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            action TEXT NOT NULL,
            module TEXT,
            record_id INTEGER,
            details TEXT,
            ip_address TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """,
    "policies": """
        CREATE TABLE IF NOT EXISTS policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            version TEXT DEFAULT '1.0',
            approved_by TEXT,
            approval_date TEXT,
            review_date TEXT,
            summary TEXT,
            content TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "policy_acknowledgements": """
        CREATE TABLE IF NOT EXISTS policy_acknowledgements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            policy_id INTEGER NOT NULL,
            staff_name TEXT NOT NULL,
            acknowledged_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (policy_id) REFERENCES policies(id),
            UNIQUE(policy_id, staff_name)
        )
    """,
    "communication_log": """
        CREATE TABLE IF NOT EXISTS communication_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            contact_type TEXT NOT NULL DEFAULT 'phone_call',
            contact_with TEXT NOT NULL,
            direction TEXT NOT NULL DEFAULT 'outgoing',
            subject TEXT,
            summary TEXT NOT NULL,
            outcome TEXT,
            follow_up_needed INTEGER NOT NULL DEFAULT 0,
            follow_up_date TEXT,
            follow_up_done INTEGER NOT NULL DEFAULT 0,
            recorded_by TEXT,
            contact_date TEXT NOT NULL DEFAULT (date('now')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "exclusions": """
        CREATE TABLE IF NOT EXISTS exclusions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            exclusion_type TEXT NOT NULL DEFAULT 'fixed_term',
            reason TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'persistent_disruptive',
            start_date TEXT NOT NULL,
            end_date TEXT,
            days INTEGER NOT NULL DEFAULT 1,
            excluded_by TEXT,
            governor_review INTEGER NOT NULL DEFAULT 0,
            governor_review_date TEXT,
            parent_notified INTEGER NOT NULL DEFAULT 0,
            la_notified INTEGER NOT NULL DEFAULT 0,
            reintegration_date TEXT,
            reintegration_meeting INTEGER NOT NULL DEFAULT 0,
            alternative_provision TEXT,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "progress_targets": """
        CREATE TABLE IF NOT EXISTS progress_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            academic_year TEXT NOT NULL DEFAULT '2025/2026',
            baseline_grade TEXT,
            target_grade TEXT,
            autumn_grade TEXT,
            spring_grade TEXT,
            summer_grade TEXT,
            current_grade TEXT,
            effort TEXT,
            teacher_comment TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (subject_id) REFERENCES subjects(id),
            UNIQUE(student_id, subject_id, academic_year)
        )
    """,
    "seating_plans": """
        CREATE TABLE IF NOT EXISTS seating_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            room TEXT NOT NULL,
            subject_id INTEGER,
            year_group TEXT,
            teacher TEXT,
            rows INTEGER NOT NULL DEFAULT 5,
            columns INTEGER NOT NULL DEFAULT 6,
            status TEXT NOT NULL DEFAULT 'active',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        )
    """,
    "seating_assignments": """
        CREATE TABLE IF NOT EXISTS seating_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            seat_row INTEGER NOT NULL,
            seat_col INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (plan_id) REFERENCES seating_plans(id),
            FOREIGN KEY (student_id) REFERENCES students(id),
            UNIQUE(plan_id, student_id),
            UNIQUE(plan_id, seat_row, seat_col)
        )
    """,
    "consent_records": """
        CREATE TABLE IF NOT EXISTS consent_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            consent_type TEXT NOT NULL,
            description TEXT,
            granted INTEGER NOT NULL DEFAULT 0,
            granted_by TEXT,
            granted_date TEXT,
            expires_at TEXT,
            academic_year TEXT DEFAULT '2025/2026',
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """,
    "incidents": """
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_type TEXT NOT NULL DEFAULT 'accident',
            severity TEXT NOT NULL DEFAULT 'minor',
            location TEXT,
            date TEXT NOT NULL DEFAULT (date('now')),
            time TEXT,
            description TEXT NOT NULL,
            people_involved TEXT,
            witnesses TEXT,
            action_taken TEXT,
            reported_by TEXT,
            reported_to TEXT,
            investigation_notes TEXT,
            riddor_reportable INTEGER NOT NULL DEFAULT 0,
            follow_up_needed INTEGER NOT NULL DEFAULT 0,
            follow_up_done INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "emails": """
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            recipient_id INTEGER NOT NULL,
            subject TEXT NOT NULL DEFAULT '(no subject)',
            body TEXT NOT NULL DEFAULT '',
            is_read INTEGER NOT NULL DEFAULT 0,
            sender_deleted INTEGER NOT NULL DEFAULT 0,
            recipient_deleted INTEGER NOT NULL DEFAULT 0,
            sent_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (sender_id) REFERENCES users(id),
            FOREIGN KEY (recipient_id) REFERENCES users(id)
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
            status TEXT NOT NULL DEFAULT 'draft'
                CHECK(status IN ('draft','pending_approval','approved','processed','paid')),
            approved_by TEXT,
            processed_date TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (staff_id) REFERENCES staff(id)
        )
    """,
    "payroll_config": """
        CREATE TABLE IF NOT EXISTS payroll_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tax_year TEXT NOT NULL,
            tax_band_1 REAL NOT NULL DEFAULT 12570,
            tax_rate_1 REAL NOT NULL DEFAULT 0.20,
            tax_band_2 REAL NOT NULL DEFAULT 50270,
            tax_rate_2 REAL NOT NULL DEFAULT 0.40,
            ni_threshold REAL NOT NULL DEFAULT 12570,
            ni_rate REAL NOT NULL DEFAULT 0.12,
            pension_rate REAL NOT NULL DEFAULT 0.05,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
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
    # ── Student Wellbeing ──
    "wellbeing_referrals": """
        CREATE TABLE IF NOT EXISTS wellbeing_referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            referred_by TEXT NOT NULL,
            concern_type TEXT NOT NULL,
            description TEXT NOT NULL,
            risk_level TEXT DEFAULT 'Low',
            status TEXT DEFAULT 'Open',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "wellbeing_checkins": """
        CREATE TABLE IF NOT EXISTS wellbeing_checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            mood_rating INTEGER NOT NULL,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "counselling_sessions": """
        CREATE TABLE IF NOT EXISTS counselling_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            counsellor TEXT NOT NULL,
            session_date TEXT NOT NULL,
            notes TEXT,
            outcome TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Interventions ──
    "interventions": """
        CREATE TABLE IF NOT EXISTS interventions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            intervention_type TEXT NOT NULL,
            reason TEXT,
            lead_staff_id TEXT,
            targets TEXT,
            status TEXT DEFAULT 'active',
            start_date TEXT,
            end_date TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "intervention_sessions": """
        CREATE TABLE IF NOT EXISTS intervention_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intervention_id INTEGER NOT NULL,
            session_date TEXT NOT NULL,
            notes TEXT,
            attendees TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "intervention_outcomes": """
        CREATE TABLE IF NOT EXISTS intervention_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intervention_id INTEGER NOT NULL,
            outcome TEXT,
            impact_rating TEXT,
            measured_at TEXT,
            notes TEXT
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
    # ── Staff Appraisals ──
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
    # ── Lesson Observations ──
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
    # ── Staff Wellbeing ──
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
    "portfolio_items": """
        CREATE TABLE IF NOT EXISTS portfolio_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT,
            file_path TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "portfolio_shares": """
        CREATE TABLE IF NOT EXISTS portfolio_shares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_item_id INTEGER NOT NULL,
            shared_with_id TEXT NOT NULL,
            shared_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "skills_passport": """
        CREATE TABLE IF NOT EXISTS skills_passport (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            skill_name TEXT NOT NULL,
            category TEXT,
            level TEXT DEFAULT 'beginner',
            endorsed_by TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "skill_endorsements": """
        CREATE TABLE IF NOT EXISTS skill_endorsements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill_id INTEGER NOT NULL,
            endorsed_by TEXT NOT NULL,
            comment TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Student Council ──
    "council_members": """
        CREATE TABLE IF NOT EXISTS council_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            role TEXT DEFAULT 'representative',
            year_group TEXT,
            term TEXT,
            active INTEGER DEFAULT 1,
            joined_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "council_meetings": """
        CREATE TABLE IF NOT EXISTS council_meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_date TEXT NOT NULL,
            agenda TEXT,
            location TEXT,
            minutes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "council_proposals": """
        CREATE TABLE IF NOT EXISTS council_proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposed_by TEXT,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT,
            status TEXT DEFAULT 'submitted',
            vote_result TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Study Planner ──
    "study_goals": """
        CREATE TABLE IF NOT EXISTS study_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            subject TEXT,
            goal_description TEXT NOT NULL,
            target_date TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """,
    "study_sessions": """
        CREATE TABLE IF NOT EXISTS study_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            subject TEXT,
            duration_mins INTEGER NOT NULL,
            notes TEXT,
            session_date TEXT DEFAULT (date('now')),
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,
    # ── Homework Enhancements (homework_rubrics, homework_feedback, homework_drafts
    #    defined earlier with FK constraints) ──
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
}

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_students_student_id ON students(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_students_year_group ON students(year_group)",
    "CREATE INDEX IF NOT EXISTS idx_students_form_group ON students(form_group)",
    "CREATE INDEX IF NOT EXISTS idx_enrollments_student ON enrollments(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_enrollments_subject ON enrollments(subject_id)",
    "CREATE INDEX IF NOT EXISTS idx_grades_student ON grades(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_grades_subject ON grades(subject_id)",
    "CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance_records(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance_records(date)",
    "CREATE INDEX IF NOT EXISTS idx_behaviour_student ON behaviour_records(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_timetable_day ON timetable_slots(day_of_week)",
    "CREATE INDEX IF NOT EXISTS idx_emails_sender ON emails(sender_id)",
    "CREATE INDEX IF NOT EXISTS idx_emails_recipient ON emails(recipient_id)",
    "CREATE INDEX IF NOT EXISTS idx_exams_subject ON exams(subject_id)",
    "CREATE INDEX IF NOT EXISTS idx_exams_date ON exams(date)",
    "CREATE INDEX IF NOT EXISTS idx_exam_results_exam ON exam_results(exam_id)",
    "CREATE INDEX IF NOT EXISTS idx_exam_results_student ON exam_results(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_staff_hr_staff_id ON staff_hr(staff_id)",
    "CREATE INDEX IF NOT EXISTS idx_staff_leave_staff ON staff_leave(staff_hr_id)",
    "CREATE INDEX IF NOT EXISTS idx_finance_transactions_date ON finance_transactions(date)",
    "CREATE INDEX IF NOT EXISTS idx_finance_transactions_type ON finance_transactions(transaction_type)",
    "CREATE INDEX IF NOT EXISTS idx_send_records_student ON send_records(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_safeguarding_student ON safeguarding_concerns(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_cover_date ON cover_lessons(date)",
    "CREATE INDEX IF NOT EXISTS idx_homework_subject ON homework(subject_id)",
    "CREATE INDEX IF NOT EXISTS idx_homework_due ON homework(due_date)",
    "CREATE INDEX IF NOT EXISTS idx_homework_subs_hw ON homework_submissions(homework_id)",
    "CREATE INDEX IF NOT EXISTS idx_homework_subs_stu ON homework_submissions(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_homework_rubrics_hw ON homework_rubrics(homework_id)",
    "CREATE INDEX IF NOT EXISTS idx_homework_feedback_sub ON homework_feedback(submission_id)",
    "CREATE INDEX IF NOT EXISTS idx_homework_drafts_hw ON homework_drafts(homework_id)",
    "CREATE INDEX IF NOT EXISTS idx_homework_drafts_stu ON homework_drafts(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_school_events_date ON school_events(date)",
    "CREATE INDEX IF NOT EXISTS idx_pastoral_student ON pastoral_notes(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_library_loans_book ON library_loans(book_id)",
    "CREATE INDEX IF NOT EXISTS idx_library_loans_student ON library_loans(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_medical_student ON medical_conditions(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_first_aid_student ON first_aid_log(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_first_aid_date ON first_aid_log(incident_date)",
    "CREATE INDEX IF NOT EXISTS idx_meal_reg_student ON meal_registrations(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_meal_bookings_date ON meal_bookings(date)",
    "CREATE INDEX IF NOT EXISTS idx_trips_date ON trips(date)",
    "CREATE INDEX IF NOT EXISTS idx_trip_students_trip ON trip_students(trip_id)",
    "CREATE INDEX IF NOT EXISTS idx_trip_students_stu ON trip_students(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_clubs_status ON clubs(status)",
    "CREATE INDEX IF NOT EXISTS idx_club_members_club ON club_members(club_id)",
    "CREATE INDEX IF NOT EXISTS idx_club_members_stu ON club_members(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_detentions_student ON detentions(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_detentions_date ON detentions(date)",
    "CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category)",
    "CREATE INDEX IF NOT EXISTS idx_visitors_date ON visitors(sign_in_time)",
    "CREATE INDEX IF NOT EXISTS idx_room_bookings_date ON room_bookings(date)",
    "CREATE INDEX IF NOT EXISTS idx_room_bookings_room ON room_bookings(room)",
    "CREATE INDEX IF NOT EXISTS idx_assets_tag ON assets(asset_tag)",
    "CREATE INDEX IF NOT EXISTS idx_assets_category ON assets(category)",
    "CREATE INDEX IF NOT EXISTS idx_settings_key ON school_settings(key)",
    "CREATE INDEX IF NOT EXISTS idx_admissions_status ON admissions_applications(status)",
    "CREATE INDEX IF NOT EXISTS idx_admissions_year ON admissions_applications(year_group_applying)",
    "CREATE INDEX IF NOT EXISTS idx_intervention_groups_status ON intervention_groups(status)",
    "CREATE INDEX IF NOT EXISTS idx_intervention_members_group ON intervention_members(group_id)",
    "CREATE INDEX IF NOT EXISTS idx_intervention_members_stu ON intervention_members(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_cpd_staff ON cpd_records(staff_name)",
    "CREATE INDEX IF NOT EXISTS idx_cpd_date ON cpd_records(date)",
    "CREATE INDEX IF NOT EXISTS idx_transport_routes_status ON transport_routes(status)",
    "CREATE INDEX IF NOT EXISTS idx_transport_students_route ON transport_students(route_id)",
    "CREATE INDEX IF NOT EXISTS idx_transport_students_stu ON transport_students(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_rewards_student ON rewards(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_rewards_date ON rewards(awarded_date)",
    "CREATE INDEX IF NOT EXISTS idx_rewards_type ON rewards(reward_type)",
    "CREATE INDEX IF NOT EXISTS idx_careers_student ON careers_records(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_work_exp_student ON work_experience(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_work_exp_dates ON work_experience(start_date)",
    "CREATE INDEX IF NOT EXISTS idx_form_groups_year ON form_groups(year_group)",
    "CREATE INDEX IF NOT EXISTS idx_form_group_students_group ON form_group_students(form_group_id)",
    "CREATE INDEX IF NOT EXISTS idx_form_group_students_stu ON form_group_students(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action)",
    "CREATE INDEX IF NOT EXISTS idx_audit_log_date ON audit_log(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_policies_category ON policies(category)",
    "CREATE INDEX IF NOT EXISTS idx_policies_status ON policies(status)",
    "CREATE INDEX IF NOT EXISTS idx_policy_ack_policy ON policy_acknowledgements(policy_id)",
    "CREATE INDEX IF NOT EXISTS idx_comms_log_student ON communication_log(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_comms_log_date ON communication_log(contact_date)",
    "CREATE INDEX IF NOT EXISTS idx_exclusions_student ON exclusions(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_exclusions_date ON exclusions(start_date)",
    "CREATE INDEX IF NOT EXISTS idx_exclusions_type ON exclusions(exclusion_type)",
    "CREATE INDEX IF NOT EXISTS idx_progress_student ON progress_targets(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_progress_subject ON progress_targets(subject_id)",
    "CREATE INDEX IF NOT EXISTS idx_progress_year ON progress_targets(academic_year)",
    "CREATE INDEX IF NOT EXISTS idx_seating_plans_room ON seating_plans(room)",
    "CREATE INDEX IF NOT EXISTS idx_seating_assignments_plan ON seating_assignments(plan_id)",
    "CREATE INDEX IF NOT EXISTS idx_seating_assignments_stu ON seating_assignments(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_consent_student ON consent_records(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_consent_type ON consent_records(consent_type)",
    "CREATE INDEX IF NOT EXISTS idx_incidents_date ON incidents(date)",
    "CREATE INDEX IF NOT EXISTS idx_incidents_type ON incidents(incident_type)",
    "CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status)",
]


def initialise_database(db_path: str | None = None):
    """Create all tables and indexes if they don't exist."""
    conn = connect(db_path)
    try:
        for table_name, ddl in TABLES.items():
            conn.execute(ddl)
            logger.debug("Table ensured: %s", table_name)

        for idx_sql in INDEXES:
            conn.execute(idx_sql)

        # Migration: add previous_system columns to students if missing
        cols = {r[1] for r in conn.execute("PRAGMA table_info(students)").fetchall()}
        if "previous_system" not in cols:
            conn.execute("ALTER TABLE students ADD COLUMN previous_system TEXT")
        if "previous_system_id" not in cols:
            conn.execute("ALTER TABLE students ADD COLUMN previous_system_id TEXT")

        # Migration: add new columns to homework_submissions if missing
        hw_sub_cols = {r[1] for r in conn.execute("PRAGMA table_info(homework_submissions)").fetchall()}
        if "file_path" not in hw_sub_cols:
            conn.execute("ALTER TABLE homework_submissions ADD COLUMN file_path TEXT")
        if "is_late" not in hw_sub_cols:
            conn.execute("ALTER TABLE homework_submissions ADD COLUMN is_late INTEGER NOT NULL DEFAULT 0")
        if "resubmission_of" not in hw_sub_cols:
            conn.execute("ALTER TABLE homework_submissions ADD COLUMN resubmission_of INTEGER")

        # Shared LMS tables
        from education_system.shared.lms.schema import create_lms_tables
        create_lms_tables(conn)

        conn.commit()
        logger.info("Database schema initialised successfully.")
    except sqlite3.Error as e:
        conn.rollback()
        logger.error("Schema initialisation failed: %s", e)
        raise
    finally:
        conn.close()


def seed_default_staff(db_path: str | None = None):
    """Seed default staff records into the staff table (secondary school)."""
    conn = connect(db_path)
    try:
        staff_records = [
            ("STF0001", None, "Dr", "Priya", "Sharma", "p.sharma@secondary.school.uk",
             "Mathematics", "Head of Maths", 0, None, "active"),
            ("STF0002", None, "Ms", "Helen", "Cartwright", "h.cartwright@secondary.school.uk",
             "English", "teacher", 0, None, "active"),
            ("STF0003", None, "Mr", "James", "Nkomo", "j.nkomo@secondary.school.uk",
             "Science", "teacher", 0, None, "active"),
            ("STF0004", None, "Mrs", "Karen", "Fletcher", "k.fletcher@secondary.school.uk",
             "Physical Education", "teacher", 0, None, "active"),
            ("STF0005", None, "Mr", "Robert", "Ainsworth", "r.ainsworth@secondary.school.uk",
             "Pastoral", "Head of Year 7", 1, "7A", "active"),
        ]
        for sid, uid, title, fn, ln, email, dept, role, is_ft, fg, status in staff_records:
            conn.execute(
                """INSERT OR IGNORE INTO staff
                   (staff_id, user_id, title, first_name, last_name, email,
                    department, role, is_form_tutor, form_group, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sid, uid, title, fn, ln, email, dept, role, is_ft, fg, status),
            )
        conn.commit()
        logger.info("Default staff records seeded for secondary school")
    except sqlite3.Error as e:
        conn.rollback()
        logger.error("Failed to seed default staff: %s", e)
    finally:
        conn.close()


def seed_default_users(db_path: str | None = None):
    """Create default admin/teacher/student accounts if they don't exist."""
    from education_system.secondary_school.infrastructure.auth.password_manager import hash_password
    from education_system.secondary_school.core.defaults import (
        DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD,
        DEFAULT_TEACHER_USERNAME, DEFAULT_TEACHER_PASSWORD,
        DEFAULT_STUDENT_USERNAME, DEFAULT_STUDENT_PASSWORD,
    )

    defaults = [
        (DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD, "admin", "admin@school.local"),
        (DEFAULT_TEACHER_USERNAME, DEFAULT_TEACHER_PASSWORD, "teacher", "teacher@school.local"),
        (DEFAULT_STUDENT_USERNAME, DEFAULT_STUDENT_PASSWORD, "student", "student@school.local"),
    ]

    conn = connect(db_path)
    try:
        for username, password, role, email in defaults:
            existing = conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if not existing:
                conn.execute(
                    """INSERT INTO users (username, password_hash, role, email)
                       VALUES (?, ?, ?, ?)""",
                    (username, hash_password(password), role, email),
                )
                logger.info("Default user created: %s (%s)", username, role)
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        logger.error("Failed to seed default users: %s", e)
    finally:
        conn.close()
