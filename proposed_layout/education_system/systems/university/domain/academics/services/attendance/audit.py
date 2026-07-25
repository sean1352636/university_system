"""Audit logging for the attendance tracking system."""

import json
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.domain.academics.services.attendance.settings import get_enhanced_setting


def log_audit_event(user_id, action, table_name, record_id, old_values=None, new_values=None):
    """Log audit event"""
    try:
        if get_enhanced_setting('enable_audit_log', True, 'boolean'):
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO attendance_audit_log
            (user_id, action, table_name, record_id, old_values, new_values, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, action, table_name, str(record_id),
                  json.dumps(old_values) if old_values else None,
                  json.dumps(new_values) if new_values else None,
                  '127.0.0.1'))  # Would get actual IP in web context

            conn.commit()
            conn.close()

    except Exception as e:
        print(f"Error logging audit event: {e}")
