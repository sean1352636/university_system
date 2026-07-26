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


