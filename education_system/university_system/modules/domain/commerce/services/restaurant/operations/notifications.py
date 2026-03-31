from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta

from education_system.university_system.modules.domain.commerce.services.restaurant.operations import restaurant_context as ctx
from education_system.university_system.modules.domain.commerce.services.restaurant.operations.restaurant_context import (
    backup_before_operation,
    get_db_connection,
)
from education_system.university_system.modules.domain.commerce.services.restaurant.operations.audit import log_audit_action
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

def manage_notifications():
    """Manage system notifications"""
    try:
        print("\n" + "="*50)
        print(_t("commerce.restaurant.notifications.menu_title"))
        print("="*50)

        print("\n" + _t("commerce.restaurant.notifications.options"))
        print(_t("commerce.restaurant.notifications.option_view"))
        print(_t("commerce.restaurant.notifications.option_create"))
        print(_t("commerce.restaurant.notifications.option_mark_read"))
        print(_t("commerce.restaurant.notifications.option_clear_old"))
        print(_t("commerce.restaurant.notifications.option_return"))

        choice = input(_t("commerce.restaurant.notifications.choose_option"))

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

        print("\n" + _t("commerce.restaurant.notifications.filter_options"))
        print(_t("commerce.restaurant.notifications.filter_all"))
        print(_t("commerce.restaurant.notifications.filter_unread"))
        print(_t("commerce.restaurant.notifications.filter_by_priority"))
        print(_t("commerce.restaurant.notifications.filter_by_category"))

        filter_choice = input(_t("commerce.restaurant.notifications.choose_filter"))

        if filter_choice == '1':
            cursor.execute('SELECT * FROM restaurant_notifications ORDER BY created_date DESC LIMIT 50')
        elif filter_choice == '2':
            cursor.execute('SELECT * FROM restaurant_notifications WHERE read_date IS NULL ORDER BY created_date DESC')
        elif filter_choice == '3':
            priority = input(_t("commerce.restaurant.notifications.enter_priority"))
            cursor.execute('SELECT * FROM restaurant_notifications WHERE priority = ? ORDER BY created_date DESC',
                          (priority,))
        elif filter_choice == '4':
            category = input(_t("commerce.restaurant.notifications.enter_category"))
            cursor.execute('SELECT * FROM restaurant_notifications WHERE category = ? ORDER BY created_date DESC',
                          (category,))

        notifications = cursor.fetchall()

        if not notifications:
            print(_t("commerce.restaurant.notifications.no_notifications_found"))
            conn.close()
            return

        print(f"\n" + "="*120)
        print(_t("commerce.restaurant.notifications.notifications_header"))
        print("="*120)
        print(f"{_t('common.id'):<15} {_t('common.date'):<12} {_t('common.priority'):<8} {_t('common.title'):<25} {_t('common.category'):<12} {_t('common.read'):<6}")
        print("-"*120)

        for notif in notifications:
            created_date = notif[4][:10] if notif[4] else 'N/A'
            title = notif[3][:24] if len(notif[3]) > 24 else notif[3]
            is_read = "Yes" if notif[5] else "No"

            print(f"{notif[0]:<15} {created_date:<12} {notif[6]:<8} {title:<25} {notif[7] or 'N/A':<12} {is_read:<6}")

        print("="*120)
        print(_t("commerce.restaurant.notifications.total_notifications", count=len(notifications)))

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
        print(_t("commerce.restaurant.notifications.create_notification_title"))
        print("="*50)

        # Generate notification ID
        notification_id = f"NOT{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"

        user_id = input(_t("commerce.restaurant.notifications.enter_user_id_or_all")).strip()
        if user_id.lower() == 'all':
            user_id = None

        print("\n" + _t("commerce.restaurant.notifications.notification_types"))
        print(_t("commerce.restaurant.notifications.type_system"))
        print(_t("commerce.restaurant.notifications.type_alert"))
        print(_t("commerce.restaurant.notifications.type_warning"))
        print(_t("commerce.restaurant.notifications.type_info"))
        print(_t("commerce.restaurant.notifications.type_maintenance"))

        type_choice = input(_t("commerce.restaurant.notifications.choose_type"))
        types = {
            '1': 'System',
            '2': 'Alert',
            '3': 'Warning',
            '4': 'Info',
            '5': 'Maintenance'
        }
        notif_type = types.get(type_choice, 'Info')

        title = input(_t("commerce.restaurant.notifications.enter_title")).strip()
        if not title:
            print(_t("commerce.restaurant.notifications.title_required"))
            return

        message = input(_t("commerce.restaurant.notifications.enter_message")).strip()
        if not message:
            print(_t("commerce.restaurant.notifications.message_required"))
            return

        print("\n" + _t("commerce.restaurant.notifications.priority_levels"))
        print(_t("commerce.restaurant.notifications.priority_low"))
        print(_t("commerce.restaurant.notifications.priority_normal"))
        print(_t("commerce.restaurant.notifications.priority_high"))

        priority_choice = input(_t("commerce.restaurant.notifications.choose_priority"))
        priorities = {'1': 'Low', '2': 'Normal', '3': 'High'}
        priority = priorities.get(priority_choice, 'Normal')

        category = input(_t("commerce.restaurant.notifications.enter_category_optional")).strip()

        action_required = input(_t("commerce.restaurant.notifications.action_required_prompt")).lower() == 'y'

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

        print(f"\n✅ " + _t("commerce.restaurant.notifications.notification_created"))
        print(_t("commerce.restaurant.notifications.notification_id", id=notification_id))
        print(_t("commerce.restaurant.notifications.title_label", title=title))
        print(_t("commerce.restaurant.notifications.priority_label", priority=priority))
        target = _t("commerce.restaurant.notifications.all_users") if not user_id else _t("commerce.restaurant.notifications.user_target", user_id=user_id)
        print(_t("commerce.restaurant.notifications.target_label", target=target))

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
        notification_id = input(_t("commerce.restaurant.notifications.enter_notification_id"))

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM restaurant_notifications WHERE notification_id = ?', (notification_id,))
        notification = cursor.fetchone()

        if not notification:
            print(_t("commerce.restaurant.notifications.notification_not_found"))
            conn.close()
            return

        if notification[5]:  # Already read
            print(_t("commerce.restaurant.notifications.already_marked_read"))
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

        print("✅ " + _t("commerce.restaurant.notifications.marked_as_read", id=notification_id))

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

        print("\n" + _t("commerce.restaurant.notifications.clear_options"))
        print(_t("commerce.restaurant.notifications.clear_read_30_days"))
        print(_t("commerce.restaurant.notifications.clear_all_90_days"))
        print(_t("commerce.restaurant.notifications.clear_by_priority"))
        print(_t("commerce.restaurant.notifications.clear_cancel"))

        choice = input(_t("commerce.restaurant.notifications.choose_option"))

        conn = get_db_connection()
        cursor = conn.cursor()

        if choice == '1':
            cutoff_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            cursor.execute('''
                DELETE FROM restaurant_notifications
                WHERE read_date IS NOT NULL AND created_date < ?
            ''', (cutoff_date,))
            cleared_count = cursor.rowcount
            print(_t("commerce.restaurant.notifications.cleared_read_30_days", count=cleared_count))

        elif choice == '2':
            cutoff_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
            cursor.execute('DELETE FROM restaurant_notifications WHERE created_date < ?', (cutoff_date,))
            cleared_count = cursor.rowcount
            print(_t("commerce.restaurant.notifications.cleared_all_90_days", count=cleared_count))

        elif choice == '3':
            priority = input(_t("commerce.restaurant.notifications.enter_priority_to_clear"))
            cursor.execute('DELETE FROM restaurant_notifications WHERE priority = ? AND read_date IS NOT NULL',
                          (priority,))
            cleared_count = cursor.rowcount
            print(_t("commerce.restaurant.notifications.cleared_by_priority", count=cleared_count, priority=priority))

        elif choice == '4':
            print(_t("common.operation_cancelled"))
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
