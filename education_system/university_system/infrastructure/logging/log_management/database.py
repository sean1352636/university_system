"""SQLite database for enhanced log storage and querying."""

from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH as _DB_PATH
from education_system.university_system.infrastructure.database.db import sqlite3, ensure_parent_dir

from education_system.university_system.infrastructure.logging.log_management.security import LogSecurity


class LogDatabase:
    """SQLite database for enhanced log storage and querying"""

    def __init__(self, db_path=None):
        self.db_path = db_path if db_path else str(_DB_PATH)
        ensure_parent_dir(self.db_path)
        self.init_database()

    def init_database(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(str(_DB_PATH))
        try:
            cursor = conn.cursor()

            # Main logs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    role TEXT NOT NULL,
                    action TEXT NOT NULL,
                    module TEXT NOT NULL,
                    details TEXT,
                    status TEXT NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    session_id TEXT,
                    hash TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Alerts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    triggered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    resolved BOOLEAN DEFAULT FALSE,
                    resolved_at DATETIME,
                    resolved_by TEXT
                )
            ''')

            # Saved searches table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS saved_searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    search_params TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_user_id ON logs(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_action ON logs(action)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_module ON logs(module)')

            conn.commit()
        finally:
            conn.close()

    def insert_log(self, log_data):
        """Insert a log entry into the database"""
        try:
            conn = sqlite3.connect(str(_DB_PATH))
            cursor = conn.cursor()

            # Generate hash for integrity
            log_hash = LogSecurity.generate_hash(log_data)

            # Handle user_id - convert 'system' to None to avoid FK constraint
            user_id = log_data.get('user_id')
            if user_id == 'system' or (user_id and not str(user_id).isdigit()):
                user_id = None

            cursor.execute('''
                INSERT INTO logs
                (timestamp, user_id, username, role, action, module, details, status, hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                log_data.get('timestamp'),
                user_id,
                log_data.get('username'),
                log_data.get('role', ''),
                log_data.get('action'),
                log_data.get('module', ''),
                log_data.get('details', ''),
                log_data.get('status', ''),
                log_hash
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error inserting log: {e}")
            import traceback
            traceback.print_exc()
            return False

    def search_logs(self, filters, limit=1000):
        """Advanced log search with filters"""
        try:
            conn = sqlite3.connect(str(_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT * FROM logs WHERE 1=1"
            params = []

            if filters.get('date_from'):
                query += " AND date(timestamp) >= ?"
                params.append(filters['date_from'])

            if filters.get('date_to'):
                query += " AND date(timestamp) <= ?"
                params.append(filters['date_to'])

            if filters.get('user_id'):
                query += " AND user_id = ?"
                params.append(filters['user_id'])

            if filters.get('username'):
                query += " AND username LIKE ?"
                params.append(f"%{escape_like(filters['username'])}%")

            if filters.get('action'):
                query += " AND action = ?"
                params.append(filters['action'])

            if filters.get('module'):
                query += " AND module = ?"
                params.append(filters['module'])

            if filters.get('status'):
                query += " AND status = ?"
                params.append(filters['status'])

            if filters.get('search_text'):
                query += " AND (details LIKE ? OR module LIKE ?)"
                search_term = f"%{escape_like(filters['search_text'])}%"
                params.extend([search_term, search_term])

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()

            return [dict(row) for row in results]
        except Exception as e:
            print(f"Error searching logs: {e}")
            import traceback
            traceback.print_exc()
            return []
