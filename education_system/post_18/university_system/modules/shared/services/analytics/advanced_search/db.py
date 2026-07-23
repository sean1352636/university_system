"""Database initialization, schema management, and search analytics record helpers."""
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.post_18.university_system.core.sql_safety import (
    validate_identifier,
    validate_table_name,
)
from education_system.post_18.university_system.modules.shared.services.analytics.advanced_search import _globals


def refresh_search_analytics_columns(cursor) -> List[str]:
    """Refresh cached search_analytics columns."""
    cursor.execute("PRAGMA table_info(search_analytics)")
    _globals.SEARCH_ANALYTICS_COLUMNS_CACHE = [row[1] for row in cursor.fetchall()]
    return _globals.SEARCH_ANALYTICS_COLUMNS_CACHE


def get_search_analytics_columns(cursor) -> List[str]:
    if _globals.SEARCH_ANALYTICS_COLUMNS_CACHE is None:
        return refresh_search_analytics_columns(cursor)
    return _globals.SEARCH_ANALYTICS_COLUMNS_CACHE


def ensure_search_analytics_schema(cursor) -> List[str]:
    """Ensure search_analytics table contains the columns expected across modules."""
    columns = set(refresh_search_analytics_columns(cursor))

    if 'search_query' not in columns:
        cursor.execute("ALTER TABLE search_analytics ADD COLUMN search_query TEXT")
        columns = set(refresh_search_analytics_columns(cursor))

    if 'search_criteria' not in columns:
        cursor.execute("ALTER TABLE search_analytics ADD COLUMN search_criteria TEXT")
        columns = set(refresh_search_analytics_columns(cursor))

    if 'timestamp' not in columns and 'search_datetime' not in columns:
        cursor.execute("ALTER TABLE search_analytics ADD COLUMN timestamp TEXT")
        columns = set(refresh_search_analytics_columns(cursor))

    if 'search_query' in columns:
        cursor.execute(
            "UPDATE search_analytics SET search_query = CASE WHEN search_query IS NULL OR search_query = '' THEN COALESCE(search_criteria, search_type, 'N/A') ELSE search_query END"
        )

    time_column = 'timestamp' if 'timestamp' in columns else 'search_datetime' if 'search_datetime' in columns else None
    if time_column:
        validated_time_col = validate_identifier(time_column, 'column')
        cursor.execute(
            f"UPDATE search_analytics SET {validated_time_col} = COALESCE({validated_time_col}, datetime('now'))"
        )

    return list(columns)


