from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta

from . import restaurant_context as ctx
from university_system.modules.core.services.restaurant_misc.restaurant_context import (
    backup_before_operation,
    get_db_connection,
)
from university_system.modules.core.services.restaurant_misc.audit import log_audit_action

def manage_notifications():
    """Manage system notifications"""
    try:
        print("\n" + "="*50)
        print("NOTIFICATION MANAGEMENT")
        print("="*50)

        print("\nOptions:")
        print("1. View notifications")
        print("2. Create notification")
        print("3. Mark as read")
        print("4. Clear old notifications")
        print("5. Return to system settings")

        choice = input("Choose an option (1-5): ")

        if choice == '1':
            view_notifications()
        elif choice == '2':
            create_notification()
        elif choice == '3':
            mark_notification_read()
        elif choice == '4':
            clear_old_notifications()
        elif choice == '5':
            return
        else:
            print("Invalid choice.")

    except Exception as e:
        logging.error(f"Error in manage_notifications: {e}")
        print(f"An error occurred: {e}")

def view_notifications():
    """View system notifications"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\nFilter options:")
        print("1. All notifications")
        print("2. Unread notifications")
        print("3. By priority")
        print("4. By category")

        filter_choice = input("Choose filter (1-4): ")

        if filter_choice == '1':
            cursor.execute('SELECT * FROM restaurant_notifications ORDER BY created_date DESC LIMIT 50')
        elif filter_choice == '2':
            cursor.execute('SELECT * FROM restaurant_notifications WHERE read_date IS NULL ORDER BY created_date DESC')
        elif filter_choice == '3':
            priority = input("Enter priority (High/Normal/Low): ")
            cursor.execute('SELECT * FROM restaurant_notifications WHERE priority = ? ORDER BY created_date DESC', 
                          (priority,))
        elif filter_choice == '4':
            category = input("Enter category: ")
            cursor.execute('SELECT * FROM restaurant_notifications WHERE category = ? ORDER BY created_date DESC', 
                          (category,))

        notifications = cursor.fetchall()

        if not notifications:
            print("No notifications found.")
            conn.close()
            return

        print(f"\n" + "="*120)
        print("NOTIFICATIONS")
        print("="*120)
        print(f"{'ID':<15} {'Date':<12} {'Priority':<8} {'Title':<25} {'Category':<12} {'Read':<6}")
        print("-"*120)

        for notif in notifications:
            created_date = notif[4][:10] if notif[4] else 'N/A'
            title = notif[3][:24] if len(notif[3]) > 24 else notif[3]
            is_read = "Yes" if notif[5] else "No"

            print(f"{notif[0]:<15} {created_date:<12} {notif[6]:<8} {title:<25} {notif[7] or 'N/A':<12} {is_read:<6}")

        print("="*120)
        print(f"Total notifications: {len(notifications)}")

        conn.close()

    except Exception as e:
        logging.error(f"Error in view_notifications: {e}")
        print(f"An error occurred: {e}")

def create_notification():
    """Create new notification"""
    
    if not ctx.auth or not ctx.auth.current_user:
        print("You must be logged in to create notifications.")
        return

    try:
        backup_before_operation('create_notification')

        print("\n" + "="*50)
        print("CREATE NOTIFICATION")
        print("="*50)

        # Generate notification ID
        notification_id = f"NOT{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"

        user_id = input("Enter user ID (or 'all' for system-wide): ").strip()
        if user_id.lower() == 'all':
            user_id = None

        print("\nNotification types:")
        print("1. System")
        print("2. Alert")
        print("3. Warning")
        print("4. Info")
        print("5. Maintenance")

        type_choice = input("Choose type (1-5): ")
        types = {
            '1': 'System',
            '2': 'Alert',
            '3': 'Warning',
            '4': 'Info',
            '5': 'Maintenance'
        }
        notif_type = types.get(type_choice, 'Info')

        title = input("Enter notification title: ").strip()
        if not title:
            print("Title is required.")
            return

        message = input("Enter notification message: ").strip()
        if not message:
            print("Message is required.")
            return

        print("\nPriority levels:")
        print("1. Low")
        print("2. Normal")
        print("3. High")

        priority_choice = input("Choose priority (1-3): ")
        priorities = {'1': 'Low', '2': 'Normal', '3': 'High'}
        priority = priorities.get(priority_choice, 'Normal')

        category = input("Enter category (optional): ").strip()

        action_required = input("Does this require action? (y/n): ").lower() == 'y'

        conn = get_db_connection()
        cursor = conn.cursor()

        # Create notification
        cursor.execute('''
            INSERT INTO restaurant_notifications VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            notification_id, user_id, notif_type, title, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            None, priority, category, int(action_required)
        ))

        conn.commit()
        conn.close()

        print(f"\n✅ Notification created successfully!")
        print(f"Notification ID: {notification_id}")
        print(f"Title: {title}")
        print(f"Priority: {priority}")
        print(f"Target: {'All users' if not user_id else f'User {user_id}'}")

        # Log audit action
        log_audit_action(
            ctx.auth.current_user['id'],
            'CREATE_NOTIFICATION',
            'restaurant_notifications',
            notification_id,
            None,
            {'title': title, 'priority': priority, 'user_id': user_id}
        )

    except Exception as e:
        logging.error(f"Error in create_notification: {e}")
        print(f"An error occurred: {e}")

def mark_notification_read():
    """Mark notification as read - FIXED"""
    
    if not ctx.auth or not ctx.auth.current_user:
        print("You must be logged in to mark notifications as read.")
        return

    try:
        notification_id = input("Enter notification ID: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM restaurant_notifications WHERE notification_id = ?', (notification_id,))
        notification = cursor.fetchone()

        if not notification:
            print("Notification not found.")
            conn.close()
            return

        if notification[5]:  # Already read
            print("Notification is already marked as read.")
            conn.close()
            return

        # Mark as read
        cursor.execute('''
            UPDATE restaurant_notifications 
            SET read_date = ?
            WHERE notification_id = ?
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), notification_id))

        conn.commit()
        conn.close()

        print(f"✅ Notification {notification_id} marked as read.")

        # Log audit action
        log_audit_action(
            ctx.auth.current_user['id'],
            'MARK_NOTIFICATION_READ',
            'restaurant_notifications',
            notification_id,
            None,
            {'marked_read': True}
        )

    except Exception as e:
        logging.error(f"Error in mark_notification_read: {e}")
        print(f"An error occurred: {e}")

def clear_old_notifications():
    """Clear old notifications - FIXED"""
    
    if not ctx.auth or not ctx.auth.current_user:
        print("You must be logged in to clear notifications.")
        return

    if not ctx.auth.check_permission('admin'):
        print("You don't have permission to clear notifications.")
        return

    try:
        backup_before_operation('clear_old_notifications')

        print("\nClear options:")
        print("1. Clear read notifications older than 30 days")
        print("2. Clear all notifications older than 90 days")
        print("3. Clear notifications by priority")
        print("4. Cancel")

        choice = input("Choose option (1-4): ")

        conn = get_db_connection()
        cursor = conn.cursor()

        if choice == '1':
            cutoff_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            cursor.execute('''
                DELETE FROM restaurant_notifications 
                WHERE read_date IS NOT NULL AND created_date < ?
            ''', (cutoff_date,))
            cleared_count = cursor.rowcount
            print(f"Cleared {cleared_count} read notifications older than 30 days.")

        elif choice == '2':
            cutoff_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
            cursor.execute('DELETE FROM restaurant_notifications WHERE created_date < ?', (cutoff_date,))
            cleared_count = cursor.rowcount
            print(f"Cleared {cleared_count} notifications older than 90 days.")

        elif choice == '3':
            priority = input("Enter priority to clear (High/Normal/Low): ")
            cursor.execute('DELETE FROM restaurant_notifications WHERE priority = ? AND read_date IS NOT NULL', 
                          (priority,))
            cleared_count = cursor.rowcount
            print(f"Cleared {cleared_count} read {priority} priority notifications.")

        elif choice == '4':
            print("Operation cancelled.")
            conn.close()
            return
        else:
            print("Invalid choice.")
            conn.close()
            return

        conn.commit()
        conn.close()

        # Log audit action
        log_audit_action(
            ctx.auth.current_user['id'],
            'CLEAR_OLD_NOTIFICATIONS',
            'restaurant_notifications',
            None,
            None,
            {'cleared_count': cleared_count, 'method': choice}
        )

    except Exception as e:
        logging.error(f"Error in clear_old_notifications: {e}")
        print(f"An error occurred: {e}")
