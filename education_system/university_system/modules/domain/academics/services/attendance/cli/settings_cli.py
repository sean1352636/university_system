"""CLI handler for enhanced settings management."""

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.domain.academics.services.attendance.settings import (
    get_enhanced_setting, set_enhanced_setting,
)


def handle_enhanced_settings():
    """Handle enhanced settings management"""
    print("\n⚙️  ENHANCED SETTINGS MANAGEMENT")
    print("1. View All Settings")
    print("2. Update Setting")
    print("3. Feature Toggles")
    print("4. Reset to Defaults")

    choice = input("Enter your choice (1-4): ")

    if choice == '1':
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT setting_name, setting_value, description, category, data_type
            FROM attendance_settings
            ORDER BY category, setting_name
            ''')

            settings = cursor.fetchall()
            conn.close()

            if settings:
                current_category = None
                for setting_name, setting_value, description, category, data_type in settings:
                    if category != current_category:
                        print(f"\n📂 {category.upper()} SETTINGS:")
                        print("-" * 50)
                        current_category = category

                    print(f"{setting_name}: {setting_value} ({data_type})")
                    if description:
                        print(f"  {description}")
                    print()
            else:
                print("No settings found.")

        except Exception as e:
            print(f"Error retrieving settings: {e}")

    elif choice == '2':
        setting_name = input("Enter setting name: ")
        current_value = get_enhanced_setting(setting_name)

        if current_value is not None:
            print(f"Current value: {current_value}")
            new_value = input("Enter new value: ")

            if set_enhanced_setting(setting_name, new_value):
                print("✅ Setting updated successfully!")
            else:
                print("❌ Failed to update setting.")
        else:
            print("Setting not found.")

    elif choice == '3':
        print("\n🔧 FEATURE TOGGLES")

        features = [
            ('enable_qr_checkin', 'QR Code Check-in'),
            ('enable_geofencing', 'Geofencing'),
            ('enable_face_recognition', 'Face Recognition'),
            ('enable_gamification', 'Gamification'),
            ('enable_sms_notifications', 'SMS Notifications'),
            ('enable_parent_portal', 'Parent Portal'),
            ('enable_predictive_analytics', 'Predictive Analytics'),
            ('enable_audit_log', 'Audit Logging'),
            ('auto_backup_enabled', 'Automatic Backups')
        ]

        for setting_name, feature_name in features:
            current_value = get_enhanced_setting(setting_name, False, 'boolean')
            status = "✅ ON" if current_value else "❌ OFF"
            print(f"{feature_name}: {status}")

        print("\nEnter feature name to toggle (or 'back' to return):")
        feature_input = input().strip()

        if feature_input != 'back':
            for setting_name, feature_name in features:
                if feature_name.lower() == feature_input.lower():
                    current_value = get_enhanced_setting(setting_name, False, 'boolean')
                    new_value = not current_value

                    if set_enhanced_setting(setting_name, new_value, data_type='boolean'):
                        status = "enabled" if new_value else "disabled"
                        print(f"✅ {feature_name} {status}!")
                    else:
                        print("❌ Failed to update feature setting.")
                    break
            else:
                print("Feature not found.")
