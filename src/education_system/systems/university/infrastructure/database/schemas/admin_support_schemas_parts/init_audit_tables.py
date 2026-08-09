"""Extracted function implementation."""

from .. import admin_support_schemas_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def init_audit_tables():
    """Initialize audit system database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="audit"))

        # Create audit_log table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    action TEXT NOT NULL,
                    table_name TEXT,
                    record_id TEXT,
                    old_values TEXT, -- JSON
                    new_values TEXT, -- JSON
                    ip_address TEXT,
                    user_agent TEXT,
                    session_id TEXT,
                    timestamp TEXT NOT NULL
                , accommodation_id INTEGER, details TEXT)
        ''')

        # Create audit_trail table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_trail (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT,
                    old_values TEXT,  -- JSON
                    new_values TEXT,  -- JSON
                    ip_address TEXT,
                    user_agent TEXT,
                    success BOOLEAN NOT NULL,
                    error_message TEXT,
                    duration REAL,
                    timestamp TEXT NOT NULL
                )
        ''')

        # Create backup_history table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS backup_history (
                            id TEXT PRIMARY KEY,
                            backup_type TEXT NOT NULL,
                            file_path TEXT NOT NULL,
                            file_size INTEGER,
                            backup_time TEXT NOT NULL,
                            status TEXT NOT NULL,
                            notes TEXT
                        )
        ''')

        # Create backups table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS backups (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        backup_name TEXT,
                        backup_path TEXT,
                        backup_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        backup_size INTEGER,
                        description TEXT
                    )
        ''')

        # Create privacy_audit_log table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS privacy_audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        action TEXT NOT NULL,
                        student_id TEXT,
                        user_id INTEGER,
                        data_accessed TEXT,
                        timestamp TEXT NOT NULL,
                        ip_address TEXT
                    )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="audit"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="audit", error=str(e)))
        if 'conn' in locals():
            conn.close()
