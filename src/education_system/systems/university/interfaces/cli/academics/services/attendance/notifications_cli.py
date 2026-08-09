"""CLI handlers for alerts, parent notifications, and notification settings."""

from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.domain.academics.services.attendance.records import (
    get_modules, get_student_attendance,
)
from education_system.systems.university.domain.academics.services.attendance.settings import (
    get_enhanced_setting, set_enhanced_setting,
)
from education_system.systems.university.domain.academics.services.attendance.notifications import EnhancedNotificationSystem


def handle_alerts_manager(notification_system):
    """Handle attendance alerts management"""
    print("\n🔔 ATTENDANCE ALERTS MANAGER")
    print("1. View Pending Alerts")
    print("2. Create Custom Alert")
    print("3. Acknowledge Alerts")
    print("4. Alert Statistics")

    choice = input("Enter your choice (1-4): ")

    if choice == '1':
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT aa.alert_id, aa.student_id, s.first_name, s.last_name,
                   aa.module_code, aa.alert_type, aa.severity, aa.message, aa.created_at
            FROM attendance_alerts aa
            JOIN students s ON aa.student_id = s.student_id
            WHERE aa.status = 'pending'
            ORDER BY aa.created_at DESC
            LIMIT 20
            ''')

            alerts = cursor.fetchall()
            conn.close()

            if alerts:
                print("\n🚨 PENDING ALERTS")
                print("=" * 100)
                print(f"{'Alert ID':<8} {'Student':<20} {'Module':<10} {'Type':<15} {'Severity':<10} {'Created'}")
                print("-" * 100)

                for alert in alerts:
                    alert_id, student_id, first_name, last_name, module_code, alert_type, severity, message, created_at = alert
                    student_name = f"{first_name} {last_name} ({student_id})"
                    created_date = created_at.split('T')[0] if 'T' in created_at else created_at[:10]

                    print(f"{alert_id[:8]:<8} {student_name:<20} {module_code:<10} {alert_type:<15} {severity:<10} {created_date}")

                # Show alert details
                alert_id = input("\nEnter alert ID to view details (or press Enter to return): ")
                if alert_id:
                    for alert in alerts:
                        if alert[0].startswith(alert_id):
                            print("\n📋 ALERT DETAILS:")
                            print(f"Student: {alert[2]} {alert[3]} ({alert[1]})")
                            print(f"Module: {alert[4]}")
                            print(f"Type: {alert[5]}")
                            print(f"Severity: {alert[6]}")
                            print(f"Message: {alert[7]}")
                            print(f"Created: {alert[8]}")
                            break
                    else:
                        print("Alert not found.")
            else:
                print("No pending alerts.")

        except Exception as e:
            print(f"Error retrieving alerts: {e}")

    elif choice == '2':
        student_id = input("Enter student ID: ")

        modules = get_modules()
        if not modules:
            print("No modules found.")
            return

        print("\nAvailable Modules:")
        for i, (code, name) in enumerate(modules, 1):
            print(f"{i}. {code} - {name}")

        try:
            module_idx = int(input("Select module number: ")) - 1
            if 0 <= module_idx < len(modules):
                module_code = modules[module_idx][0]

                alert_type = input("Enter alert type (attendance_warning/custom): ") or "custom"
                severity = input("Enter severity (low/medium/high/critical): ") or "medium"
                message = input("Enter alert message: ")

                success = notification_system.create_attendance_alert(
                    student_id, module_code, alert_type, severity, message
                )

                if success:
                    print("✅ Alert created successfully!")
                else:
                    print("❌ Failed to create alert.")
        except (ValueError, IndexError):
            print("Invalid selection.")


def handle_parent_notifications(notification_system):
    """Handle parent notification system"""
    print("\n👨‍👩‍👧‍👦 PARENT NOTIFICATION SYSTEM")

    if get_enhanced_setting('enable_parent_portal', False, 'boolean'):
        print("1. Send Attendance Summary to Parents")
        print("2. Configure Parent Contacts")
        print("3. View Parent Notification History")

        choice = input("Enter your choice (1-3): ")

        if choice == '1':
            student_id = input("Enter student ID (or 'all' for all students): ")

            if student_id.lower() == 'all':
                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    cursor.execute('SELECT student_id FROM students WHERE parent_email IS NOT NULL')
                    students = cursor.fetchall()
                    conn.close()

                    success_count = 0
                    for student_id, in students:
                        # Generate attendance summary message
                        stats = get_student_attendance(student_id)

                        if stats:
                            overall_rate = sum(data['percentage'] for data in stats.values()) / len(stats)
                            message = f"Weekly attendance summary for your child (Student ID: {student_id}). "
                            message += f"Overall attendance rate: {overall_rate:.1f}%. "

                            if overall_rate < 80:
                                message += "Please ensure regular attendance for academic success."
                            else:
                                message += "Great attendance! Keep up the good work."

                            if notification_system.send_parent_notifications(student_id, message):
                                success_count += 1

                    print(f"✅ Sent notifications to {success_count} parents.")

                except Exception as e:
                    print(f"Error sending batch notifications: {e}")
            else:
                # Single student
                stats = get_student_attendance(student_id)

                if stats:
                    overall_rate = sum(data['percentage'] for data in stats.values()) / len(stats)
                    message = f"Attendance update for your child (Student ID: {student_id}). "
                    message += f"Current attendance rate: {overall_rate:.1f}%. "

                    if overall_rate < 80:
                        message += "Please ensure regular attendance for academic success."
                    else:
                        message += "Great attendance! Keep up the good work."

                    if notification_system.send_parent_notifications(student_id, message):
                        print("✅ Parent notification sent successfully!")
                    else:
                        print("❌ Failed to send parent notification.")
                else:
                    print("No attendance data found for student.")
    else:
        print("❌ Parent portal is disabled. Enable it in Enhanced Settings to use this feature.")


def handle_notification_settings():
    """Handle notification settings"""
    print("\n📨 NOTIFICATION SETTINGS")
    print("1. Email Settings")
    print("2. SMS Settings")
    print("3. Alert Thresholds")
    print("4. Test Notifications")

    choice = input("Enter your choice (1-4): ")

    if choice == '1':
        print("\n📧 EMAIL SETTINGS")

        auto_email = get_enhanced_setting('auto_email_warnings', False, 'boolean')
        print(f"Automatic Email Warnings: {'Enabled' if auto_email else 'Disabled'}")

        toggle = input("Toggle automatic email warnings? (y/n): ")
        if toggle.lower() == 'y':
            new_value = not auto_email
            if set_enhanced_setting('auto_email_warnings', new_value, data_type='boolean'):
                status = "enabled" if new_value else "disabled"
                print(f"✅ Automatic email warnings {status}!")

    elif choice == '2':
        print("\n📱 SMS SETTINGS")

        sms_enabled = get_enhanced_setting('enable_sms_notifications', False, 'boolean')
        sms_api_key = get_enhanced_setting('sms_api_key', '', 'string')

        print(f"SMS Notifications: {'Enabled' if sms_enabled else 'Disabled'}")
        print(f"API Key: {'Configured' if sms_api_key else 'Not configured'}")

        print("\n1. Toggle SMS notifications")
        print("2. Configure SMS API key")

        sms_choice = input("Enter choice (1-2): ")

        if sms_choice == '1':
            new_value = not sms_enabled
            if set_enhanced_setting('enable_sms_notifications', new_value, data_type='boolean'):
                status = "enabled" if new_value else "disabled"
                print(f"✅ SMS notifications {status}!")

        elif sms_choice == '2':
            new_api_key = input("Enter SMS API key: ")
            if set_enhanced_setting('sms_api_key', new_api_key, data_type='string'):
                print("✅ SMS API key updated!")

    elif choice == '3':
        print("\n⚠️  ALERT THRESHOLDS")

        warning_threshold = get_enhanced_setting('attendance_threshold_warning', 80, 'integer')
        critical_threshold = get_enhanced_setting('attendance_threshold_critical', 70, 'integer')
        consecutive_warning = get_enhanced_setting('consecutive_absences_warning', 2, 'integer')
        consecutive_critical = get_enhanced_setting('consecutive_absences_critical', 3, 'integer')

        print(f"Attendance Warning Threshold: {warning_threshold}%")
        print(f"Attendance Critical Threshold: {critical_threshold}%")
        print(f"Consecutive Absences Warning: {consecutive_warning}")
        print(f"Consecutive Absences Critical: {consecutive_critical}")

        print("\n1. Update attendance thresholds")
        print("2. Update consecutive absence thresholds")

        threshold_choice = input("Enter choice (1-2): ")

        if threshold_choice == '1':
            try:
                new_warning = int(input(f"Enter new warning threshold (current: {warning_threshold}%): "))
                new_critical = int(input(f"Enter new critical threshold (current: {critical_threshold}%): "))

                if 0 <= new_critical <= new_warning <= 100:
                    if set_enhanced_setting('attendance_threshold_warning', new_warning, data_type='integer'):
                        if set_enhanced_setting('attendance_threshold_critical', new_critical, data_type='integer'):
                            print("✅ Attendance thresholds updated successfully!")
                        else:
                            print("❌ Failed to update critical threshold.")
                    else:
                        print("❌ Failed to update warning threshold.")
                else:
                    print("❌ Invalid thresholds. Critical must be ≤ Warning, and both must be 0-100%.")
            except ValueError:
                print("❌ Invalid threshold values.")

        elif threshold_choice == '2':
            try:
                new_warning = int(input(f"Enter new consecutive absences warning (current: {consecutive_warning}): "))
                new_critical = int(input(f"Enter new consecutive absences critical (current: {consecutive_critical}): "))

                if 0 <= new_warning <= new_critical <= 10:
                    if set_enhanced_setting('consecutive_absences_warning', new_warning, data_type='integer'):
                        if set_enhanced_setting('consecutive_absences_critical', new_critical, data_type='integer'):
                            print("✅ Consecutive absence thresholds updated successfully!")
                        else:
                            print("❌ Failed to update critical threshold.")
                    else:
                        print("❌ Failed to update warning threshold.")
                else:
                    print("❌ Invalid thresholds. Warning must be ≤ Critical, and both must be 0-10.")
            except ValueError:
                print("❌ Invalid threshold values.")

    elif choice == '4':
        print("\n🧪 TEST NOTIFICATIONS")

        test_email = input("Enter test email address: ")
        if test_email:
            notification_system = EnhancedNotificationSystem()

            success = notification_system.send_email_notification(
                test_email,
                "Test Notification",
                "This is a test notification from the Enhanced Attendance System."
            )

            if success:
                print("✅ Test email sent successfully!")
            else:
                print("❌ Failed to send test email.")

        test_phone = input("Enter test phone number (optional): ")
        if test_phone:
            if get_enhanced_setting('enable_sms_notifications', False, 'boolean'):
                success = notification_system.send_sms_notification(
                    test_phone,
                    "Test SMS from Enhanced Attendance System."
                )

                if success:
                    print("✅ Test SMS sent successfully!")
                else:
                    print("❌ Failed to send test SMS.")
            else:
                print("❌ SMS notifications are disabled.")
