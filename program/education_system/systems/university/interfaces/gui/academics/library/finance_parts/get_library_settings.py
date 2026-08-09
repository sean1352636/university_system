"""Extracted function implementation."""

from .. import finance_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def get_library_settings(setting_name):
    """Get library setting value"""
    try:
        conn = get_db_connection()
        if not conn:
            return None

        cursor = conn.cursor()
        cursor.execute('SELECT setting_value FROM library_settings WHERE setting_name = ?', (setting_name,))
        result = cursor.fetchone()
        conn.close()

        return result[0] if result else None
    except (sqlite3.Error, DatabaseError) as e:
        print(f"Error getting setting {setting_name}: {e}")
        return None
