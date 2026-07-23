"""Main attendance tracking menu dispatcher."""

from education_system.post_18.university_system.core.i18n import get_text
from education_system.post_18.university_system.modules.shared.utils.language_selector import display_language_menu_option
from education_system.post_18.university_system.modules.domain.academics.services.attendance.db import (
    init_enhanced_attendance_db, create_missing_tables,
)
from education_system.post_18.university_system.modules.domain.academics.services.attendance.qr_system import QRAttendanceSystem
from education_system.post_18.university_system.modules.domain.academics.services.attendance.geofencing import GeofencingSystem
from education_system.post_18.university_system.modules.domain.academics.services.attendance.face_recognition_system import FaceRecognitionSystem
from education_system.post_18.university_system.modules.domain.academics.services.attendance.notifications import EnhancedNotificationSystem
from education_system.post_18.university_system.modules.domain.academics.services.attendance.predictive_analytics import AttendancePredictiveAnalytics
from education_system.post_18.university_system.modules.domain.academics.services.attendance.backup import BackupRecoverySystem
from education_system.post_18.university_system.modules.domain.academics.services.attendance.dashboard import AttendanceDashboard
from education_system.post_18.university_system.modules.domain.academics.services.attendance.reporting import generate_executive_summary_report
from education_system.post_18.university_system.modules.domain.academics.services.attendance.cli.qr_cli import handle_qr_system
from education_system.post_18.university_system.modules.domain.academics.services.attendance.cli.geofencing_cli import handle_geofencing_system
from education_system.post_18.university_system.modules.domain.academics.services.attendance.cli.face_recognition_cli import handle_face_recognition_system
from education_system.post_18.university_system.modules.domain.academics.services.attendance.cli.records_cli import (
    take_attendance, handle_view_records, handle_student_reports, handle_module_reports,
)
from education_system.post_18.university_system.modules.domain.academics.services.attendance.cli.analytics_cli import handle_predictive_analytics
from education_system.post_18.university_system.modules.domain.academics.services.attendance.cli.gamification_cli import (
    handle_gamification_portal, handle_leaderboards, handle_achievements,
)
from education_system.post_18.university_system.modules.domain.academics.services.attendance.cli.notifications_cli import (
    handle_alerts_manager, handle_parent_notifications, handle_notification_settings,
)
from education_system.post_18.university_system.modules.domain.academics.services.attendance.cli.settings_cli import handle_enhanced_settings
from education_system.post_18.university_system.modules.domain.academics.services.attendance.cli.backup_cli import handle_backup_recovery
from education_system.post_18.university_system.modules.domain.academics.services.attendance.cli.api_cli import handle_api_management
from education_system.post_18.university_system.modules.domain.academics.services.attendance.cli.integrations_cli import (
    handle_lms_integration, handle_calendar_sync, handle_import_export, handle_audit_logs,
)


