"""Settings management for the attendance tracking system."""

import datetime
from education_system.post_18.university_system.infrastructure.database.db import get_connection


def get_setting(setting_name, default_value=None):
    """Get setting value from database or return default"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT setting_value FROM attendance_settings
        WHERE setting_name = ?
        ''', (setting_name,))

        result = cursor.fetchone()
        conn.close()

        return result[0] if result else default_value

    except Exception as e:
        print(f"Error getting setting: {e}")
        return default_value


def get_enhanced_setting(setting_name, default_value=None, data_type='string'):
    """Get enhanced setting with type conversion"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT setting_value, data_type FROM attendance_settings
        WHERE setting_name = ?
        ''', (setting_name,))

        result = cursor.fetchone()
        conn.close()

        if result:
            value, stored_type = result
            actual_type = stored_type or data_type

            # Type conversion
            if actual_type == 'boolean':
                return value.lower() in ('true', '1', 'yes', 'on')
            elif actual_type == 'integer':
                return int(value)
            elif actual_type == 'float':
                return float(value)
            else:
                return value

        return default_value

    except Exception as e:
        print(f"Error retrieving enhanced setting: {e}")
        return default_value


def set_enhanced_setting(setting_name, setting_value, description=None, category='general', data_type='string'):
    """Set enhanced setting with metadata"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        INSERT OR REPLACE INTO attendance_settings
        (setting_name, setting_value, description, category, data_type, last_modified)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (setting_name, str(setting_value), description, category, data_type,
              datetime.datetime.now().isoformat()))

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(f"Error setting enhanced setting: {e}")
        return False
