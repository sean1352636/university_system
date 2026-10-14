from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta

from education_system.systems.university.plugins.campus_commerce.domain.services.restaurant.operations import restaurant_context as ctx
from education_system.systems.university.plugins.campus_commerce.domain.services.restaurant.operations.restaurant_context import (
    backup_before_operation,
    get_db_connection,
)
from education_system.systems.university.plugins.campus_commerce.domain.services.restaurant.operations.audit import log_audit_action
from education_system.systems.university.infrastructure.i18n import get_text as _t

def manage_notifications():
    """Manage system notifications"""
    try:
        print("\n" + "="*50)
        print(_t("commerce.restaurant.notifications.menu_title", default="===== NOTIFICATIONS ====="))
        print("="*50)

        print("\n" + _t("commerce.restaurant.notifications.options", default="Options:"))
        print(_t("commerce.restaurant.notifications.option_view", default="1. View"))
        print(_t("commerce.restaurant.notifications.option_create", default="2. Create"))
        print(_t("commerce.restaurant.notifications.option_mark_read", default="3. Mark Read"))
        print(_t("commerce.restaurant.notifications.option_clear_old", default="4. Clear Old"))
        print(_t("commerce.restaurant.notifications.option_return", default="5. Return"))

        choice = input(_t("commerce.restaurant.notifications.choose_option", default="Enter your choice: "))

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
            print(_t("common.invalid_choice"))

    except Exception as e:
        logging.error(f"Error in manage_notifications: {e}")
        print(f"An error occurred: {e}")

