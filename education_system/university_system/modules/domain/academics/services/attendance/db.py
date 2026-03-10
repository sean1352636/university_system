"""Database schema initialization for the enhanced attendance tracking system."""

from education_system.university_system.infrastructure.database.db import sqlite3, get_connection


def init_enhanced_attendance_db():
    """Initialize enhanced attendance tracking database with all new features"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Original attendance records table (enhanced)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_code TEXT,
            date TEXT,
            status TEXT,
            notes TEXT,
            recorded_by TEXT,
            recorded_at TEXT,
            check_in_method TEXT DEFAULT 'manual',
            location_data TEXT,
            ip_address TEXT,
            session_id TEXT,
            makeup_for_date TEXT,
            verification_status TEXT DEFAULT 'verified',
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        # Enhanced attendance settings
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_name TEXT UNIQUE,
            setting_value TEXT,
            description TEXT,
            category TEXT DEFAULT 'general',
            data_type TEXT DEFAULT 'string',
            last_modified TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Attendance sessions (for QR codes and geofencing)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE,
            module_code TEXT,
            date TEXT,
            start_time TEXT,
            end_time TEXT,
            location_name TEXT,
            latitude REAL,
            longitude REAL,
            geofence_radius INTEGER DEFAULT 50,
            qr_code_data TEXT,
            qr_code_expires TEXT,
            session_type TEXT DEFAULT 'lecture',
            max_capacity INTEGER,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        # Student biometric data
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_biometrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            face_encoding BLOB,
            face_photo_path TEXT,
            enrolled_date TEXT DEFAULT CURRENT_TIMESTAMP,
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Attendance alerts and notifications
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id TEXT UNIQUE,
            student_id TEXT,
            module_code TEXT,
            alert_type TEXT,
            severity TEXT,
            message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            sent_at TEXT,
            acknowledged_at TEXT,
            status TEXT DEFAULT 'pending',
            recipient_email TEXT,
            recipient_phone TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        # Attendance policies and rules
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            policy_id TEXT UNIQUE,
            name TEXT,
            description TEXT,
            module_code TEXT,
            course TEXT,
            min_attendance_percentage REAL,
            max_consecutive_absences INTEGER,
            late_tolerance_minutes INTEGER DEFAULT 15,
            makeup_allowed BOOLEAN DEFAULT 1,
            auto_fail_threshold REAL,
            grace_period_days INTEGER DEFAULT 0,
            effective_from TEXT,
            effective_until TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active'
        )
        ''')

        # Gamification system
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_gamification (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            points INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            badges TEXT,
            achievements TEXT,
            streak_days INTEGER DEFAULT 0,
            best_streak INTEGER DEFAULT 0,
            last_attendance_date TEXT,
            total_rewards INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Attendance appeals
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_appeals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appeal_id TEXT UNIQUE,
            student_id TEXT,
            module_code TEXT,
            attendance_record_id INTEGER,
            original_status TEXT,
            requested_status TEXT,
            reason TEXT,
            evidence_files TEXT,
            submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            reviewed_by TEXT,
            reviewed_at TEXT,
            decision TEXT,
            decision_reason TEXT,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code),
            FOREIGN KEY (attendance_record_id) REFERENCES attendance_records (id)
        )
        ''')

        # System audit log
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            action TEXT,
            table_name TEXT,
            record_id TEXT,
            old_values TEXT,
            new_values TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT
        )
        ''')

        # API keys and integrations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_integrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            integration_name TEXT UNIQUE,
            api_key TEXT,
            endpoint_url TEXT,
            status TEXT DEFAULT 'active',
            last_sync TEXT,
            sync_frequency TEXT DEFAULT 'daily',
            config_data TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Predictive analytics data
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_code TEXT,
            prediction_date TEXT,
            predicted_attendance_rate REAL,
            risk_level TEXT,
            confidence_score REAL,
            factors TEXT,
            recommendations TEXT,
            model_version TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (module_code) REFERENCES modules (module_code)
        )
        ''')

        # Insert enhanced default settings
        enhanced_settings = [
            # Original settings
            ('attendance_threshold_warning', '80', 'Attendance percentage below which a warning is issued', 'thresholds', 'integer'),
            ('attendance_threshold_critical', '70', 'Attendance percentage below which critical action is required', 'thresholds', 'integer'),
            ('consecutive_absences_warning', '2', 'Number of consecutive absences before a warning is issued', 'thresholds', 'integer'),
            ('consecutive_absences_critical', '3', 'Number of consecutive absences before critical action is required', 'thresholds', 'integer'),
            ('auto_email_warnings', 'False', 'Whether to automatically email students with attendance warnings', 'notifications', 'boolean'),
            ('attendance_statuses', 'Present,Late,Excused,Absent', 'Comma-separated list of valid attendance statuses', 'general', 'string'),

            # New enhanced settings
            ('enable_qr_checkin', 'True', 'Enable QR code check-in system', 'features', 'boolean'),
            ('qr_code_expiry_minutes', '15', 'QR code expiry time in minutes', 'qr_system', 'integer'),
            ('enable_geofencing', 'False', 'Enable location-based attendance', 'features', 'boolean'),
            ('geofence_radius_meters', '50', 'Geofence radius in meters', 'location', 'integer'),
            ('enable_face_recognition', 'False', 'Enable facial recognition for attendance', 'features', 'boolean'),
            ('enable_gamification', 'True', 'Enable gamification features', 'features', 'boolean'),
            ('points_per_attendance', '10', 'Points awarded for each attendance', 'gamification', 'integer'),
            ('streak_bonus_multiplier', '1.5', 'Bonus multiplier for attendance streaks', 'gamification', 'float'),
            ('enable_sms_notifications', 'False', 'Enable SMS notifications', 'notifications', 'boolean'),
            ('sms_api_key', '', 'SMS service API key', 'integrations', 'string'),
            ('enable_parent_portal', 'False', 'Enable parent access to attendance', 'features', 'boolean'),
            ('auto_backup_enabled', 'True', 'Enable automatic data backup', 'system', 'boolean'),
            ('backup_frequency_hours', '24', 'Backup frequency in hours', 'system', 'integer'),
            ('api_rate_limit', '1000', 'API requests per hour limit', 'api', 'integer'),
            ('enable_audit_log', 'True', 'Enable detailed audit logging', 'system', 'boolean'),
            ('session_timeout_minutes', '60', 'User session timeout in minutes', 'security', 'integer'),
            ('enable_two_factor_auth', 'False', 'Enable two-factor authentication', 'security', 'boolean'),
            ('dashboard_refresh_seconds', '30', 'Dashboard auto-refresh interval', 'ui', 'integer'),
            ('enable_dark_mode', 'False', 'Enable dark mode interface', 'ui', 'boolean'),
            ('language', 'en', 'Default system language', 'ui', 'string'),
            ('timezone', 'UTC', 'Default system timezone', 'system', 'string'),
            ('enable_predictive_analytics', 'True', 'Enable ML-based predictions', 'analytics', 'boolean'),
            ('prediction_model_accuracy_threshold', '0.75', 'Minimum model accuracy required', 'analytics', 'float'),
            ('enable_auto_interventions', 'False', 'Enable automatic intervention recommendations', 'analytics', 'boolean')
        ]

        for setting in enhanced_settings:
            cursor.execute('''
            INSERT OR IGNORE INTO attendance_settings
            (setting_name, setting_value, description, category, data_type)
            VALUES (?, ?, ?, ?, ?)
            ''', setting)

        conn.commit()
        conn.close()
        print("Enhanced attendance database initialized successfully!")
        return True

    except sqlite3.Error as e:
        print(f"An error occurred while initializing the enhanced attendance database: {e}")
        return False


def create_missing_tables():
    """Create missing tables needed by reporting system"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Create student_attendance table from attendance_records
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_attendance AS
        SELECT student_id, module_code, date, status, notes, recorded_at
        FROM attendance_records
        WHERE student_id IS NOT NULL
        ''')

        # Ensure registration_datetime exists in students table
        cursor.execute("PRAGMA table_info(students)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'registration_datetime' not in columns:
            cursor.execute('ALTER TABLE students ADD COLUMN registration_datetime TEXT')
            # Set default values
            cursor.execute('''
            UPDATE students
            SET registration_datetime = datetime('now', '-' || (CAST(student_id AS INTEGER) * 7) || ' days')
            WHERE registration_datetime IS NULL
            ''')

        conn.commit()
        conn.close()
        print("✅ Missing tables created successfully")

    except Exception as e:
        print(f"Error creating missing tables: {e}")
