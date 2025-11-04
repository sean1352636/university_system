from __future__ import annotations

import json
import logging
import random
from datetime import datetime

from university_system.modules.core.services.restaurant_misc.restaurant_context import get_db_connection

def log_audit_action(user_id, action, table_name=None, record_id=None, old_values=None, new_values=None):
    """Log user actions for audit trail"""
    try:
        conn = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor()

        audit_id = f"AUDIT{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            INSERT INTO restaurant_audit_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            audit_id, user_id, action, table_name, record_id,
            json.dumps(old_values) if old_values else None,
            json.dumps(new_values) if new_values else None,
            timestamp, None, None
        ))

        conn.commit()
        conn.close()

    except Exception as e:
        logging.error(f"Error logging audit action: {e}")

def view_user_activity_logs():
    """View user activity logs"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\nFilter options:")
        print("1. All recent activity (last 100)")
        print("2. By user")
        print("3. By action type")
        print("4. Today's activity")

        filter_choice = input("Choose filter (1-4): ")

        if filter_choice == '1':
            cursor.execute('SELECT * FROM restaurant_audit_logs ORDER BY timestamp DESC LIMIT 100')
        elif filter_choice == '2':
            user_id = input("Enter user ID: ")
            cursor.execute('SELECT * FROM restaurant_audit_logs WHERE user_id = ? ORDER BY timestamp DESC', (user_id,))
        elif filter_choice == '3':
            action = input("Enter action type: ")
            cursor.execute('SELECT * FROM restaurant_audit_logs WHERE action = ? ORDER BY timestamp DESC', (action,))
        elif filter_choice == '4':
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute('SELECT * FROM restaurant_audit_logs WHERE DATE(timestamp) = ? ORDER BY timestamp DESC', (today,))

        logs = cursor.fetchall()

        if not logs:
            print("No activity logs found.")
            conn.close()
            return

        print(f"\n" + "="*120)
        print("USER ACTIVITY LOGS")
        print("="*120)
        print(f"{'Timestamp':<20} {'User ID':<10} {'Action':<20} {'Table':<15} {'Record ID':<12}")
        print("-"*120)

        for log in logs:
            timestamp = log[7][:19] if log[7] else 'N/A'
            table_name = log[2][:14] if log[2] else 'N/A'
            record_id = log[3][:11] if log[3] else 'N/A'

            print(f"{timestamp:<20} {log[1]:<10} {log[1]:<20} {table_name:<15} {record_id:<12}")

        print("="*120)
        print(f"Total logs: {len(logs)}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in view_user_activity_logs: {e}")
        print(f"An error occurred: {e}")

def view_audit_logs():
    """View system audit logs"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\nFilter options:")
        print("1. Recent logs (last 50)")
        print("2. By user")
        print("3. By action")
        print("4. By table")
        print("5. Today's logs")
        print("6. By date range")

        filter_choice = input("Choose filter (1-6): ")

        if filter_choice == '1':
            cursor.execute('SELECT * FROM restaurant_audit_logs ORDER BY timestamp DESC LIMIT 50')
        elif filter_choice == '2':
            user_id = input("Enter user ID: ")
            cursor.execute('SELECT * FROM restaurant_audit_logs WHERE user_id = ? ORDER BY timestamp DESC', 
                          (user_id,))
        elif filter_choice == '3':
            action = input("Enter action: ")
            cursor.execute('SELECT * FROM restaurant_audit_logs WHERE action = ? ORDER BY timestamp DESC', 
                          (action,))
        elif filter_choice == '4':
            table_name = input("Enter table name: ")
            cursor.execute('SELECT * FROM restaurant_audit_logs WHERE table_name = ? ORDER BY timestamp DESC', 
                          (table_name,))
        elif filter_choice == '5':
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute('SELECT * FROM restaurant_audit_logs WHERE DATE(timestamp) = ? ORDER BY timestamp DESC', 
                          (today,))
        elif filter_choice == '6':
            start_date = input("Enter start date (YYYY-MM-DD): ")
            end_date = input("Enter end date (YYYY-MM-DD): ")
            cursor.execute('''
                SELECT * FROM restaurant_audit_logs 
                WHERE DATE(timestamp) BETWEEN ? AND ? 
                ORDER BY timestamp DESC
            ''', (start_date, end_date))

        logs = cursor.fetchall()

        if not logs:
            print("No audit logs found.")
            conn.close()
            return

        print(f"\n" + "="*120)
        print("AUDIT LOGS")
        print("="*120)
        print(f"{'Timestamp':<20} {'User':<10} {'Action':<20} {'Table':<15} {'Record':<12} {'IP':<15}")
        print("-"*120)

        for log in logs:
            timestamp = log[7][:19] if log[7] else 'N/A'
            table_name = log[2][:14] if log[2] else 'N/A'
            record_id = log[3][:11] if log[3] else 'N/A'
            ip_address = log[8][:14] if log[8] else 'N/A'

            print(f"{timestamp:<20} {log[1]:<10} {log[1]:<20} {table_name:<15} {record_id:<12} {ip_address:<15}")

        print("="*120)
        print(f"Total logs: {len(logs)}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in view_audit_logs: {e}")
        print(f"An error occurred: {e}")
