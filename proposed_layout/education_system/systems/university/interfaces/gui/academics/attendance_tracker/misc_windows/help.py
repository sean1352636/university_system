import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext
from education_system.systems.university.infrastructure.database.db import sqlite3
import datetime
import json
import threading
from pathlib import Path
import uuid
from PIL import Image, ImageTk
import io
import os
import csv
import re
import shutil
from collections import deque

# Import internationalization support
from education_system.systems.university.infrastructure.i18n import get_text as _, init_i18n
# --- central logger (routes to university_system/logs/app.log) ----------
try:
    from education_system.systems.university.infrastructure.logging.log_config import (
        configure_logging,
    )
    logger = configure_logging(name="attendance_tracker.gui.misc_windows")
except Exception:  # pragma: no cover
    import logging
    logger = logging.getLogger("attendance_tracker.gui.misc_windows")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)
# -------------------------------------------------------------------------

init_i18n()

# Import path constants
from education_system.systems.university.infrastructure.paths import BACKUP_DIR, DEFAULT_DB_PATH, LOG_DIR

# Import authentication system
from education_system.systems.university.infrastructure.auth import UserAuth

# Import main database connection
try:
    from education_system.systems.university.infrastructure.database.db import get_db_connection
    MAIN_DB_AVAILABLE = True
except ImportError:
    logger.exception("misc_windows.py:50 %s", 'except ImportError')
    MAIN_DB_AVAILABLE = False

# Import all original functions and classes
try:
    from education_system.systems.university.domain.academics.services.attendance.attendance_tracker import (
        AttendancePredictiveAnalytics, BackupRecoverySystem,
        EnhancedNotificationSystem, FaceRecognitionSystem, GeofencingSystem,
        QRAttendanceSystem, create_missing_tables, display_attendance_menu,
        generate_executive_summary_report, get_enhanced_setting,
        get_module_attendance, get_modules, get_student_attendance,
        init_enhanced_attendance_db, record_attendance, set_enhanced_setting
    )
    ORIGINAL_FUNCTIONS_AVAILABLE = True
except ImportError:
    logger.exception("misc_windows.py:64 %s", 'except ImportError')
    print("Warning: Original attendance_tracker.py not found. Some functions may not work.")
    ORIGINAL_FUNCTIONS_AVAILABLE = False

# Import attendance notification service
try:
    from education_system.systems.university.domain.academics.services.attendance.attendance_notifications import (
        AttendanceNotificationService, check_and_notify_low_attendance
    )
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = True
except ImportError:
    logger.exception("misc_windows.py:74 %s", 'except ImportError')
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = False

# Feature flags
GEOFENCING_SUPPORT = True
FACE_RECOGNITION_SUPPORT = True

class HelpWindow:
    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.user_manual"))
        self.window.geometry("600x500")
        self.window.transient(parent)

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="📖 User Manual", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        # Help content
        help_frame = ttk.Frame(self.window)
        help_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        help_text = tk.Text(help_frame, wrap=tk.WORD)
        help_scrollbar = ttk.Scrollbar(help_frame, orient=tk.VERTICAL, command=help_text.yview)
        help_text.configure(yscrollcommand=help_scrollbar.set)

        help_content = """
ENHANCED ATTENDANCE TRACKING SYSTEM - USER MANUAL
=================================================

OVERVIEW
--------
This GUI application provides a comprehensive attendance management solution with advanced features including QR codes, geofencing, face recognition, and predictive analytics.

MAIN FEATURES
-------------

📊 DASHBOARD
- View real-time attendance statistics
- Monitor attendance trends and status distribution
- See recent activity and alerts

📋 ATTENDANCE MANAGEMENT
- Manual attendance entry
- QR code-based check-in
- Geofencing attendance
- Face recognition check-in
- Edit attendance records

👥 STUDENT MANAGEMENT
- Add, edit, and delete students
- Search and filter students
- Import student data from files

📈 REPORTS
- Generate various attendance reports
- Export data in multiple formats
- Custom report builder
- Executive summaries

🔮 ANALYTICS
- Predictive risk assessment
- Gamification features
- Attendance trends analysis
- Student leaderboards

⚙️ SETTINGS
- Configure system preferences
- Manage notification settings
- Toggle features on/off
- Set attendance thresholds

🔧 ADMIN TOOLS
- Database backup and restore
- System information
- Audit logs
- Data import/export

GETTING STARTED
---------------

1. INITIAL SETUP
   - Launch the application
   - The system will initialize the database
   - Configure basic settings in the Settings tab

2. ADD STUDENTS
   - Go to Students tab
   - Click "Add Student" button
   - Fill in student information
   - Save the student record

3. CREATE MODULES
   - Students are automatically enrolled in modules
   - Module codes are derived from attendance records

4. TAKE ATTENDANCE
   - Go to Attendance tab
   - Select module and date
   - Choose attendance method:
     * Manual: Enter status for each student
     * QR Code: Generate QR for students to scan
     * Geofencing: Set location-based attendance
     * Face Recognition: Use facial recognition

ADVANCED FEATURES
-----------------

QR CODE ATTENDANCE
- Generate unique QR codes for each session
- Students scan QR codes to check in
- Automatic expiry and security features

GEOFENCING
- Set geographic boundaries for attendance
- Students automatically check in when in range
- Configurable radius and location settings

FACE RECOGNITION
- Enroll student faces for recognition
- Automated attendance through facial recognition
- High accuracy and security

GAMIFICATION
- Points and levels for students
- Achievement badges and streaks
- Leaderboards and competitions

PREDICTIVE ANALYTICS
- AI-powered risk assessment
- Early warning for at-risk students
- Batch analysis and recommendations

TROUBLESHOOTING
---------------

Common Issues:
1. Database errors: Check file permissions
2. QR code not displaying: Install PIL/Pillow
3. Face recognition not working: Install face_recognition library
4. Geofencing not available: Install geopy library

For technical support, check the system information in the Admin tab.

KEYBOARD SHORTCUTS
------------------
- Ctrl+R: Refresh data
- F5: Refresh current view
- Escape: Close current dialog
- Enter: Confirm action

TIPS AND BEST PRACTICES
-----------------------
1. Regular backups: Use Admin > Backup Database
2. Monitor attendance trends in Dashboard
3. Set appropriate thresholds in Settings
4. Use reports for analysis and decision making
5. Enable notifications for early intervention

VERSION INFORMATION
-------------------
Enhanced Attendance System v2.0
Built with Python and tkinter
Backwards compatible with CLI version

For more information, visit the system documentation or contact your administrator.
        """

        help_text.insert(tk.END, help_content)
        help_text.config(state=tk.DISABLED)

        help_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        help_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Close button
        ttk.Button(self.window, text=_("common.close"), command=self.window.destroy, style='Primary.TButton').pack(pady=10)

# Aliases for backward compatibility
