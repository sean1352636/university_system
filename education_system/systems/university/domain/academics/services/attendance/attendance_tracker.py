"""
Enhanced Attendance Tracking System - Backward Compatibility Module

This module has been split into smaller, focused modules for maintainability.
All public symbols are re-exported here so existing imports continue to work.

Submodules:
    db              - Database schema initialization
    settings        - Settings management (get_setting, get_enhanced_setting, set_enhanced_setting)
    records         - Core CRUD (get_modules, get_attendance_records, record_attendance, ...)
    audit           - Audit logging
    gamification    - Points, streaks, badges
    qr_system       - QR code attendance (QRAttendanceSystem)
    geofencing      - Geofencing attendance (GeofencingSystem)
    face_recognition_system - Face recognition (FaceRecognitionSystem)
    predictive_analytics    - ML risk prediction (AttendancePredictiveAnalytics)
    notifications   - Email/SMS alerts (EnhancedNotificationSystem)
    dashboard       - Plotly Dash dashboard (AttendanceDashboard)
    api             - Flask REST API (AttendanceAPI)
    reporting       - PDF/CSV report generation
    backup          - Backup & recovery (BackupRecoverySystem)
    cli/            - Interactive menu handlers
"""

# --- Database ---
from education_system.systems.university.domain.academics.services.attendance.db import (
    init_enhanced_attendance_db,
    create_missing_tables,
)

# --- Settings ---
from education_system.systems.university.domain.academics.services.attendance.settings import (
    get_setting,
    get_enhanced_setting,
    set_enhanced_setting,
)

# --- Records (core CRUD) ---
from education_system.systems.university.domain.academics.services.attendance.records import (
    get_modules,
    get_attendance_records,
    get_student_attendance,
    get_module_attendance,
    record_attendance,
)

# --- Audit ---
from education_system.systems.university.domain.academics.services.attendance.audit import (
    log_audit_event,
)

# --- Gamification ---
from education_system.systems.university.domain.academics.services.attendance.gamification import (
    update_gamification_points,
)

# --- QR Code System ---
from education_system.systems.university.domain.academics.services.attendance.qr_system import (
    QRAttendanceSystem,
)

# --- Geofencing ---
from education_system.systems.university.domain.academics.services.attendance.geofencing import (
    GeofencingSystem,
    GEOFENCING_SUPPORT,
)

# --- Face Recognition ---
from education_system.systems.university.domain.academics.services.attendance.face_recognition_system import (
    FaceRecognitionSystem,
    FACE_RECOGNITION_SUPPORT,
)

# --- Predictive Analytics ---
from education_system.systems.university.domain.academics.services.attendance.predictive_analytics import (
    AttendancePredictiveAnalytics,
)

# --- Notifications ---
from education_system.systems.university.domain.academics.services.attendance.notifications import (
    EnhancedNotificationSystem,
)

# --- Dashboard ---
from education_system.systems.university.domain.academics.services.attendance.dashboard import (
    AttendanceDashboard,
)

# --- API ---
from education_system.systems.university.domain.academics.services.attendance.api import (
    AttendanceAPI,
)

# --- Reporting ---
from education_system.systems.university.domain.academics.services.attendance.reporting import (
    generate_executive_summary_report,
    generate_student_attendance_report,
    generate_module_attendance_report,
)

# --- Backup ---
from education_system.systems.university.domain.academics.services.attendance.backup import (
    BackupRecoverySystem,
)

# --- CLI (menu + all handlers) ---
from education_system.systems.university.interfaces.cli.academics.services.attendance.menu import (
    display_attendance_menu,
)
from education_system.systems.university.interfaces.cli.academics.services.attendance.qr_cli import handle_qr_system
from education_system.systems.university.interfaces.cli.academics.services.attendance.gamification_cli import (
    handle_gamification_portal, handle_leaderboards, handle_achievements,
)
from education_system.systems.university.interfaces.cli.academics.services.attendance.analytics_cli import handle_predictive_analytics
from education_system.systems.university.interfaces.cli.academics.services.attendance.settings_cli import handle_enhanced_settings
from education_system.systems.university.interfaces.cli.academics.services.attendance.backup_cli import handle_backup_recovery
from education_system.systems.university.interfaces.cli.academics.services.attendance.api_cli import handle_api_management
from education_system.systems.university.interfaces.cli.academics.services.attendance.records_cli import (
    take_attendance, handle_view_records, handle_student_reports, handle_module_reports,
)
from education_system.systems.university.interfaces.cli.academics.services.attendance.notifications_cli import (
    handle_alerts_manager, handle_parent_notifications, handle_notification_settings,
)
from education_system.systems.university.interfaces.cli.academics.services.attendance.geofencing_cli import handle_geofencing_system
from education_system.systems.university.interfaces.cli.academics.services.attendance.face_recognition_cli import handle_face_recognition_system
from education_system.systems.university.interfaces.cli.academics.services.attendance.integrations_cli import (
    handle_lms_integration, handle_calendar_sync, handle_import_export, handle_audit_logs,
)


# GUI Launcher using factory pattern
try:
    from education_system.systems.university.services.feature_gui_factory import create_gui_launcher

    launch_advanced_attendance_gui = create_gui_launcher(
        title="Advanced Attendance System",
        description="""Advanced attendance tracking with QR codes, geolocation, facial recognition, and analytics.

Features:
• QR code check-in
• Geolocation verification
• Facial recognition
• Predictive analytics
• Automated notifications
• Gamification system
• Real-time dashboard
• Attendance reports
• Backup & recovery
• Parent notifications""",
        cli_instruction="Use CLI: Advanced Attendance System"
    )
except ImportError:
    # Fallback if factory not available
    def launch_advanced_attendance_gui(root, auth):
        from tkinter import messagebox
        messagebox.showinfo("Attendance System", "Please use the CLI: Advanced Attendance System")


# Export public API
__all__ = [
    # Classes
    'QRAttendanceSystem',
    'GeofencingSystem',
    'FaceRecognitionSystem',
    'AttendancePredictiveAnalytics',
    'EnhancedNotificationSystem',
    'AttendanceDashboard',
    'AttendanceAPI',
    'BackupRecoverySystem',
    # Functions
    'init_enhanced_attendance_db',
    'create_missing_tables',
    'display_attendance_menu',
    'launch_advanced_attendance_gui',
    'get_modules',
    'get_student_attendance',
    'get_module_attendance',
    'record_attendance',
    'get_enhanced_setting',
    'set_enhanced_setting',
    'generate_executive_summary_report',
]


# Main function to run the enhanced attendance system
if __name__ == "__main__":
    print("🎓 ENHANCED ATTENDANCE TRACKING SYSTEM")
    print("=" * 50)
    display_attendance_menu()
