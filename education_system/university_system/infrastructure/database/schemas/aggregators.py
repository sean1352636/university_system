from __future__ import annotations
from datetime import datetime
from education_system.university_system.infrastructure.database.db import get_connection, sqlite3
from education_system.university_system.core.i18n import get_text as _t, init_i18n

# Initialize i18n
init_i18n()

def init_additional_missing_tables():
    """Initialize additional tables that were missing from schemas (109 tables)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing_additional_tables"))

        # accessibility_audit_logs
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS accessibility_audit_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_url TEXT NOT NULL,
            issues_found TEXT,
            severity TEXT,
            audited_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            audited_by INTEGER
        )
        ''')

        # accessibility_profiles
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS accessibility_profiles (
            profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL UNIQUE,
            disabilities TEXT,
            accommodations TEXT,
            assistive_technologies TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
        ''')

        # accessibility_settings
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS accessibility_settings (
            setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL UNIQUE,
            theme TEXT DEFAULT 'standard',
            font_size INTEGER DEFAULT 16,
            contrast_level TEXT DEFAULT 'normal',
            screen_reader_enabled BOOLEAN DEFAULT 0,
            keyboard_navigation BOOLEAN DEFAULT 0,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
        ''')

        # accommodation_approvals
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS accommodation_approvals (
            approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            approved_by INTEGER NOT NULL,
            approved_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (request_id) REFERENCES accommodation_requests(request_id)
        )
        ''')

        # accommodation_requests
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS accommodation_requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            accommodation_type TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending',
            requested_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_by INTEGER,
            review_date TIMESTAMP,
            review_notes TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
        ''')

        # aid_components
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS aid_components (
            component_id INTEGER PRIMARY KEY AUTOINCREMENT,
            package_id INTEGER NOT NULL,
            aid_type TEXT NOT NULL,
            source TEXT,
            name TEXT NOT NULL,
            amount REAL NOT NULL,
            disbursement_plan TEXT,
            terms_conditions TEXT,
            is_need_based BOOLEAN DEFAULT 0,
            is_renewable BOOLEAN DEFAULT 0,
            status TEXT DEFAULT 'offered',
            FOREIGN KEY (package_id) REFERENCES aid_packages(package_id) ON DELETE CASCADE
        )
        ''')

        # aid_packages
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS aid_packages (
            package_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            academic_year TEXT NOT NULL,
            total_aid_amount REAL DEFAULT 0,
            total_grants REAL DEFAULT 0,
            total_scholarships REAL DEFAULT 0,
            total_loans REAL DEFAULT 0,
            total_work_study REAL DEFAULT 0,
            package_status TEXT DEFAULT 'offered',
            offered_date DATE,
            response_deadline DATE,
            response_date DATE,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            UNIQUE(student_id, academic_year)
        )
        ''')

        # alternative_materials
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alternative_materials (
            material_id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            original_material_id INTEGER,
            format_type TEXT NOT NULL,
            file_url TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER
        )
        ''')

        # announcements
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            target_audience TEXT NOT NULL,
            is_urgent INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            start_date TEXT NOT NULL,
            end_date TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (creator_id) REFERENCES users (id)
        )
        ''')

        # api_rate_limits
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_rate_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identifier TEXT NOT NULL,
            identifier_type TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            request_count INTEGER DEFAULT 0,
            window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_request TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(identifier, identifier_type, endpoint)
        )
        ''')

        # app_installations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS app_installations (
            install_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            device_id INTEGER NOT NULL,
            installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            uninstalled_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (device_id) REFERENCES mobile_devices(device_id)
        )
        ''')

        # assignment_group_members
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assignment_group_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            role TEXT DEFAULT 'member',
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES assignment_groups(id),
            FOREIGN KEY (student_id) REFERENCES users(id)
        )
        ''')

        # assignment_groups
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assignment_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            group_name TEXT NOT NULL,
            description TEXT,
            max_members INTEGER DEFAULT 4,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assignment_id) REFERENCES assignments(id)
        )
        ''')

        # assignment_templates
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assignment_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            template_data TEXT NOT NULL,
            category TEXT,
            created_by INTEGER,
            created_at TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            usage_count INTEGER DEFAULT 0,
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
        ''')

        # assistive_tech_requests
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assistive_tech_requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            technology_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            requested_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fulfilled_date TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
        ''')

        # badge_issuances
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS badge_issuances (
            issuance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            badge_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            issued_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            blockchain_hash TEXT,
            evidence_url TEXT,
            expires_at DATE,
            is_revoked BOOLEAN DEFAULT 0,
            FOREIGN KEY (badge_id) REFERENCES digital_badges(badge_id),
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
        ''')

        # blockchain_credentials
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS blockchain_credentials (
            credential_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            credential_type TEXT NOT NULL,
            credential_name TEXT NOT NULL,
            issue_date DATE NOT NULL,
            blockchain_hash TEXT UNIQUE NOT NULL,
            blockchain_address TEXT,
            ipfs_hash TEXT,
            metadata TEXT,
            is_revoked BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
        ''')

        # blockchain_wallets
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS blockchain_wallets (
            wallet_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            wallet_address TEXT UNIQUE NOT NULL,
            blockchain_type TEXT DEFAULT 'ethereum',
            public_key TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        ''')

        # breakout_rooms
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS breakout_rooms (
            room_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            room_name TEXT NOT NULL,
            room_number INTEGER,
            participants TEXT,
            facilitator_id INTEGER,
            max_capacity INTEGER DEFAULT 10,
            topic TEXT,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            duration INTEGER,
            is_active BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES virtual_sessions(session_id) ON DELETE CASCADE
        )
        ''')

        # bulk_export_log
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bulk_export_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            export_type TEXT,
            resource_type TEXT,
            record_count INTEGER,
            status TEXT DEFAULT 'pending',
            ip_address TEXT,
            exported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved_by INTEGER,
            approved_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (approved_by) REFERENCES users(id)
        )
        ''')

        # calendar_events
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT,
            event_type TEXT NOT NULL,
            assignment_id INTEGER,
            created_by INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (assignment_id) REFERENCES assignments (id),
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
        ''')

        # compliance_reports
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS compliance_reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_type TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            report_period TEXT,
            generated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            generated_by INTEGER,
            file_url TEXT,
            submitted_date TIMESTAMP,
            submission_status TEXT,
            notes TEXT
        )
        ''')

        # credential_templates
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS credential_templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name TEXT NOT NULL,
            credential_type TEXT NOT NULL,
            template_design TEXT,
            fields TEXT,
            is_active BOOLEAN DEFAULT 1
        )
        ''')

        # credential_verifications
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS credential_verifications (
            verification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            credential_id INTEGER,
            badge_issuance_id INTEGER,
            verifier_name TEXT,
            verifier_email TEXT,
            verified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            verification_method TEXT,
            FOREIGN KEY (credential_id) REFERENCES blockchain_credentials(credential_id),
            FOREIGN KEY (badge_issuance_id) REFERENCES badge_issuances(issuance_id)
        )
        ''')

        # data_access_log
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS data_access_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            resource_type TEXT NOT NULL,
            resource_id INTEGER,
            action TEXT NOT NULL,
            session_id INTEGER,
            ip_address TEXT,
            accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
        ''')

        # degree_course_prerequisites
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS degree_course_prerequisites (
            prerequisite_id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT NOT NULL,
            prerequisite_module_code TEXT NOT NULL,
            min_grade TEXT,
            is_corequisite INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(module_code, prerequisite_module_code)
        )
        ''')

        # degree_programs_test
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS degree_programs_test (
            program_id INTEGER PRIMARY KEY AUTOINCREMENT,
            program_code TEXT UNIQUE NOT NULL,
            program_name TEXT NOT NULL
        )
        ''')

        # degree_requirements_test
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS degree_requirements_test (
            requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            program_id INTEGER NOT NULL
        )
        ''')

        # digital_badges
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS digital_badges (
            badge_id INTEGER PRIMARY KEY AUTOINCREMENT,
            badge_name TEXT NOT NULL,
            description TEXT,
            criteria TEXT NOT NULL,
            badge_image_url TEXT,
            issuer_name TEXT NOT NULL,
            badge_type TEXT DEFAULT 'skill',
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # disability_documentation
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS disability_documentation (
            doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            disability_type TEXT NOT NULL,
            file_url TEXT,
            uploaded_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expiry_date DATE,
            verified_by INTEGER,
            verified_date TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
        ''')

        # disbursements
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS disbursements (
            disbursement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            award_id INTEGER,
            component_id INTEGER,
            student_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            disbursement_type TEXT,
            disbursement_date DATE NOT NULL,
            scheduled_date DATE,
            academic_term TEXT,
            status TEXT DEFAULT 'pending',
            payment_method TEXT DEFAULT 'account_credit',
            transaction_id TEXT,
            processed_by INTEGER,
            processed_at TIMESTAMP,
            error_message TEXT,
            FOREIGN KEY (award_id) REFERENCES scholarship_awards(award_id),
            FOREIGN KEY (component_id) REFERENCES aid_components(component_id),
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
        ''')

        # email_metrics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            sent_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0,
            opened_count INTEGER DEFAULT 0,
            clicked_count INTEGER DEFAULT 0
        )
        ''')

        # emergency_alerts
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS emergency_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_title TEXT,
            alert_message TEXT,
            alert_type TEXT,
            created_date TEXT,
            created_by INTEGER,
            active BOOLEAN DEFAULT 1,
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
        ''')

        # encrypted_fields_metadata
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS encrypted_fields_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            column_name TEXT NOT NULL,
            key_id TEXT,
            encrypted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(table_name, column_name)
        )
        ''')

        # encryption_keys
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS encryption_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_id TEXT UNIQUE NOT NULL,
            public_key TEXT,
            private_key_encrypted TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            rotated_at TEXT,
            is_active INTEGER DEFAULT 1,
            algorithm TEXT,
            status TEXT
        )
        ''')

        # exam_accommodations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS exam_accommodations (
            accommodation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            exam_id INTEGER,
            extended_time INTEGER,
            separate_room BOOLEAN DEFAULT 0,
            assistive_technology TEXT,
            reader_scribe BOOLEAN DEFAULT 0,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
        ''')

        # external_scholarships
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS external_scholarships (
            external_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            provider_name TEXT NOT NULL,
            scholarship_name TEXT,
            amount REAL NOT NULL,
            academic_year TEXT NOT NULL,
            disbursement_date DATE,
            is_recurring BOOLEAN DEFAULT 0,
            contact_email TEXT,
            contact_phone TEXT,
            documentation_url TEXT,
            reported_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
        ''')

        # fafsa_data
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS fafsa_data (
            fafsa_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            academic_year TEXT NOT NULL,
            efc INTEGER,
            submission_date DATE,
            processed_date DATE,
            sai INTEGER,
            dependency_status TEXT,
            pell_eligible BOOLEAN DEFAULT 0,
            pell_amount REAL,
            verification_status TEXT DEFAULT 'not_required',
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            UNIQUE(student_id, academic_year)
        )
        ''')

        # feedback_files
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_type TEXT,
            created_by INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (submission_id) REFERENCES assignment_submissions (id),
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
        ''')

        # file_versions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS file_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            version_number INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_current INTEGER DEFAULT 0,
            FOREIGN KEY (submission_id) REFERENCES assignment_submissions (id)
        )
        ''')

        # financial_aid_applications
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS financial_aid_applications (
            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            academic_year TEXT NOT NULL,
            application_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
            family_income REAL,
            household_size INTEGER,
            special_circumstances TEXT,
            submitted_by INTEGER,
            reviewed_by INTEGER,
            review_date TIMESTAMP,
            review_notes TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
        ''')

        # forensic_analysis_results
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS forensic_analysis_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evidence_id TEXT NOT NULL,
            analysis_type TEXT NOT NULL,
            results_json TEXT,
            performed_by INTEGER,
            performed_at TEXT NOT NULL,
            FOREIGN KEY (evidence_id) REFERENCES forensic_evidence(evidence_id),
            FOREIGN KEY (performed_by) REFERENCES users(id)
        )
        ''')

        # forensic_cases
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS forensic_cases (
            case_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            priority TEXT NOT NULL DEFAULT 'MEDIUM',
            status TEXT NOT NULL DEFAULT 'OPEN',
            investigator_id INTEGER,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (investigator_id) REFERENCES users(id)
        )
        ''')

        # forensic_custody_log
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS forensic_custody_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evidence_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            user_id INTEGER,
            notes TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (evidence_id) REFERENCES forensic_evidence(evidence_id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        ''')

        # forensic_evidence
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS forensic_evidence (
            evidence_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            evidence_type TEXT NOT NULL,
            description TEXT,
            file_path TEXT,
            hash_md5 TEXT,
            hash_sha1 TEXT,
            hash_sha256 TEXT,
            hash_sha512 TEXT,
            state TEXT NOT NULL DEFAULT 'ACQUIRED',
            collected_by INTEGER,
            collected_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT,
            FOREIGN KEY (case_id) REFERENCES forensic_cases(case_id),
            FOREIGN KEY (collected_by) REFERENCES users(id)
        )
        ''')

        # group_members
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS group_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            role TEXT DEFAULT 'member',
            joined_at TEXT NOT NULL,
            contribution_score REAL DEFAULT 0,
            FOREIGN KEY (group_id) REFERENCES groups (id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # groups
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            group_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            created_by TEXT,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (assignment_id) REFERENCES assignments (id),
            FOREIGN KEY (created_by) REFERENCES students (student_id)
        )
        ''')

        # health_advisories
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_advisories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            advisory_type TEXT,
            content TEXT,
            priority TEXT,
            target_audience TEXT,
            effective_date TEXT,
            expiry_date TEXT,
            issued_by TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT
        )
        ''')

        # incident_response_actions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS incident_response_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            action_details TEXT,
            performed_by INTEGER,
            performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (incident_id) REFERENCES security_incidents(id),
            FOREIGN KEY (performed_by) REFERENCES users(id)
        )
        ''')

        # instructor_modules
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS instructor_modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instructor_id INTEGER NOT NULL,
            module_code TEXT NOT NULL,
            academic_year TEXT,
            semester TEXT,
            FOREIGN KEY (instructor_id) REFERENCES instructors(id),
            FOREIGN KEY (module_code) REFERENCES modules(module_code),
            UNIQUE(instructor_id, module_code)
        )
        ''')

        # instructor_schedules
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS instructor_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instructor_id INTEGER NOT NULL,
            module_code TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            room TEXT,
            academic_year TEXT,
            semester TEXT,
            FOREIGN KEY (instructor_id) REFERENCES instructors(id),
            FOREIGN KEY (module_code) REFERENCES modules(module_code)
        )
        ''')

        # insurance_information
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS insurance_information (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            insurance_provider TEXT,
            policy_number TEXT,
            group_number TEXT,
            subscriber_name TEXT,
            relationship_to_subscriber TEXT,
            effective_date TEXT,
            expiry_date TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # lms_settings
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lms_settings (
            id INTEGER PRIMARY KEY,
            platform TEXT,
            api_url TEXT,
            api_key TEXT,
            username TEXT,
            auto_sync INTEGER,
            sync_grades INTEGER,
            bidirectional INTEGER,
            sync_frequency TEXT
        )
        ''')

        # lms_student_enrollment
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lms_student_enrollment (
            enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            lms_course_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            enrollment_date TEXT NOT NULL DEFAULT (datetime('now')),
            last_accessed TEXT,
            progress_percentage REAL DEFAULT 0.0,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (lms_course_id) REFERENCES lms_courses(lms_course_id) ON DELETE CASCADE,
            UNIQUE(lms_course_id, student_id)
        )
        ''')

        # managed_api_keys
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS managed_api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_id TEXT UNIQUE NOT NULL,
            key_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            user_id INTEGER,
            created_at TEXT NOT NULL,
            expires_at TEXT,
            last_used_at TEXT,
            is_active INTEGER DEFAULT 1,
            permissions TEXT,
            metadata TEXT,
            previous_key_hash TEXT,
            previous_key_valid_until TEXT
        )
        ''')

        # messages
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            recipient_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            message TEXT,
            content TEXT,
            attachment_path TEXT,
            assignment_id INTEGER,
            is_read INTEGER DEFAULT 0,
            is_archived INTEGER DEFAULT 0,
            is_deleted_by_sender INTEGER DEFAULT 0,
            is_deleted_by_recipient INTEGER DEFAULT 0,
            sent_at TEXT NOT NULL,
            read_at TEXT,
            reply_to INTEGER,
            FOREIGN KEY (sender_id) REFERENCES users (id),
            FOREIGN KEY (recipient_id) REFERENCES users (id),
            FOREIGN KEY (assignment_id) REFERENCES assignments (id),
            FOREIGN KEY (reply_to) REFERENCES messages (id)
        )
        ''')

        # micro_credentials
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS micro_credentials (
            micro_id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill_name TEXT NOT NULL,
            description TEXT,
            criteria TEXT NOT NULL,
            points INTEGER DEFAULT 1,
            category TEXT,
            is_stackable BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # mobile_analytics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS mobile_analytics (
            analytics_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            device_id INTEGER,
            event_type TEXT NOT NULL,
            event_data TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (device_id) REFERENCES mobile_devices(device_id)
        )
        ''')

        # mobile_devices
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS mobile_devices (
            device_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            device_type TEXT NOT NULL,
            device_name TEXT,
            push_token TEXT UNIQUE,
            os_version TEXT,
            app_version TEXT,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        ''')

        # mobile_preferences
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS mobile_preferences (
            pref_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            theme TEXT DEFAULT 'light',
            notifications_enabled BOOLEAN DEFAULT 1,
            biometric_enabled BOOLEAN DEFAULT 0,
            offline_mode_enabled BOOLEAN DEFAULT 0,
            data_saver_enabled BOOLEAN DEFAULT 0,
            language TEXT DEFAULT 'en',
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        ''')

        # mobile_sessions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS mobile_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            device_id INTEGER NOT NULL,
            session_token TEXT UNIQUE NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (device_id) REFERENCES mobile_devices(device_id)
        )
        ''')

        # offline_sync_queue
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS offline_sync_queue (
            queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            device_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER,
            payload TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            synced_at TIMESTAMP,
            sync_status TEXT DEFAULT 'pending',
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (device_id) REFERENCES mobile_devices(device_id)
        )
        ''')

        # parent_accounts
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            relationship TEXT,
            verified INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')

        # parent_communications
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_communications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            type TEXT NOT NULL,
            subject TEXT,
            content TEXT,
            sent_at TEXT,
            read_at TEXT,
            FOREIGN KEY (parent_id) REFERENCES parent_accounts (id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # parent_conference_requests
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_conference_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            instructor_id INTEGER,
            requested_date TEXT,
            preferred_time TEXT,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            FOREIGN KEY (parent_id) REFERENCES parent_accounts (id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # parent_conferences
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_conferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            instructor_id INTEGER,
            scheduled_date TEXT,
            duration INTEGER DEFAULT 30,
            location TEXT,
            meeting_type TEXT DEFAULT 'in_person',
            meeting_link TEXT,
            notes TEXT,
            status TEXT DEFAULT 'scheduled',
            created_at TEXT,
            FOREIGN KEY (parent_id) REFERENCES parent_accounts (id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # parent_contacts
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER NOT NULL,
            contact_type TEXT NOT NULL,
            contact_value TEXT NOT NULL,
            is_primary INTEGER DEFAULT 0,
            verified INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (parent_id) REFERENCES parent_accounts (id)
        )
        ''')

        # parent_document_access
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_document_access (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER NOT NULL,
            document_id INTEGER NOT NULL,
            accessed_at TEXT,
            FOREIGN KEY (parent_id) REFERENCES parent_accounts (id),
            FOREIGN KEY (document_id) REFERENCES documents (document_id)
        )
        ''')

        # parent_notifications
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER NOT NULL,
            student_id TEXT,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TEXT,
            read_at TEXT,
            FOREIGN KEY (parent_id) REFERENCES parent_accounts (id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # parent_permissions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            permission_type TEXT NOT NULL,
            granted INTEGER DEFAULT 1,
            granted_at TEXT,
            expires_at TEXT,
            FOREIGN KEY (parent_id) REFERENCES parent_accounts (id),
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # parent_portal_activity
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_portal_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL,
            description TEXT,
            ip_address TEXT,
            created_at TEXT,
            FOREIGN KEY (parent_id) REFERENCES parent_accounts (id)
        )
        ''')

        # parent_student_links
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_student_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            relationship TEXT,
            is_primary_contact INTEGER DEFAULT 0,
            can_view_grades INTEGER DEFAULT 1,
            can_view_attendance INTEGER DEFAULT 1,
            can_view_finances INTEGER DEFAULT 0,
            verified INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (parent_id) REFERENCES parent_accounts (id),
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            UNIQUE(parent_id, student_id)
        )
        ''')

        # parking_occupancy
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_occupancy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lot_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            occupied_spaces INTEGER DEFAULT 0,
            available_spaces INTEGER DEFAULT 0,
            occupancy_rate REAL DEFAULT 0.0,
            FOREIGN KEY (lot_id) REFERENCES parking_lots (id)
        )
        ''')

        # password_history
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS password_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        ''')

        # password_policy_compliance
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS password_policy_compliance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            last_password_change TEXT,
            password_expires_at TEXT,
            failed_attempts INTEGER DEFAULT 0,
            locked_until TEXT,
            mfa_enabled INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        ''')

        # payment_schedules
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_schedules (
            schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            plan_id INTEGER,
            installment_number INTEGER NOT NULL,
            due_date TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            paid_date TEXT,
            paid_amount REAL,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (plan_id) REFERENCES payment_plan_templates (template_id)
        )
        ''')

        # permission_changes_log
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS permission_changes_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            changed_by INTEGER NOT NULL,
            old_permissions TEXT,
            new_permissions TEXT,
            change_reason TEXT,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (changed_by) REFERENCES users(id)
        )
        ''')

        # poll_responses
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS poll_responses (
            response_id INTEGER PRIMARY KEY AUTOINCREMENT,
            poll_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            option_index INTEGER NOT NULL,
            responded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (poll_id) REFERENCES virtual_polls(poll_id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            UNIQUE(poll_id, user_id)
        )
        ''')

        # realtime_notifications
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS realtime_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            notification_type TEXT DEFAULT 'info',
            is_read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT,
            action_url TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        ''')

        # renewal_requirements
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS renewal_requirements (
            requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            scholarship_id INTEGER NOT NULL,
            requirement_type TEXT NOT NULL,
            min_gpa REAL,
            min_credits INTEGER,
            description TEXT,
            FOREIGN KEY (scholarship_id) REFERENCES scholarships(scholarship_id)
        )
        ''')

        # revoked_credentials
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS revoked_credentials (
            revocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            credential_id INTEGER,
            badge_issuance_id INTEGER,
            revoked_by INTEGER NOT NULL,
            revoked_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reason TEXT NOT NULL,
            FOREIGN KEY (credential_id) REFERENCES blockchain_credentials(credential_id),
            FOREIGN KEY (badge_issuance_id) REFERENCES badge_issuances(issuance_id)
        )
        ''')

        # rideshare_posts
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS rideshare_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            trip_type TEXT NOT NULL,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL,
            departure_date TEXT NOT NULL,
            departure_time TEXT,
            seats_available INTEGER DEFAULT 1,
            price_per_seat REAL,
            notes TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')

        # scheduled_emails
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS scheduled_emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            scheduled_time TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            sent_at TEXT,
            error_message TEXT
        )
        ''')

        # scheduling_system_settings
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS scheduling_system_settings (
            id INTEGER PRIMARY KEY,
            setting_key TEXT UNIQUE NOT NULL,
            setting_value TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # schema_migrations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            migration_name TEXT NOT NULL UNIQUE,
            applied_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # scholarship_applications
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS scholarship_applications (
            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            scholarship_id INTEGER NOT NULL,
            academic_year TEXT NOT NULL,
            application_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
            essay TEXT,
            gpa REAL,
            financial_need_statement TEXT,
            reviewed_by INTEGER,
            review_date TIMESTAMP,
            review_notes TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (scholarship_id) REFERENCES scholarships(scholarship_id)
        )
        ''')

        # scholarship_awards
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS scholarship_awards (
            award_id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER,
            student_id INTEGER NOT NULL,
            scholarship_id INTEGER NOT NULL,
            academic_year TEXT NOT NULL,
            amount_awarded REAL NOT NULL,
            award_date DATE NOT NULL,
            status TEXT DEFAULT 'active',
            disbursement_schedule TEXT,
            terms_accepted BOOLEAN DEFAULT 0,
            terms_accepted_date TIMESTAMP,
            FOREIGN KEY (application_id) REFERENCES scholarship_applications(application_id),
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (scholarship_id) REFERENCES scholarships(scholarship_id)
        )
        ''')

        # search_profiles
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            profile_name TEXT NOT NULL,
            search_criteria TEXT NOT NULL,
            is_default INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')

        # search_result_archives
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_result_archives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            search_query TEXT NOT NULL,
            results_data TEXT NOT NULL,
            result_count INTEGER DEFAULT 0,
            archived_at TEXT,
            expires_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')

        # security_events
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS security_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            source TEXT,
            user_id INTEGER,
            ip_address TEXT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        ''')

        # security_incident_events
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS security_incident_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            description TEXT,
            performed_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (incident_id) REFERENCES security_incidents(id),
            FOREIGN KEY (performed_by) REFERENCES users(id)
        )
        ''')

        # security_incidents
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS security_incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            severity TEXT NOT NULL,
            status TEXT DEFAULT 'open',
            reported_by INTEGER,
            assigned_to INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            resolution_notes TEXT,
            FOREIGN KEY (reported_by) REFERENCES users(id),
            FOREIGN KEY (assigned_to) REFERENCES users(id)
        )
        ''')

        # security_policies
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS security_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            policy_name TEXT NOT NULL UNIQUE,
            policy_type TEXT NOT NULL,
            policy_config TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # session_participants
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS session_participants (
            participant_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT DEFAULT 'attendee',
            joined_at TIMESTAMP,
            left_at TIMESTAMP,
            attendance_duration INTEGER DEFAULT 0,
            is_present BOOLEAN DEFAULT 0,
            FOREIGN KEY (session_id) REFERENCES virtual_sessions(session_id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        ''')

        # sessions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_token TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        ''')

        # shuttle_buses
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shuttle_buses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bus_number TEXT UNIQUE NOT NULL,
            capacity INTEGER DEFAULT 40,
            current_route_id INTEGER,
            current_location TEXT,
            status TEXT DEFAULT 'active',
            last_updated TEXT,
            FOREIGN KEY (current_route_id) REFERENCES shuttle_routes (id)
        )
        ''')

        # shuttle_routes
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shuttle_routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route_name TEXT NOT NULL,
            description TEXT,
            start_time TEXT,
            end_time TEXT,
            frequency_minutes INTEGER DEFAULT 15,
            is_active INTEGER DEFAULT 1,
            created_at TEXT
        )
        ''')

        # shuttle_stops
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shuttle_stops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route_id INTEGER NOT NULL,
            stop_name TEXT NOT NULL,
            stop_order INTEGER NOT NULL,
            latitude REAL,
            longitude REAL,
            estimated_time_from_start INTEGER,
            FOREIGN KEY (route_id) REFERENCES shuttle_routes (id)
        )
        ''')

        # sms_messages
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sms_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_phone TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            sent_at TEXT,
            delivered_at TEXT,
            error_message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # student_timetables
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_timetables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            module_code TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            room TEXT,
            instructor_id INTEGER,
            academic_year TEXT,
            semester TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (module_code) REFERENCES modules(module_code)
        )
        ''')

        # verification_requests
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS verification_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            request_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            processed_by INTEGER,
            notes TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
        ''')

        # violation_appeals
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS violation_appeals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            violation_id INTEGER NOT NULL,
            appealed_by INTEGER NOT NULL,
            appeal_reason TEXT NOT NULL,
            appeal_date TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            reviewed_by INTEGER,
            review_date TEXT,
            review_notes TEXT,
            FOREIGN KEY (violation_id) REFERENCES parking_violations (id),
            FOREIGN KEY (appealed_by) REFERENCES users (id)
        )
        ''')

        # virtual_chat_messages
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS virtual_chat_messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            message_text TEXT NOT NULL,
            message_type TEXT DEFAULT 'text',
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_private BOOLEAN DEFAULT 0,
            recipient_id INTEGER,
            FOREIGN KEY (session_id) REFERENCES virtual_sessions(session_id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        ''')

        # virtual_classrooms
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS virtual_classrooms (
            classroom_id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            classroom_name TEXT NOT NULL,
            platform TEXT DEFAULT 'internal',
            meeting_url TEXT,
            access_code TEXT,
            max_participants INTEGER DEFAULT 100,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses(course_id)
        )
        ''')

        # virtual_polls
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS virtual_polls (
            poll_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            options TEXT NOT NULL,
            poll_type TEXT DEFAULT 'single_choice',
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closes_at TIMESTAMP,
            is_anonymous BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (session_id) REFERENCES virtual_sessions(session_id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES users(user_id)
        )
        ''')

        # virtual_recordings
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS virtual_recordings (
            recording_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            recording_url TEXT NOT NULL,
            duration INTEGER,
            file_size INTEGER,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_available BOOLEAN DEFAULT 1,
            FOREIGN KEY (session_id) REFERENCES virtual_sessions(session_id) ON DELETE CASCADE
        )
        ''')

        # virtual_sessions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS virtual_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            classroom_id INTEGER NOT NULL,
            session_title TEXT NOT NULL,
            session_type TEXT DEFAULT 'lecture',
            scheduled_start TIMESTAMP NOT NULL,
            scheduled_end TIMESTAMP NOT NULL,
            actual_start TIMESTAMP,
            actual_end TIMESTAMP,
            host_id INTEGER NOT NULL,
            meeting_link TEXT,
            status TEXT DEFAULT 'scheduled',
            recording_enabled BOOLEAN DEFAULT 0,
            max_duration INTEGER DEFAULT 120,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (classroom_id) REFERENCES virtual_classrooms(classroom_id),
            FOREIGN KEY (host_id) REFERENCES users(user_id)
        )
        ''')

        # visitor_parking
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS visitor_parking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visitor_name TEXT NOT NULL,
            vehicle_plate TEXT NOT NULL,
            host_id INTEGER NOT NULL,
            lot_id INTEGER NOT NULL,
            check_in_time TEXT NOT NULL,
            check_out_time TEXT,
            pass_number TEXT,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (host_id) REFERENCES users (id),
            FOREIGN KEY (lot_id) REFERENCES parking_lots (id)
        )
        ''')

        # vulnerability_scan_results
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS vulnerability_scan_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_type TEXT NOT NULL,
            target TEXT NOT NULL,
            vulnerability_name TEXT,
            severity TEXT,
            description TEXT,
            remediation TEXT,
            scan_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'open'
        )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.additional_tables_success"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="additional missing", error=str(e)))
        if 'conn' in locals():
            conn.close()


# ============================================================================
# MASTER INITIALIZATION FUNCTION
# ============================================================================


def init_all_missing_tables():
    """Initialize all missing tables"""
    print("=" * 80)
    print(_t("schemas.init_missing_all_header"))
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
    print(_t("schemas.all_missing_initialized_success"))
    print("=" * 80)

__all__ = [
    'init_additional_missing_tables',
    'init_all_missing_tables',
]


if __name__ == "__main__":
    """Run schema initialization when executed directly."""
    print(_t("schemas.creating_all_tables"))
    print()
    initialize_all_schemas()
    print()
    print(_t("schemas.database_setup_complete"))


