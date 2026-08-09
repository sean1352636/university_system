"""Extracted function implementation."""

from .. import admin_support_schemas_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def init_auth_tables():
    """Initialize auth system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="auth"))

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

        # Create permissions table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    permission_name TEXT UNIQUE NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
        ''')

        # Create photo_permissions table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS photo_permissions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        permission_type TEXT,
                        consent_given BOOLEAN DEFAULT 0,
                        conditions TEXT,
                        valid_from TEXT,
                        valid_until TEXT,
                        parent_signature TEXT,
                        date_signed TEXT,
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
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

        # Create security_settings table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS security_settings (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            setting_name TEXT UNIQUE,
                            setting_value TEXT,
                            updated_at TEXT,
                            updated_by TEXT
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

        # Create user_accounts table
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

        # Create user_achievements table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_achievements (
                    achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    achievement_type TEXT NOT NULL,
                    achievement_name TEXT NOT NULL,
                    description TEXT,
                    earned_date TEXT NOT NULL,
                    points INTEGER DEFAULT 0
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

        # Create user_preferences table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id TEXT PRIMARY KEY,
                    email_notifications BOOLEAN DEFAULT 1,
                    in_app_notifications BOOLEAN DEFAULT 1,
                    push_notifications BOOLEAN DEFAULT 1,
                    digest_frequency TEXT DEFAULT 'daily',  -- immediate, daily, weekly
                    theme TEXT DEFAULT 'light',
                    language TEXT DEFAULT 'en',
                    timezone TEXT DEFAULT 'UTC',
                    preferences_json TEXT  -- Additional JSON preferences
                )
        ''')

        # Create user_timezone_preferences table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_timezone_preferences (
                            user_id TEXT PRIMARY KEY,
                            timezone_name TEXT NOT NULL,
                            auto_dst BOOLEAN DEFAULT TRUE,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            FOREIGN KEY (user_id) REFERENCES users (id)
                        )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="auth"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="auth", error=str(e)))
        if 'conn' in locals():
            conn.close()
