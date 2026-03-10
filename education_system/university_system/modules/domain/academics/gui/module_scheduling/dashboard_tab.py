from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH, get_connection, transaction  # injected
from education_system.university_system.infrastructure.exceptions import (
    CourseNotFoundError,
    ValidationError,
)

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.modules.shared.utils.i18n import (
        get_text as _t,
        get_current_language,
        get_current_language_name,
        set_language,
        get_available_language_list,
        init_i18n,
    )
    from education_system.university_system.modules.shared.utils.gui_language_selector import (
        show_gui_language_selector,
    )
    I18N_AVAILABLE = True
    GUI_LANG_SELECTOR_AVAILABLE = True
    # Initialize i18n if not already done
    init_i18n()
except ImportError:
    I18N_AVAILABLE = False
    GUI_LANG_SELECTOR_AVAILABLE = False
    _t = lambda key, **kwargs: key  # Fallback: return key as-is
    get_current_language = lambda: "en"
    get_current_language_name = lambda: "English"
    set_language = lambda lang, save=True: False
    get_available_language_list = lambda: [("en", "English")]
    show_gui_language_selector = lambda parent=None: "en"

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.font import Font
import os
import sys
from datetime import datetime, timedelta
import threading
import subprocess
import webbrowser
from pathlib import Path

# This ensures full backward compatibility
try:
    from education_system.university_system.modules.domain.academics.services.module_scheduling import (
        ModuleScheduler, DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES,
        display_enhanced_scheduling_menu  # Keep CLI available
    )
except ImportError:
    # If the original module isn't available, we'll define basic constants
    DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
    SESSION_TYPES = ['Lecture', 'Lab', 'Tutorial', 'Seminar', 'Workshop']
    ROOM_TYPES = ['Lecture Hall', 'Lab', 'Tutorial Room', 'Seminar Room', 'Workshop Room', 'Computer Lab', 'Other']
    
    # Import the ModuleScheduler class from the document
    try:
        from education_system.university_system.modules.domain.academics.services.module_scheduling import (ModuleScheduler, DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES, display_enhanced_scheduling_menu)
    except Exception:
        class ModuleScheduler: pass

from .main_gui import ModuleSchedulingGUI

def create_dashboard_tab(self):
    """Create the dashboard overview tab"""
    dashboard_frame = ttk.Frame(self.notebook)
    self.notebook.add(dashboard_frame, text=_t("scheduling.tabs.dashboard"))
    
    # Title
    title_label = ttk.Label(dashboard_frame, text=_t("scheduling.dashboard_title"),
                           font=('Arial', 16, 'bold'))
    title_label.pack(pady=10)
    
    # Stats frame
    stats_frame = ttk.LabelFrame(dashboard_frame, text=_t("scheduling.system_overview"), padding=15)
    stats_frame.pack(fill=tk.X, padx=20, pady=10)

    # Create stats grid
    stats_grid = ttk.Frame(stats_frame)
    stats_grid.pack(fill=tk.X)

    # Stats labels (will be updated by refresh_dashboard)
    self.stats_labels = {}
    stats = [
        (_t("scheduling.stats.total_schedules"), "schedules"),
        (_t("scheduling.stats.active_rooms"), "rooms"),
        (_t("scheduling.stats.active_instructors"), "instructors"),
        (_t("scheduling.stats.conflicts"), "conflicts")
    ]
    
    for i, (label, key) in enumerate(stats):
        row = i // 2
        col = i % 2
        
        frame = ttk.Frame(stats_grid)
        frame.grid(row=row, column=col, padx=20, pady=10, sticky="ew")
        
        ttk.Label(frame, text=label + ":", font=('Arial', 12)).pack()
        self.stats_labels[key] = ttk.Label(frame, text="0", font=('Arial', 20, 'bold'))
        self.stats_labels[key].pack()
    
    stats_grid.columnconfigure(0, weight=1)
    stats_grid.columnconfigure(1, weight=1)
    
    # Quick actions frame
    actions_frame = ttk.LabelFrame(dashboard_frame, text=_t("scheduling.quick_actions"), padding=15)
    actions_frame.pack(fill=tk.X, padx=20, pady=10)

    # Action buttons
    actions_grid = ttk.Frame(actions_frame)
    actions_grid.pack(fill=tk.X)

    action_buttons = [
        (_t("scheduling.actions.add_schedule"), self.quick_add_schedule),
        (_t("scheduling.actions.add_room"), self.quick_add_room),
        (_t("scheduling.actions.add_instructor"), self.quick_add_instructor),
        (_t("scheduling.actions.add_module"), self.quick_add_module),
        (_t("scheduling.actions.generate_report"), self.quick_generate_report),
        (_t("scheduling.actions.check_conflicts"), self.detect_all_conflicts),
        (_t("scheduling.actions.backup_system"), self.create_backup)
    ]        
    for i, (text, command) in enumerate(action_buttons):
        row = i // 3
        col = i % 3
        
        btn = ttk.Button(actions_grid, text=text, command=command, style='Action.TButton')
        btn.grid(row=row, column=col, padx=10, pady=5, sticky="ew")
    
    for i in range(3):
        actions_grid.columnconfigure(i, weight=1)
    
    # Recent activity frame
    activity_frame = ttk.LabelFrame(dashboard_frame, text=_t("scheduling.recent_activity"), padding=15)
    activity_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
    
    # Activity list
    self.activity_text = scrolledtext.ScrolledText(activity_frame, height=10, state=tk.DISABLED)
    self.activity_text.pack(fill=tk.BOTH, expand=True)

