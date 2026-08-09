"""Extracted function implementation."""

from .. import finance_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def update_library_setting(setting_name, setting_value):
    """Update library setting"""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        cursor.execute('''
        INSERT OR REPLACE INTO library_settings (setting_name, setting_value)
        VALUES (?, ?)
        ''', (setting_name, setting_value))

        conn.commit()
        conn.close()
        return True
    except (sqlite3.Error, DatabaseError) as e:
        print(f"Error updating setting {setting_name}: {e}")
        return False