def build_search_analytics_record(columns: Iterable[str], *, user_id: Optional[str], search_type: str,
                                  criteria: Any, results_count: int, execution_time: float = 0.0,
                                  timestamp: Optional[str] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
    column_set = set(columns)
    record: Dict[str, Any] = {}
    criteria_str = str(criteria) if criteria is not None else ''
    timestamp_value = timestamp or datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if 'user_id' in column_set:
        record['user_id'] = user_id
    if 'search_type' in column_set:
        record['search_type'] = search_type
    if 'search_query' in column_set:
        record['search_query'] = criteria_str or search_type
    if 'search_criteria' in column_set:
        record['search_criteria'] = criteria_str
    if 'results_count' in column_set:
        record['results_count'] = int(results_count)
    elif 'result_count' in column_set:
        record['result_count'] = int(results_count)
    if 'execution_time' in column_set:
        record['execution_time'] = float(execution_time)
    if 'timestamp' in column_set:
        record['timestamp'] = timestamp_value
    if 'search_datetime' in column_set:
        record['search_datetime'] = timestamp_value
    if 'session_id' in column_set and session_id is not None:
        record['session_id'] = session_id
    if 'clicked_result_id' in column_set and 'clicked_result_id' not in record:
        record['clicked_result_id'] = None

    return record


def insert_search_analytics_record(cursor, **kwargs):
    columns = ensure_search_analytics_schema(cursor)
    record = build_search_analytics_record(columns, **kwargs)
    if not record:
        return
    placeholders = ', '.join('?' for _ in record)
    cursor.execute(
        f"INSERT INTO search_analytics ({', '.join(record.keys())}) VALUES ({placeholders})",
        tuple(record.values())
    )

def init_enhanced_database():
    """Initialize database with enhanced tables for new features"""
    try:
        # Connect to the database
        conn = get_connection()
        cursor = conn.cursor()

        print("Creating enhanced database tables...")

        # Create the main students table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            email TEXT,
            title TEXT,
            first_name TEXT,
            middle_name TEXT,
            last_name TEXT,
            gender TEXT,
            date_of_birth TEXT,
            age INTEGER,
            course TEXT,
            registration_datetime TEXT
        )
        ''')

        # Create the student_modules table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            module_type TEXT,
            module_code TEXT,
            module_name TEXT,
            grade TEXT,
            enrollment_date TEXT,
            completion_date TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Create enhanced tables for new features
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            search_query TEXT,
            search_type TEXT,
            search_criteria TEXT,
            results_count INTEGER,
            execution_time REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            session_id TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS saved_searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            search_name TEXT,
            search_criteria TEXT,
            is_shared BOOLEAN DEFAULT 0,
            created_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_permissions (
            user_id TEXT PRIMARY KEY,
            role TEXT,
            permissions TEXT,
            created_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS scheduled_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            report_name TEXT,
            search_criteria TEXT,
            schedule_pattern TEXT,
            email_recipients TEXT,
            last_run DATETIME,
            is_active BOOLEAN DEFAULT 1
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS duplicate_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id_1 TEXT,
            student_id_2 TEXT,
            similarity_score REAL,
            status TEXT DEFAULT 'pending',
            reviewed_by TEXT,
            reviewed_date DATETIME
        )
        ''')

        # Create indexes for better performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_students_name ON students(first_name, last_name)",
            "CREATE INDEX IF NOT EXISTS idx_students_course ON students(course)",
            "CREATE INDEX IF NOT EXISTS idx_students_age ON students(age)",
            "CREATE INDEX IF NOT EXISTS idx_students_registration ON students(registration_datetime)",
            "CREATE INDEX IF NOT EXISTS idx_modules_student ON student_modules(student_id)",
            "CREATE INDEX IF NOT EXISTS idx_modules_code ON student_modules(module_code)",
            "CREATE INDEX IF NOT EXISTS idx_search_analytics_user ON search_analytics(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_search_analytics_type ON search_analytics(search_type)",
            "CREATE INDEX IF NOT EXISTS idx_saved_searches_user ON saved_searches(user_id)"
        ]

        for index_sql in indexes:
            cursor.execute(index_sql)

        ensure_search_analytics_schema(cursor)

        cursor.execute("SELECT COUNT(*) FROM students")
        student_count = cursor.fetchone()[0]
        if student_count == 0:
            print("⚠ No student records found. Populate the students table to unlock advanced analytics.")

        cursor.execute("SELECT COUNT(*) FROM student_modules")
        module_enrollment_count = cursor.fetchone()[0]
        if module_enrollment_count == 0:
            print("⚠ No student module enrolments detected in the database.")

        cursor.execute("SELECT COUNT(*) FROM user_permissions WHERE user_id = 'system'")
        system_permissions = cursor.fetchone()[0]
        if system_permissions == 0:
            print("⚠ System user permissions are not configured. Please configure them through the administration interface.")

        cursor.execute("SELECT COUNT(*) FROM search_analytics")
        analytics_count = cursor.fetchone()[0]
        if analytics_count == 0:
            print("ℹ️ Search analytics table is empty. Records will accumulate as users perform searches.")

        # Commit changes
        conn.commit()
        conn.close()

        print("✅ Enhanced database initialized successfully!")
        print("Tables created:")
        print("  • students")
        print("  • student_modules")
        print("  • search_analytics")
        print("  • saved_searches")
        print("  • user_permissions")
        print("  • scheduled_reports")
        print("  • duplicate_candidates")
        print("\nYou can now run the enhanced search system without errors.")

    except sqlite3.Error as e:
        print(f"❌ Database initialization error: {e}")

def ensure_tables_exist():
    """Quick function to ensure all tables exist before running analytics"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if search_analytics table exists
        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='search_analytics'
        """)

        if not cursor.fetchone():
            conn.close()
            print("🔧 Required tables missing. Initializing database...")
            init_enhanced_database()
            return True

        conn.close()
        return False

    except sqlite3.Error:
        init_enhanced_database()
        return True

def check_database_status():
    """Check the current status of the database"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()

        print("📊 Current Database Status:")
        print("=" * 40)

        if not tables:
            print("❌ No tables found in database")
            return

        for (table_name,) in tables:
            safe_table = validate_table_name(table_name, conn=conn)
            cursor.execute("SELECT COUNT(*) FROM [" + safe_table + "]")
            count = cursor.fetchone()[0]
            print(f"  {table_name}: {count} records")

        conn.close()

    except sqlite3.Error as e:
        print(f"❌ Error checking database: {e}")
