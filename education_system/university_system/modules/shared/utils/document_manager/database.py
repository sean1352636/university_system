from ._common import (
    datetime, hashlib, sqlite3,
    get_connection, _t, log_activity,
    ACTIVITY_LOGGER_AVAILABLE,
)


class DatabaseMixin:
    def init_enhanced_db(self):
        """Initialize enhanced database with all new tables"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Users table for authentication
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password_hash TEXT,
                role TEXT,
                email TEXT,
                first_name TEXT,
                last_name TEXT,
                created_date TEXT,
                is_active BOOLEAN DEFAULT 1
            )
            ''')

            # Students table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                email_address TEXT,
                course TEXT,
                year INTEGER,
                program TEXT,
                enrollment_date TEXT,
                status TEXT DEFAULT 'active',
                phone TEXT,
                address TEXT,
                emergency_contact TEXT,
                created_date TEXT DEFAULT (datetime('now')),
                is_active BOOLEAN DEFAULT 1,
                grade_level TEXT
            )
            ''')

            # Enhanced document_types table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS document_types (
                type_id INTEGER PRIMARY KEY AUTOINCREMENT,
                type_name TEXT UNIQUE,
                description TEXT,
                is_required BOOLEAN,
                has_expiry BOOLEAN,
                expiry_reminder_days INTEGER,
                max_file_size_mb INTEGER DEFAULT 10,
                allowed_formats TEXT,
                requires_approval BOOLEAN DEFAULT 1,
                category TEXT,
                sort_order INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT 1
            )
            ''')

            # Enhanced student_documents table with versioning
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_documents (
                document_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                type_id INTEGER,
                file_path TEXT,
                original_filename TEXT,
                upload_date TEXT,
                expiry_date TEXT,
                verification_status TEXT,
                verification_date TEXT,
                verification_notes TEXT,
                version_number INTEGER DEFAULT 1,
                parent_document_id INTEGER,
                uploaded_by TEXT,
                file_size INTEGER,
                file_hash TEXT,
                tags TEXT,
                is_current_version BOOLEAN DEFAULT 1,
                workflow_status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 0,
                FOREIGN KEY (student_id) REFERENCES students (student_id),
                FOREIGN KEY (type_id) REFERENCES document_types (type_id),
                FOREIGN KEY (parent_document_id) REFERENCES student_documents (document_id),
                FOREIGN KEY (uploaded_by) REFERENCES users (username)
            )
            ''')

            # Document workflow table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS document_workflow (
                workflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER,
                step_name TEXT,
                step_order INTEGER,
                assigned_to TEXT,
                status TEXT,
                comments TEXT,
                completed_date TEXT,
                completed_by TEXT,
                FOREIGN KEY (document_id) REFERENCES student_documents (document_id)
            )
            ''')

            # Notification system
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_id TEXT,
                notification_type TEXT,
                title TEXT,
                message TEXT,
                created_date TEXT,
                sent_date TEXT,
                is_read BOOLEAN DEFAULT 0,
                is_sent BOOLEAN DEFAULT 0,
                priority TEXT DEFAULT 'normal',
                related_document_id INTEGER,
                FOREIGN KEY (related_document_id) REFERENCES student_documents (document_id)
            )
            ''')

            # Document tags table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS document_tags (
                tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag_name TEXT UNIQUE,
                tag_color TEXT,
                description TEXT
            )
            ''')

            # Document requirements by course/program
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS course_requirements (
                requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_code TEXT,
                program TEXT,
                type_id INTEGER,
                is_mandatory BOOLEAN DEFAULT 1,
                deadline_days INTEGER,
                FOREIGN KEY (type_id) REFERENCES document_types (type_id)
            )
            ''')

            # System settings
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_settings (
                setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_name TEXT UNIQUE,
                setting_value TEXT,
                description TEXT,
                updated_by TEXT,
                updated_date TEXT
            )
            ''')

            # Audit trail
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                action TEXT,
                table_name TEXT,
                record_id TEXT,
                old_values TEXT,
                new_values TEXT,
                timestamp TEXT,
                ip_address TEXT
            )
            ''')

            # Migrate existing tables if needed
            self.migrate_tables(cursor)

            # Insert default data if tables are empty
            self.insert_default_data(cursor)

            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            print(_t("shared.utils.document_manager.database_error", default="Database error: {error}", error=str(e)))
            return False

    def migrate_tables(self, cursor):
        """Migrate existing tables to add missing columns"""
        try:
            # Check if has_expiry column exists in document_types
            cursor.execute("PRAGMA table_info(document_types)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'has_expiry' not in columns:
                print("Migrating document_types table: adding has_expiry column")
                cursor.execute("ALTER TABLE document_types ADD COLUMN has_expiry BOOLEAN DEFAULT 0")

            if 'expiry_reminder_days' not in columns:
                print("Migrating document_types table: adding expiry_reminder_days column")
                cursor.execute("ALTER TABLE document_types ADD COLUMN expiry_reminder_days INTEGER DEFAULT 0")

            if 'category' not in columns:
                print("Migrating document_types table: adding category column")
                cursor.execute("ALTER TABLE document_types ADD COLUMN category TEXT DEFAULT 'General'")

            if 'sort_order' not in columns:
                print("Migrating document_types table: adding sort_order column")
                cursor.execute("ALTER TABLE document_types ADD COLUMN sort_order INTEGER DEFAULT 0")

            if 'is_active' not in columns:
                print("Migrating document_types table: adding is_active column")
                cursor.execute("ALTER TABLE document_types ADD COLUMN is_active BOOLEAN DEFAULT 1")

            # Check if students table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='students'")
            if not cursor.fetchone():
                print("Creating missing students table")
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS students (
                    student_id TEXT PRIMARY KEY,
                    first_name TEXT,
                    last_name TEXT,
                    email_address TEXT,
                    course TEXT,
                    year INTEGER,
                    program TEXT,
                    enrollment_date TEXT,
                    status TEXT DEFAULT 'active',
                    phone TEXT,
                    address TEXT,
                    emergency_contact TEXT,
                    created_date TEXT DEFAULT (datetime('now')),
                    is_active BOOLEAN DEFAULT 1,
                    grade_level TEXT
                )
                ''')

        except sqlite3.Error as e:
            print(f"Migration warning: {e}")

    def insert_default_data(self, cursor):
        """Insert default data for the system"""
        # Check if users exist
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            # Create default admin user using centralized authentication
            from education_system.university_system.core.defaults import DEFAULT_ADMIN_PASSWORD
            admin_password = DEFAULT_ADMIN_PASSWORD
            admin_created = False
            user_id = None

            try:
                from education_system.university_system.infrastructure.auth import UserAuth
                auth_system = UserAuth()
                user_id = auth_system.create_user(
                    username="admin",
                    password=admin_password,
                    email="admin@school.edu",
                    first_name="System",
                    last_name="Administrator",
                    role="admin"
                )
                if user_id:
                    print("Default admin user created via centralized auth system")
                    admin_created = True
                    # Log activity
                    if ACTIVITY_LOGGER_AVAILABLE:
                        log_activity('create', 'user', user_id=user_id, details={
                            'username': 'admin',
                            'role': 'admin',
                            'source': 'bootstrap',
                            'method': 'central_auth'
                        })
                else:
                    raise Exception("Auth system returned no user_id")
            except Exception as e:
                # Fallback to direct insertion if auth system not available during initialization
                # This is ONLY for bootstrap scenarios where the auth system may not be fully initialized
                print(f"WARNING: Using fallback admin creation (auth system unavailable): {e}")
                print("NOTE: This fallback uses weaker password hashing and should only occur during initial setup.")

                # Use PBKDF2 for better security instead of SHA256
                import secrets
                salt = secrets.token_hex(16)
                # Simple PBKDF2 implementation
                password_hash = hashlib.pbkdf2_hmac('sha256', admin_password.encode(), salt.encode(), 100000).hex()

                cursor.execute('''
                INSERT INTO users (username, password_hash, password_salt, role, email, first_name, last_name, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', ("admin", password_hash, salt, "admin", "admin@school.edu", "System", "Administrator", datetime.now().strftime('%Y-%m-%d')))
                user_id = cursor.lastrowid
                admin_created = True

                # Log activity even in fallback mode
                if ACTIVITY_LOGGER_AVAILABLE:
                    log_activity('create', 'user', user_id=user_id, details={
                        'username': 'admin',
                        'role': 'admin',
                        'source': 'bootstrap',
                        'method': 'fallback'
                    })

            if not admin_created:
                print("ERROR: Failed to create default admin user")

        # Check if document types exist
        cursor.execute('SELECT COUNT(*) FROM document_types')
        if cursor.fetchone()[0] == 0:
            default_types = [
                ('ID Photo', 'Student identification photograph', True, False, 0, 5, 'jpg,jpeg,png', True, 'Identity', 1),
                ('Birth Certificate', 'Official birth certificate', True, False, 0, 10, 'pdf,jpg,jpeg,png', True, 'Identity', 2),
                ('National ID Card', 'Government issued identification card', True, True, 30, 10, 'pdf,jpg,jpeg,png', True, 'Identity', 3),
                ('Passport', 'International passport', False, True, 60, 10, 'pdf,jpg,jpeg,png', True, 'Identity', 4),
                ('Prior Qualification', 'Previous educational qualification certificate', True, False, 0, 15, 'pdf,jpg,jpeg,png', True, 'Academic', 5),
                ('Visa Document', 'Student visa documentation', False, True, 30, 10, 'pdf,jpg,jpeg,png', True, 'Immigration', 6),
                ('Health Insurance', 'Student health insurance documentation', False, True, 30, 10, 'pdf,jpg,jpeg,png', True, 'Health', 7),
                ('Transcripts', 'Academic transcripts', True, False, 0, 15, 'pdf', True, 'Academic', 8),
                ('Medical Records', 'Health and medical records', False, True, 365, 20, 'pdf,doc,docx', True, 'Health', 9),
                ('Financial Documentation', 'Proof of financial support', False, True, 90, 15, 'pdf,doc,docx', True, 'Financial', 10)
            ]

            cursor.executemany('''
            INSERT INTO document_types (type_name, description, is_required, has_expiry, expiry_reminder_days,
            max_file_size_mb, allowed_formats, requires_approval, category, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', default_types)

        # Insert default system settings (SMTP settings removed - handled by email_manager)
        cursor.execute('SELECT COUNT(*) FROM system_settings')
        if cursor.fetchone()[0] == 0:
            default_settings = [
                ('notification_enabled', 'true', 'Enable email notifications'),
                ('auto_backup_enabled', 'false', 'Enable automatic backups'),
                ('backup_frequency_days', '7', 'Backup frequency in days'),
                ('max_file_size_mb', '50', 'Maximum file size for uploads'),
                ('document_retention_years', '7', 'Document retention period in years'),
                ('workflow_enabled', 'true', 'Enable document workflow approval process'),
                ('auto_expiry_check', 'true', 'Automatically check for expiring documents'),
                ('expiry_check_frequency_days', '1', 'How often to check for expiring documents'),
                ('bulk_upload_enabled', 'true', 'Enable bulk document upload functionality'),
                ('versioning_enabled', 'true', 'Enable document versioning')
            ]

            cursor.executemany('''
            INSERT INTO system_settings (setting_name, setting_value, description, updated_date)
            VALUES (?, ?, ?, ?)
            ''', [(s[0], s[1], s[2], datetime.now().strftime('%Y-%m-%d')) for s in default_settings])

        # Insert default tags
        cursor.execute('SELECT COUNT(*) FROM document_tags')
        if cursor.fetchone()[0] == 0:
            default_tags = [
                ('urgent', '#ff0000', 'Urgent documents requiring immediate attention'),
                ('verified', '#00ff00', 'Documents that have been verified'),
                ('pending', '#ffff00', 'Documents pending review'),
                ('archived', '#808080', 'Archived documents'),
                ('international', '#0000ff', 'Documents for international students'),
                ('renewal', '#ff8800', 'Documents requiring renewal')
            ]

            cursor.executemany('''
            INSERT INTO document_tags (tag_name, tag_color, description)
            VALUES (?, ?, ?)
            ''', default_tags)
