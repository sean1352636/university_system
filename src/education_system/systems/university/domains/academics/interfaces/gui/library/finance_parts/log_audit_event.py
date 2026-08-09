"""Extracted function implementation."""

from .. import finance_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def log_audit_event(user_id, action, table_name=None, record_id=None, success=True):
    """Log audit event"""
    try:
        if not ORIGINAL_LIBRARY_AVAILABLE:
            return

        conn = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        user_value = user_id if user_id not in (None, "") else 'system'

        insert_attempts = [
            (
                "user_id, action, table_affected, record_id, timestamp, success",
                (user_value, action, table_name, record_id, timestamp, int(bool(success)))
            ),
            (
                "user_id, action, record_id, timestamp",
                (user_value, action, record_id, timestamp)
            ),
            (
                "action, user_id, timestamp",
                (action, user_value, timestamp)
            ),
            (
                "action, timestamp",
                (action, timestamp)
            ),
        ]

        logged = False
        for column_list, values in insert_attempts:
            placeholders = ', '.join('?' for _ in values)
            try:
                cursor.execute(
                    f"INSERT INTO audit_log ({column_list}) VALUES ({placeholders})",
                    values
                )
                logged = True
                break
            except sqlite3.OperationalError:
                continue

        if not logged:
            print("Warning: Unable to record audit event; audit_log schema not compatible.")

        conn.commit()
        conn.close()
    except (sqlite3.Error, DatabaseError, ValueError, TypeError) as e:
        print(f"Error logging audit event: {e}")
