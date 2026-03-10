"""CLI handlers for integrations (LMS, calendar, import/export)."""

import datetime
import pandas as pd
from education_system.university_system.infrastructure.database.db import get_connection


def handle_lms_integration():
    """Handle LMS integration"""
    print("\n🔗 LMS INTEGRATION")
    print("This feature would integrate with learning management systems")
    print("like Moodle, Canvas, Blackboard, etc.")
    print("Implementation depends on specific LMS APIs and requirements.")


def handle_calendar_sync():
    """Handle calendar synchronization"""
    print("\n📅 CALENDAR SYNC")
    print("This feature would sync with calendar systems")
    print("like Google Calendar, Outlook, etc.")
    print("Implementation requires calendar API access.")


def handle_import_export():
    """Handle data import/export"""
    print("\n📁 IMPORT/EXPORT DATA")
    print("1. Export Attendance Data")
    print("2. Import Student Data")
    print("3. Backup Database")

    choice = input("Enter your choice (1-3): ")

    if choice == '1':
        print("Exporting attendance data...")

        try:
            conn = get_connection()

            query = '''
            SELECT ar.student_id, s.first_name, s.last_name, ar.module_code,
                   ar.date, ar.status, ar.notes, ar.check_in_method, ar.recorded_at
            FROM attendance_records ar
            JOIN students s ON ar.student_id = s.student_id
            ORDER BY ar.date DESC, ar.student_id
            '''

            df = pd.read_sql_query(query, conn)
            conn.close()

            if not df.empty:
                output_path = f"attendance_export_{datetime.date.today().strftime('%Y%m%d')}.xlsx"
                df.to_excel(output_path, index=False)
                print(f"✅ Attendance data exported to: {output_path}")
            else:
                print("No attendance data to export.")

        except Exception as e:
            print(f"Error exporting data: {e}")


def handle_audit_logs():
    """Handle audit logs viewing"""
    print("\n📋 AUDIT LOGS")
    print("1. View Recent Logs")
    print("2. Search Logs")
    print("3. Export Logs")

    choice = input("Enter your choice (1-3): ")

    if choice == '1':
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT user_id, action, table_name, record_id, timestamp
            FROM attendance_audit_log
            ORDER BY timestamp DESC
            LIMIT 50
            ''')

            logs = cursor.fetchall()
            conn.close()

            if logs:
                print("\n📋 RECENT AUDIT LOGS")
                print("=" * 80)
                print(f"{'User':<15} {'Action':<20} {'Table':<20} {'Record ID':<15} {'Timestamp'}")
                print("-" * 80)

                for log in logs:
                    user_id, action, table_name, record_id, timestamp = log
                    timestamp_display = timestamp.split('T')[0] + ' ' + timestamp.split('T')[1][:8]
                    print(f"{user_id:<15} {action:<20} {table_name:<20} {record_id:<15} {timestamp_display}")
            else:
                print("No audit logs found.")

        except Exception as e:
            print(f"Error retrieving audit logs: {e}")
