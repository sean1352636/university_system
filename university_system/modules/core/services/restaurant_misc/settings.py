from __future__ import annotations

import logging
from datetime import datetime

from . import restaurant_context as ctx
from university_system.modules.core.services.restaurant_misc.restaurant_context import (
    backup_before_operation,
    database_optimization,
    get_db_connection,
    manage_notifications,
    system_backup,
    system_maintenance,
    user_management,
    view_audit_logs,
)
from university_system.modules.core.services.restaurant_misc.audit import log_audit_action

def display_system_settings():
    """System settings menu with full functionality"""
    
    while True:
        print("\n" + "="*50)
        print("SYSTEM SETTINGS")
        print("="*50)

        print("\nOptions:")
        print("1. View system settings")
        print("2. Update settings")
        print("3. User management")
        print("4. System maintenance")
        print("5. Audit logs")
        print("6. Notifications")
        print("7. System backup")
        print("8. Database optimization")
        print("9. Return to main menu")

        choice = input("Choose an option (1-9): ")

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
            print("Invalid choice. Please try again.")

def view_system_settings():
    """View current system settings"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM restaurant_system_settings ORDER BY category, setting_name')
        settings = cursor.fetchall()

        if not settings:
            print("No system settings found.")
            conn.close()
            return

        print(f"\n" + "="*100)
        print("SYSTEM SETTINGS")
        print("="*100)
        print(f"{'Setting':<25} {'Value':<15} {'Description':<35} {'Category':<12} {'Updated':<12}")
        print("-"*100)

        current_category = None
        for setting in settings:
            if setting[3] != current_category:
                current_category = setting[3]
                print(f"\n[{current_category}]")
                print("-" * 50)

            updated_date = setting[4][:10] if setting[4] else 'N/A'
            description = setting[2][:34] if setting[2] and len(setting[2]) > 34 else (setting[2] or '')

            print(f"{setting[0]:<25} {setting[1]:<15} {description:<35} {setting[3]:<12} {updated_date:<12}")

        print("="*100)

        conn.close()

    except Exception as e:
        logging.error(f"Error in view_system_settings: {e}")
        print(f"An error occurred: {e}")

def update_system_settings():
    """Update system settings"""
    
    if not ctx.auth or not ctx.auth.current_user:
        print("You must be logged in to update system settings.")
        return

    if not ctx.auth.check_permission('admin'):
        print("You don't have permission to update system settings.")
        return

    try:
        backup_before_operation('update_system_settings')

        setting_name = input("Enter setting name to update: ")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM restaurant_system_settings WHERE setting_name = ?', (setting_name,))
        setting = cursor.fetchone()

        if not setting:
            print("Setting not found.")
            conn.close()
            return

        print(f"Current setting:")
        print(f"Name: {setting[0]}")
        print(f"Value: {setting[1]}")
        print(f"Description: {setting[2]}")

        new_value = input("Enter new value: ").strip()

        cursor.execute('''
            UPDATE restaurant_system_settings 
            SET setting_value = ?, last_updated = ?, updated_by = ?
            WHERE setting_name = ?
        ''', (new_value, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ctx.auth.current_user['id'], setting_name))

        conn.commit()
        conn.close()

        print(f"✅ Setting '{setting_name}' updated to '{new_value}'")

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
        print(f"An error occurred: {e}")
