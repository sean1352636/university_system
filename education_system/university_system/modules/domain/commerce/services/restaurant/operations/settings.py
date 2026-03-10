from __future__ import annotations

import logging
from datetime import datetime

from . import restaurant_context as ctx
from education_system.university_system.modules.domain.commerce.services.restaurant.operations.restaurant_context import (
    backup_before_operation,
    database_optimization,
    get_db_connection,
    manage_notifications,
    system_backup,
    system_maintenance,
    user_management,
    view_audit_logs,
)
from education_system.university_system.modules.domain.commerce.services.restaurant.operations.audit import log_audit_action
from education_system.university_system.modules.shared.utils.i18n import get_text

def display_system_settings():
    """System settings menu with full functionality"""

    while True:
        print("\n" + "="*50)
        print(get_text("restaurant.settings.title"))
        print("="*50)

        print("\n" + get_text("restaurant.settings.options_title"))
        print(get_text("restaurant.settings.option_view"))
        print(get_text("restaurant.settings.option_update"))
        print(get_text("restaurant.settings.option_user_management"))
        print(get_text("restaurant.settings.option_maintenance"))
        print(get_text("restaurant.settings.option_audit_logs"))
        print(get_text("restaurant.settings.option_notifications"))
        print(get_text("restaurant.settings.option_backup"))
        print(get_text("restaurant.settings.option_db_optimization"))
        print(get_text("restaurant.settings.option_return"))

        choice = input(get_text("restaurant.settings.choose_option"))

        if choice == '1':
            view_system_settings()
        elif choice == '2':
            update_system_settings()
        elif choice == '3':
            user_management()
        elif choice == '4':
            system_maintenance()
        elif choice == '5':
            view_audit_logs()
        elif choice == '6':
            manage_notifications()
        elif choice == '7':
            system_backup()
        elif choice == '8':
            database_optimization()
        elif choice == '9':
            return
        else:
            print(get_text("restaurant.settings.invalid_choice"))

def view_system_settings():
    """View current system settings"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM restaurant_system_settings ORDER BY category, setting_name')
        settings = cursor.fetchall()

        if not settings:
            print(get_text("restaurant.settings.no_settings_found"))
            conn.close()
            return

        print(f"\n" + "="*100)
        print(get_text("restaurant.settings.title"))
        print("="*100)
        print(f"{get_text('restaurant.settings.header_setting'):<25} {get_text('restaurant.settings.header_value'):<15} {get_text('restaurant.settings.header_description'):<35} {get_text('restaurant.settings.header_category'):<12} {get_text('restaurant.settings.header_updated'):<12}")
        print("-"*100)

        current_category = None
        for setting in settings:
            if setting[3] != current_category:
                current_category = setting[3]
                print(f"\n[{current_category}]")
                print("-" * 50)

            updated_date = setting[4][:10] if setting[4] else get_text("common.na")

            description = setting[2][:34] if setting[2] and len(setting[2]) > 34 else (setting[2] or '')

            print(f"{setting[0]:<25} {setting[1]:<15} {description:<35} {setting[3]:<12} {updated_date:<12}")

        print("="*100)

        conn.close()

    except Exception as e:
        logging.error(f"Error in view_system_settings: {e}")
        print(get_text("restaurant.settings.error_occurred", error=e))

def update_system_settings():
    """Update system settings"""

    if not ctx.auth or not ctx.auth.current_user:
        print(get_text("restaurant.settings.login_required"))
        return

    if not ctx.auth.check_permission('admin'):
        print(get_text("restaurant.settings.permission_denied"))
        return

    try:
        backup_before_operation('update_system_settings')

        setting_name = input(get_text("restaurant.settings.enter_setting_name"))

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM restaurant_system_settings WHERE setting_name = ?', (setting_name,))
        setting = cursor.fetchone()

        if not setting:
            print(get_text("restaurant.settings.setting_not_found"))
            conn.close()
            return

        print(get_text("restaurant.settings.current_setting"))
        print(get_text("restaurant.settings.name_label", name=setting[0]))
        print(get_text("restaurant.settings.value_label", value=setting[1]))
        print(get_text("restaurant.settings.description_label", description=setting[2]))

        new_value = input(get_text("restaurant.settings.enter_new_value")).strip()

        cursor.execute('''
            UPDATE restaurant_system_settings
            SET setting_value = ?, last_updated = ?, updated_by = ?
            WHERE setting_name = ?
        ''', (new_value, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ctx.auth.current_user['id'], setting_name))

        conn.commit()
        conn.close()

        print(get_text("restaurant.settings.setting_updated", setting_name=setting_name, new_value=new_value))

        # Log audit action
        log_audit_action(
            ctx.auth.current_user['id'],
            'UPDATE_SYSTEM_SETTING',
            'restaurant_system_settings',
            setting_name,
            {'old_value': setting[1]},
            {'new_value': new_value}
        )

    except Exception as e:
        logging.error(f"Error in update_system_settings: {e}")
        print(get_text("restaurant.settings.error_occurred", error=e))
