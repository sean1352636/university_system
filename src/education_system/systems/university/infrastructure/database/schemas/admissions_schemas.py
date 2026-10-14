from __future__ import annotations
from datetime import datetime
from education_system.systems.university.infrastructure.database.db import get_connection, sqlite3
from education_system.systems.university.infrastructure.i18n import get_text as _t, init_i18n

# Initialize i18n
init_i18n()

def init_admissions_crm_system_db():
    """Initialize the Admissions & Recruitment CRM database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="Admissions & Recruitment CRM"))

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

        # End-to-end admissions lifecycle.  These tables deliberately sit
        # beside the long-standing CRM tables: prospects/applicants remain
        # separate from enrolled students and an application may contain
        # several ranked course choices.
        for column, definition in (
            ("journey_id", "TEXT"),
            ("external_reference", "TEXT"),
            ("accepted_choice_id", "INTEGER"),
            ("converted_student_id", "TEXT"),
            ("lifecycle_updated_at", "TEXT"),
        ):
            columns = {
                row[1] for row in cursor.execute(
                    "PRAGMA table_info(admission_applications)"
                ).fetchall()
            }
            if column not in columns:
                # db-audit: ignore[DBW001] - loop over a literal table
                cursor.execute(
                    f"ALTER TABLE admission_applications "
                    f"ADD COLUMN {column} {definition}"
                )

        cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS
            idx_admission_applications_journey_external
        ON admission_applications(journey_id, external_reference)
        WHERE journey_id IS NOT NULL AND external_reference IS NOT NULL
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admission_application_choices (
            choice_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            programme_code TEXT NOT NULL,
            programme_name TEXT,
            entry_year TEXT,
            rank INTEGER NOT NULL DEFAULT 1,
            choice_status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(application_id, programme_code),
            FOREIGN KEY (application_id)
                REFERENCES admission_applications(application_id)
                ON DELETE CASCADE
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admission_requirements (
            requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            requirement_type TEXT NOT NULL,
            description TEXT NOT NULL,
            required INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'outstanding',
            evidence_document_id INTEGER,
            due_date TEXT,
            verified_by TEXT,
            verified_at TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(application_id, requirement_type, description),
            FOREIGN KEY (application_id)
                REFERENCES admission_applications(application_id)
                ON DELETE CASCADE
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admission_interviews (
            interview_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL DEFAULT 'interview',
            scheduled_at TEXT NOT NULL,
            format TEXT,
            location TEXT,
            panel TEXT,
            status TEXT NOT NULL DEFAULT 'scheduled',
            outcome TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (application_id)
                REFERENCES admission_applications(application_id)
                ON DELETE CASCADE
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admission_conditions (
            condition_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            condition_type TEXT NOT NULL,
            description TEXT NOT NULL,
            amount REAL,
            currency TEXT,
            sponsor_name TEXT,
            due_date TEXT,
            status TEXT NOT NULL DEFAULT 'outstanding',
            satisfied_at TEXT,
            evidence_reference TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(application_id, condition_type, description),
            FOREIGN KEY (application_id)
                REFERENCES admission_applications(application_id)
                ON DELETE CASCADE
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admission_status_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            from_status TEXT,
            to_status TEXT NOT NULL,
            reason TEXT,
            actor_id TEXT,
            changed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (application_id)
                REFERENCES admission_applications(application_id)
                ON DELETE CASCADE
        )
        ''')

        # application_documents merged into unified documents table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            document_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL DEFAULT 'general',
            source_document_id INTEGER,
            owner_id TEXT,
            owner_type TEXT,
            reference_type TEXT,
            reference_id TEXT,
            document_type TEXT,
            document_name TEXT,
            file_path TEXT,
            file_content TEXT,
            file_size INTEGER,
            file_hash TEXT,
            original_filename TEXT,
            upload_date TEXT,
            expiry_date TEXT,
            issue_date TEXT,
            status TEXT DEFAULT 'active',
            verification_status TEXT,
            verification_date TEXT,
            verification_notes TEXT,
            verified_by TEXT,
            version_number INTEGER DEFAULT 1,
            parent_document_id INTEGER,
            is_current_version INTEGER DEFAULT 1,
            workflow_status TEXT,
            priority INTEGER,
            tags TEXT,
            notes TEXT,
            uploaded_by TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT
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
        print(_t("schemas.initialized_success", name="Admissions & Recruitment CRM"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="Admissions CRM", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# PREDICTIVE ANALYTICS DASHBOARD SCHEMAS
# ============================================================================

