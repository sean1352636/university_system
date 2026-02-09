from __future__ import annotations

import json
import logging
import random
from datetime import datetime

from university_system.modules.domain.commerce.services.restaurant.operations.restaurant_context import get_db_connection
from university_system.modules.shared.utils.i18n import get_text

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

        print("\n" + get_text("restaurant.audit.filter_options"))
        print(get_text("restaurant.audit.option_all_recent"))
        print(get_text("restaurant.audit.option_by_user"))
        print(get_text("restaurant.audit.option_by_action_type"))
        print(get_text("restaurant.audit.option_today"))

        filter_choice = input(get_text("restaurant.audit.choose_filter_1_4"))

        if filter_choice == '1':
            cursor.execute('SELECT * FROM restaurant_audit_logs ORDER BY timestamp DESC LIMIT 100')
        elif filter_choice == '2':
            user_id = input(get_text("restaurant.audit.enter_user_id"))
            cursor.execute('SELECT * FROM restaurant_audit_logs WHERE user_id = ? ORDER BY timestamp DESC', (user_id,))
        elif filter_choice == '3':
            action = input(get_text("restaurant.audit.enter_action_type"))
            cursor.execute('SELECT * FROM restaurant_audit_logs WHERE action = ? ORDER BY timestamp DESC', (action,))
        elif filter_choice == '4':
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute('SELECT * FROM restaurant_audit_logs WHERE DATE(timestamp) = ? ORDER BY timestamp DESC', (today,))

        logs = cursor.fetchall()

        if not logs:
            print(get_text("restaurant.audit.no_activity_logs"))
            conn.close()
            return

        print(f"\n" + "="*120)
        print(get_text("restaurant.audit.user_activity_logs_title"))
        print("="*120)
        print(f"{get_text('restaurant.audit.header_timestamp'):<20} {get_text('restaurant.audit.header_user_id'):<10} {get_text('restaurant.audit.header_action'):<20} {get_text('restaurant.audit.header_table'):<15} {get_text('restaurant.audit.header_record_id'):<12}")
        print("-"*120)

        for log in logs:
            timestamp = log[7][:19] if log[7] else get_text("common.na")
            table_name = log[2][:14] if log[2] else get_text("common.na")
            record_id = log[3][:11] if log[3] else get_text("common.na")

            print(f"{timestamp:<20} {log[1]:<10} {log[1]:<20} {table_name:<15} {record_id:<12}")

        print("="*120)
        print(get_text("restaurant.audit.total_logs", count=len(logs)))

        conn.close()

    except Exception as e:
        logging.error(f"Error in view_user_activity_logs: {e}")
        print(get_text("restaurant.audit.error_occurred", error=e))

def view_audit_logs():
    """View system audit logs"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\n" + get_text("restaurant.audit.filter_options_system"))
        print(get_text("restaurant.audit.option_recent_50"))
        print(get_text("restaurant.audit.option_by_user"))
        print(get_text("restaurant.audit.option_by_action"))
        print(get_text("restaurant.audit.option_by_table"))
        print(get_text("restaurant.audit.option_today_logs"))
        print(get_text("restaurant.audit.option_by_date_range"))

        filter_choice = input(get_text("restaurant.audit.choose_filter_1_6"))

        if filter_choice == '1':
            cursor.execute('SELECT * FROM restaurant_audit_logs ORDER BY timestamp DESC LIMIT 50')
        elif filter_choice == '2':
            user_id = input(get_text("restaurant.audit.enter_user_id"))
            cursor.execute('SELECT * FROM restaurant_audit_logs WHERE user_id = ? ORDER BY timestamp DESC',
                          (user_id,))
        elif filter_choice == '3':
            action = input(get_text("restaurant.audit.enter_action"))
            cursor.execute('SELECT * FROM restaurant_audit_logs WHERE action = ? ORDER BY timestamp DESC',
                          (action,))
        elif filter_choice == '4':
            table_name = input(get_text("restaurant.audit.enter_table_name"))
            cursor.execute('SELECT * FROM restaurant_audit_logs WHERE table_name = ? ORDER BY timestamp DESC',
                          (table_name,))
        elif filter_choice == '5':
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute('SELECT * FROM restaurant_audit_logs WHERE DATE(timestamp) = ? ORDER BY timestamp DESC',
                          (today,))
        elif filter_choice == '6':
            start_date = input(get_text("restaurant.audit.enter_start_date"))
            end_date = input(get_text("restaurant.audit.enter_end_date"))
            cursor.execute('''
                SELECT * FROM restaurant_audit_logs
                WHERE DATE(timestamp) BETWEEN ? AND ?
                ORDER BY timestamp DESC
            ''', (start_date, end_date))

        logs = cursor.fetchall()

        if not logs:
            print(get_text("restaurant.audit.no_audit_logs"))
            conn.close()
            return

        print(f"\n" + "="*120)
        print(get_text("restaurant.audit.audit_logs_title"))
        print("="*120)
        print(f"{get_text('restaurant.audit.header_timestamp'):<20} {get_text('restaurant.audit.header_user'):<10} {get_text('restaurant.audit.header_action'):<20} {get_text('restaurant.audit.header_table'):<15} {get_text('restaurant.audit.header_record'):<12} {get_text('restaurant.audit.header_ip'):<15}")
        print("-"*120)

        for log in logs:
            timestamp = log[7][:19] if log[7] else get_text("common.na")
            table_name = log[2][:14] if log[2] else get_text("common.na")
            record_id = log[3][:11] if log[3] else get_text("common.na")
            ip_address = log[8][:14] if log[8] else get_text("common.na")

            print(f"{timestamp:<20} {log[1]:<10} {log[1]:<20} {table_name:<15} {record_id:<12} {ip_address:<15}")

        print("="*120)
        print(get_text("restaurant.audit.total_logs", count=len(logs)))

        conn.close()

    except Exception as e:
        logging.error(f"Error in view_audit_logs: {e}")
        print(get_text("restaurant.audit.error_occurred", error=e))
