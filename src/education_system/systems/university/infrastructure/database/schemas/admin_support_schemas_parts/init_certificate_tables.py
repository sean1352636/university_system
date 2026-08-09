"""Extracted function implementation."""

from .. import admin_support_schemas_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def init_certificate_tables():
    """Initialize certificate and transcript request tables."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(_t("schemas.initializing", name="Certificates & Transcripts"))

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            certificate_number TEXT UNIQUE NOT NULL,
            certificate_type TEXT NOT NULL,
            course_name TEXT NOT NULL,
            award_date TEXT NOT NULL,
            grade TEXT,
            additional_info TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            issued_by TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS transcript_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            requested_by TEXT,
            academic_year TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            generated_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        conn.commit()
        conn.close()
        print(_t("schemas.initialized_success", name="Certificates & Transcripts"))

    except sqlite3.Error as e:
        print(_t("schemas.init_error", name="Certificates & Transcripts", error=str(e)))
        if 'conn' in locals():
            conn.close()