def display_attendance_menu():
    """Display the enhanced attendance tracking menu"""
    # Initialize enhanced database
    init_enhanced_attendance_db()

    # Initialize systems
    qr_system = QRAttendanceSystem()
    geo_system = GeofencingSystem()
    face_system = FaceRecognitionSystem()
    notification_system = EnhancedNotificationSystem()
    analytics = AttendancePredictiveAnalytics()
    backup_system = BackupRecoverySystem()

    # Start automatic backups
    backup_system.schedule_automatic_backups()

    while True:
        print("\n" + "="*100)
        print(get_text('attendance.title', default='ENHANCED ATTENDANCE TRACKING SYSTEM'))
        print("="*100)

        print(f"\n📋 {get_text('attendance.sections.management', default='ATTENDANCE MANAGEMENT')}:")
        print(f"{'1.  ' + get_text('attendance.menu.traditional', default='Traditional'):<25} {'2.  ' + get_text('attendance.menu.qr_checkin', default='QR Code Check-in'):<25} {'3.  ' + get_text('attendance.menu.geofencing', default='Geofencing'):<25} {'4.  ' + get_text('attendance.menu.face_recognition', default='Face Recognition'):<25}")
        print(f"{'5.  ' + get_text('attendance.menu.view_records', default='View Records'):<25}")

        print(f"\n📊 {get_text('attendance.sections.analytics', default='ANALYTICS & REPORTING')}:")
        print(f"{'6.  ' + get_text('attendance.menu.student_report', default='Student Report'):<25} {'7.  ' + get_text('attendance.menu.module_report', default='Module Report'):<25} {'8.  ' + get_text('attendance.menu.executive_summary', default='Executive Summary'):<25} {'9.  ' + get_text('attendance.menu.predictive', default='Predictive Analytics'):<25}")
        print(f"{'10. ' + get_text('attendance.menu.dashboard', default='Real-time Dashboard'):<25}")

        print(f"\n🎮 {get_text('attendance.sections.gamification', default='GAMIFICATION & ENGAGEMENT')}:")
        print(f"{'11. ' + get_text('attendance.menu.gamification', default='Gamification Portal'):<25} {'12. ' + get_text('attendance.menu.achievements', default='Achievements'):<25} {'13. ' + get_text('attendance.menu.leaderboards', default='Leaderboards'):<25}")

        print(f"\n🔔 {get_text('attendance.sections.notifications', default='NOTIFICATIONS & ALERTS')}:")
        print(f"{'14. ' + get_text('attendance.menu.alerts', default='Alerts Manager'):<25} {'15. ' + get_text('attendance.menu.parent_notif', default='Parent Notifications'):<25} {'16. ' + get_text('attendance.menu.sms_email', default='SMS/Email Settings'):<25}")

        print(f"\n🔧 {get_text('attendance.sections.system', default='SYSTEM MANAGEMENT')}:")
        print(f"{'17. ' + get_text('attendance.menu.settings', default='Enhanced Settings'):<25} {'18. ' + get_text('attendance.menu.backup', default='Backup & Recovery'):<25} {'19. ' + get_text('attendance.menu.api', default='API Management'):<25} {'20. ' + get_text('attendance.menu.audit', default='Audit Logs'):<25}")

        print(f"\n📱 {get_text('attendance.sections.integrations', default='INTEGRATIONS')}:")
        print(f"{'21. ' + get_text('attendance.menu.lms', default='LMS Integration'):<25} {'22. ' + get_text('attendance.menu.calendar', default='Calendar Sync'):<25} {'23. ' + get_text('attendance.menu.import_export', default='Import/Export Data'):<25}")

        print(f"\n🌐 {get_text('attendance.sections.settings', default='SETTINGS')}:")
        print(f"24. {get_text('attendance.menu.language', default='Language')}")

        print(f"\n🚪 {get_text('attendance.sections.exit', default='EXIT')}:")
        print(f"25. {get_text('attendance.menu.return_main', default='Return to Main Menu')}")

        choice = input(f"\n{get_text('attendance.enter_choice', default='Enter your choice')} (1-25): ")

        if choice == '1':
            take_attendance()

        elif choice == '2':
            handle_qr_system(qr_system)

        elif choice == '3':
            handle_geofencing_system(geo_system)

        elif choice == '4':
            handle_face_recognition_system(face_system)

        elif choice == '5':
            handle_view_records()

        elif choice == '6':
            handle_student_reports()

        elif choice == '7':
            handle_module_reports()

        elif choice == '8':
            create_missing_tables()  # Add this line
            print("\nGenerating Executive Summary Report...")
            date_from = input("Enter start date (YYYY-MM-DD, leave empty for last 30 days): ")
            date_to = input("Enter end date (YYYY-MM-DD, leave empty for today): ")
            output_path = input("Enter output path (leave empty for default): ")

            if not date_from:
                date_from = None
            if not date_to:
                date_to = None
            if not output_path:
                output_path = None

            generate_executive_summary_report(date_from, date_to, output_path)

        elif choice == '9':
            handle_predictive_analytics(analytics)

        elif choice == '10':
            print("\nStarting Real-time Dashboard...")
            dashboard = AttendanceDashboard()
            print("Dashboard will open in your web browser at http://localhost:8050")
            try:
                dashboard.run_dashboard(debug=False)
            except KeyboardInterrupt:
                print("\nDashboard stopped.")

        elif choice == '11':
            handle_gamification_portal()

        elif choice == '12':
            handle_achievements()

        elif choice == '13':
            handle_leaderboards()

        elif choice == '14':
            handle_alerts_manager(notification_system)

        elif choice == '15':
            handle_parent_notifications(notification_system)

        elif choice == '16':
            handle_notification_settings()

        elif choice == '17':
            handle_enhanced_settings()

        elif choice == '18':
            handle_backup_recovery(backup_system)

        elif choice == '19':
            handle_api_management()

        elif choice == '20':
            handle_audit_logs()

        elif choice == '21':
            handle_lms_integration()

        elif choice == '22':
            handle_calendar_sync()

        elif choice == '23':
            handle_import_export()

        elif choice == '24':
            display_language_menu_option()

        elif choice == '25':
            print(get_text('attendance.returning', default='Returning to main menu...'))
            break

        else:
            print(get_text('attendance.invalid_choice', default='Invalid choice. Please try again.'))
