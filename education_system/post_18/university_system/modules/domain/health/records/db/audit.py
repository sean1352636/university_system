from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
import time
from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging

audit_logger = configure_logging(name=__name__)


def log_audit_event(user_id, action, resource_type, resource_id, details=None, conn=None, max_retries=5):
    """Write an audit row. Reuse caller's connection if provided to avoid SQLite writer locks."""
    try:
        reuse_conn = conn is not None
        if not reuse_conn:
            conn = get_connection()
        cursor = conn.cursor()

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Keep table-creation here for safety (no-op if it already exists).
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

        payload = (user_id, action, resource_type, str(resource_id), timestamp, '', details or '')

        for attempt in range(max_retries):
            try:
                cursor.execute("""
                    INSERT INTO audit_trail
                        (user_id, action, resource_type, resource_id, timestamp, old_values, new_values)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, payload)
                if not reuse_conn:
                    conn.commit()
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    time.sleep(0.15 * (2 ** attempt))  # 150ms, 300ms, 600ms, ...
                    continue
                raise

        # File-based audit log too
        audit_logger.info(
            f"USER:{user_id} ACTION:{action} RESOURCE:{resource_type}:{resource_id} DETAILS:{details}"
        )

    except Exception as e:
        # Don't break the flow for audit failures
        print(f"Warning: Audit logging failed: {e}")
    finally:
        if conn and not reuse_conn:
            try:
                conn.close()
            except Exception:
                pass



