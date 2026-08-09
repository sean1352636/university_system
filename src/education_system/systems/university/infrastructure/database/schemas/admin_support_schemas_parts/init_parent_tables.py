"""Extracted function implementation."""

from .. import admin_support_schemas_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def init_parent_tables():
    """Initialize parent system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="parent"))

        # parent_documents merged into unified documents table
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

        # Create parent_messages table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        parent_id TEXT,
                        teacher_id INTEGER,
                        student_id TEXT,
                        message_content TEXT,
                        created_date TEXT,
                        is_read BOOLEAN DEFAULT 0,
                        is_from_parent BOOLEAN DEFAULT 1,
                        message_type TEXT DEFAULT 'individual',
                        group_id TEXT,
                        FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                        FOREIGN KEY (teacher_id) REFERENCES users (id),
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create parent_preferences table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id TEXT UNIQUE,
                    email_notifications BOOLEAN DEFAULT 1,
                    sms_notifications BOOLEAN DEFAULT 0,
                    grade_alerts BOOLEAN DEFAULT 1,
                    attendance_alerts BOOLEAN DEFAULT 1,
                    behavior_alerts BOOLEAN DEFAULT 1,
                    assignment_alerts BOOLEAN DEFAULT 0,
                    weekly_summary BOOLEAN DEFAULT 1,
                    notification_timing TEXT DEFAULT '08:00',
                    quiet_hours_start TEXT DEFAULT '20:00',
                    quiet_hours_end TEXT DEFAULT '07:00',
                    FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
                )
        ''')

        # Create parent_teacher_meetings table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_teacher_meetings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        parent_id TEXT,
                        teacher_id INTEGER,
                        student_id TEXT,
                        meeting_date TEXT,
                        start_time TEXT,
                        end_time TEXT,
                        location TEXT,
                        meeting_type TEXT,
                        status TEXT DEFAULT 'scheduled',
                        agenda TEXT,
                        notes TEXT,
                        FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                        FOREIGN KEY (teacher_id) REFERENCES users (id),
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        # Create parent_user_mapping table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_user_mapping (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    parent_id TEXT UNIQUE,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
                )
        ''')

        # Create pickup_authorizations table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS pickup_authorizations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        authorized_person_name TEXT,
                        relationship TEXT,
                        phone_number TEXT,
                        id_number TEXT,
                        photo_path TEXT,
                        valid_from TEXT,
                        valid_until TEXT,
                        active BOOLEAN DEFAULT 1,
                        created_by TEXT,
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="parent"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="parent", error=str(e)))
        if 'conn' in locals():
            conn.close()
