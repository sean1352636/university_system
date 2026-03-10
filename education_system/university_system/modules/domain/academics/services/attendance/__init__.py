"""
Advanced Attendance System Service Module

This module provides comprehensive attendance tracking with QR codes,
geolocation verification, facial recognition, and automated notifications.

NOTE: This module now redirects to the comprehensive attendance_tracker module.
"""

# Import from the comprehensive attendance tracking system
from education_system.university_system.modules.domain.academics.services.attendance.attendance_tracker import (
    QRAttendanceSystem,
    GeofencingSystem,
    FaceRecognitionSystem,
    AttendancePredictiveAnalytics,
    EnhancedNotificationSystem,
    AttendanceDashboard,
    AttendanceAPI,
    BackupRecoverySystem,
    display_attendance_menu as display_advanced_attendance_menu,
    launch_advanced_attendance_gui,
    init_enhanced_attendance_db,
    create_missing_tables,
    get_modules,
    get_student_attendance,
    get_module_attendance,
    record_attendance,
)

__all__ = [
    # Main classes
    'QRAttendanceSystem',
    'GeofencingSystem',
    'FaceRecognitionSystem',
    'AttendancePredictiveAnalytics',
    'EnhancedNotificationSystem',
    'AttendanceDashboard',
    'AttendanceAPI',
    'BackupRecoverySystem',
    # Functions
    'display_advanced_attendance_menu',
    'launch_advanced_attendance_gui',
    'init_enhanced_attendance_db',
    'create_missing_tables',
    'get_modules',
    'get_student_attendance',
    'get_module_attendance',
    'record_attendance',
]
