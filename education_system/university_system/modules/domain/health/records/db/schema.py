from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta


def init_enhanced_health_db():
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Original tables (keeping existing structure)
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

        # Enhanced tables for new features

        # Audit trail table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_trail (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            action TEXT,
            resource_type TEXT,
            resource_id TEXT,
            old_values TEXT,
            new_values TEXT,
            ip_address TEXT,
            user_agent TEXT,
            timestamp TEXT,
            session_id TEXT
        )
        ''')

        # Data retention policies - FIXED COLUMN NAME
        # First check if table exists and has wrong column name
        cursor.execute("PRAGMA table_info(data_retention_policies)")
        existing_columns = cursor.fetchall()

        if existing_columns:
            # Check if table has wrong column name
            column_names = [col[1] for col in existing_columns]
            if 'retention_period_days' not in column_names:
                # Drop and recreate table with correct schema
                cursor.execute('DROP TABLE IF EXISTS data_retention_policies')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS data_retention_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_type TEXT,
            retention_period_days INTEGER,
            auto_archive INTEGER DEFAULT 0,
            auto_delete INTEGER DEFAULT 0,
            created_at TEXT
        )
        ''')

        # Security settings
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS security_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_name TEXT UNIQUE,
            setting_value TEXT,
            updated_at TEXT,
            updated_by TEXT
        )
        ''')

        # Allergies and medical conditions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS allergies (
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

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS medical_conditions (
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

        # Prescriptions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS prescriptions (
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

        # Vital signs
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS vital_signs (
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

        # Care plans
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS care_plans (
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

        # Referrals
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
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

        # Health metrics and analytics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_metrics (
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

        # Health screening schedules
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS screening_schedules (
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

        # Risk assessments
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS risk_assessments (
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

        # Emergency contacts (enhanced)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS emergency_contacts (
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

        # Provider schedules and availability
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS provider_schedules (
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

        # Health campaigns and programs
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_campaigns (
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

        # Wellness program participation
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS wellness_participation (
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

        # Disease surveillance
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS disease_surveillance (
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

        # Lab results
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lab_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            test_name TEXT,
            test_code TEXT,
            result_value TEXT,
            reference_range TEXT,
            units TEXT,
            status TEXT,
            ordered_date TEXT,
            collected_date TEXT,
            resulted_date TEXT,
            ordering_provider TEXT,
            lab_name TEXT,
            abnormal_flag TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Quality metrics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS quality_metrics (
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

        # Check if data retention policies need to be populated
        cursor.execute("SELECT COUNT(*) FROM data_retention_policies")
        if cursor.fetchone()[0] == 0:
            policies = [
                ('health_records', 2555, 1, 0),  # 7 years
                ('vaccination_records', 2555, 1, 0),  # 7 years
                ('appointments', 1095, 1, 0),  # 3 years
                ('audit_trail', 2555, 0, 0),  # 7 years, no auto-delete
                ('prescriptions', 1825, 1, 0),  # 5 years
                ('lab_results', 2555, 1, 0),  # 7 years
                ('vital_signs', 1095, 1, 0),  # 3 years
            ]

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for policy in policies:
                cursor.execute(
                    'INSERT INTO data_retention_policies (data_type, retention_period_days, auto_archive, auto_delete, created_at) VALUES (?, ?, ?, ?, ?)',
                    (*policy, timestamp)
                )

        # Check if security settings need to be populated
        cursor.execute("SELECT COUNT(*) FROM security_settings")
        if cursor.fetchone()[0] == 0:
            settings = [
                ('session_timeout_minutes', '30'),
                ('max_failed_login_attempts', '3'),
                ('password_expiry_days', '90'),
                ('require_2fa_for_providers', '1'),
                ('encryption_enabled', '1'),
                ('audit_logging_enabled', '1'),
                ('ip_restriction_enabled', '0'),
                ('allowed_ip_ranges', ''),
            ]

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for setting in settings:
                cursor.execute(
                    'INSERT INTO security_settings (setting_name, setting_value, updated_at) VALUES (?, ?, ?)',
                    (*setting, timestamp)
                )

        conn.commit()
        conn.close()
        print("Enhanced health portal database initialized successfully!")

    except sqlite3.Error as e:
        print(f"An error occurred while initializing the enhanced health database: {e}")
        if conn:
            conn.close()



def ensure_student_dob_compat():
    """
    Ensure both 'date_of_birth' and 'dob' exist on students.
    If one is missing, add it and backfill from the other.
    Safe to run repeatedly.
    """
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("PRAGMA table_info(students)")
        cols = {row[1] for row in c.fetchall()}

        if 'date_of_birth' not in cols and 'dob' in cols:
            c.execute("ALTER TABLE students ADD COLUMN date_of_birth TEXT")
            c.execute("UPDATE students SET date_of_birth = dob WHERE date_of_birth IS NULL OR date_of_birth = ''")
            conn.commit()

        elif 'dob' not in cols and 'date_of_birth' in cols:
            c.execute("ALTER TABLE students ADD COLUMN dob TEXT")
            c.execute("UPDATE students SET dob = date_of_birth WHERE dob IS NULL OR dob = ''")
            conn.commit()

    except Exception as e:
        # Don't crash menus if PRAGMA/ALTER fails; just surface a note.
        print(f"(Schema compat) {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass



