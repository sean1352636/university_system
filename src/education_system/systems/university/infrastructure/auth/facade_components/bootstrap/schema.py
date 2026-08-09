"""Extracted backwards-compatible UserAuth methods."""
from ...facade_support import *

class AuthBootstrapSchemaMixin:
    def _init_db(self):
        """
        Initialize database tables needed for authentication.

        Thread-safe: Uses double-checked locking pattern to prevent
        race conditions during initialization.
        """
        # This method lives in a mixin and must not import the concrete
        # ``UserAuth`` facade (that would create a circular import). Resolve
        # the owning class from the instance instead.
        auth_class = type(self)

        # Fast path - check without lock first
        if auth_class._db_initialized:
            return

        # Slow path - acquire lock and double-check
        with auth_class._init_lock:
            # Double-check after acquiring lock
            if auth_class._db_initialized:
                return

            # All initialization happens within the lock
            self._do_init_db()
            auth_class._db_initialized = True

    def _do_init_db(self):
        """Perform the actual database initialization (called within lock)."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            # Ensure the student catalogue exists before creating dependent tables
            self._ensure_students_table(cursor)

            # Create users table for storing user profile information
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                role TEXT NOT NULL,
                student_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            ''')

            # Create user_accounts table - for storing authentication data
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                is_active INTEGER DEFAULT 1,
                last_login TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                password_reset_required INTEGER DEFAULT 0,
                two_fa_enabled INTEGER DEFAULT 0,
                two_fa_secret TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            ''')

            # Create two_fa_recovery_codes table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS two_fa_recovery_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                code_hash TEXT NOT NULL,
                is_used INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                used_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            ''')

            # Create roles table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_name TEXT UNIQUE NOT NULL,
                description TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            ''')

            # Create permissions table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                permission_name TEXT UNIQUE NOT NULL,
                description TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            ''')

            # Create role_permissions table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS role_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_id INTEGER NOT NULL,
                permission_id INTEGER NOT NULL,
                FOREIGN KEY (role_id) REFERENCES roles (id),
                FOREIGN KEY (permission_id) REFERENCES permissions (id),
                UNIQUE(role_id, permission_id)
            )
            ''')

            # Create user_permissions table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                permission_id INTEGER NOT NULL,
                granted INTEGER NOT NULL,
                UNIQUE(user_id, permission_id),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(permission_id) REFERENCES permissions(id) ON DELETE CASCADE
            )
            ''')

            # Create login_attempts table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                attempt_time TEXT NOT NULL,
                ip_address TEXT,
                success INTEGER NOT NULL
            )
            ''')

            # Create activity_log table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                timestamp TEXT NOT NULL,
                ip_address TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            ''')

            conn.commit()

            # Initialize roles if they don't exist
            cursor.execute('SELECT COUNT(*) FROM roles')
            role_count = cursor.fetchone()[0]

            if role_count == 0:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Insert default roles
                for role_name, description in ROLES.items():
                    cursor.execute(
                        'INSERT INTO roles (role_name, description, created_at, updated_at) VALUES (?, ?, ?, ?)',
                        (role_name, description, timestamp, timestamp)
                    )

                conn.commit()

            # Initialize permissions if they don't exist
            cursor.execute('SELECT COUNT(*) FROM permissions')
            permission_count = cursor.fetchone()[0]

            if permission_count == 0:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Gather all unique permissions
                all_permissions = set()
                for perms in PERMISSIONS.values():
                    all_permissions.update(perms)

                # Insert permissions
                for perm in all_permissions:
                    description = ' '.join(word.capitalize() for word in perm.split('_'))
                    cursor.execute(
                        'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                        (perm, description, timestamp)
                    )

                conn.commit()

                # Now associate permissions with roles
                for role, perms in PERMISSIONS.items():
                    cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role,))
                    role_result = cursor.fetchone()
                    if role_result:
                        role_id = role_result[0]

                        for perm in perms:
                            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm,))
                            perm_result = cursor.fetchone()
                            if perm_result:
                                perm_id = perm_result[0]

                                cursor.execute(
                                    'SELECT COUNT(*) FROM role_permissions WHERE role_id = ? AND permission_id = ?',
                                    (role_id, perm_id)
                                )
                                if cursor.fetchone()[0] == 0:
                                    cursor.execute(
                                        'INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                                        (role_id, perm_id)
                                    )

                conn.commit()
            else:
                # If permissions already exist, ensure all permissions in PERMISSIONS are created
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                all_permissions = set()
                for perms in PERMISSIONS.values():
                    all_permissions.update(perms)

                for perm in all_permissions:
                    cursor.execute('SELECT COUNT(*) FROM permissions WHERE permission_name = ?', (perm,))
                    if cursor.fetchone()[0] == 0:
                        description = ' '.join(word.capitalize() for word in perm.split('_'))
                        cursor.execute(
                            'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                            (perm, description, timestamp)
                        )

                conn.commit()

                # Then ensure all role-permission associations exist
                for role, perms in PERMISSIONS.items():
                    cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role,))
                    role_result = cursor.fetchone()
                    if role_result:
                        role_id = role_result[0]

                        for perm in perms:
                            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm,))
                            perm_result = cursor.fetchone()
                            if perm_result:
                                perm_id = perm_result[0]

                                cursor.execute(
                                    'SELECT COUNT(*) FROM role_permissions WHERE role_id = ? AND permission_id = ?',
                                    (role_id, perm_id)
                                )
                                if cursor.fetchone()[0] == 0:
                                    cursor.execute(
                                        'INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                                        (role_id, perm_id)
                                    )

                conn.commit()

            # Create default student record if needed
            self._create_default_student_if_needed(cursor, conn)

            # Create default accounts ONLY if they don't exist
            self._create_default_accounts_if_needed(cursor, conn)
        finally:
            # Always close the connection, even if an error occurs
            conn.close()

    def _ensure_students_table(self, cursor):
        """Guarantee the student catalogue exists for auth relationships"""
        try:
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                email_address TEXT,
                title TEXT,
                first_name TEXT,
                middle_name TEXT,
                last_name TEXT,
                gender TEXT,
                dob TEXT,
                age INTEGER,
                course TEXT,
                registration_datetime TEXT,
                status TEXT DEFAULT 'Active',
                enrollment_date TEXT
            )
            ''')

            cursor.execute("PRAGMA table_info(students)")
            existing_columns = {column[1] for column in cursor.fetchall()}

            required_columns = {
                'email_address': 'TEXT',
                'title': 'TEXT',
                'first_name': 'TEXT',
                'middle_name': 'TEXT',
                'last_name': 'TEXT',
                'gender': 'TEXT',
                'dob': 'TEXT',
                'age': 'INTEGER',
                'course': 'TEXT',
                'registration_datetime': 'TEXT',
                'status': 'TEXT DEFAULT "Active"',
                'enrollment_date': 'TEXT'
            }

            # Use centralized SQL safety validation for column definitions
            for column, definition in required_columns.items():
                if column not in existing_columns:
                    try:
                        # Validate column definition using SQL safety module
                        col_def = validate_column_definition(column, definition)
                        cursor.execute('ALTER TABLE students ADD COLUMN [' + col_def.name + '] ' + col_def.type_def)
                        logging.info(f"Added missing column '{column}' to students table")
                    except SQLIdentifierError as e:
                        logging.warning(f"Invalid column definition for '{column}': {e}")
                        continue
                    except sqlite3.OperationalError as e:
                        if "duplicate column name" in str(e).lower():
                            continue
                        logging.warning(f"Could not add column '{column}' to students table: {e}")
                    except sqlite3.Error as e:
                        logging.warning(f"SQLite error while adding column '{column}': {e}")

        except sqlite3.Error as e:
            logging.error(f"Failed to ensure students table exists: {e}")
            raise

    def _create_default_student_if_needed(self, cursor, conn):
        """Ensure the default student record exists in the students table."""

        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='students'")
            table_exists = cursor.fetchone() is not None
            if not table_exists:
                logging.warning(
                    "Students table is missing; student-related authentication features may be unavailable."
                )
                return

            cursor.execute('SELECT student_id FROM students WHERE student_id = ?',
                           (defaults.DEFAULT_STUDENT_ID,))
            if not cursor.fetchone():
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    INSERT INTO students (student_id, first_name, last_name, email_address,
                                          status, registration_datetime)
                    VALUES (?, ?, ?, ?, 'Active', ?)
                ''', (
                    defaults.DEFAULT_STUDENT_ID,
                    defaults.DEFAULT_STUDENT_FIRST_NAME,
                    defaults.DEFAULT_STUDENT_LAST_NAME,
                    defaults.DEFAULT_STUDENT_EMAIL,
                    timestamp,
                ))
                conn.commit()
                logging.info(f"Created default student record: {defaults.DEFAULT_STUDENT_ID}")
        except sqlite3.Error as exc:
            logging.warning(f"Could not inspect students table: {exc}")