def view_notifications():
    """View system notifications"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\n" + _t("commerce.restaurant.notifications.filter_options", default="Options"))
        print(_t("commerce.restaurant.notifications.filter_all", default="All"))
        print(_t("commerce.restaurant.notifications.filter_unread", default="Unread"))
        print(_t("commerce.restaurant.notifications.filter_by_priority", default="By Priority"))
        print(_t("commerce.restaurant.notifications.filter_by_category", default="By Category"))

        filter_choice = input(_t("commerce.restaurant.notifications.choose_filter", default="Choose Filter"))

        if filter_choice == '1':
            cursor.execute('SELECT * FROM restaurant_notifications ORDER BY created_date DESC LIMIT 50')
        elif filter_choice == '2':
            cursor.execute('SELECT * FROM restaurant_notifications WHERE read_date IS NULL ORDER BY created_date DESC')
        elif filter_choice == '3':
            priority = input(_t("commerce.restaurant.notifications.enter_priority", default="Enter Priority: "))
            cursor.execute('SELECT * FROM restaurant_notifications WHERE priority = ? ORDER BY created_date DESC',
                          (priority,))
        elif filter_choice == '4':
            category = input(_t("commerce.restaurant.notifications.enter_category", default="Enter Category: "))
            cursor.execute('SELECT * FROM restaurant_notifications WHERE category = ? ORDER BY created_date DESC',
                          (category,))

        notifications = cursor.fetchall()

        if not notifications:
            print(_t("commerce.restaurant.notifications.no_notifications_found", default="No Notifications Found."))
            conn.close()
            return

        print("\n" + "="*120)
        print(_t("commerce.restaurant.notifications.notifications_header", default="Notifications:"))
        print("="*120)
        print(f"{_t('common.id'):<15} {_t('common.date'):<12} {_t('common.priority'):<8} {_t('common.title'):<25} {_t('common.category'):<12} {_t('common.read'):<6}")
        print("-"*120)

        for notif in notifications:
            created_date = notif[4][:10] if notif[4] else 'N/A'
            title = notif[3][:24] if len(notif[3]) > 24 else notif[3]
            is_read = "Yes" if notif[5] else "No"

            print(f"{notif[0]:<15} {created_date:<12} {notif[6]:<8} {title:<25} {notif[7] or 'N/A':<12} {is_read:<6}")

        print("="*120)
        print(_t("commerce.restaurant.notifications.total_notifications", count=len(notifications), default="Total Notifications {count}"))

        conn.close()

    except Exception as e:
        logging.error(f"Error in view_notifications: {e}")
        print(_t("common.error_occurred", error=str(e)))

def create_notification():
    """Create new notification"""

    if not ctx.auth or not ctx.auth.current_user:
        print(_t("common.login_required"))
        return

    try:
        backup_before_operation('create_notification')

        print("\n" + "="*50)
        print(_t("commerce.restaurant.notifications.create_notification_title", default="===== CREATE NOTIFICATION ====="))
        print("="*50)

        # Generate notification ID
        notification_id = f"NOT{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"

        user_id = input(_t("commerce.restaurant.notifications.enter_user_id_or_all", default="Enter User ID Or All: ")).strip()
        if user_id.lower() == 'all':
            user_id = None

        print("\n" + _t("commerce.restaurant.notifications.notification_types", default="Notification Types"))
        print(_t("commerce.restaurant.notifications.type_system", default="Type System"))
        print(_t("commerce.restaurant.notifications.type_alert", default="Type Alert"))
        print(_t("commerce.restaurant.notifications.type_warning", default="Type Warning"))
        print(_t("commerce.restaurant.notifications.type_info", default="Type Info"))
        print(_t("commerce.restaurant.notifications.type_maintenance", default="Type Maintenance"))

        type_choice = input(_t("commerce.restaurant.notifications.choose_type", default="Choose Type"))
        types = {
            '1': 'System',
            '2': 'Alert',
            '3': 'Warning',
            '4': 'Info',
            '5': 'Maintenance'
        }
        notif_type = types.get(type_choice, 'Info')

        title = input(_t("commerce.restaurant.notifications.enter_title", default="===== ENTER =====")).strip()
        if not title:
            print(_t("commerce.restaurant.notifications.title_required", default="Title Required"))
            return

        message = input(_t("commerce.restaurant.notifications.enter_message", default="Enter: ")).strip()
        if not message:
            print(_t("commerce.restaurant.notifications.message_required", default="Message Required"))
            return

        print("\n" + _t("commerce.restaurant.notifications.priority_levels", default="Priority Levels"))
        print(_t("commerce.restaurant.notifications.priority_low", default="Priority Low"))
        print(_t("commerce.restaurant.notifications.priority_normal", default="Priority Normal"))
        print(_t("commerce.restaurant.notifications.priority_high", default="Priority High"))

        priority_choice = input(_t("commerce.restaurant.notifications.choose_priority", default="Choose Priority"))
        priorities = {'1': 'Low', '2': 'Normal', '3': 'High'}
        priority = priorities.get(priority_choice, 'Normal')

        category = input(_t("commerce.restaurant.notifications.enter_category_optional", default="Enter Category Optional: ")).strip()

        action_required = input(_t("commerce.restaurant.notifications.action_required_prompt", default="Action Required: ")).lower() == 'y'

        conn = get_db_connection()
        cursor = conn.cursor()

        # Create notification
        # ``message`` is collected above and was previously dropped: the
        # positional form supplied nine values against a ten-column table, so
        # the timestamp landed in ``message`` and the insert failed outright.
        cursor.execute('''
            INSERT INTO restaurant_notifications (
                notification_id, user_id, type, title, message,
                created_date, read_date, priority, category, action_required
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            notification_id, user_id, notif_type, title, message,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            None, priority, category, int(action_required)
        ))

        conn.commit()
        conn.close()

        print("\n✅ " + _t("commerce.restaurant.notifications.notification_created", default="Notification created."))
        print(_t("commerce.restaurant.notifications.notification_id", id=notification_id, default="Notification ID {id}"))
        print(_t("commerce.restaurant.notifications.title_label", title=title, default="Title: {title}"))
        print(_t("commerce.restaurant.notifications.priority_label", priority=priority, default="Priority: {priority}"))
        target = _t("commerce.restaurant.notifications.all_users", default="All Users") if not user_id else _t("commerce.restaurant.notifications.user_target", user_id=user_id, default="User Target {user_id}")
        print(_t("commerce.restaurant.notifications.target_label", target=target, default="Target: {target}"))

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
        print(_t("common.error_occurred", error=str(e)))

def mark_notification_read():
    """Mark notification as read - FIXED"""

    if not ctx.auth or not ctx.auth.current_user:
        print(_t("common.login_required"))
        return

    try:
        notification_id = input(_t("commerce.restaurant.notifications.enter_notification_id", default="Enter Notification ID: "))

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM restaurant_notifications WHERE notification_id = ?', (notification_id,))
        notification = cursor.fetchone()

        if not notification:
            print(_t("commerce.restaurant.notifications.notification_not_found", default="Notification Not Found"))
            conn.close()
            return

        if notification[5]:  # Already read
            print(_t("commerce.restaurant.notifications.already_marked_read", default="Already Marked Read"))
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

        print("✅ " + _t("commerce.restaurant.notifications.marked_as_read", id=notification_id, default="Notification {id} marked as read."))

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
        print(_t("common.error_occurred", error=str(e)))

def clear_old_notifications():
    """Clear old notifications - FIXED"""

    if not ctx.auth or not ctx.auth.current_user:
        print(_t("common.login_required"))
        return

    if not ctx.auth.check_permission('admin'):
        print(_t("common.permission_denied"))
        return

    try:
        backup_before_operation('clear_old_notifications')

        print("\n" + _t("commerce.restaurant.notifications.clear_options", default="Clear Options"))
        print(_t("commerce.restaurant.notifications.clear_read_30_days", default="Clear Read 30 Days"))
        print(_t("commerce.restaurant.notifications.clear_all_90_days", default="Clear All 90 Days"))
        print(_t("commerce.restaurant.notifications.clear_by_priority", default="Clear By Priority"))
        print(_t("commerce.restaurant.notifications.clear_cancel", default="Clear Cancel"))

        choice = input(_t("commerce.restaurant.notifications.choose_option", default="Enter your choice: "))

        conn = get_db_connection()
        cursor = conn.cursor()

        if choice == '1':
            cutoff_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            cursor.execute('''
                DELETE FROM restaurant_notifications
                WHERE read_date IS NOT NULL AND created_date < ?
            ''', (cutoff_date,))
            cleared_count = cursor.rowcount
            print(_t("commerce.restaurant.notifications.cleared_read_30_days", count=cleared_count, default="Cleared Read 30 Days {count}"))

        elif choice == '2':
            cutoff_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
            cursor.execute('DELETE FROM restaurant_notifications WHERE created_date < ?', (cutoff_date,))
            cleared_count = cursor.rowcount
            print(_t("commerce.restaurant.notifications.cleared_all_90_days", count=cleared_count, default="Cleared All 90 Days {count}"))

        elif choice == '3':
            priority = input(_t("commerce.restaurant.notifications.enter_priority_to_clear", default="Enter Priority To Clear: "))
            cursor.execute('DELETE FROM restaurant_notifications WHERE priority = ? AND read_date IS NOT NULL',
                          (priority,))
            cleared_count = cursor.rowcount
            print(_t("commerce.restaurant.notifications.cleared_by_priority", count=cleared_count, priority=priority, default="Cleared By Priority {count} {priority}"))

        elif choice == '4':
            print(_t("common.operation_cancelled", default="Operation Cancelled"))
            conn.close()
            return
        else:
            print(_t("common.invalid_choice"))
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
        print(_t("common.error_occurred", error=str(e)))