ModuleSchedulingGUI.create_dashboard_tab = create_dashboard_tab

def refresh_dashboard(self):
    """Update dashboard statistics"""
    try:
        from education_system.university_system.infrastructure.database.db import sqlite3
        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()

            # Get statistics
            cursor.execute("SELECT COUNT(*) FROM module_schedule")
            schedule_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM rooms WHERE is_active = 1")
            room_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM instructors WHERE CASE WHEN status = 'Active' THEN 1 ELSE COALESCE(is_active, 1) END = 1")
            instructor_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM schedule_conflicts WHERE resolved = 0")
            conflict_count = cursor.fetchone()[0]
        
        # Update labels
        self.stats_labels["schedules"].config(text=str(schedule_count))
        self.stats_labels["rooms"].config(text=str(room_count))
        self.stats_labels["instructors"].config(text=str(instructor_count))
        self.stats_labels["conflicts"].config(text=str(conflict_count))
        
        # Update activity log
        self.update_activity_log("Dashboard refreshed")
        
    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("scheduling.dashboard.refresh_failed", error=str(e)))

ModuleSchedulingGUI.refresh_dashboard = refresh_dashboard

def _analyze_peak_usage(self):
    """Analyze peak usage times"""
    with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
        cursor = conn.cursor()

        cursor.execute('''
        SELECT day_of_week, start_time, COUNT(*) as session_count
        FROM module_schedule
        GROUP BY day_of_week, start_time
        ORDER BY day_of_week, session_count DESC
        ''')

        usage_data = cursor.fetchall()
    
    peak_times = {}
    for day in DAYS_OF_WEEK:
        day_data = [row for row in usage_data if row[0] == day]
        if day_data:
            max_count = max(row[2] for row in day_data)
            peak_slots = [row[1] for row in day_data if row[2] == max_count]
            peak_times[day] = peak_slots[:3]
        else:
            peak_times[day] = []
    
    return peak_times

ModuleSchedulingGUI._analyze_peak_usage = _analyze_peak_usage

def _analyze_module_distribution(self):
    """Analyze module scheduling distribution"""
    with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(DISTINCT module_code) FROM module_schedule')
        total_modules = cursor.fetchone()[0]

        cursor.execute('''
        SELECT session_type, COUNT(*) as count
        FROM module_schedule
        GROUP BY session_type
        ORDER BY count DESC
        ''')
        session_types = cursor.fetchall()

        cursor.execute('''
        SELECT module_code, COUNT(*) as sessions
        FROM module_schedule
        GROUP BY module_code
        ''')
        module_sessions = cursor.fetchall()
    
    most_common_type = session_types[0][0] if session_types else "None"
    avg_sessions = sum(row[1] for row in module_sessions) / len(module_sessions) if module_sessions else 0
    
    return {
        'total': total_modules,
        'most_common_type': most_common_type,
        'avg_sessions': avg_sessions
    }

ModuleSchedulingGUI._analyze_module_distribution = _analyze_module_distribution

def _get_admin_email(self):
    """Get admin email from database"""
    try:
        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM users WHERE LOWER(role) = 'admin' LIMIT 1")
            admin_row = cursor.fetchone()
            return admin_row[0] if admin_row else "admin@university.edu"
    except Exception as e:
        print(f"Warning: Could not fetch admin email from database: {e}")
        return "admin@university.edu"

ModuleSchedulingGUI._get_admin_email = _get_admin_email

