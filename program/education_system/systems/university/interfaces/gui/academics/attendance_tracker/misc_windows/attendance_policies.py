
from education_system.systems.university.infrastructure.i18n import get_text as _t
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
from education_system.paths import (
    UNIVERSITY_BACKUP_DIR,
    UNIVERSITY_DEFAULT_DB_PATH,
    UNIVERSITY_LOG_DIR,
)

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

class AttendancePoliciesWindow:
    """Manage attendance policies and rules"""

    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title(_("attendance.windows.attendance_policies"))
        self.window.geometry("900x750")
        self.window.transient(parent)
        self.window.grab_set()

        # Load current policies
        self.policies = self.load_policies()
        self.create_widgets()

    def load_policies(self):
        """Load current attendance policies from database"""
        policies = {
            'minimum_attendance_percentage': 75,
            'late_arrival_minutes': 15,
            'excused_absence_types': ['Medical', 'Family Emergency', 'University Event', 'Religious Holiday'],
            'allow_retroactive_changes': True,
            'retroactive_days_limit': 7,
            'require_absence_documentation': True,
            'auto_fail_below_threshold': False,
            'auto_fail_threshold': 50,
            'grace_period_weeks': 2,
            'absence_penalty_points': 1,
            'late_penalty_points': 0.5,
            'max_penalty_points': 10,
            'enable_attendance_appeals': True,
            'appeal_deadline_days': 14,
            'require_instructor_approval': True,
            'enable_self_check_in': True,
            'check_in_time_window_minutes': 30,
            'enable_geofencing': True,
            'geofence_radius_meters': 100
        }

        try:
            if MAIN_DB_AVAILABLE:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Try to load policies from database
                cursor.execute("SELECT policy_key, policy_value FROM attendance_policies")
                rows = cursor.fetchall()

                for key, value in rows:
                    if key in policies:
                        # Convert string values to appropriate types
                        if isinstance(policies[key], bool):
                            policies[key] = value.lower() == 'true'
                        elif isinstance(policies[key], int):
                            policies[key] = int(value)
                        elif isinstance(policies[key], float):
                            policies[key] = float(value)
                        elif isinstance(policies[key], list):
                            policies[key] = json.loads(value)
                        else:
                            policies[key] = value

                conn.close()
        except Exception as e:
            logger.exception("misc_windows.py:1884 %s", 'except Exception as e')
            print(f"Error loading attendance policies: {e}")

        return policies

    def create_widgets(self):
        # Title
        title_frame = ttk.Frame(self.window)
        title_frame.pack(fill=tk.X, padx=15, pady=15)

        ttk.Label(title_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.labels.attendance_policies_rules', default="📋 Attendance Policies & Rules"),
                 font=('Arial', 16, 'bold')).pack(side=tk.LEFT)

        # Create notebook for different policy categories
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        # Basic policies tab
        basic_frame = ttk.Frame(notebook)
        notebook.add(basic_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.tabs.basic_rules', default="Basic Rules"))
        self.create_basic_policies_tab(basic_frame)

        # Penalties tab
        penalties_frame = ttk.Frame(notebook)
        notebook.add(penalties_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.tabs.penalties', default="Penalties"))
        self.create_penalties_tab(penalties_frame)

        # Excused absences tab
        excused_frame = ttk.Frame(notebook)
        notebook.add(excused_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.tabs.excused_absences', default="Excused Absences"))
        self.create_excused_absences_tab(excused_frame)

        # Advanced tab
        advanced_frame = ttk.Frame(notebook)
        notebook.add(advanced_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.tabs.advanced', default="Advanced"))
        self.create_advanced_tab(advanced_frame)

        # Action buttons
        button_frame = ttk.Frame(self.window)
        button_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

        ttk.Button(button_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.buttons.save_policies', default="💾 Save Policies"),
                  command=self.save_policies, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(button_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.buttons.reset_to_defaults', default="🔄 Reset to Defaults"),
                  command=self.reset_to_defaults).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(button_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.buttons.export_policies', default="📄 Export Policies"),
                  command=self.export_policies).pack(side=tk.LEFT)

        ttk.Button(button_frame, text=_("common.close"),
                  command=self.window.destroy).pack(side=tk.RIGHT)

    def create_basic_policies_tab(self, parent):
        """Basic attendance policy settings"""

        # Minimum attendance
        attendance_frame = ttk.LabelFrame(parent, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.labels.attendance_requirements', default="Attendance Requirements"), padding=15)
        attendance_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(attendance_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.labels.minimum_attendance_percentage', default="Minimum Attendance Percentage:")).pack(anchor=tk.W, pady=(0, 5))
        self.minimum_attendance_var = tk.IntVar(value=self.policies['minimum_attendance_percentage'])
        min_scale = ttk.Scale(attendance_frame, from_=0, to=100,
                             variable=self.minimum_attendance_var,
                             orient=tk.HORIZONTAL)
        min_scale.pack(fill=tk.X, pady=(0, 5))

        self.min_attendance_label = ttk.Label(attendance_frame,
                                             text=f"{self.policies['minimum_attendance_percentage']}%")
        self.min_attendance_label.pack(anchor=tk.W)

        min_scale.configure(command=lambda v: self.min_attendance_label.config(
            text=f"{int(float(v))}%"))

        # Late arrival
        ttk.Label(attendance_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.labels.late_arrival_grace_period_minutes', default="Late Arrival Grace Period (minutes):")).pack(anchor=tk.W, pady=(10, 5))
        self.late_arrival_var = tk.IntVar(value=self.policies['late_arrival_minutes'])
        ttk.Spinbox(attendance_frame, from_=0, to=60,
                   textvariable=self.late_arrival_var,
                   width=10).pack(anchor=tk.W)

        # Grace period
        ttk.Label(attendance_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.labels.grace_period_at_semester_start_weeks', default="Grace Period at Semester Start (weeks):")).pack(anchor=tk.W, pady=(10, 5))
        self.grace_period_var = tk.IntVar(value=self.policies['grace_period_weeks'])
        ttk.Spinbox(attendance_frame, from_=0, to=8,
                   textvariable=self.grace_period_var,
                   width=10).pack(anchor=tk.W)

        # Retroactive changes
        retro_frame = ttk.LabelFrame(parent, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.labels.record_modifications', default="Record Modifications"), padding=15)
        retro_frame.pack(fill=tk.X, padx=10, pady=10)

        self.allow_retroactive_var = tk.BooleanVar(value=self.policies['allow_retroactive_changes'])
        ttk.Checkbutton(retro_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.buttons.allow_retroactive_attendance_changes', default="Allow Retroactive Attendance Changes"),
                       variable=self.allow_retroactive_var).pack(anchor=tk.W, pady=5)

        ttk.Label(retro_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.labels.retroactive_change_limit_days', default="Retroactive Change Limit (days):")).pack(anchor=tk.W, pady=(5, 5))
        self.retroactive_days_var = tk.IntVar(value=self.policies['retroactive_days_limit'])
        ttk.Spinbox(retro_frame, from_=1, to=30,
                   textvariable=self.retroactive_days_var,
                   width=10).pack(anchor=tk.W)

        self.require_instructor_approval_var = tk.BooleanVar(value=self.policies['require_instructor_approval'])
        ttk.Checkbutton(retro_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.buttons.require_instructor_approval_for_changes', default="Require Instructor Approval for Changes"),
                       variable=self.require_instructor_approval_var).pack(anchor=tk.W, pady=(10, 5))

    def create_penalties_tab(self, parent):
        """Configure penalty system"""

        # Penalty points
        points_frame = ttk.LabelFrame(parent, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.labels.penalty_points_system', default="Penalty Points System"), padding=15)
        points_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(points_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.labels.points_for_absence', default="Points for Absence:")).pack(anchor=tk.W, pady=(0, 5))
        self.absence_penalty_var = tk.DoubleVar(value=self.policies['absence_penalty_points'])
        ttk.Spinbox(points_frame, from_=0, to=10, increment=0.5,
                   textvariable=self.absence_penalty_var,
                   width=10).pack(anchor=tk.W, pady=(0, 10))

        ttk.Label(points_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.labels.points_for_late_arrival', default="Points for Late Arrival:")).pack(anchor=tk.W, pady=(0, 5))
        self.late_penalty_var = tk.DoubleVar(value=self.policies['late_penalty_points'])
        ttk.Spinbox(points_frame, from_=0, to=10, increment=0.5,
                   textvariable=self.late_penalty_var,
                   width=10).pack(anchor=tk.W, pady=(0, 10))

        ttk.Label(points_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.labels.maximum_penalty_points', default="Maximum Penalty Points:")).pack(anchor=tk.W, pady=(0, 5))
        self.max_penalty_var = tk.IntVar(value=self.policies['max_penalty_points'])
        ttk.Spinbox(points_frame, from_=1, to=50,
                   textvariable=self.max_penalty_var,
                   width=10).pack(anchor=tk.W)

        # Auto-fail
        fail_frame = ttk.LabelFrame(parent, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.labels.auto_fail_policy', default="Auto-Fail Policy"), padding=15)
        fail_frame.pack(fill=tk.X, padx=10, pady=10)

        self.auto_fail_var = tk.BooleanVar(value=self.policies['auto_fail_below_threshold'])
        ttk.Checkbutton(fail_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.buttons.automatically_fail_students_below_threshold', default="Automatically Fail Students Below Threshold"),
                       variable=self.auto_fail_var).pack(anchor=tk.W, pady=5)

        ttk.Label(fail_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.labels.auto_fail_threshold', default="Auto-Fail Threshold (%):")).pack(anchor=tk.W, pady=(5, 5))
        self.auto_fail_threshold_var = tk.IntVar(value=self.policies['auto_fail_threshold'])
        ttk.Scale(fail_frame, from_=0, to=100,
                 variable=self.auto_fail_threshold_var,
                 orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 5))

        ttk.Label(fail_frame,
                 textvariable=tk.StringVar(value=f"{self.policies['auto_fail_threshold']}%")).pack(anchor=tk.W)

    def create_excused_absences_tab(self, parent):
        """Configure excused absence types"""

        frame = ttk.LabelFrame(parent, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.labels.excused_absence_management', default="Excused Absence Management"), padding=15)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.require_documentation_var = tk.BooleanVar(value=self.policies['require_absence_documentation'])
        ttk.Checkbutton(frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.buttons.require_documentation_for_excused_absences', default="Require Documentation for Excused Absences"),
                       variable=self.require_documentation_var).pack(anchor=tk.W, pady=(0, 10))

        ttk.Label(frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.labels.accepted_excused_absence_types', default="Accepted Excused Absence Types:")).pack(anchor=tk.W, pady=(0, 10))

        # Listbox for absence types
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.absence_types_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, height=10)
        self.absence_types_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.absence_types_listbox.yview)

        # Populate listbox
        for absence_type in self.policies['excused_absence_types']:
            self.absence_types_listbox.insert(tk.END, absence_type)

        # Buttons for managing absence types
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.buttons.add_type', default="➕ Add Type"),
                  command=self.add_absence_type).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.buttons.remove_type', default="➖ Remove Type"),
                  command=self.remove_absence_type).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.buttons.edit_type', default="✏️ Edit Type"),
                  command=self.edit_absence_type).pack(side=tk.LEFT)

    def create_advanced_tab(self, parent):
        """Advanced policy settings"""

        # Self check-in
        checkin_frame = ttk.LabelFrame(parent, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.labels.self_check_in_settings', default="Self Check-In Settings"), padding=15)
        checkin_frame.pack(fill=tk.X, padx=10, pady=10)

        self.enable_self_checkin_var = tk.BooleanVar(value=self.policies['enable_self_check_in'])
        ttk.Checkbutton(checkin_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.buttons.enable_student_self_check_in', default="Enable Student Self Check-In"),
                       variable=self.enable_self_checkin_var).pack(anchor=tk.W, pady=5)

        ttk.Label(checkin_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.labels.check_in_time_window_minutes_before_after_class', default="Check-In Time Window (minutes before/after class):")).pack(anchor=tk.W, pady=(5, 5))
        self.checkin_window_var = tk.IntVar(value=self.policies['check_in_time_window_minutes'])
        ttk.Spinbox(checkin_frame, from_=5, to=120,
                   textvariable=self.checkin_window_var,
                   width=10).pack(anchor=tk.W)

        # Geofencing
        geo_frame = ttk.LabelFrame(parent, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.labels.geofencing_settings', default="Geofencing Settings"), padding=15)
        geo_frame.pack(fill=tk.X, padx=10, pady=10)

        self.enable_geofencing_var = tk.BooleanVar(value=self.policies['enable_geofencing'])
        ttk.Checkbutton(geo_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.buttons.enable_geofencing_for_check_in', default="Enable Geofencing for Check-In"),
                       variable=self.enable_geofencing_var).pack(anchor=tk.W, pady=5)

        ttk.Label(geo_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.labels.geofence_radius_meters', default="Geofence Radius (meters):")).pack(anchor=tk.W, pady=(5, 5))
        self.geofence_radius_var = tk.IntVar(value=self.policies['geofence_radius_meters'])
        ttk.Spinbox(geo_frame, from_=10, to=500,
                   textvariable=self.geofence_radius_var,
                   width=10).pack(anchor=tk.W)

        # Appeals
        appeals_frame = ttk.LabelFrame(parent, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.labels.attendance_appeals', default="Attendance Appeals"), padding=15)
        appeals_frame.pack(fill=tk.X, padx=10, pady=10)

        self.enable_appeals_var = tk.BooleanVar(value=self.policies['enable_attendance_appeals'])
        ttk.Checkbutton(appeals_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.buttons.enable_attendance_appeals_process', default="Enable Attendance Appeals Process"),
                       variable=self.enable_appeals_var).pack(anchor=tk.W, pady=5)

        ttk.Label(appeals_frame, text=_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.labels.appeal_deadline_days_after_attendance_taken', default="Appeal Deadline (days after attendance taken):")).pack(anchor=tk.W, pady=(5, 5))
        self.appeal_deadline_var = tk.IntVar(value=self.policies['appeal_deadline_days'])
        ttk.Spinbox(appeals_frame, from_=1, to=60,
                   textvariable=self.appeal_deadline_var,
                   width=10).pack(anchor=tk.W)

    def add_absence_type(self):
        """Add new excused absence type"""
        new_type = simpledialog.askstring(_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.dialogs.add_absence_type', default="Add Absence Type"),
                                         _t('gui.academics.attendance_tracker.misc_windows.attendance_policies.dialogs.enter_new_excused_absence_type', default="Enter new excused absence type:"),
                                         parent=self.window)
        if new_type and new_type.strip():
            self.absence_types_listbox.insert(tk.END, new_type.strip())

    def remove_absence_type(self):
        """Remove selected absence type"""
        selection = self.absence_types_listbox.curselection()
        if selection:
            self.absence_types_listbox.delete(selection[0])
        else:
            messagebox.showwarning(_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.dialogs.no_selection', default="No Selection"), _t('gui.academics.attendance_tracker.misc_windows.attendance_policies.dialogs.please_select_an_absence_type_to_remove', default="Please select an absence type to remove."))

    def edit_absence_type(self):
        """Edit selected absence type"""
        selection = self.absence_types_listbox.curselection()
        if selection:
            current_value = self.absence_types_listbox.get(selection[0])
            new_value = simpledialog.askstring(_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.dialogs.edit_absence_type', default="Edit Absence Type"),
                                              _t('gui.academics.attendance_tracker.misc_windows.attendance_policies.dialogs.edit_absence_type_variant_2', default="Edit absence type:"),
                                              initialvalue=current_value,
                                              parent=self.window)
            if new_value and new_value.strip():
                self.absence_types_listbox.delete(selection[0])
                self.absence_types_listbox.insert(selection[0], new_value.strip())
        else:
            messagebox.showwarning(_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.dialogs.no_selection', default="No Selection"), _t('gui.academics.attendance_tracker.misc_windows.attendance_policies.dialogs.please_select_an_absence_type_to_edit', default="Please select an absence type to edit."))

    def save_policies(self):
        """Save attendance policies to database"""
        try:
            # Update policies dictionary
            self.policies['minimum_attendance_percentage'] = self.minimum_attendance_var.get()
            self.policies['late_arrival_minutes'] = self.late_arrival_var.get()
            self.policies['allow_retroactive_changes'] = self.allow_retroactive_var.get()
            self.policies['retroactive_days_limit'] = self.retroactive_days_var.get()
            self.policies['require_absence_documentation'] = self.require_documentation_var.get()
            self.policies['auto_fail_below_threshold'] = self.auto_fail_var.get()
            self.policies['auto_fail_threshold'] = self.auto_fail_threshold_var.get()
            self.policies['grace_period_weeks'] = self.grace_period_var.get()
            self.policies['absence_penalty_points'] = self.absence_penalty_var.get()
            self.policies['late_penalty_points'] = self.late_penalty_var.get()
            self.policies['max_penalty_points'] = self.max_penalty_var.get()
            self.policies['enable_attendance_appeals'] = self.enable_appeals_var.get()
            self.policies['appeal_deadline_days'] = self.appeal_deadline_var.get()
            self.policies['require_instructor_approval'] = self.require_instructor_approval_var.get()
            self.policies['enable_self_check_in'] = self.enable_self_checkin_var.get()
            self.policies['check_in_time_window_minutes'] = self.checkin_window_var.get()
            self.policies['enable_geofencing'] = self.enable_geofencing_var.get()
            self.policies['geofence_radius_meters'] = self.geofence_radius_var.get()

            # Get absence types from listbox
            absence_types = []
            for i in range(self.absence_types_listbox.size()):
                absence_types.append(self.absence_types_listbox.get(i))
            self.policies['excused_absence_types'] = absence_types

            # Save to database
            if MAIN_DB_AVAILABLE:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Create table if it doesn't exist
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS attendance_policies (
                        policy_key TEXT PRIMARY KEY,
                        policy_value TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Save each policy
                for key, value in self.policies.items():
                    # Convert lists to JSON
                    if isinstance(value, list):
                        value = json.dumps(value)

                    cursor.execute('''
                        INSERT OR REPLACE INTO attendance_policies (policy_key, policy_value, updated_at)
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                    ''', (key, str(value)))

                conn.commit()
                conn.close()

            messagebox.showinfo(_("common.success"), _t('gui.academics.attendance_tracker.misc_windows.attendance_policies.dialogs.attendance_policies_saved_successfully', default="Attendance policies saved successfully!"))

            # Log activity
            try:
                from education_system.systems.university.infrastructure.activity_logger import log_activity
                log_activity('update', 'attendance_policies',
                           details={'policies_count': len(self.policies)})
            except Exception:
                logger.exception("misc_windows.py:2210 %s", 'except Exception')
        except Exception as e:
            logger.exception("misc_windows.py:2213 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Failed to save policies:\n{e}")
            import traceback
            traceback.print_exc()

    def reset_to_defaults(self):
        """Reset policies to default values"""
        if messagebox.askyesno(_t('gui.academics.attendance_tracker.misc_windows.attendance_policies.dialogs.confirm_reset', default="Confirm Reset"),
                              _t('gui.academics.attendance_tracker.misc_windows.attendance_policies.dialogs.are_you_sure_you_want_to_reset_all_attendance_policies_to_defaul', default="Are you sure you want to reset all attendance policies to defaults?")):
            # Reset all variables to defaults
            self.minimum_attendance_var.set(75)
            self.late_arrival_var.set(15)
            self.allow_retroactive_var.set(True)
            self.retroactive_days_var.set(7)
            self.require_documentation_var.set(True)
            self.auto_fail_var.set(False)
            self.auto_fail_threshold_var.set(50)
            self.grace_period_var.set(2)
            self.absence_penalty_var.set(1)
            self.late_penalty_var.set(0.5)
            self.max_penalty_var.set(10)
            self.enable_appeals_var.set(True)
            self.appeal_deadline_var.set(14)
            self.require_instructor_approval_var.set(True)
            self.enable_self_checkin_var.set(True)
            self.checkin_window_var.set(30)
            self.enable_geofencing_var.set(True)
            self.geofence_radius_var.set(100)

            # Reset absence types
            self.absence_types_listbox.delete(0, tk.END)
            default_types = ['Medical', 'Family Emergency', 'University Event', 'Religious Holiday']
            for absence_type in default_types:
                self.absence_types_listbox.insert(tk.END, absence_type)

            messagebox.showinfo(_("common.success"), _t('gui.academics.attendance_tracker.misc_windows.attendance_policies.dialogs.policies_reset_to_defaults', default="Policies reset to defaults!"))

    def export_policies(self):
        """Export policies to JSON file"""
        try:
            # Get all current policies
            self.policies['minimum_attendance_percentage'] = self.minimum_attendance_var.get()
            self.policies['late_arrival_minutes'] = self.late_arrival_var.get()
            self.policies['allow_retroactive_changes'] = self.allow_retroactive_var.get()
            self.policies['retroactive_days_limit'] = self.retroactive_days_var.get()

            # Get absence types
            absence_types = []
            for i in range(self.absence_types_listbox.size()):
                absence_types.append(self.absence_types_listbox.get(i))
            self.policies['excused_absence_types'] = absence_types

            # Ask for file location
            filename = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialfile="attendance_policies.json",
                parent=self.window
            )

            if filename:
                with open(filename, 'w') as f:
                    json.dump(self.policies, f, indent=4)

                messagebox.showinfo(_("common.success"), f"Policies exported to:\n{filename}")

        except Exception as e:
            logger.exception("misc_windows.py:2279 %s", 'except Exception as e')
            messagebox.showerror(_("common.error"), f"Failed to export policies:\n{e}")

