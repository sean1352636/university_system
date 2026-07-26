import logging
from datetime import datetime

from education_system.systems.university.domain.operations.campus.housing.services.accommodation._common import (
    sqlite3, DB_PATH, get_current_user, HAS_AUTH, set_auth_instance,
    set_shared_auth, get_text,
)

auth = None
_AUDIT_LOG_COLUMNS_CACHE = None

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Set in centralized shared context
    set_shared_auth(auth_instance)
    # Also set it in the user_authentication module if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)

def log_action(action, accommodation_id=None, details=None):
    """Record an audit log entry with enhanced tracking."""
    try:
        user = get_current_user()
        user_id = None
        legacy_user_label = 'system'

        # Handle different types of user values
        if user is None or user == 'system':
            # For system actions, use NULL user_id but include username in details
            user_id = None
            if details:
                details = f"[system] {details}"
            else:
                details = "[system action]"
            legacy_user_label = 'system'
        elif isinstance(user, dict) and 'id' in user:
            # User object with ID
            user_id = user['id']
            legacy_user_label = str(user.get('username') or user.get('email') or user.get('id'))
        elif isinstance(user, (int, str)) and str(user).isdigit():
            # Numeric user ID
            user_id = int(user)
            legacy_user_label = str(user_id)
        else:
            # Unknown user format, log as system
            user_id = None
            if details:
                details = f"[unknown_user:{user}] {details}"
            else:
                details = f"[unknown_user:{user}]"
            legacy_user_label = str(user)

        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ip_address = "127.0.0.1"  # Default localhost - in a real system, would get actual IP

        if details is not None and not isinstance(details, str):
            details = str(details)

        try:
            record_id_int = int(accommodation_id) if accommodation_id is not None else None
        except (TypeError, ValueError):
            record_id_int = None
        record_id_text = str(accommodation_id) if accommodation_id is not None else None

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            global _AUDIT_LOG_COLUMNS_CACHE
            if _AUDIT_LOG_COLUMNS_CACHE is None:
                cursor.execute("PRAGMA table_info(audit_log)")
                _AUDIT_LOG_COLUMNS_CACHE = tuple(row[1] for row in cursor.fetchall())

            columns = _AUDIT_LOG_COLUMNS_CACHE or ()

            if 'table_affected' in columns:
                cursor.execute('''
                    INSERT INTO audit_log (user_id, action, table_affected, record_id, new_values, timestamp, ip_address, success)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, action, 'accommodations', record_id_text, details, ts, ip_address, True))
            else:
                legacy_user_value = legacy_user_label or 'system'
                cursor.execute('''
                    INSERT INTO audit_log (action, user_id, accommodation_id, details, ip_address, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (action, legacy_user_value, record_id_int, details, ip_address, ts))

            conn.commit()
            logging.info(f"Audit log: {action} by {user_id or legacy_user_label} for accommodation {accommodation_id}")
    except Exception as e:
        logging.error(f"Failed to log action '{action}': {e}")
        print(get_text("housing.accommodation.log.warning_action_logging_failed", "Warning: Action logging failed: {error}").format(error=e))
