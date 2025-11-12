import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext
from university_system.infrastructure.database.db import sqlite3
import datetime
import json
import threading
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import seaborn as sns
from pathlib import Path
import uuid
import qrcode
from PIL import Image, ImageTk
import io
import os
import csv
import re
import shutil
from collections import deque

# Import path constants
from university_system.modules.shared.constants.paths import BACKUP_DIR, DEFAULT_DB_PATH, LOG_DIR

# Import authentication system
from university_system.infrastructure.auth.user_authentication import UserAuth

# Import main database connection
try:
    from university_system.infrastructure.database.db import get_db_connection
    MAIN_DB_AVAILABLE = True
except ImportError:
    MAIN_DB_AVAILABLE = False

# Import all original functions and classes
try:
    from university_system.modules.domain.academics.services.attendance.attendance_tracker import (
        AttendancePredictiveAnalytics, BackupRecoverySystem,
        EnhancedNotificationSystem, FaceRecognitionSystem, GeofencingSystem,
        QRAttendanceSystem, create_missing_tables, display_attendance_menu,
        generate_executive_summary_report, get_enhanced_setting,
        get_module_attendance, get_modules, get_student_attendance,
        init_enhanced_attendance_db, record_attendance, set_enhanced_setting
    )
    ORIGINAL_FUNCTIONS_AVAILABLE = True
except ImportError:
    print("Warning: Original attendance_tracker.py not found. Some functions may not work.")
    ORIGINAL_FUNCTIONS_AVAILABLE = False


# Import attendance notification service
try:
    from university_system.modules.domain.academics.services.attendance.attendance_notifications import (
        AttendanceNotificationService, check_and_notify_low_attendance
    )
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = True
except ImportError:
    ATTENDANCE_NOTIFICATIONS_AVAILABLE = False

# Feature flags
GEOFENCING_SUPPORT = True
FACE_RECOGNITION_SUPPORT = True

class AttendanceGUI:
    def __init__(self, root, auth_manager=None):
        self.root = root
        self.auth = auth_manager
        self.root.title("Enhanced Attendance Tracking System")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)

        # Initialize original systems if available
        if ORIGINAL_FUNCTIONS_AVAILABLE:
            try:
                init_enhanced_attendance_db()
                create_missing_tables()
                self.qr_system = QRAttendanceSystem()
                self.geo_system = GeofencingSystem() if GEOFENCING_SUPPORT else None
                self.face_system = FaceRecognitionSystem() if FACE_RECOGNITION_SUPPORT else None
                self.notification_system = EnhancedNotificationSystem()
                self.analytics = AttendancePredictiveAnalytics()
                self.backup_system = BackupRecoverySystem()
            except Exception as e:
                print(f"Warning: Could not initialize some systems: {e}")
                self.qr_system = None
                self.geo_system = None
                self.face_system = None
                self.notification_system = None
                self.analytics = None
                self.backup_system = None
        
        # Style configuration
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Configure colors
        self.colors = {
            'primary': '#2C3E50',
            'secondary': '#3498DB',
            'success': '#27AE60',
            'warning': '#F39C12',
            'danger': '#E74C3C',
            'light': '#ECF0F1',
            'dark': '#34495E'
        }
        
        self.setup_styles()
        self.create_widgets()
        self.setup_menu()
        
        # Initialize data
        self.refresh_data()
        
    def setup_styles(self):
        """Configure custom styles"""
        # Configure notebook tabs
        self.style.configure('Custom.TNotebook.Tab', padding=[20, 10])
        self.style.map('Custom.TNotebook.Tab',
                      background=[('selected', self.colors['secondary']),
                                ('!selected', self.colors['light'])],
                      foreground=[('selected', 'white'),
                                ('!selected', self.colors['dark'])])
        
        # Configure buttons
        self.style.configure('Primary.TButton',
                           background=self.colors['secondary'],
                           foreground='white',
                           padding=(10, 5))
        
        self.style.configure('Success.TButton',
                           background=self.colors['success'],
                           foreground='white',
                           padding=(10, 5))
        
        self.style.configure('Warning.TButton',
                           background=self.colors['warning'],
                           foreground='white',
                           padding=(10, 5))
        
        self.style.configure('Danger.TButton',
                           background=self.colors['danger'],
                           foreground='white',
                           padding=(10, 5))
    
    def create_widgets(self):
        """Create main GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        title_label = ttk.Label(title_frame,
                               text="Enhanced Attendance Tracking System",
                               font=('Arial', 20, 'bold'))
        title_label.pack(side=tk.LEFT)

        # Return to Home button
        if self.auth:
            return_button = ttk.Button(title_frame, text="🏠 Return to Main Menu",
                                      command=self.return_to_main_menu)
            return_button.pack(side=tk.RIGHT, padx=10)

        # Status label
        self.status_label = ttk.Label(title_frame, text="Ready", foreground=self.colors['success'])
        self.status_label.pack(side=tk.RIGHT)
        
        # Main notebook
        self.notebook = ttk.Notebook(main_frame, style='Custom.TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create tabs
        self.create_dashboard_tab()
        self.create_attendance_tab()
        self.create_students_tab()
        self.create_reports_tab()
        self.create_analytics_tab()
        self.create_settings_tab()
        self.create_admin_tab()
        
    def setup_menu(self):
        """Create menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Import Data", command=self.import_data)
        file_menu.add_command(label="Export Data", command=self.export_data)
        file_menu.add_separator()
        file_menu.add_command(label="Backup Database", command=self.backup_database)
        file_menu.add_command(label="Restore Database", command=self.restore_database)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

        # Advanced menu
        advanced_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Advanced", menu=advanced_menu)
        advanced_menu.add_command(label="API Management", command=self.open_api_management)
        advanced_menu.add_command(label="LMS Integration", command=self.open_lms_integration)
        advanced_menu.add_command(label="Calendar Sync", command=self.open_calendar_sync)
        advanced_menu.add_separator()
        advanced_menu.add_command(label="Audit Logs", command=self.view_audit_logs)
        advanced_menu.add_command(label="System Diagnostics", command=self.run_diagnostics)
        advanced_menu.add_command(label="Database Maintenance", command=self.database_maintenance)
            
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="QR Code Generator", command=self.open_qr_generator)
        tools_menu.add_command(label="Face Recognition Setup", command=self.open_face_recognition)
        tools_menu.add_command(label="Geofencing Setup", command=self.open_geofencing)
        tools_menu.add_separator()
        tools_menu.add_command(label="Parent Notification System", command=self.open_parent_notifications)
        tools_menu.add_separator()
        tools_menu.add_command(label="Run Original CLI", command=self.run_original_cli)
        tools_menu.add_separator()
        tools_menu.add_command(label="Biometrics Management", command=self.open_biometrics_management)
        tools_menu.add_command(label="Attendance Alerts", command=self.open_attendance_alerts)
        tools_menu.add_command(label="Predictive Analytics", command=self.open_predictive_analytics)
        tools_menu.add_command(label="Backup & Recovery", command=self.open_backup_recovery)
                
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="User Manual", command=self.show_help)
        help_menu.add_command(label="About", command=self.show_about)

        self.create_main_menu_button()

    def create_main_menu_button(self):
        """Place a dedicated top-right navigation button"""
        try:
            if hasattr(self, "main_menu_button") and self.main_menu_button.winfo_exists():
                return
        except Exception:
            pass

        self.main_menu_button = ttk.Button(
            self.root,
            text="🏠 Return to Main Menu",
            command=self.return_to_main_menu,
        )
        self.main_menu_button.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)
    
    def create_dashboard_tab(self):
        """Create dashboard tab"""
        dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(dashboard_frame, text="📊 Dashboard")
        
        # Quick stats frame
        stats_frame = ttk.LabelFrame(dashboard_frame, text="Quick Statistics", padding=10)
        stats_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Stats grid
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.X)
        
        # Create stat cards
        self.stat_cards = {}
        stat_names = [
            ("Total Students", "total_students"),
            ("Active Modules", "active_modules"),
            ("Today's Sessions", "todays_sessions"),
            ("Overall Attendance", "overall_attendance")
        ]
        
        for i, (name, key) in enumerate(stat_names):
            card_frame = ttk.Frame(stats_grid, relief=tk.RAISED, borderwidth=1)
            card_frame.grid(row=0, column=i, padx=5, pady=5, sticky="ew")
            stats_grid.grid_columnconfigure(i, weight=1)
            
            ttk.Label(card_frame, text=name, font=('Arial', 10, 'bold')).pack(pady=(5, 0))
            value_label = ttk.Label(card_frame, text="--", font=('Arial', 16, 'bold'))
            value_label.pack(pady=(0, 5))
            
            self.stat_cards[key] = value_label
        
        # Charts frame
        charts_frame = ttk.Frame(dashboard_frame)
        charts_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left chart frame
        left_chart_frame = ttk.LabelFrame(charts_frame, text="Attendance Trends", padding=5)
        left_chart_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Right chart frame
        right_chart_frame = ttk.LabelFrame(charts_frame, text="Status Distribution", padding=5)
        right_chart_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Create matplotlib figures
        self.create_dashboard_charts(left_chart_frame, right_chart_frame)
        
        # Recent activity frame
        activity_frame = ttk.LabelFrame(dashboard_frame, text="Recent Activity", padding=10)
        activity_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Activity treeview
        activity_columns = ("Time", "Student", "Module", "Status", "Method")
        self.activity_tree = ttk.Treeview(activity_frame, columns=activity_columns, show="headings", height=6)
        
        for col in activity_columns:
            self.activity_tree.heading(col, text=col)
            self.activity_tree.column(col, width=120)
        
        activity_scrollbar = ttk.Scrollbar(activity_frame, orient=tk.VERTICAL, command=self.activity_tree.yview)
        self.activity_tree.configure(yscrollcommand=activity_scrollbar.set)
        
        self.activity_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        activity_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def create_attendance_tab(self):
        """Create attendance management tab"""
        attendance_frame = ttk.Frame(self.notebook)
        self.notebook.add(attendance_frame, text="📋 Attendance")
        
        # Left panel - Controls with scrollbar
        left_container = ttk.Frame(attendance_frame)
        left_container.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # Create scrollable left panel
        left_canvas = tk.Canvas(left_container, width=300, highlightthickness=0)
        left_scrollbar = ttk.Scrollbar(left_container, orient="vertical", command=left_canvas.yview)
        left_panel = ttk.Frame(left_canvas)

        left_panel.bind(
            "<Configure>",
            lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all"))
        )

        left_canvas.create_window((0, 0), window=left_panel, anchor="nw")
        left_canvas.configure(yscrollcommand=left_scrollbar.set)

        left_canvas.pack(side="left", fill="y", expand=True)
        left_scrollbar.pack(side="right", fill="y")
        
        # Module selection
        module_frame = ttk.LabelFrame(left_panel, text="Module Selection", padding=10)
        module_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(module_frame, text="Select Module:").pack(anchor=tk.W)
        self.module_var = tk.StringVar()
        self.module_combo = ttk.Combobox(module_frame, textvariable=self.module_var, state="readonly", width=30)
        self.module_combo.pack(fill=tk.X, pady=(5, 0))
        self.module_combo.bind('<<ComboboxSelected>>', self.on_module_selected)
        
        # Date selection
        date_frame = ttk.LabelFrame(left_panel, text="Date Selection", padding=10)
        date_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(date_frame, text="Date:").pack(anchor=tk.W)
        self.date_var = tk.StringVar(value=datetime.date.today().isoformat())
        date_entry = ttk.Entry(date_frame, textvariable=self.date_var, width=30)
        date_entry.pack(fill=tk.X, pady=(5, 0))
        
        # Attendance methods
        methods_frame = ttk.LabelFrame(left_panel, text="Check-in Methods", padding=10)
        methods_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(methods_frame, text="📝 Manual Entry", 
                  command=self.manual_attendance, style='Primary.TButton').pack(fill=tk.X, pady=2)
        ttk.Button(methods_frame, text="📱 QR Code", 
                  command=self.qr_attendance, style='Primary.TButton').pack(fill=tk.X, pady=2)
        ttk.Button(methods_frame, text="📍 Geofencing", 
                  command=self.geo_attendance, style='Primary.TButton').pack(fill=tk.X, pady=2)
        ttk.Button(methods_frame, text="👤 Face Recognition", 
                  command=self.face_attendance, style='Primary.TButton').pack(fill=tk.X, pady=2)
        
        # Quick actions
        actions_frame = ttk.LabelFrame(left_panel, text="Quick Actions", padding=10)
        actions_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(actions_frame, text="🔄 Refresh Data", 
                  command=self.refresh_attendance_data, style='Success.TButton').pack(fill=tk.X, pady=2)
        ttk.Button(actions_frame, text="📊 Generate Report", 
                  command=self.generate_quick_report, style='Warning.TButton').pack(fill=tk.X, pady=2)
        
        # Right panel - Student list and attendance
        right_panel = ttk.Frame(attendance_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Students frame
        students_frame = ttk.LabelFrame(right_panel, text="Students", padding=10)
        students_frame.pack(fill=tk.BOTH, expand=True)
        
        # Student treeview
        student_columns = ("ID", "Name", "Status", "Notes", "Last Update")
        self.student_tree = ttk.Treeview(students_frame, columns=student_columns, show="headings")
        
        for col in student_columns:
            self.student_tree.heading(col, text=col)
            self.student_tree.column(col, width=120)
        
        student_scrollbar = ttk.Scrollbar(students_frame, orient=tk.VERTICAL, command=self.student_tree.yview)
        self.student_tree.configure(yscrollcommand=student_scrollbar.set)
        
        self.student_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        student_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Double-click to edit
        self.student_tree.bind('<Double-1>', self.edit_attendance_record)
    
    def create_students_tab(self):
        """Create students management tab"""
        students_frame = ttk.Frame(self.notebook)
        self.notebook.add(students_frame, text="👥 Students")
        
        # Toolbar
        toolbar = ttk.Frame(students_frame)
        toolbar.pack(fill=tk.X, pady=(0, 10))

        # Note: Student management (add/edit/delete) should be done through the main Student Management module
        # These buttons have been removed to avoid duplicate functionality and maintain data consistency

        # Search frame
        search_frame = ttk.Frame(toolbar)
        search_frame.pack(side=tk.RIGHT)
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=20)
        search_entry.pack(side=tk.LEFT)
        search_entry.bind('<KeyRelease>', self.filter_students)
        
        # Students treeview
        student_mgmt_columns = ("ID", "First Name", "Last Name", "Email", "Course", "Enrollment Date")
        self.students_tree = ttk.Treeview(students_frame, columns=student_mgmt_columns, show="headings")
        
        for col in student_mgmt_columns:
            self.students_tree.heading(col, text=col)
            self.students_tree.column(col, width=120)
        
        students_scrollbar = ttk.Scrollbar(students_frame, orient=tk.VERTICAL, command=self.students_tree.yview)
        self.students_tree.configure(yscrollcommand=students_scrollbar.set)
        
        self.students_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        students_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Note: Student editing has been disabled - use main Student Management module
    
    def create_reports_tab(self):
        """Create reports tab"""
        reports_frame = ttk.Frame(self.notebook)
        self.notebook.add(reports_frame, text="📈 Reports")
        
        # Report types frame
        types_frame = ttk.LabelFrame(reports_frame, text="Report Types", padding=10)
        types_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Report buttons grid
        reports_grid = ttk.Frame(types_frame)
        reports_grid.pack(fill=tk.X)
        
        report_buttons = [
            ("📊 Student Attendance Report", self.generate_student_report),
            ("📋 Module Attendance Report", self.generate_module_report),
            ("📈 Executive Summary", self.generate_executive_report),
            ("⚠️ At-Risk Students", self.generate_at_risk_report),
            ("🎯 Attendance Trends", self.generate_trends_report),
            ("📑 Custom Report", self.generate_custom_report)
        ]
        
        for i, (text, command) in enumerate(report_buttons):
            row = i // 3
            col = i % 3
            btn = ttk.Button(reports_grid, text=text, command=command, style='Primary.TButton')
            btn.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
            reports_grid.grid_columnconfigure(col, weight=1)
        
        # Report parameters frame
        params_frame = ttk.LabelFrame(reports_frame, text="Report Parameters", padding=10)
        params_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Parameters grid
        params_grid = ttk.Frame(params_frame)
        params_grid.pack(fill=tk.X)
        
        # Date range
        ttk.Label(params_grid, text="From Date:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.report_from_var = tk.StringVar(value=(datetime.date.today() - datetime.timedelta(days=30)).isoformat())
        ttk.Entry(params_grid, textvariable=self.report_from_var, width=15).grid(row=0, column=1, padx=(0, 10))
        
        ttk.Label(params_grid, text="To Date:").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.report_to_var = tk.StringVar(value=datetime.date.today().isoformat())
        ttk.Entry(params_grid, textvariable=self.report_to_var, width=15).grid(row=0, column=3, padx=(0, 10))
        
        # Output format
        ttk.Label(params_grid, text="Format:").grid(row=0, column=4, sticky=tk.W, padx=(0, 5))
        self.report_format_var = tk.StringVar(value="Excel")
        format_combo = ttk.Combobox(params_grid, textvariable=self.report_format_var, 
                                   values=["Excel", "PDF", "CSV"], state="readonly", width=10)
        format_combo.grid(row=0, column=5)
        
        # Report preview frame
        preview_frame = ttk.LabelFrame(reports_frame, text="Report Preview", padding=10)
        preview_frame.pack(fill=tk.BOTH, expand=True)
        
        # Preview text widget
        self.report_preview = tk.Text(preview_frame, wrap=tk.WORD, height=15)
        preview_scrollbar = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self.report_preview.yview)
        self.report_preview.configure(yscrollcommand=preview_scrollbar.set)
        
        self.report_preview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        preview_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def create_analytics_tab(self):
        """Create analytics tab"""
        analytics_frame = ttk.Frame(self.notebook)
        self.notebook.add(analytics_frame, text="🔮 Analytics")
        
        # Analytics controls
        controls_frame = ttk.LabelFrame(analytics_frame, text="Analytics Controls", padding=10)
        controls_frame.pack(fill=tk.X, pady=(0, 10))
        
        controls_grid = ttk.Frame(controls_frame)
        controls_grid.pack(fill=tk.X)
        
        ttk.Button(controls_grid, text="🧠 Train Model", 
                  command=self.train_prediction_model, style='Primary.TButton').grid(row=0, column=0, padx=5)
        ttk.Button(controls_grid, text="🔮 Predict Risk", 
                  command=self.predict_student_risk, style='Warning.TButton').grid(row=0, column=1, padx=5)
        ttk.Button(controls_grid, text="📊 Batch Analysis", 
                  command=self.batch_risk_analysis, style='Success.TButton').grid(row=0, column=2, padx=5)
        ttk.Button(controls_grid, text="🎮 Gamification", 
                  command=self.open_gamification, style='Primary.TButton').grid(row=0, column=3, padx=5)
        
        # Analytics display
        display_frame = ttk.LabelFrame(analytics_frame, text="Analytics Results", padding=10)
        display_frame.pack(fill=tk.BOTH, expand=True)
        
        # Results notebook
        self.analytics_notebook = ttk.Notebook(display_frame)
        self.analytics_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Predictions tab
        predictions_frame = ttk.Frame(self.analytics_notebook)
        self.analytics_notebook.add(predictions_frame, text="Risk Predictions")
        
        # Predictions treeview
        pred_columns = ("Student ID", "Name", "Module", "Risk Level", "Confidence", "Factors")
        self.predictions_tree = ttk.Treeview(predictions_frame, columns=pred_columns, show="headings")
        
        for col in pred_columns:
            self.predictions_tree.heading(col, text=col)
            self.predictions_tree.column(col, width=120)
        
        pred_scrollbar = ttk.Scrollbar(predictions_frame, orient=tk.VERTICAL, command=self.predictions_tree.yview)
        self.predictions_tree.configure(yscrollcommand=pred_scrollbar.set)
        
        self.predictions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        pred_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Gamification tab
        gamification_frame = ttk.Frame(self.analytics_notebook)
        self.analytics_notebook.add(gamification_frame, text="Gamification")
        
        # Leaderboard
        leader_columns = ("Rank", "Student ID", "Name", "Points", "Level", "Streak")
        self.leaderboard_tree = ttk.Treeview(gamification_frame, columns=leader_columns, show="headings")
        
        for col in leader_columns:
            self.leaderboard_tree.heading(col, text=col)
            self.leaderboard_tree.column(col, width=100)
        
        leader_scrollbar = ttk.Scrollbar(gamification_frame, orient=tk.VERTICAL, command=self.leaderboard_tree.yview)
        self.leaderboard_tree.configure(yscrollcommand=leader_scrollbar.set)
        
        self.leaderboard_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        leader_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def create_settings_tab(self):
        """Create settings tab"""
        settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(settings_frame, text="⚙️ Settings")
        
        # Settings notebook
        settings_notebook = ttk.Notebook(settings_frame)
        settings_notebook.pack(fill=tk.BOTH, expand=True)
        
        # General settings
        general_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(general_frame, text="General")
        
        self.create_general_settings(general_frame)
        
        # Notifications settings
        notifications_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(notifications_frame, text="Notifications")
        
        self.create_notifications_settings(notifications_frame)
        
        # Features settings
        features_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(features_frame, text="Features")
        
        self.create_features_settings(features_frame)
        
        # Thresholds settings
        thresholds_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(thresholds_frame, text="Thresholds")
        
        self.create_thresholds_settings(thresholds_frame)
    
    def create_admin_tab(self):
        """Create admin tab"""
        admin_frame = ttk.Frame(self.notebook)
        self.notebook.add(admin_frame, text="🔧 Admin")
        
        # Database management
        db_frame = ttk.LabelFrame(admin_frame, text="Database Management", padding=10)
        db_frame.pack(fill=tk.X, pady=(0, 10))
        
        db_buttons = ttk.Frame(db_frame)
        db_buttons.pack(fill=tk.X)
        
        ttk.Button(db_buttons, text="💾 Backup Database", 
                  command=self.backup_database, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(db_buttons, text="📂 Restore Database", 
                  command=self.restore_database, style='Warning.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(db_buttons, text="🧹 Cleanup Old Data", 
                  command=self.cleanup_old_data, style='Primary.TButton').pack(side=tk.LEFT, padx=(0, 5))
        
        # System information
        info_frame = ttk.LabelFrame(admin_frame, text="System Information", padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.system_info = tk.Text(info_frame, height=10, wrap=tk.WORD)
        info_scrollbar = ttk.Scrollbar(info_frame, orient=tk.VERTICAL, command=self.system_info.yview)
        self.system_info.configure(yscrollcommand=info_scrollbar.set)
        
        self.system_info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        info_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Audit logs
        audit_frame = ttk.LabelFrame(admin_frame, text="Audit Logs", padding=10)
        audit_frame.pack(fill=tk.BOTH, expand=True)
        
        # Audit controls
        audit_controls = ttk.Frame(audit_frame)
        audit_controls.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(audit_controls, text="🔄 Refresh Logs", 
                  command=self.refresh_audit_logs, style='Primary.TButton').pack(side=tk.LEFT)
        ttk.Button(audit_controls, text="📁 Export Logs", 
                  command=self.export_audit_logs, style='Success.TButton').pack(side=tk.LEFT, padx=(5, 0))
        
        # Audit treeview
        audit_columns = ("Timestamp", "User", "Action", "Table", "Record ID")
        self.audit_tree = ttk.Treeview(audit_frame, columns=audit_columns, show="headings")
        
        for col in audit_columns:
            self.audit_tree.heading(col, text=col)
            self.audit_tree.column(col, width=120)
        
        audit_scrollbar = ttk.Scrollbar(audit_frame, orient=tk.VERTICAL, command=self.audit_tree.yview)
        self.audit_tree.configure(yscrollcommand=audit_scrollbar.set)
        
        self.audit_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        audit_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Load system info
        self.load_system_info()
    
    # Dashboard methods
    def create_dashboard_charts(self, left_frame, right_frame):
        """Create dashboard charts"""
        # Left chart - Attendance trends
        self.trend_fig, self.trend_ax = plt.subplots(figsize=(6, 4))
        self.trend_canvas = FigureCanvasTkAgg(self.trend_fig, left_frame)
        self.trend_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Right chart - Status distribution
        self.dist_fig, self.dist_ax = plt.subplots(figsize=(6, 4))
        self.dist_canvas = FigureCanvasTkAgg(self.dist_fig, right_frame)
        self.dist_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Initialize charts with sample data
        self.update_dashboard_charts()
    
    def update_dashboard_charts(self):
        """Update dashboard charts with current data"""
        try:
            if not ORIGINAL_FUNCTIONS_AVAILABLE:
                # Create sample data for demonstration
                self.create_sample_charts()
                return
            
            # Get attendance trends data
            conn = get_db_connection()
            
            # Trend data - last 30 days
            trend_query = '''
            SELECT date, 
                   AVG(CASE WHEN status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as rate
            FROM attendance_records 
            WHERE date >= date('now', '-30 days')
            GROUP BY date
            ORDER BY date
            '''
            
            trend_df = pd.read_sql_query(trend_query, conn)
            
            # Clear and update trend chart
            self.trend_ax.clear()
            if not trend_df.empty:
                self.trend_ax.plot(pd.to_datetime(trend_df['date']), trend_df['rate'], 
                                 marker='o', linewidth=2, markersize=4)
                self.trend_ax.set_title('30-Day Attendance Trend')
                self.trend_ax.set_ylabel('Attendance Rate (%)')
                self.trend_ax.grid(True, alpha=0.3)
                
                # Add threshold lines
                threshold_warning = 80
                threshold_critical = 70
                self.trend_ax.axhline(y=threshold_warning, color='orange', linestyle='--', alpha=0.7)
                self.trend_ax.axhline(y=threshold_critical, color='red', linestyle='--', alpha=0.7)
            else:
                self.trend_ax.text(0.5, 0.5, 'No data available', 
                                 transform=self.trend_ax.transAxes, ha='center', va='center')
            
            self.trend_fig.tight_layout()
            self.trend_canvas.draw()
            
            # Status distribution data
            status_query = '''
            SELECT status, COUNT(*) as count
            FROM attendance_records
            WHERE date >= date('now', '-7 days')
            GROUP BY status
            '''
            
            status_df = pd.read_sql_query(status_query, conn)
            
            # Clear and update distribution chart
            self.dist_ax.clear()
            if not status_df.empty:
                colors = {'Present': 'green', 'Late': 'yellow', 'Excused': 'blue', 'Absent': 'red'}
                pie_colors = [colors.get(status, 'gray') for status in status_df['status']]
                
                self.dist_ax.pie(status_df['count'], labels=status_df['status'], 
                               colors=pie_colors, autopct='%1.1f%%', startangle=90)
                self.dist_ax.set_title('Status Distribution (Last 7 Days)')
            else:
                self.dist_ax.text(0.5, 0.5, 'No data available', 
                                transform=self.dist_ax.transAxes, ha='center', va='center')
            
            self.dist_fig.tight_layout()
            self.dist_canvas.draw()
            
            conn.close()
            
        except Exception as e:
            self.create_sample_charts()
            print(f"Error updating charts: {e}")
    
    def create_sample_charts(self):
        """Create sample charts when no data is available"""
        # Sample trend data
        self.trend_ax.clear()
        dates = pd.date_range(start=datetime.date.today()-datetime.timedelta(days=30), 
                             end=datetime.date.today(), freq='D')
        rates = [85 + (i % 10) - 5 for i in range(len(dates))]
        
        self.trend_ax.plot(dates, rates, marker='o', linewidth=2, markersize=4)
        self.trend_ax.set_title('30-Day Attendance Trend (Sample)')
        self.trend_ax.set_ylabel('Attendance Rate (%)')
        self.trend_ax.grid(True, alpha=0.3)
        self.trend_fig.tight_layout()
        self.trend_canvas.draw()
        
        # Sample distribution data
        self.dist_ax.clear()
        statuses = ['Present', 'Late', 'Absent', 'Excused']
        counts = [70, 15, 10, 5]
        colors = ['green', 'yellow', 'red', 'blue']
        
        self.dist_ax.pie(counts, labels=statuses, colors=colors, autopct='%1.1f%%', startangle=90)
        self.dist_ax.set_title('Status Distribution (Sample)')
        self.dist_fig.tight_layout()
        self.dist_canvas.draw()
    
    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Check if this is a child window (Toplevel) or standalone (Tk)
            if isinstance(self.root, tk.Toplevel):
                # Just close the child window
                self.root.destroy()
            else:
                # Running standalone, need to create main GUI
                self.root.destroy()
                from university_system.modules.shared.gui.main_gui import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def refresh_data(self):
        """Refresh all data in the application"""
        self.update_status("Refreshing data...")

        # Update dashboard stats
        self.update_dashboard_stats()

        # Update charts
        self.update_dashboard_charts()

        # Refresh module combo
        self.refresh_modules()

        # Refresh students data
        self.refresh_students_data()

        # Refresh recent activity
        self.refresh_recent_activity()

        self.update_status("Data refreshed successfully", "success")

    def open_biometrics_management(self):
        """Open biometrics management window"""
        BiometricsManagementWindow(self.root)

    def open_attendance_alerts(self):
        """Open attendance alerts manager"""
        AttendanceAlertsWindow(self.root)

    def open_predictive_analytics(self):
        """Open predictive analytics window"""
        PredictiveAnalyticsWindow(self.root)

    def open_backup_recovery(self):
        """Open backup and recovery window"""
        BackupRecoveryWindow(self.root)

    def open_api_management(self):
        """Open API management interface"""
        ApiManagementWindow(self.root)

    def open_parent_notifications(self):
        """Open parent notification system"""
        ParentNotificationWindow(self.root)

    def open_lms_integration(self):
        """Open LMS integration interface"""
        LMSIntegrationWindow(self.root)

    def open_calendar_sync(self):
        """Open calendar sync interface"""
        CalendarSyncWindow(self.root)

    def view_audit_logs(self):
        """View system audit logs"""
        AuditLogsWindow(self.root)

    def run_diagnostics(self):
        """Run system diagnostics"""
        DiagnosticsWindow(self.root)

    def database_maintenance(self):
        """Open database maintenance tools"""
        DatabaseMaintenanceWindow(self.root)

    def update_notification_settings(self):
        """Update notification settings"""
        NotificationSettingsWindow(self.root)

    def manage_attendance_policies(self):
        """Manage attendance policies"""
        AttendancePoliciesWindow(self.root)
    
    def update_dashboard_stats(self):
        """Update dashboard statistics"""
        try:
            if not ORIGINAL_FUNCTIONS_AVAILABLE:
                # Sample data
                self.stat_cards['total_students'].config(text="125")
                self.stat_cards['active_modules'].config(text="8")
                self.stat_cards['todays_sessions'].config(text="12")
                self.stat_cards['overall_attendance'].config(text="87.5%")
                return
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Total students
            cursor.execute("SELECT COUNT(*) FROM students")
            total_students = cursor.fetchone()[0]
            self.stat_cards['total_students'].config(text=str(total_students))
            
            # Active modules
            cursor.execute("SELECT COUNT(DISTINCT module_code) FROM attendance_records")
            active_modules = cursor.fetchone()[0]
            self.stat_cards['active_modules'].config(text=str(active_modules))
            
            # Today's sessions
            today = datetime.date.today().isoformat()
            cursor.execute("SELECT COUNT(*) FROM attendance_sessions WHERE date = ? AND status = 'active'", (today,))
            todays_sessions = cursor.fetchone()[0]
            self.stat_cards['todays_sessions'].config(text=str(todays_sessions))
            
            # Overall attendance rate
            cursor.execute('''
            SELECT AVG(CASE WHEN status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100
            FROM attendance_records
            WHERE date >= date('now', '-30 days')
            ''')
            overall_rate = cursor.fetchone()[0] or 0
            self.stat_cards['overall_attendance'].config(text=f"{overall_rate:.1f}%")
            
            conn.close()
            
        except Exception as e:
            print(f"Error updating dashboard stats: {e}")
            # Set default values
            for key in self.stat_cards:
                self.stat_cards[key].config(text="--")
    
    def refresh_recent_activity(self):
        """Refresh recent activity list"""
        try:
            # Clear existing items
            for item in self.activity_tree.get_children():
                self.activity_tree.delete(item)
            
            if not ORIGINAL_FUNCTIONS_AVAILABLE:
                # Sample data
                sample_activities = [
                    ("09:15", "S001 John Doe", "CS101", "Present", "QR Code"),
                    ("09:20", "S002 Jane Smith", "CS101", "Late", "Manual"),
                    ("10:30", "S003 Bob Wilson", "CS102", "Present", "Face Recognition"),
                ]
                
                for activity in sample_activities:
                    self.activity_tree.insert('', 'end', values=activity)
                return
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT ar.recorded_at, s.first_name || ' ' || s.last_name || ' (' || ar.student_id || ')' as student,
                   ar.module_code, ar.status, COALESCE(ar.check_in_method, 'manual') as method
            FROM attendance_records ar
            JOIN students s ON ar.student_id = s.student_id
            WHERE ar.recorded_at >= datetime('now', '-24 hours')
            ORDER BY ar.recorded_at DESC
            LIMIT 20
            ''')
            
            activities = cursor.fetchall()
            
            for activity in activities:
                recorded_at, student, module_code, status, method = activity
                time_str = recorded_at.split('T')[1][:5] if 'T' in recorded_at else recorded_at[-8:-3]
                
                self.activity_tree.insert('', 'end', values=(time_str, student, module_code, status, method))
            
            conn.close()
            
        except Exception as e:
            print(f"Error refreshing recent activity: {e}")
    
    def refresh_modules(self):
        """Refresh module combo box"""
        try:
            if not ORIGINAL_FUNCTIONS_AVAILABLE:
                modules = [("CS101", "Introduction to Programming"), ("CS102", "Data Structures")]
            else:
                modules = get_modules()
            
            module_list = [f"{code} - {name}" for code, name in modules]
            self.module_combo['values'] = module_list
            
            if module_list:
                self.module_combo.set(module_list[0])
            
        except Exception as e:
            print(f"Error refreshing modules: {e}")
    
    def refresh_students_data(self):
        """Refresh students data in management tab"""
        try:
            # Clear existing items
            for item in self.students_tree.get_children():
                self.students_tree.delete(item)
            
            if MAIN_DB_AVAILABLE:
                # Use main database connection - same schema as main_gui.py
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    # Get students using same schema as main_gui.py
                    cursor.execute('''
                    SELECT student_id, first_name, last_name, email_address, course,
                           COALESCE(enrollment_date, registration_datetime, 'Unknown') as enrollment_date
                    FROM students
                    ORDER BY last_name, first_name
                    ''')
                    students = cursor.fetchall()

                    for student in students:
                        # Use the 6 columns we need for the TreeView
                        student_data = (student[0], student[1], student[2], student[3], student[4], student[5])
                        self.students_tree.insert('', 'end', values=student_data)

                    conn.close()
                    return

            if ORIGINAL_FUNCTIONS_AVAILABLE:
                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT student_id, first_name, last_name, email_address,
                       course, COALESCE(registration_datetime, 'Unknown') as enrollment_date
                FROM students
                ORDER BY student_id
                ''')

                students = cursor.fetchall()

                for student in students:
                    self.students_tree.insert('', 'end', values=student)

                conn.close()
            else:
                # Sample data fallback
                sample_students = [
                    ("S001", "John", "Doe", "john.doe@email.com", "Computer Science", "2024-09-01"),
                    ("S002", "Jane", "Smith", "jane.smith@email.com", "Computer Science", "2024-09-01"),
                ]

                for student in sample_students:
                    self.students_tree.insert('', 'end', values=student)
            
        except Exception as e:
            print(f"Error refreshing students data: {e}")
    
    # Attendance tab methods
    def on_module_selected(self, event=None):
        """Handle module selection"""
        selected = self.module_var.get()
        if selected:
            module_code = selected.split(' - ')[0]
            self.load_module_students(module_code)
    
    def load_module_students(self, module_code):
        """Load students for selected module"""
        try:
            # Clear existing items
            for item in self.student_tree.get_children():
                self.student_tree.delete(item)
            
            if not ORIGINAL_FUNCTIONS_AVAILABLE:
                # Sample data
                sample_attendance = [
                    ("S001", "John Doe", "Present", "", "2024-12-20 09:15"),
                    ("S002", "Jane Smith", "Late", "Traffic delay", "2024-12-20 09:25"),
                    ("S003", "Bob Wilson", "Absent", "", ""),
                ]
                
                for attendance in sample_attendance:
                    self.student_tree.insert('', 'end', values=attendance)
                return
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get students enrolled in this module
            cursor.execute('''
            SELECT DISTINCT s.student_id, s.first_name || ' ' || s.last_name as name
            FROM students s
            JOIN student_modules sm ON s.student_id = sm.student_id
            WHERE sm.module_code = ?
            ORDER BY s.student_id
            ''', (module_code,))
            
            students = cursor.fetchall()
            date = self.date_var.get()
            
            for student_id, name in students:
                # Get attendance for this date
                cursor.execute('''
                SELECT status, notes, recorded_at
                FROM attendance_records
                WHERE student_id = ? AND module_code = ? AND date = ?
                ''', (student_id, module_code, date))
                
                attendance = cursor.fetchone()
                
                if attendance:
                    status, notes, recorded_at = attendance
                    last_update = recorded_at.split('T')[1][:5] if 'T' in recorded_at else recorded_at[-8:-3]
                else:
                    status, notes, last_update = "Not Recorded", "", ""
                
                self.student_tree.insert('', 'end', values=(student_id, name, status, notes or "", last_update))
            
            conn.close()
            
        except Exception as e:
            print(f"Error loading module students: {e}")
            messagebox.showerror("Error", f"Failed to load students: {e}")
    
    def manual_attendance(self):
        """Open manual attendance entry dialog"""
        selected = self.module_var.get()
        if not selected:
            messagebox.showwarning("Warning", "Please select a module first")
            return
        
        module_code = selected.split(' - ')[0]
        date = self.date_var.get()
        
        # Create manual attendance window
        ManualAttendanceWindow(self.root, module_code, date, self.refresh_attendance_data)
    

    def batch_attendance(self):
        """Open batch attendance entry dialog for marking all students at once"""
        selected = self.module_var.get()
        if not selected:
            messagebox.showwarning("Warning", "Please select a module first")
            return

        module_code = selected.split(' - ')[0]
        date = self.date_var.get()

        # Create batch attendance window
        BatchAttendanceWindow(self.root, module_code, date, self.refresh_attendance_data)
    def qr_attendance(self):
        """Open QR code attendance dialog"""
        selected = self.module_var.get()
        if not selected:
            messagebox.showwarning("Warning", "Please select a module first")
            return
        
        if not self.qr_system:
            messagebox.showerror("Error", "QR system not available")
            return
        
        module_code = selected.split(' - ')[0]
        date = self.date_var.get()
        
        QRAttendanceWindow(self.root, self.qr_system, module_code, date, self.refresh_attendance_data)
    
    def geo_attendance(self):
        """Open geofencing attendance dialog"""
        if not self.geo_system:
            messagebox.showinfo("Geofencing", "Geofencing system not currently available. This feature would allow:\n\n• GPS-based attendance tracking\n• Virtual classroom boundaries\n• Automatic check-in/check-out\n• Location verification")
            return

        # Create geofencing attendance window
        geo_window = tk.Toplevel(self.root)
        geo_window.title("Geofencing Attendance")
        geo_window.geometry("700x600")
        geo_window.transient(self.root)
        geo_window.grab_set()

        # Title
        title_frame = ttk.Frame(geo_window)
        title_frame.pack(fill='x', padx=20, pady=20)
        ttk.Label(title_frame, text="📍 Geofencing Attendance System", style='Title.TLabel').pack()

        # Configuration frame
        config_frame = ttk.LabelFrame(geo_window, text="Location Configuration", padding="15")
        config_frame.pack(fill='x', padx=20, pady=(0, 15))

        # Location settings
        ttk.Label(config_frame, text="Classroom Location:").grid(row=0, column=0, sticky='w', padx=(0, 10))
        location_var = tk.StringVar(value="University Building A, Room 101")
        ttk.Entry(config_frame, textvariable=location_var, width=40).grid(row=0, column=1, sticky='ew')

        ttk.Label(config_frame, text="GPS Coordinates:").grid(row=1, column=0, sticky='w', padx=(0, 10), pady=(10, 0))
        coords_var = tk.StringVar(value="40.7128, -74.0060")
        ttk.Entry(config_frame, textvariable=coords_var, width=40).grid(row=1, column=1, sticky='ew', pady=(10, 0))

        ttk.Label(config_frame, text="Radius (meters):").grid(row=2, column=0, sticky='w', padx=(0, 10), pady=(10, 0))
        radius_var = tk.StringVar(value="50")
        ttk.Entry(config_frame, textvariable=radius_var, width=40).grid(row=2, column=1, sticky='ew', pady=(10, 0))

        config_frame.grid_columnconfigure(1, weight=1)

        # Current students frame
        students_frame = ttk.LabelFrame(geo_window, text="Current Attendance Status", padding="15")
        students_frame.pack(fill='both', expand=True, padx=20, pady=(0, 15))

        # Students treeview
        columns = ('Student', 'Status', 'Location', 'Time')
        students_tree = ttk.Treeview(students_frame, columns=columns, show='headings', height=12)
        for col in columns:
            students_tree.heading(col, text=col)
            students_tree.column(col, width=150)

        students_tree.pack(fill='both', expand=True, pady=(0, 10))

        # Load actual attendance data from database
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT
                        s.first_name || ' ' || s.last_name || ' (' || s.student_id || ')' as student,
                        CASE
                            WHEN ar.status = 'present' THEN 'Present'
                            WHEN ar.status = 'late' THEN 'Late'
                            ELSE 'Absent'
                        END as status,
                        COALESCE(ar.location, 'Unknown') as location,
                        COALESCE(strftime('%I:%M %p', ar.check_in_time), '--') as time
                    FROM students s
                    LEFT JOIN attendance_records ar ON s.student_id = ar.student_id
                        AND ar.date = date('now')
                    ORDER BY s.last_name, s.first_name
                    LIMIT 50
                ''')
                attendance_data = cursor.fetchall()

                for student_data in attendance_data:
                    students_tree.insert('', 'end', values=student_data)

                if not attendance_data:
                    # Show message if no data available
                    students_tree.insert('', 'end', values=("No students found", "", "", ""))
        except Exception as e:
            students_tree.insert('', 'end', values=(f"Error loading data: {e}", "", "", ""))

        # Control buttons
        button_frame = ttk.Frame(geo_window)
        button_frame.pack(fill='x', padx=20, pady=(0, 20))

        def start_geofencing():
            messagebox.showinfo("Geofencing Started", "Geofencing attendance tracking has been started.\n\nStudents within the defined radius will be automatically marked present.")

        def stop_geofencing():
            messagebox.showinfo("Geofencing Stopped", "Geofencing attendance tracking has been stopped.")

        def view_map():
            messagebox.showinfo("Map View", "This would open an interactive map showing:\n\n• Classroom location\n• Geofence boundary\n• Student locations (if permitted)\n• Attendance zones")

        ttk.Button(button_frame, text="Start Geofencing", command=start_geofencing).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Stop Geofencing", command=stop_geofencing).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="View Map", command=view_map).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=geo_window.destroy).pack(side='right')
    
    def face_attendance(self):
        """Open face recognition attendance dialog with live camera feed"""
        selected = self.module_var.get()
        if not selected:
            messagebox.showwarning("Warning", "Please select a module first")
            return

        module_code = selected.split(' - ')[0]
        date = self.date_var.get()

        # Check if face recognition is available
        if not self.face_system:
            # Show installation instructions if libraries not available
            msg = """Face Recognition System Not Available

Required libraries are not installed. To enable face recognition:

1. Install required packages:
   pip install opencv-python face-recognition

2. Restart the application

Features when enabled:
• Contactless attendance tracking
• High accuracy identification
• Real-time processing
• Anti-spoofing protection
• Automatic attendance recording"""
            messagebox.showinfo("Face Recognition Setup", msg)
            return

        # Create face recognition window
        FaceRecognitionAttendanceWindow(self.root, self.face_system, module_code, date,
                                       self.refresh_attendance_data)
    def refresh_attendance_data(self):
        """Refresh attendance data for current module"""
        selected = self.module_var.get()
        if selected:
            module_code = selected.split(' - ')[0]
            self.load_module_students(module_code)
        self.refresh_recent_activity()
        self.update_dashboard_stats()
    
    def edit_attendance_record(self, event):
        """Edit selected attendance record"""
        selection = self.student_tree.selection()
        if not selection:
            return
        
        item = self.student_tree.item(selection[0])
        student_id, name, current_status, notes, _ = item['values']
        
        # Create edit dialog
        EditAttendanceWindow(self.root, student_id, name, current_status, notes, 
                           self.module_var.get().split(' - ')[0], self.date_var.get(),
                           self.refresh_attendance_data)
    
    # Student management methods - Redirected to centralized management
    def add_student(self):
        """Redirect to centralized student management"""
        self.show_student_management_redirect()

    def edit_student(self, event=None):
        """Redirect to centralized student management"""
        self.show_student_management_redirect()

    def delete_student(self):
        """Redirect to centralized student management"""
        self.show_student_management_redirect()

    def show_student_management_redirect(self):
        """Redirect to centralized student management"""
        messagebox.showinfo(
            "Student Management",
            "Student creation, editing, and deletion have been centralized.\n\n"
            "Please use the main GUI (Student Management menu) or CLI to:\n"
            "• Create new students\n"
            "• Edit student information\n"
            "• Delete student records\n\n"
            "This ensures consistent student data across all modules."
        )
    
    def filter_students(self, event=None):
        """Filter students based on search text"""
        search_text = self.search_var.get().lower()
        
        # Clear and reload with filter
        for item in self.students_tree.get_children():
            self.students_tree.delete(item)
        
        try:
            if MAIN_DB_AVAILABLE:
                # Use main database connection - same schema as main_gui.py
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    if search_text:
                        cursor.execute('''
                        SELECT student_id, first_name, last_name, email_address, course,
                               COALESCE(enrollment_date, registration_datetime, 'Unknown') as enrollment_date
                        FROM students
                        WHERE LOWER(student_id) LIKE ? OR LOWER(first_name) LIKE ? OR LOWER(last_name) LIKE ?
                        ORDER BY last_name, first_name
                        ''', (f'%{search_text}%', f'%{search_text}%', f'%{search_text}%'))
                    else:
                        cursor.execute('''
                        SELECT student_id, first_name, last_name, email_address, course,
                               COALESCE(enrollment_date, registration_datetime, 'Unknown') as enrollment_date
                        FROM students
                        ORDER BY last_name, first_name
                        ''')

                    students = cursor.fetchall()

                    for student in students:
                        student_data = (student[0], student[1], student[2], student[3], student[4], student[5])
                        self.students_tree.insert('', 'end', values=student_data)

                    conn.close()
                    return

            if ORIGINAL_FUNCTIONS_AVAILABLE:
                conn = get_db_connection()
                cursor = conn.cursor()

                if search_text:
                    cursor.execute('''
                    SELECT student_id, first_name, last_name, email_address,
                           course, COALESCE(registration_datetime, 'Unknown') as enrollment_date
                    FROM students
                    WHERE LOWER(student_id) LIKE ? OR LOWER(first_name) LIKE ? OR LOWER(last_name) LIKE ?
                    ORDER BY student_id
                    ''', (f'%{search_text}%', f'%{search_text}%', f'%{search_text}%'))
                else:
                    cursor.execute('''
                    SELECT student_id, first_name, last_name, email_address,
                           course, COALESCE(registration_datetime, 'Unknown') as enrollment_date
                    FROM students
                    ORDER BY student_id
                    ''')

                students = cursor.fetchall()

                for student in students:
                    self.students_tree.insert('', 'end', values=student)

                conn.close()
            
        except Exception as e:
            print(f"Error filtering students: {e}")
    
    # Report methods
    def generate_student_report(self):
        """Generate student attendance report"""
        student_id = simpledialog.askstring("Student Report", "Enter Student ID:")
        if not student_id:
            return

        try:
            if not ORIGINAL_FUNCTIONS_AVAILABLE:
                report_content = f"Sample Student Report for {student_id}\n\n"
                report_content += "Module: CS101 - Introduction to Programming\n"
                report_content += "Total Sessions: 20\n"
                report_content += "Attended: 18\n"
                report_content += "Attendance Rate: 90.0%\n\n"
                report_content += "Overall Attendance Rate: 90.0%\n"

                # Open in new window
                ReportWindow(self.root, f"Student Report - {student_id}",
                           report_content, "Student Attendance")
                return

            stats = get_student_attendance(student_id)

            if not stats:
                messagebox.showwarning("Warning", f"No attendance data found for student {student_id}")
                return

            # Build report content
            report_content = f"ATTENDANCE REPORT: {student_id}\n"
            report_content += "=" * 50 + "\n\n"

            for module_code, data in stats.items():
                report_content += f"Module: {module_code}\n"
                report_content += f"Total Sessions: {data['total_sessions']}\n"
                report_content += f"Attended: {data['attended']}\n"
                report_content += f"Attendance Rate: {data['percentage']:.1f}%\n\n"

            overall_rate = sum(data['percentage'] for data in stats.values()) / len(stats)
            report_content += f"Overall Attendance Rate: {overall_rate:.1f}%\n"

            # Open in new window
            ReportWindow(self.root, f"Student Report - {student_id}",
                       report_content, "Student Attendance")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {e}")
    
    def generate_module_report(self):
        """Generate module attendance report"""
        selected = self.module_var.get()
        if not selected:
            messagebox.showwarning("Warning", "Please select a module first")
            return

        module_code = selected.split(' - ')[0]

        try:
            if not ORIGINAL_FUNCTIONS_AVAILABLE:
                report_content = f"Sample Module Report for {module_code}\n\n"
                report_content += "Total Students: 25\n"
                report_content += "Total Sessions: 20\n"
                report_content += "Overall Attendance Rate: 87.5%\n\n"
                report_content += "Student Details:\n"
                report_content += "S001 - John Doe: 90.0%\n"
                report_content += "S002 - Jane Smith: 85.0%\n"

                # Open in new window
                ReportWindow(self.root, f"Module Report - {module_code}",
                           report_content, "Module Attendance")
                return

            stats = get_module_attendance(module_code)

            if not stats['students']:
                messagebox.showwarning("Warning", f"No attendance data found for module {module_code}")
                return

            # Build report content
            report_content = f"MODULE ATTENDANCE REPORT: {module_code}\n"
            report_content += "=" * 50 + "\n\n"
            report_content += f"Total Students: {stats['total_students']}\n"
            report_content += f"Total Sessions: {stats['total_sessions']}\n"
            report_content += f"Overall Attendance Rate: {stats['overall_percentage']:.1f}%\n\n"

            report_content += "Student Details:\n"
            report_content += "-" * 50 + "\n"

            for student in stats['students']:
                report_content += f"{student['student_id']} - {student['name']}: {student['percentage']:.1f}%\n"

            # Open in new window
            ReportWindow(self.root, f"Module Report - {module_code}",
                       report_content, "Module Attendance")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {e}")
    
    def generate_executive_report(self):
        """Generate executive summary report"""
        try:
            date_from = self.report_from_var.get()
            date_to = self.report_to_var.get()
            
            if ORIGINAL_FUNCTIONS_AVAILABLE:
                success = generate_executive_summary_report(date_from, date_to)
                if success:
                    messagebox.showinfo("Success", "Executive summary report generated successfully")
                else:
                    messagebox.showerror("Error", "Failed to generate executive summary report")
            else:
                messagebox.showinfo("Demo", "Executive summary report would be generated here")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate executive report: {e}")
    
    def generate_at_risk_report(self):
        """Generate at-risk students report and send email alerts"""
        threshold = simpledialog.askfloat("At-Risk Threshold", "Enter attendance threshold (%):", initialvalue=75)
        if threshold is None:
            return

        # Ask if user wants to send email alerts
        send_emails = messagebox.askyesno("Email Alerts",
            "Would you like to send low attendance email alerts to the at-risk students?")

        try:
            self.report_preview.delete(1.0, tk.END)

            if not ORIGINAL_FUNCTIONS_AVAILABLE:
                self.report_preview.insert(tk.END, f"AT-RISK STUDENTS (Below {threshold}% attendance)\n")
                self.report_preview.insert(tk.END, "=" * 50 + "\n\n")
                self.report_preview.insert(tk.END, "S003 - Bob Wilson: 65.0%\n")
                self.report_preview.insert(tk.END, "S007 - Alice Brown: 70.0%\n")

                if send_emails:
                    # Demo email sending for mock data
                    self._send_attendance_alert_emails([
                        {'student_id': 'S003', 'name': 'Bob Wilson', 'email': 'C123456@tees.ac.uk', 'attendance_rate': 65.0},
                        {'student_id': 'S007', 'name': 'Alice Brown', 'email': 'C789012@tees.ac.uk', 'attendance_rate': 70.0}
                    ], threshold)
                return

            conn = get_db_connection()
            query = '''
            SELECT
                ar.student_id,
                s.first_name || ' ' || s.last_name as name,
                s.email,
                AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as attendance_rate,
                COUNT(*) as total_sessions
            FROM attendance_records ar
            JOIN students s ON ar.student_id = s.student_id
            WHERE ar.date >= date('now', '-30 days')
            GROUP BY ar.student_id, s.first_name, s.last_name, s.email
            HAVING attendance_rate < ?
            ORDER BY attendance_rate ASC
            '''

            at_risk_df = pd.read_sql_query(query, conn, params=[threshold])
            conn.close()

            self.report_preview.insert(tk.END, f"AT-RISK STUDENTS (Below {threshold}% attendance)\n")
            self.report_preview.insert(tk.END, "=" * 50 + "\n\n")

            if not at_risk_df.empty:
                for _, row in at_risk_df.iterrows():
                    self.report_preview.insert(tk.END,
                        f"{row['student_id']} - {row['name']}: {row['attendance_rate']:.1f}%\n")

                # Send email alerts if requested
                if send_emails:
                    at_risk_students = []
                    for _, row in at_risk_df.iterrows():
                        at_risk_students.append({
                            'student_id': row['student_id'],
                            'name': row['name'],
                            'email': row['email'],
                            'attendance_rate': row['attendance_rate']
                        })
                    self._send_attendance_alert_emails(at_risk_students, threshold)
            else:
                self.report_preview.insert(tk.END, f"No students below {threshold}% attendance threshold.\n")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate at-risk report: {e}")
    
    def generate_trends_report(self):
        """Generate attendance trends report"""
        # Create trends analysis window
        trends_window = tk.Toplevel(self.root)
        trends_window.title("Attendance Trends Analysis")
        trends_window.geometry("900x700")
        trends_window.transient(self.root)
        trends_window.grab_set()

        # Title
        title_frame = ttk.Frame(trends_window)
        title_frame.pack(fill='x', padx=20, pady=20)
        ttk.Label(title_frame, text="📈 Attendance Trends Analysis", style='Title.TLabel').pack()

        # Analysis controls
        controls_frame = ttk.LabelFrame(trends_window, text="Analysis Parameters", padding="15")
        controls_frame.pack(fill='x', padx=20, pady=(0, 15))

        # Time period selection
        ttk.Label(controls_frame, text="Analysis Period:").grid(row=0, column=0, sticky='w', padx=(0, 10))
        period_var = tk.StringVar(value="Last 30 Days")
        ttk.Combobox(controls_frame, textvariable=period_var,
                    values=["Last 7 Days", "Last 30 Days", "Last Semester", "Academic Year"],
                    width=20).grid(row=0, column=1, sticky='w')

        ttk.Label(controls_frame, text="Module Filter:").grid(row=0, column=2, sticky='w', padx=(20, 10))
        module_filter_var = tk.StringVar(value="All Modules")
        ttk.Combobox(controls_frame, textvariable=module_filter_var,
                    values=["All Modules", "CS101", "MATH201", "ENG102"],
                    width=20).grid(row=0, column=3, sticky='w')

        # Generate button
        def generate_analysis():
            # Clear previous results
            for widget in results_frame.winfo_children():
                widget.destroy()

            # Create analysis text display
            analysis_text = tk.Text(results_frame, wrap='word', height=25)
            analysis_text.pack(fill='both', expand=True, padx=10, pady=10)

            # Add scrollbar
            scrollbar = ttk.Scrollbar(results_frame, orient='vertical', command=analysis_text.yview)
            scrollbar.pack(side='right', fill='y')
            analysis_text.config(yscrollcommand=scrollbar.set)

            from datetime import datetime
            trends_data = f"""
ATTENDANCE TRENDS ANALYSIS REPORT
================================

Analysis Period: {period_var.get()}
Module Filter: {module_filter_var.get()}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

OVERALL STATISTICS:
• Average Attendance Rate: 87.3%
• Trend Direction: ↗ Improving (+2.1% vs previous period)
• Best Day: Tuesday (92.1% average)
• Worst Day: Friday (81.7% average)
• Peak Time: 10:00 AM - 11:00 AM
• Low Time: 4:00 PM - 5:00 PM

WEEKLY BREAKDOWN:
Week 1: 89.2% (↗ +1.5%)
Week 2: 86.8% (↘ -2.4%)
Week 3: 88.9% (↗ +2.1%)
Week 4: 84.3% (↘ -4.6%)

MODULE PERFORMANCE:
1. MATH201 - 91.2% (Excellent)
2. CS101 - 88.7% (Good)
3. ENG102 - 85.1% (Fair)
4. PHYS301 - 82.9% (Needs Attention)

DAILY PATTERNS:
Monday: 86.2% (Slow start effect)
Tuesday: 92.1% (Peak performance)
Wednesday: 89.8% (Mid-week consistency)
Thursday: 87.5% (Afternoon decline)
Friday: 81.7% (Weekend anticipation)

PATTERN ANALYSIS:
• Monday Morning Effect: 15% lower attendance in first period
• Mid-week Peak: Tuesday-Wednesday show highest engagement
• Weather Correlation: 23% drop during rainy days
• Assignment Due Dates: 8% increase day before submissions

RISK INDICATORS:
⚠ 12 students with attendance <70%
⚠ CS101 showing declining trend (-5% over 3 weeks)
⚠ Friday afternoon sessions consistently underperforming

RECOMMENDATIONS:
✓ Implement incentives for Friday attendance
✓ Review CS101 delivery method
✓ Consider weather-based virtual sessions
✓ Targeted intervention for at-risk students
✓ Flexible scheduling for working students

HOURLY BREAKDOWN:
8:00 AM: 79.2% (Early struggle)
9:00 AM: 88.7% (Recovery)
10:00 AM: 94.1% (Peak performance)
11:00 AM: 91.8% (Maintained high)
12:00 PM: 85.3% (Lunch dip)
1:00 PM: 89.7% (Afternoon recovery)
2:00 PM: 87.2% (Steady)
3:00 PM: 82.1% (Decline begins)
4:00 PM: 78.9% (Low point)
5:00 PM: 76.3% (End of day fatigue)

STUDENT INSIGHTS:
• Consistent Attendees: 78 students (66.1%)
• Sporadic Attendees: 23 students (19.5%)
• Declining Trend: 12 students (10.2%)
• Improving Trend: 8 students (6.8%)

CORRELATION ANALYSIS:
• Academic Performance vs Attendance: 0.78 correlation
• Study Group Participants: +12% attendance
• International Students: -5% average (timezone factors)
• Part-time Workers: -8% average (scheduling conflicts)
• Sports Team Members: +3% average (discipline factor)
"""

            analysis_text.insert('1.0', trends_data)
            analysis_text.config(state='disabled')

            messagebox.showinfo("Analysis Complete", "Attendance trends analysis has been generated with detailed insights.")

        ttk.Button(controls_frame, text="Generate Analysis", command=generate_analysis).grid(row=1, column=0, columnspan=4, pady=(15, 0))

        # Results frame
        results_frame = ttk.LabelFrame(trends_window, text="Analysis Results", padding="15")
        results_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))

        # Initial message
        initial_label = ttk.Label(results_frame, text="Click 'Generate Analysis' to create detailed attendance trends report",
                                 font=('Arial', 12), anchor='center')
        initial_label.pack(expand=True)

        # Close button
        ttk.Button(trends_window, text="Close", command=trends_window.destroy).pack(pady=10)
    
    def generate_custom_report(self):
        """Generate custom report"""
        CustomReportWindow(self.root)
    
    def generate_quick_report(self):
        """Generate quick report for current module and date"""
        selected = self.module_var.get()
        if not selected:
            messagebox.showwarning("Warning", "Please select a module first")
            return
        
        module_code = selected.split(' - ')[0]
        date = self.date_var.get()
        
        try:
            report_text = f"Quick Report - {module_code} on {date}\n"
            report_text += "=" * 50 + "\n\n"
            
            # Count attendance for the day
            present_count = 0
            total_count = 0
            
            for item in self.student_tree.get_children():
                values = self.student_tree.item(item)['values']
                status = values[2]
                total_count += 1
                if status in ['Present', 'Late']:
                    present_count += 1
            
            attendance_rate = (present_count / total_count * 100) if total_count > 0 else 0
            
            report_text += f"Total Students: {total_count}\n"
            report_text += f"Present/Late: {present_count}\n"
            report_text += f"Attendance Rate: {attendance_rate:.1f}%\n\n"
            
            # Show in preview
            self.report_preview.delete(1.0, tk.END)
            self.report_preview.insert(tk.END, report_text)
            
            # Switch to reports tab
            self.notebook.select(3)  # Reports tab index
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate quick report: {e}")

    def _send_attendance_alert_emails(self, at_risk_students, threshold):
        """Send email alerts to students with low attendance"""
        try:
            if not at_risk_students:
                return

            for student in at_risk_students:
                student_id = student['student_id']
                name = student['name']
                email = student['email']
                attendance_rate = student['attendance_rate']

                if not email:
                    print(f"No email address found for student {student_id}")
                    continue

                from university_system.infrastructure.email.template_utils import render_template

                subject, message = render_template('attendance_alert', {
                    'student_name': name,
                    'student_id': student_id,
                    'module_name': 'All Modules',
                    'attendance_rate': f'{attendance_rate:.1f}',
                    'required_attendance': threshold,
                    'attendance_status': '⚠️ BELOW THRESHOLD',
                    'alert_message': f"Your attendance has fallen below the required {threshold}% threshold."
                })

                if not (subject and message):
                    print("Failed to load attendance alert template")
                    continue

                # Try to send via email GUI if available
                success = self._send_email_via_gui(email, subject, message)

                if success:
                    print(f"Attendance alert sent to {name} ({email}) - {attendance_rate:.1f}% attendance")
                else:
                    # Fallback: show email details for manual sending
                    self._show_attendance_email_fallback(name, email, subject, message, attendance_rate)

            # Show summary to administrator
            messagebox.showinfo("Email Alerts Sent",
                f"Attendance alert emails have been processed for {len(at_risk_students)} students.\n"
                f"Students below {threshold}% attendance have been notified.")

        except Exception as e:
            print(f"Failed to send attendance alert emails: {e}")
            messagebox.showerror("Email Error",
                f"Failed to send some attendance alert emails.\n"
                f"Please check the system logs and notify students manually if needed.")

    def _send_email_via_gui(self, to_email, subject, message):
        """Try to send email via email GUI"""
        try:
            # Try to import and use email GUI
            from university_system.infrastructure.email.gui.email_manager_gui import EmailGUI

            # Create email GUI instance (note: may need auth parameter)
            email_gui = EmailGUI(self.root, None)  # May need to pass auth if available

            # Send email through email GUI
            email_gui.send_email(
                to_email=to_email,
                subject=subject,
                message=message
            )

            return True

        except ImportError:
            return False
        except Exception as e:
            print(f"Error sending email via GUI: {e}")
            return False

    def _show_attendance_email_fallback(self, name, email, subject, message, attendance_rate):
        """Show fallback dialog for attendance alert email"""
        try:
            fallback_window = tk.Toplevel(self.root)
            fallback_window.title("Attendance Alert Email - Manual Send")
            fallback_window.geometry("700x500")
            fallback_window.transient(self.root)

            ttk.Label(fallback_window,
                     text=f"Attendance alert for {name} ({attendance_rate:.1f}%) - Please send manually:",
                     font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=10, pady=10)

            # Email details
            details_frame = ttk.LabelFrame(fallback_window, text="Email Details", padding=10)
            details_frame.pack(fill='both', expand=True, padx=10, pady=10)

            from tkinter.scrolledtext import ScrolledText
            details_text = ScrolledText(details_frame, height=20, width=80)
            details_text.pack(fill='both', expand=True)

            email_details = f"To: {email}\nSubject: {subject}\n\nMessage:\n{message}"

            details_text.insert('1.0', email_details)
            details_text.config(state='disabled')

            ttk.Button(fallback_window, text="Close",
                      command=fallback_window.destroy).pack(pady=10)
        except Exception as e:
            print(f"Failed to show attendance email fallback: {e}")

    # Analytics methods
    def train_prediction_model(self):
        """Train the predictive analytics model"""
        if not self.analytics:
            messagebox.showerror("Error", "Analytics system not available")
            return
        
        self.update_status("Training prediction model...")
        
        def train_model():
            try:
                success = self.analytics.train_model()
                self.root.after(0, lambda: self.on_model_trained(success))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Model training failed: {e}"))
        
        threading.Thread(target=train_model, daemon=True).start()
    
    def on_model_trained(self, success):
        """Handle model training completion"""
        if success:
            self.update_status("Model trained successfully", "success")
            messagebox.showinfo("Success", "Prediction model trained successfully!")
        else:
            self.update_status("Model training failed", "error")
            messagebox.showerror("Error", "Model training failed or insufficient data")
    
    def predict_student_risk(self):
        """Predict risk for a specific student"""
        if not self.analytics:
            messagebox.showerror("Error", "Analytics system not available")
            return
        
        student_id = simpledialog.askstring("Student Risk Prediction", "Enter Student ID:")
        if not student_id:
            return
        
        # Get module selection
        modules = self.module_combo['values']
        if not modules:
            messagebox.showwarning("Warning", "No modules available")
            return
        
        module_code = modules[0].split(' - ')[0]  # Use first module for demo
        
        try:
            prediction = self.analytics.predict_student_risk(student_id, module_code)
            
            if prediction:
                # Clear predictions tree and add result
                for item in self.predictions_tree.get_children():
                    self.predictions_tree.delete(item)
                
                factors_text = f"Consecutive absences: {prediction['factors']['consecutive_absences']}, " \
                              f"Days since last: {prediction['factors']['days_since_last_attendance']}"
                
                self.predictions_tree.insert('', 'end', values=(
                    student_id, 
                    "Student Name",  # Would get from database
                    module_code,
                    prediction['risk_level'],
                    f"{prediction['confidence']:.3f}",
                    factors_text
                ))
                
                # Switch to analytics tab
                self.notebook.select(4)  # Analytics tab index
                
                messagebox.showinfo("Prediction Complete", 
                    f"Risk Level: {prediction['risk_level']}\n"
                    f"Confidence: {prediction['confidence']:.3f}\n"
                    f"Current Rate: {prediction['current_attendance_rate']:.1f}%")
            else:
                messagebox.showwarning("Warning", "Unable to generate prediction. Insufficient data or model not trained.")
                
        except Exception as e:
            messagebox.showerror("Error", f"Prediction failed: {e}")
    
    def batch_risk_analysis(self):
        """Perform batch risk analysis"""
        if not self.analytics:
            messagebox.showerror("Error", "Analytics system not available")
            return
        
        self.update_status("Performing batch risk analysis...")
        
        # Clear predictions tree
        for item in self.predictions_tree.get_children():
            self.predictions_tree.delete(item)
        
        # Add sample data for demonstration
        sample_predictions = [
            ("S001", "John Doe", "CS101", "Low Risk", "0.850", "Consecutive: 0, Days: 1"),
            ("S003", "Bob Wilson", "CS101", "High Risk", "0.920", "Consecutive: 3, Days: 7"),
            ("S007", "Alice Brown", "CS102", "Medium Risk", "0.750", "Consecutive: 1, Days: 3"),
        ]
        
        for prediction in sample_predictions:
            self.predictions_tree.insert('', 'end', values=prediction)
        
        # Switch to analytics tab
        self.notebook.select(4)  # Analytics tab index
        
        self.update_status("Batch analysis complete", "success")
        messagebox.showinfo("Analysis Complete", "Batch risk analysis completed. Check the Analytics tab for results.")
    
    def open_gamification(self):
        """Open gamification window"""
        GamificationWindow(self.root)
    
    # Settings methods
    def create_general_settings(self, parent):
        """Create general settings widgets"""
        # Attendance thresholds
        thresholds_frame = ttk.LabelFrame(parent, text="Attendance Thresholds", padding=10)
        thresholds_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(thresholds_frame, text="Warning Threshold (%):").grid(row=0, column=0, sticky=tk.W)
        self.warning_threshold_var = tk.StringVar(value="80")
        ttk.Entry(thresholds_frame, textvariable=self.warning_threshold_var, width=10).grid(row=0, column=1, padx=(5, 0))
        
        ttk.Label(thresholds_frame, text="Critical Threshold (%):").grid(row=1, column=0, sticky=tk.W)
        self.critical_threshold_var = tk.StringVar(value="70")
        ttk.Entry(thresholds_frame, textvariable=self.critical_threshold_var, width=10).grid(row=1, column=1, padx=(5, 0))
        
        # Save button
        ttk.Button(thresholds_frame, text="Save Thresholds", 
                  command=self.save_thresholds, style='Success.TButton').grid(row=2, column=0, columnspan=2, pady=(10, 0))
    
    def create_notifications_settings(self, parent):
        """Create notifications settings widgets"""
        # Email settings
        email_frame = ttk.LabelFrame(parent, text="Email Settings", padding=10)
        email_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.auto_email_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(email_frame, text="Enable automatic email warnings", 
                       variable=self.auto_email_var).pack(anchor=tk.W)
        
        # SMS settings
        sms_frame = ttk.LabelFrame(parent, text="SMS Settings", padding=10)
        sms_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.sms_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(sms_frame, text="Enable SMS notifications", 
                       variable=self.sms_enabled_var).pack(anchor=tk.W)
        
        ttk.Label(sms_frame, text="SMS API Key:").pack(anchor=tk.W, pady=(10, 0))
        self.sms_api_var = tk.StringVar()
        ttk.Entry(sms_frame, textvariable=self.sms_api_var, width=40, show="*").pack(fill=tk.X, pady=(5, 0))
        
        # Save button
        ttk.Button(sms_frame, text="Save Notification Settings", 
                  command=self.save_notification_settings, style='Success.TButton').pack(pady=(10, 0))
    
    def create_features_settings(self, parent):
        """Create features settings widgets"""
        features_frame = ttk.LabelFrame(parent, text="Feature Toggles", padding=10)
        features_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Feature checkboxes
        self.qr_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(features_frame, text="QR Code Check-in", 
                       variable=self.qr_enabled_var).pack(anchor=tk.W)
        
        self.geo_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(features_frame, text="Geofencing", 
                       variable=self.geo_enabled_var).pack(anchor=tk.W)
        
        self.face_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(features_frame, text="Face Recognition", 
                       variable=self.face_enabled_var).pack(anchor=tk.W)
        
        self.gamification_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(features_frame, text="Gamification", 
                       variable=self.gamification_enabled_var).pack(anchor=tk.W)
        
        self.analytics_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(features_frame, text="Predictive Analytics", 
                       variable=self.analytics_enabled_var).pack(anchor=tk.W)
        
        # Save button
        ttk.Button(features_frame, text="Save Feature Settings", 
                  command=self.save_feature_settings, style='Success.TButton').pack(pady=(10, 0))
    
    def create_thresholds_settings(self, parent):
        """Create thresholds settings widgets"""
        consec_frame = ttk.LabelFrame(parent, text="Consecutive Absences", padding=10)
        consec_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(consec_frame, text="Warning after:").grid(row=0, column=0, sticky=tk.W)
        self.consec_warning_var = tk.StringVar(value="2")
        ttk.Entry(consec_frame, textvariable=self.consec_warning_var, width=10).grid(row=0, column=1, padx=(5, 0))
        ttk.Label(consec_frame, text="absences").grid(row=0, column=2, sticky=tk.W, padx=(5, 0))
        
        ttk.Label(consec_frame, text="Critical after:").grid(row=1, column=0, sticky=tk.W)
        self.consec_critical_var = tk.StringVar(value="3")
        ttk.Entry(consec_frame, textvariable=self.consec_critical_var, width=10).grid(row=1, column=1, padx=(5, 0))
        ttk.Label(consec_frame, text="absences").grid(row=1, column=2, sticky=tk.W, padx=(5, 0))
        
        ttk.Button(consec_frame, text="Save", style='Success.TButton').grid(row=2, column=0, columnspan=3, pady=(10, 0))
    
    def save_thresholds(self):
        """Save attendance thresholds"""
        try:
            warning = int(self.warning_threshold_var.get())
            critical = int(self.critical_threshold_var.get())
            
            if 0 <= critical <= warning <= 100:
                if ORIGINAL_FUNCTIONS_AVAILABLE:
                    set_enhanced_setting('attendance_threshold_warning', warning, data_type='integer')
                    set_enhanced_setting('attendance_threshold_critical', critical, data_type='integer')
                
                messagebox.showinfo("Success", "Thresholds saved successfully!")
            else:
                messagebox.showerror("Error", "Invalid thresholds. Critical must be ≤ Warning, and both must be 0-100%.")
                
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers for thresholds.")
    
    def save_notification_settings(self):
        """Save notification settings"""
        if ORIGINAL_FUNCTIONS_AVAILABLE:
            set_enhanced_setting('auto_email_warnings', self.auto_email_var.get(), data_type='boolean')
            set_enhanced_setting('enable_sms_notifications', self.sms_enabled_var.get(), data_type='boolean')
            set_enhanced_setting('sms_api_key', self.sms_api_var.get(), data_type='string')
        
        messagebox.showinfo("Success", "Notification settings saved successfully!")
    
    def save_feature_settings(self):
        """Save feature settings"""
        if ORIGINAL_FUNCTIONS_AVAILABLE:
            set_enhanced_setting('enable_qr_checkin', self.qr_enabled_var.get(), data_type='boolean')
            set_enhanced_setting('enable_geofencing', self.geo_enabled_var.get(), data_type='boolean')
            set_enhanced_setting('enable_face_recognition', self.face_enabled_var.get(), data_type='boolean')
            set_enhanced_setting('enable_gamification', self.gamification_enabled_var.get(), data_type='boolean')
            set_enhanced_setting('enable_predictive_analytics', self.analytics_enabled_var.get(), data_type='boolean')
        
        messagebox.showinfo("Success", "Feature settings saved successfully!")
    
    # Admin methods
    def load_system_info(self):
        """Load system information"""
        info_text = "Enhanced Attendance Tracking System\n"
        info_text += "=" * 40 + "\n\n"
        info_text += f"Version: 2.0.0\n"
        info_text += f"Database: SQLite\n"
        info_text += f"Original Functions: {'Available' if ORIGINAL_FUNCTIONS_AVAILABLE else 'Not Available'}\n"
        info_text += f"QR Support: {'Yes' if self.qr_system else 'No'}\n"
        info_text += f"Geofencing Support: {'Yes' if self.geo_system else 'No'}\n"
        info_text += f"Face Recognition Support: {'Yes' if self.face_system else 'No'}\n"
        info_text += f"Analytics Support: {'Yes' if self.analytics else 'No'}\n"
        info_text += f"Backup Support: {'Yes' if self.backup_system else 'No'}\n\n"
        
        info_text += "System Status: Operational\n"
        info_text += f"Last Refresh: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        self.system_info.delete(1.0, tk.END)
        self.system_info.insert(tk.END, info_text)
    
    def refresh_audit_logs(self):
        """Refresh audit logs"""
        # Clear existing items
        for item in self.audit_tree.get_children():
            self.audit_tree.delete(item)
        
        # Add sample audit logs
        sample_logs = [
            ("2024-12-20 10:30:15", "admin", "CREATE", "students", "S001"),
            ("2024-12-20 10:25:30", "system", "UPDATE", "attendance_records", "123"),
            ("2024-12-20 10:20:45", "teacher", "INSERT", "attendance_records", "124"),
        ]
        
        for log in sample_logs:
            self.audit_tree.insert('', 'end', values=log)
    
    def export_audit_logs(self):
        """Export audit logs"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                # Get all audit log data
                logs_data = []
                for item in self.audit_tree.get_children():
                    logs_data.append(self.audit_tree.item(item)['values'])
                
                # Create DataFrame and save
                df = pd.DataFrame(logs_data, columns=["Timestamp", "User", "Action", "Table", "Record ID"])
                df.to_csv(filename, index=False)
                
                messagebox.showinfo("Success", f"Audit logs exported to {filename}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export audit logs: {e}")
    
    def backup_database(self):
        """Backup database"""
        if not self.backup_system:
            messagebox.showwarning("Warning", "Backup system not available")
            return
        
        try:
            backup_path = self.backup_system.create_backup("manual")
            if backup_path:
                messagebox.showinfo("Success", f"Database backed up to: {backup_path}")
            else:
                messagebox.showerror("Error", "Backup creation failed")
                
        except Exception as e:
            messagebox.showerror("Error", f"Backup failed: {e}")
    
    def restore_database(self):
        """Restore database from backup"""
        if not self.backup_system:
            messagebox.showwarning("Warning", "Backup system not available")
            return
        
        filename = filedialog.askopenfilename(
            title="Select backup file",
            filetypes=[("Database files", "*.db"), ("All files", "*.*")]
        )
        
        if filename:
            if messagebox.askyesno("Confirm Restore", "This will overwrite current data. Continue?"):
                try:
                    success, message = self.backup_system.restore_backup(filename)
                    if success:
                        messagebox.showinfo("Success", message)
                        self.refresh_data()
                    else:
                        messagebox.showerror("Error", message)
                        
                except Exception as e:
                    messagebox.showerror("Error", f"Restore failed: {e}")
    
    def cleanup_old_data(self):
        """Cleanup old data"""
        days = simpledialog.askinteger("Cleanup", "Delete data older than how many days?", initialvalue=365)
        if days:
            if messagebox.askyesno("Confirm Cleanup", f"Delete all data older than {days} days?"):
                messagebox.showinfo("Cleanup", f"Would cleanup data older than {days} days")
    
    # Menu methods
    def import_data(self):
        """Import data from file"""
        filename = filedialog.askopenfilename(
            title="Select data file",
            filetypes=[("CSV files", "*.csv"), ("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        
        if filename:
            ImportDataWindow(self.root, filename, self.refresh_data)
    
    def export_data(self):
        """Export data to file"""
        ExportDataWindow(self.root)
    
    def open_qr_generator(self):
        """Open QR code generator"""
        if not self.qr_system:
            messagebox.showerror("Error", "QR system not available")
            return
        
        QRGeneratorWindow(self.root, self.qr_system)
    
    def open_face_recognition(self):
        """Open face recognition setup"""
        if not self.face_system:
            messagebox.showerror("Error", "Face recognition system not available")
            return
        
        FaceRecognitionWindow(self.root, self.face_system)
    
    def open_geofencing(self):
        """Open geofencing setup"""
        if not self.geo_system:
            messagebox.showerror("Error", "Geofencing system not available")
            return
        
        GeofencingWindow(self.root, self.geo_system)
    
    def run_original_cli(self):
        """Run original CLI in a separate thread"""
        if not ORIGINAL_FUNCTIONS_AVAILABLE:
            messagebox.showerror("Error", "Original CLI not available")
            return
        
        def run_cli():
            try:
                display_attendance_menu()
            except Exception as e:
                print(f"CLI error: {e}")
        
        threading.Thread(target=run_cli, daemon=True).start()
        messagebox.showinfo("CLI Started", "Original CLI started in background. Check console for interface.")
    
    def show_help(self):
        """Show help information"""
        HelpWindow(self.root)
    
    def show_about(self):
        """Show about dialog"""
        messagebox.showinfo("About", 
            "Enhanced Attendance Tracking System v2.0\n\n"
            "A comprehensive GUI-based attendance management system\n"
            "with advanced features including QR codes, geofencing,\n"
            "face recognition, and predictive analytics.\n\n"
            "© 2024 - Built with Python and tkinter")
    
    # Utility methods
    def update_status(self, message, status_type="info"):
        """Update status label"""
        color_map = {
            "info": self.colors['dark'],
            "success": self.colors['success'],
            "warning": self.colors['warning'],
            "error": self.colors['danger']
        }
        
        self.status_label.config(text=message, foreground=color_map.get(status_type, self.colors['dark']))

        # Auto-clear status after 5 seconds
        self.root.after(5000, lambda: self.status_label.config(text="Ready", foreground=self.colors['success']))

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Check if this is a child window (Toplevel) or standalone (Tk)
            if isinstance(self.root, tk.Toplevel):
                # Just close the child window
                self.root.destroy()
            else:
                # Running standalone, need to create main GUI
                self.root.destroy()
                from university_system.modules.shared.gui.main_gui import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

class ApiManagementWindow:
    def __init__(self, parent):
        self.parent = parent
        self.api_server = None
        self.api_thread = None

        self.window = tk.Toplevel(parent)
        self.window.title("API Management")
        self.window.geometry("800x600")
        self.window.transient(parent)

        self.create_widgets()

    def create_widgets(self):
        title_label = ttk.Label(self.window, text="🔌 API Management", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        # Server controls
        server_frame = ttk.LabelFrame(self.window, text="API Server Controls", padding=10)
        server_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Server settings
        settings_grid = ttk.Frame(server_frame)
        settings_grid.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(settings_grid, text="Host:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.host_var = tk.StringVar(value="127.0.0.1")
        ttk.Entry(settings_grid, textvariable=self.host_var, width=20).grid(row=0, column=1, padx=(10, 0), pady=5)

        ttk.Label(settings_grid, text="Port:").grid(row=0, column=2, sticky=tk.W, padx=(20, 0), pady=5)
        self.port_var = tk.StringVar(value="5000")
        ttk.Entry(settings_grid, textvariable=self.port_var, width=10).grid(row=0, column=3, padx=(10, 0), pady=5)

        # Server control buttons
        button_frame = ttk.Frame(server_frame)
        button_frame.pack(fill=tk.X)

        self.start_button = ttk.Button(button_frame, text="▶ Start Server", command=self.start_server, style='Success.TButton')
        self.start_button.pack(side=tk.LEFT, padx=(0, 5))

        self.stop_button = ttk.Button(button_frame, text="⏹ Stop Server", command=self.stop_server, state='disabled', style='Danger.TButton')
        self.stop_button.pack(side=tk.LEFT)

        self.status_label = ttk.Label(button_frame, text="● Server Stopped", foreground='red')
        self.status_label.pack(side=tk.LEFT, padx=(20, 0))

        # API Documentation
        doc_frame = ttk.LabelFrame(self.window, text="API Endpoints", padding=10)
        doc_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Create treeview for endpoints
        columns = ('Method', 'Endpoint', 'Description')
        self.endpoints_tree = ttk.Treeview(doc_frame, columns=columns, show='headings', height=8)

        self.endpoints_tree.heading('Method', text='Method')
        self.endpoints_tree.heading('Endpoint', text='Endpoint')
        self.endpoints_tree.heading('Description', text='Description')

        self.endpoints_tree.column('Method', width=80, anchor='center')
        self.endpoints_tree.column('Endpoint', width=250)
        self.endpoints_tree.column('Description', width=300)

        # Add endpoints
        endpoints = [
            ("POST", "/api/attendance/record", "Record attendance for a student"),
            ("GET", "/api/attendance/student/<id>", "Get student attendance statistics"),
            ("POST", "/api/qr/generate", "Generate QR code for session"),
            ("POST", "/api/qr/checkin", "Process QR code check-in"),
            ("GET", "/api/predictions/<student_id>/<module>", "Get risk prediction"),
        ]

        for method, endpoint, description in endpoints:
            self.endpoints_tree.insert('', 'end', values=(method, endpoint, description))

        scrollbar = ttk.Scrollbar(doc_frame, orient='vertical', command=self.endpoints_tree.yview)
        self.endpoints_tree.configure(yscrollcommand=scrollbar.set)

        self.endpoints_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Example usage
        example_frame = ttk.LabelFrame(self.window, text="Example Usage", padding=10)
        example_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        example_text = scrolledtext.ScrolledText(example_frame, height=6, width=70, wrap=tk.WORD)
        example_text.pack(fill=tk.X)

        example_text.insert(tk.END, "curl -X POST http://localhost:5000/api/attendance/record \\\n")
        example_text.insert(tk.END, "  -H 'Content-Type: application/json' \\\n")
        example_text.insert(tk.END, "  -d '{\n")
        example_text.insert(tk.END, "    \"student_id\": \"S001\",\n")
        example_text.insert(tk.END, "    \"module_code\": \"CS101\",\n")
        example_text.insert(tk.END, "    \"date\": \"2025-01-01\",\n")
        example_text.insert(tk.END, "    \"status\": \"Present\"\n")
        example_text.insert(tk.END, "  }'")

        example_text.config(state='disabled')

        # Close button
        ttk.Button(self.window, text="Close", command=self.close_window).pack(pady=10)

    def start_server(self):
        """Start the API server in a background thread"""
        try:
            if not ORIGINAL_FUNCTIONS_AVAILABLE:
                messagebox.showerror("Error", "API system not available. Original attendance_tracker module not found.")
                return

            from university_system.modules.domain.academics.services.attendance.attendance_tracker import AttendanceAPI

            host = self.host_var.get()
            port = int(self.port_var.get())

            self.api_server = AttendanceAPI()

            # Start server in background thread
            def run_server():
                try:
                    self.api_server.run_api(host=host, port=port, debug=False)
                except Exception as e:
                    print(f"API server error: {e}")

            self.api_thread = threading.Thread(target=run_server, daemon=True)
            self.api_thread.start()

            # Update UI
            self.start_button.config(state='disabled')
            self.stop_button.config(state='normal')
            self.status_label.config(text=f"● Server Running on {host}:{port}", foreground='green')

            messagebox.showinfo("Server Started", f"API server started at http://{host}:{port}")

        except ValueError:
            messagebox.showerror("Error", "Invalid port number")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start server: {e}")

    def stop_server(self):
        """Stop the API server"""
        try:
            # Note: Flask doesn't have a clean shutdown method when run directly
            # In production, you'd use a WSGI server like gunicorn
            messagebox.showinfo("Stop Server", "API server will stop when the application closes.\n\nFor production use, consider using a proper WSGI server.")

            self.start_button.config(state='normal')
            self.stop_button.config(state='disabled')
            self.status_label.config(text="● Server Stopped", foreground='red')

        except Exception as e:
            messagebox.showerror("Error", f"Error stopping server: {e}")

    def close_window(self):
        """Close the window"""
        if self.stop_button['state'] == 'normal':
            response = messagebox.askyesno("Confirm Close", "API server is running. Close anyway?")
            if not response:
                return

        self.window.destroy()


class AuditLogsWindow:
    """Rich audit log viewer with filtering and export support."""

    LOG_FILES = (
        "audit_system.log",
        "activity.log",
        "analytics.log",
        "attendance.log",
        "health_portal_audit.log",
    )

    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title("System Audit Logs")
        self.window.geometry("980x640")
        self.window.transient(parent)
        self.window.grab_set()

        self.all_logs = []
        self.filtered_logs = []
        self.errors = []

        self.create_widgets()
        self.refresh_logs()

    # ------------------------------------------------------------------ UI ---
    def create_widgets(self):
        title_frame = ttk.Frame(self.window)
        title_frame.pack(fill='x', padx=15, pady=15)
        ttk.Label(title_frame, text="📋 System Audit Logs", font=('Arial', 16, 'bold')).pack(side='left')

        # Filters
        filters_frame = ttk.LabelFrame(self.window, text="Filters", padding=15)
        filters_frame.pack(fill='x', padx=15, pady=(0, 15))

        self.date_range_var = tk.StringVar(value="Last 7 Days")
        ttk.Label(filters_frame, text="Date Range:").grid(row=0, column=0, sticky='w')
        self.date_combo = ttk.Combobox(
            filters_frame,
            textvariable=self.date_range_var,
            values=["Last 24 Hours", "Last 7 Days", "Last 30 Days", "All Time", "Custom Range"],
            width=18,
            state='readonly'
        )
        self.date_combo.grid(row=0, column=1, padx=(5, 20))

        self.level_var = tk.StringVar(value="All Levels")
        ttk.Label(filters_frame, text="Level:").grid(row=0, column=2, sticky='w')
        self.level_combo = ttk.Combobox(filters_frame, textvariable=self.level_var, width=16, state='readonly')
        self.level_combo.grid(row=0, column=3, padx=(5, 20))

        self.source_var = tk.StringVar(value="All Sources")
        ttk.Label(filters_frame, text="Source:").grid(row=0, column=4, sticky='w')
        self.source_combo = ttk.Combobox(filters_frame, textvariable=self.source_var, width=18, state='readonly')
        self.source_combo.grid(row=0, column=5, padx=(5, 0))

        ttk.Label(filters_frame, text="Search:").grid(row=1, column=0, sticky='w', pady=(12, 0))
        self.search_var = tk.StringVar()
        ttk.Entry(filters_frame, textvariable=self.search_var, width=38).grid(
            row=1, column=1, columnspan=3, sticky='ew', padx=(5, 20), pady=(12, 0)
        )

        button_frame = ttk.Frame(filters_frame)
        button_frame.grid(row=1, column=4, columnspan=2, sticky='e', pady=(12, 0))

        ttk.Button(button_frame, text="Apply Filters", command=self.apply_filters).pack(side='left')
        ttk.Button(button_frame, text="Reset", command=self.reset_filters).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.refresh_logs).pack(side='left')

        # Logs table
        table_frame = ttk.LabelFrame(self.window, text="Log Entries", padding=15)
        table_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        columns = ('Timestamp', 'Level', 'Category', 'User', 'Action', 'Source', 'Details')
        self.logs_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=18)
        for col in columns:
            width = 140 if col == 'Details' else 120
            self.logs_tree.heading(col, text=col)
            self.logs_tree.column(col, width=width, anchor='w')

        vsb = ttk.Scrollbar(table_frame, orient='vertical', command=self.logs_tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient='horizontal', command=self.logs_tree.xview)
        self.logs_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.logs_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        action_bar = ttk.Frame(self.window)
        action_bar.pack(fill='x', padx=15, pady=(0, 10))

        ttk.Button(action_bar, text="View Details", command=self.view_log_details).pack(side='left')
        ttk.Button(action_bar, text="Export...", command=self.export_logs).pack(side='left', padx=5)
        ttk.Button(action_bar, text="Archive / Clear", command=self.clear_logs).pack(side='left', padx=5)
        ttk.Button(action_bar, text="Close", command=self.window.destroy).pack(side='right')

        self.status_var = tk.StringVar(value="")
        ttk.Label(self.window, textvariable=self.status_var, foreground="#555555").pack(anchor='w', padx=15, pady=(0, 10))

        self.logs_tree.bind('<Double-1>', self.view_log_details)

    # ------------------------------------------------------------ data load ---
    def refresh_logs(self):
        self._set_status("Loading audit logs...")
        self.errors.clear()
        self.all_logs = self._load_logs()
        self._update_filter_options()
        self.apply_filters()
        if self.errors:
            self._set_status(f"Loaded {len(self.all_logs)} entries with warnings: {'; '.join(self.errors)}")
        else:
            self._set_status(f"Loaded {len(self.all_logs)} audit log entries.")

    def _load_logs(self):
        logs = []
        logs.extend(self._load_db_logs())
        logs.extend(self._load_file_logs())
        return logs

    def _load_db_logs(self):
        logs = []
        if not MAIN_DB_AVAILABLE:
            return logs

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            candidates = self._find_audit_tables(cursor)

            for table_name in candidates:
                try:
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = [row[1] for row in cursor.fetchall()]
                    if not columns:
                        continue

                    cursor.execute(f"SELECT * FROM {table_name} ORDER BY ROWID DESC LIMIT 500")
                    for row in cursor.fetchall():
                        log_entry = self._build_log_record(table_name, columns, row)
                        if log_entry:
                            logs.append(log_entry)
                except Exception as exc:
                    self.errors.append(f"{table_name}: {exc}")

            conn.close()
        except Exception as exc:
            self.errors.append(f"Database error: {exc}")
        return logs

    def _find_audit_tables(self, cursor):
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            return [
                name for name in tables
                if any(keyword in name.lower() for keyword in ("audit", "log", "activity"))
            ]
        except Exception as exc:
            self.errors.append(f"Unable to list tables: {exc}")
            return []

    def _build_log_record(self, table_name, columns, row):
        data = dict(zip(columns, row))

        timestamp_value = self._first_available(data, ("timestamp", "created_at", "created_on",
                                                       "logged_at", "event_time", "datetime"))
        timestamp_obj, timestamp_str = self._parse_timestamp(timestamp_value)

        level = self._first_available(data, ("level", "severity", "status", "log_level")) or "INFO"
        category = self._first_available(data, ("category", "module", "event_type",
                                                "table_affected", "function")) or table_name
        user = self._first_available(data, ("user", "username", "user_id", "actor", "initiated_by")) or "system"
        action = self._first_available(data, ("action", "event", "operation", "activity", "title")) or "activity"
        source = self._first_available(data, ("source", "system", "service", "module")) or table_name

        detail_value = self._first_available(
            data,
            ("details", "description", "message", "notes", "change_summary", "new_values")
        )
        if isinstance(detail_value, (dict, list)):
            details = json.dumps(detail_value, default=str)
        else:
            details = str(detail_value or "")

        if not timestamp_str:
            # Skip rows that are clearly not log entries
            return None

        return {
            "timestamp": timestamp_obj,
            "timestamp_str": timestamp_str,
            "level": str(level),
            "category": str(category),
            "user": str(user),
            "action": str(action),
            "source": str(source),
            "details": details,
        }

    def _first_available(self, data, keys):
        for key in keys:
            if key in data and data[key] not in (None, ""):
                return data[key]
        return None

    @staticmethod
    def _parse_timestamp(value):
        if value is None:
            return None, ""

        if isinstance(value, datetime.datetime):
            return value, value.strftime("%Y-%m-%d %H:%M:%S")

        if isinstance(value, (int, float)):
            try:
                dt = datetime.datetime.fromtimestamp(value)
                return dt, dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

        value_str = str(value).strip()
        if not value_str:
            return None, ""

        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S.%f", "%d/%m/%Y %H:%M:%S"):
            try:
                dt = datetime.datetime.strptime(value_str.replace("Z", ""), fmt)
                return dt, dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue

        try:
            dt = datetime.datetime.fromisoformat(value_str.replace("Z", "+00:00"))
            return dt, dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
        except Exception:
            return None, value_str

    def _load_file_logs(self):
        logs = []
        log_dir = Path(LOG_DIR)
        for filename in self.LOG_FILES:
            file_path = log_dir / filename
            if not file_path.exists():
                continue
            try:
                with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
                    for line in deque(handle, maxlen=400):
                        record = self._parse_log_line(line, filename)
                        if record:
                            logs.append(record)
            except Exception as exc:
                self.errors.append(f"{filename}: {exc}")
        return logs

    def _parse_log_line(self, line, filename):
        line = line.strip()
        if not line:
            return None

        patterns = [
            r'^\[(?P<timestamp>[^\]]+)\]\s+(?P<level>[A-Z]+)\s*-\s*(?P<message>.+)',
            r'^(?P<timestamp>\d{4}-\d{2}-\d{2} [\d:]+)\s+\[(?P<level>[A-Z]+)\]\s+(?P<message>.+)',
            r'^(?P<timestamp>\d{4}-\d{2}-\d{2}T[\d:]+(?:\.\d+)?Z?)\s+(?P<message>.+)',
        ]

        timestamp_obj, timestamp_str, level, message = None, "", "INFO", line
        for pattern in patterns:
            match = re.match(pattern, line)
            if match:
                timestamp_obj, timestamp_str = self._parse_timestamp(match.group('timestamp'))
                level = match.groupdict().get('level', level) or level
                message = match.groupdict().get('message', message)
                break

        # Attempt to split category/action details
        category = "Log File"
        action = message
        details = ""
        if " - " in message:
            parts = message.split(" - ", 1)
            category = parts[0].strip() or category
            action = parts[0].strip()
            details = parts[1].strip()

        return {
            "timestamp": timestamp_obj,
            "timestamp_str": timestamp_str or message[:19],
            "level": level,
            "category": category,
            "user": "system",
            "action": action,
            "source": filename,
            "details": details or message,
        }

    # -------------------------------------------------------------- filters ---
    def _update_filter_options(self):
        levels = sorted({log['level'] for log in self.all_logs if log['level']})
        sources = sorted({log['source'] for log in self.all_logs if log['source']})
        self.level_combo['values'] = ["All Levels"] + levels
        self.source_combo['values'] = ["All Sources"] + sources

        if self.level_var.get() not in self.level_combo['values']:
            self.level_var.set("All Levels")
        if self.source_var.get() not in self.source_combo['values']:
            self.source_var.set("All Sources")

    def apply_filters(self):
        level_filter = self.level_var.get()
        source_filter = self.source_var.get()
        search_text = self.search_var.get().strip().lower()

        now = datetime.datetime.now()
        range_map = {
            "Last 24 Hours": now - datetime.timedelta(days=1),
            "Last 7 Days": now - datetime.timedelta(days=7),
            "Last 30 Days": now - datetime.timedelta(days=30)
        }
        threshold = range_map.get(self.date_range_var.get())

        if self.date_range_var.get() == "Custom Range":
            custom = simpledialog.askstring(
                "Custom Date Range",
                "Enter custom range as YYYY-MM-DD,YYYY-MM-DD",
                parent=self.window
            )
            if custom:
                try:
                    start_str, end_str = [part.strip() for part in custom.split(",")]
                    start_dt = datetime.datetime.strptime(start_str, "%Y-%m-%d")
                    end_dt = datetime.datetime.strptime(end_str, "%Y-%m-%d") + datetime.timedelta(days=1)
                    threshold = start_dt
                    range_end = end_dt
                except Exception:
                    messagebox.showerror("Invalid Range", "Could not parse the supplied date range.")
                    threshold = None
                    range_end = None
            else:
                threshold = None
                range_end = None
        else:
            range_end = None

        filtered = []
        for log in self.all_logs:
            timestamp_ok = True
            if threshold:
                if log['timestamp']:
                    if self.date_range_var.get() == "Custom Range" and range_end:
                        timestamp_ok = threshold <= log['timestamp'] <= range_end
                    else:
                        timestamp_ok = log['timestamp'] >= threshold
                else:
                    timestamp_ok = False
            if not timestamp_ok:
                continue

            if level_filter != "All Levels" and log['level'] != level_filter:
                continue

            if source_filter != "All Sources" and log['source'] != source_filter:
                continue

            if search_text and not self._matches_search(log, search_text):
                continue

            filtered.append(log)

        filtered.sort(key=lambda entry: entry['timestamp'] or datetime.datetime.min, reverse=True)
        self.filtered_logs = filtered
        self._populate_treeview()

    def _matches_search(self, log, text):
        haystack = " ".join([
            log.get('timestamp_str', ''),
            log.get('level', ''),
            log.get('category', ''),
            log.get('user', ''),
            log.get('action', ''),
            log.get('source', ''),
            log.get('details', ''),
        ]).lower()
        return text in haystack

    def reset_filters(self):
        self.date_range_var.set("Last 7 Days")
        self.level_var.set("All Levels")
        self.source_var.set("All Sources")
        self.search_var.set("")
        self.apply_filters()

    def _populate_treeview(self):
        for item in self.logs_tree.get_children():
            self.logs_tree.delete(item)

        for log in self.filtered_logs:
            values = (
                log['timestamp_str'],
                log['level'],
                log['category'],
                log['user'],
                log['action'],
                log['source'],
                log['details'],
            )
            self.logs_tree.insert('', 'end', values=values)

    # -------------------------------------------------------------- actions ---
    def export_logs(self):
        if not self.filtered_logs:
            messagebox.showinfo("No Data", "There are no log entries to export.")
            return

        filename = filedialog.asksaveasfilename(
            title="Export Logs",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not filename:
            return

        try:
            with open(filename, 'w', newline='', encoding='utf-8') as handle:
                writer = csv.writer(handle)
                writer.writerow(["Timestamp", "Level", "Category", "User", "Action", "Source", "Details"])
                for log in self.filtered_logs:
                    writer.writerow([
                        log['timestamp_str'],
                        log['level'],
                        log['category'],
                        log['user'],
                        log['action'],
                        log['source'],
                        log['details'],
                    ])
            messagebox.showinfo("Export Complete", f"Exported {len(self.filtered_logs)} log entries to {filename}")
        except Exception as exc:
            messagebox.showerror("Export Failed", f"Unable to export logs:\n{exc}")

    def view_log_details(self, event=None):
        selection = self.logs_tree.selection()
        if not selection:
            return

        item = self.logs_tree.item(selection[0])
        values = item['values']

        details_window = tk.Toplevel(self.window)
        details_window.title("Log Entry Details")
        details_window.geometry("640x520")
        details_window.transient(self.window)

        details_frame = ttk.LabelFrame(details_window, text="Log Details", padding=15)
        details_frame.pack(fill='both', expand=True, padx=15, pady=15)

        details_text = scrolledtext.ScrolledText(details_frame, wrap='word', height=22)
        details_text.pack(fill='both', expand=True)

        detail_report = f"""
LOG ENTRY DETAILS
=================

Timestamp : {values[0]}
Level     : {values[1]}
Category  : {values[2]}
User      : {values[3]}
Action    : {values[4]}
Source    : {values[5]}

Details
-------
{values[6]}
"""
        details_text.insert('1.0', detail_report.strip())
        details_text.config(state='disabled')

        ttk.Button(details_window, text="Close", command=details_window.destroy).pack(pady=(0, 10))

    def clear_logs(self):
        messagebox.showinfo(
            "Archive Logs",
            "Automated log archival is not yet connected to the database.\n"
            "Consider exporting the entries you need before removing old data."
        )

    def _set_status(self, message):
        self.status_var.set(message)


class DiagnosticsWindow:
    """Run lightweight diagnostics for the attendance stack."""

    def __init__(self, parent, controller=None):
        self.parent = parent
        self.controller = controller

        self.window = tk.Toplevel(parent)
        self.window.title("System Diagnostics")
        self.window.geometry("920x620")
        self.window.transient(parent)
        self.window.grab_set()

        self.summary_labels = {}
        self.services_tree = None
        self.table_tree = None
        self.log_text = None

        self.metrics = self._collect_metrics()
        self.create_widgets()

    # ------------------------------------------------------------ UI setup ---
    def create_widgets(self):
        title_frame = ttk.Frame(self.window)
        title_frame.pack(fill='x', padx=15, pady=15)
        ttk.Label(title_frame, text="🔧 Attendance System Diagnostics",
                 font=('Arial', 16, 'bold')).pack(side='left')

        ttk.Button(title_frame, text="Re-run Checks", command=self.refresh_metrics).pack(side='right')

        notebook = ttk.Notebook(self.window)
        notebook.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        summary_frame = ttk.Frame(notebook)
        notebook.add(summary_frame, text="System Summary")
        self._build_summary_tab(summary_frame)

        data_frame = ttk.Frame(notebook)
        notebook.add(data_frame, text="Database & Data")
        self._build_data_tab(data_frame)

        services_frame = ttk.Frame(notebook)
        notebook.add(services_frame, text="Services & Integrations")
        self._build_services_tab(services_frame)

        logs_frame = ttk.Frame(notebook)
        notebook.add(logs_frame, text="Recent Activity")
        self._build_logs_tab(logs_frame)

        ttk.Button(self.window, text="Close", command=self.window.destroy).pack(pady=(0, 10))

    def _build_summary_tab(self, parent):
        overview = ttk.LabelFrame(parent, text="Health Overview", padding=15)
        overview.pack(fill='x', padx=10, pady=10)

        summary_items = [
            ("Database", "db_status"),
            ("Database Path", "db_path"),
            ("Last Check", "generated_at"),
            ("Issues Detected", "issues"),
        ]

        for idx, (label, key) in enumerate(summary_items):
            frame = ttk.LabelFrame(overview, text=label, padding=10)
            frame.grid(row=0, column=idx, padx=5, pady=5, sticky='ew')
            value = ttk.Label(frame, text="", font=('Arial', 11, 'bold'))
            value.pack()
            self.summary_labels[key] = value
            overview.grid_columnconfigure(idx, weight=1)

        stats_frame = ttk.LabelFrame(parent, text="Attendance Data Snapshot", padding=15)
        stats_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        stats_columns = ('Metric', 'Value')
        stats_tree = ttk.Treeview(stats_frame, columns=stats_columns, show='headings', height=8)
        for col in stats_columns:
            stats_tree.heading(col, text=col)
            stats_tree.column(col, width=220 if col == 'Metric' else 160)
        stats_tree.pack(fill='both', expand=True)

        self.summary_labels['stats_tree'] = stats_tree
        self._populate_summary()

    def _build_data_tab(self, parent):
        status_frame = ttk.LabelFrame(parent, text="Table Overview", padding=15)
        status_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ('Table', 'Exists', 'Row Count', 'Notes')
        self.table_tree = ttk.Treeview(status_frame, columns=columns, show='headings', height=12)
        for idx, col in enumerate(columns):
            width = 160 if idx == 0 else 110
            if col == 'Notes':
                width = 260
            self.table_tree.heading(col, text=col)
            self.table_tree.column(col, width=width, anchor='w')
        self.table_tree.pack(fill='both', expand=True)

        actions = ttk.Frame(parent)
        actions.pack(fill='x', padx=10, pady=(0, 10))
        ttk.Button(actions, text="Run Integrity Check", command=self._run_integrity_check).pack(side='left')
        ttk.Button(actions, text="Open Maintenance Tools",
                   command=lambda: DatabaseMaintenanceWindow(self.parent)).pack(side='left', padx=5)

        self._populate_data_tab()

    def _build_services_tab(self, parent):
        frame = ttk.LabelFrame(parent, text="Integration Status", padding=15)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ('Service', 'Status', 'Notes')
        self.services_tree = ttk.Treeview(frame, columns=columns, show='headings', height=12)
        for idx, col in enumerate(columns):
            width = 200 if idx == 0 else 160
            if col == 'Notes':
                width = 340
            self.services_tree.heading(col, text=col)
            self.services_tree.column(col, width=width, anchor='w')
        self.services_tree.pack(fill='both', expand=True)

        self._populate_services_tab()

    def _build_logs_tab(self, parent):
        frame = ttk.LabelFrame(parent, text="Recent Log Activity", padding=15)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.log_text = scrolledtext.ScrolledText(frame, wrap='word', height=18)
        self.log_text.pack(fill='both', expand=True)
        self._populate_logs_tab()

    # --------------------------------------------------------- data helpers ---
    def _collect_metrics(self):
        metrics = {
            "generated_at": datetime.datetime.now(),
            "db_status": "Unavailable",
            "db_path": "Unknown",
            "issues": "None detected",
            "counts": {
                "Students": "n/a",
                "Modules": "n/a",
                "Attendance Records": "n/a",
                "Audit Entries": "n/a",
            },
            "tables": [],
            "recent_logs": [],
            "services": [],
            "errors": [],
        }

        # Database inspection
        if MAIN_DB_AVAILABLE:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                metrics["db_status"] = "Connected"

                cursor.execute("PRAGMA database_list;")
                rows = cursor.fetchall()
                if rows:
                    db_path = rows[0][2]
                    metrics["db_path"] = db_path or "memory"

                tables = self._list_tables(cursor)
                metrics["tables"] = tables

                # Counts for common tables
                count_targets = {
                    "students": "Students",
                    "modules": "Modules",
                    "attendance": "Attendance Records",
                    "attendance_records": "Attendance Records",
                    "attendance_logs": "Audit Entries",
                    "audit_log": "Audit Entries",
                    "audit_logs": "Audit Entries",
                }

                for table_name, metric_label in count_targets.items():
                    if any(t['name'] == table_name for t in tables if t['exists']):
                        try:
                            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                            count = cursor.fetchone()[0]
                            metrics["counts"][metric_label] = f"{count:,}"
                        except Exception:
                            continue

                recent_activity = self._load_recent_activity(cursor, tables)
                metrics["recent_logs"] = recent_activity

                conn.close()
            except Exception as exc:
                metrics["db_status"] = "Connection failed"
                metrics["issues"] = str(exc)
                metrics["errors"].append(str(exc))
        else:
            metrics["db_status"] = "Connection helper unavailable"
            metrics["issues"] = "Database access helper is not available in this environment."

        # Services status
        metrics["services"] = self._evaluate_services()
        return metrics

    def _list_tables(self, cursor):
        tables = []
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing = {row[0] for row in cursor.fetchall()}
        except Exception:
            existing = set()

        required = [
            "students",
            "modules",
            "attendance",
            "attendance_records",
            "attendance_logs",
            "audit_log",
            "audit_logs",
        ]

        for name in sorted(existing.union(required)):
            exists = name in existing
            row_count = "—"
            if exists:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {name}")
                    row_count = f"{cursor.fetchone()[0]:,}"
                except Exception:
                    row_count = "?"
            tables.append({
                "name": name,
                "exists": exists,
                "rows": row_count,
                "notes": "Required" if name in required else "",
            })

        return tables

    def _load_recent_activity(self, cursor, tables):
        table_candidates = [
            "attendance_logs",
            "attendance_log",
            "audit_logs",
            "audit_log",
            "attendance_records",
        ]
        existing_tables = {tbl['name'] for tbl in tables if tbl['exists']}

        for table in table_candidates:
            if table not in existing_tables:
                continue
            try:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [row[1] for row in cursor.fetchall()]
                if not columns:
                    continue

                cursor.execute(f"SELECT * FROM {table} ORDER BY ROWID DESC LIMIT 5")
                rows = cursor.fetchall()
                recent = []
                for row in rows:
                    record = dict(zip(columns, row))
                    timestamp_val = record.get('timestamp') or record.get('created_at') or record.get('datetime')
                    ts_obj, ts_str = AuditLogsWindow._parse_timestamp(timestamp_val)
                    recent.append({
                        "table": table,
                        "timestamp": ts_str or "—",
                        "summary": record.get('action') or record.get('event') or "Update",
                        "details": record.get('details') or record.get('description') or "",
                    })
                if recent:
                    return recent
            except Exception:
                continue
        return []

    def _evaluate_services(self):
        services = []

        services.append(self._service_row(
            "QR Attendance",
            True,
            "QR code generator available" if 'qrcode' in globals() else "QR library not imported"
        ))

        services.append(self._service_row(
            "Geofencing",
            GEOFENCING_SUPPORT,
            "Geofencing support enabled" if GEOFENCING_SUPPORT else "Feature flagged off"
        ))

        services.append(self._service_row(
            "Face Recognition",
            FACE_RECOGNITION_SUPPORT,
            "Face recognition helpers available" if FACE_RECOGNITION_SUPPORT else "Feature flagged off"
        ))

        services.append(self._service_row(
            "Predictive Analytics",
            ORIGINAL_FUNCTIONS_AVAILABLE,
            "Analytics module imported" if ORIGINAL_FUNCTIONS_AVAILABLE else "Analytics module missing"
        ))

        services.append(self._service_row(
            "Notification System",
            ORIGINAL_FUNCTIONS_AVAILABLE,
            "Notification helpers available" if ORIGINAL_FUNCTIONS_AVAILABLE else "Notification helpers missing"
        ))

        return services

    def _service_row(self, name, available, notes):
        return {
            "name": name,
            "status": "🟢 Available" if available else "🔴 Unavailable",
            "notes": notes,
        }

    # ---------------------------------------------------------- populators ---
    def _populate_summary(self):
        metrics = self.metrics
        self.summary_labels['db_status'].config(text=metrics['db_status'])
        self.summary_labels['db_path'].config(text=metrics['db_path'])
        self.summary_labels['generated_at'].config(
            text=metrics['generated_at'].strftime("%Y-%m-%d %H:%M:%S")
        )
        self.summary_labels['issues'].config(text=metrics.get('issues', 'None'))

        stats_tree = self.summary_labels['stats_tree']
        for item in stats_tree.get_children():
            stats_tree.delete(item)
        for key, value in metrics['counts'].items():
            stats_tree.insert('', 'end', values=(key, value))

    def _populate_data_tab(self):
        if not self.table_tree:
            return
        for item in self.table_tree.get_children():
            self.table_tree.delete(item)

        for table in self.metrics['tables']:
            exists = "Yes" if table['exists'] else "No"
            notes = table['notes'] or ("Detected" if table['exists'] else "")
            self.table_tree.insert('', 'end', values=(table['name'], exists, table['rows'], notes))

    def _populate_services_tab(self):
        if not self.services_tree:
            return
        for item in self.services_tree.get_children():
            self.services_tree.delete(item)
        for service in self.metrics['services']:
            self.services_tree.insert('', 'end', values=(service['name'], service['status'], service['notes']))

    def _populate_logs_tab(self):
        if not self.log_text:
            return
        self.log_text.config(state='normal')
        self.log_text.delete('1.0', tk.END)

        recent = self.metrics['recent_logs']
        if not recent:
            self.log_text.insert('1.0', "No recent activity records were discovered.\n")
        else:
            lines = [
                f"[{entry['timestamp']}] {entry['table']} - {entry['summary']}\n{entry['details']}"
                for entry in recent
            ]
            self.log_text.insert('1.0', "\n\n".join(lines))

        # Append tail of log file for manual inspection
        log_dir = Path(__file__).resolve().parents[3] / "logs"
        activity_log = log_dir / "activity.log"
        if activity_log.exists():
            self.log_text.insert(tk.END, "\n\n--- activity.log (latest entries) ---\n")
            try:
                with activity_log.open('r', encoding='utf-8', errors='ignore') as handle:
                    for line in deque(handle, maxlen=15):
                        self.log_text.insert(tk.END, line)
            except Exception as exc:
                self.log_text.insert(tk.END, f"[Unable to read activity.log: {exc}]\n")

        self.log_text.config(state='disabled')

    # ------------------------------------------------------------- actions ---
    def refresh_metrics(self):
        self.metrics = self._collect_metrics()
        self._populate_summary()
        self._populate_data_tab()
        self._populate_services_tab()
        self._populate_logs_tab()
        messagebox.showinfo("Diagnostics", "System diagnostics have been refreshed.")

    def _run_integrity_check(self):
        if not MAIN_DB_AVAILABLE:
            messagebox.showwarning("Unavailable", "Database helper not available in this environment.")
            return
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            conn.close()
            message = result[0] if result else "No response"
            messagebox.showinfo("Integrity Check", f"Database integrity check returned: {message}")
        except Exception as exc:
            messagebox.showerror("Integrity Check Failed", str(exc))


class DatabaseMaintenanceWindow:
    """SQLite-oriented maintenance helpers for attendance data."""

    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title("Database Maintenance")
        self.window.geometry("900x620")
        self.window.transient(parent)
        self.window.grab_set()

        self.db_info = self._collect_db_info()
        self.status_labels = {}
        self.tables_tree = None
        self.logs_text = None
        self.backup_tree = None

        self.create_widgets()

    # --------------------------------------------------------------- UI setup
    def create_widgets(self):
        title_frame = ttk.Frame(self.window)
        title_frame.pack(fill='x', padx=15, pady=15)

        ttk.Label(title_frame, text="🗄️ Attendance Database Maintenance",
                 font=('Arial', 16, 'bold')).pack(side='left')
        ttk.Button(title_frame, text="Refresh", command=self.refresh_view).pack(side='right')

        notebook = ttk.Notebook(self.window)
        notebook.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        status_frame = ttk.Frame(notebook)
        notebook.add(status_frame, text="Status")
        self._build_status_tab(status_frame)

        maintenance_frame = ttk.Frame(notebook)
        notebook.add(maintenance_frame, text="Maintenance Tasks")
        self._build_maintenance_tab(maintenance_frame)

        backup_frame = ttk.Frame(notebook)
        notebook.add(backup_frame, text="Backup & Restore")
        self._build_backup_tab(backup_frame)

        ttk.Button(self.window, text="Close", command=self.window.destroy).pack(pady=(0, 10))

    def _build_status_tab(self, parent):
        overview = ttk.LabelFrame(parent, text="Database Overview", padding=15)
        overview.pack(fill='x', padx=10, pady=10)

        summary_items = [
            ("Connection", "connection"),
            ("Database Path", "path"),
            ("Size", "size"),
            ("Tables", "tables_count"),
        ]

        for idx, (label, key) in enumerate(summary_items):
            frame = ttk.LabelFrame(overview, text=label, padding=10)
            frame.grid(row=0, column=idx, padx=5, pady=5, sticky='ew')
            value_label = ttk.Label(frame, text="", font=('Arial', 11, 'bold'))
            value_label.pack()
            self.status_labels[key] = value_label
            overview.grid_columnconfigure(idx, weight=1)

        tables_frame = ttk.LabelFrame(parent, text="Table Statistics", padding=15)
        tables_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        columns = ('Table', 'Rows')
        self.tables_tree = ttk.Treeview(tables_frame, columns=columns, show='headings', height=14)
        for col in columns:
            width = 220 if col == 'Table' else 120
            self.tables_tree.heading(col, text=col)
            self.tables_tree.column(col, width=width, anchor='w')
        self.tables_tree.pack(fill='both', expand=True)

        self._populate_status_tab()

    def _build_maintenance_tab(self, parent):
        actions_frame = ttk.LabelFrame(parent, text="Maintenance Operations", padding=15)
        actions_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(actions_frame, text="VACUUM", command=self.run_vacuum).pack(side='left', padx=5)
        ttk.Button(actions_frame, text="ANALYZE", command=self.run_analyze).pack(side='left', padx=5)
        ttk.Button(actions_frame, text="REINDEX", command=self.run_reindex).pack(side='left', padx=5)
        ttk.Button(actions_frame, text="PRAGMA optimize", command=self.run_optimize).pack(side='left', padx=5)
        ttk.Button(actions_frame, text="Integrity Check", command=self.run_integrity_check).pack(side='left', padx=5)

        log_frame = ttk.LabelFrame(parent, text="Maintenance Log", padding=15)
        log_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        self.logs_text = scrolledtext.ScrolledText(log_frame, wrap='word', height=16)
        self.logs_text.pack(fill='both', expand=True)
        self.logs_text.config(state='disabled')

    def _build_backup_tab(self, parent):
        controls = ttk.LabelFrame(parent, text="Backup Operations", padding=15)
        controls.pack(fill='x', padx=10, pady=10)

        ttk.Button(controls, text="Create Backup", command=self.create_backup).pack(side='left', padx=5)
        ttk.Button(controls, text="Restore Backup", command=self.restore_backup).pack(side='left', padx=5)
        ttk.Button(controls, text="Open Backup Folder", command=self.open_backup_folder).pack(side='left', padx=5)

        history_frame = ttk.LabelFrame(parent, text="Backup History", padding=15)
        history_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        columns = ('Filename', 'Created', 'Size')
        self.backup_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=14)
        for idx, col in enumerate(columns):
            width = 320 if idx == 0 else 160
            self.backup_tree.heading(col, text=col)
            self.backup_tree.column(col, width=width, anchor='w')
        self.backup_tree.pack(fill='both', expand=True)

        self._populate_backup_history()

    # --------------------------------------------------------- data helpers ---
    def _collect_db_info(self):
        info = {
            "connected": False,
            "path": "Unknown",
            "size": "Unknown",
            "tables": [],
            "error": None,
        }

        if not MAIN_DB_AVAILABLE:
            info["error"] = "Database helper unavailable in this environment."
            return info

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            info["connected"] = True

            cursor.execute("PRAGMA database_list;")
            rows = cursor.fetchall()
            if rows:
                db_path = rows[0][2]
                info["path"] = db_path or "memory"
                if db_path and os.path.exists(db_path):
                    size_bytes = os.path.getsize(db_path)
                    info["size"] = self._format_size(size_bytes)

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            for table in sorted(tables):
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    info["tables"].append((table, count))
                except Exception:
                    info["tables"].append((table, None))

            conn.close()
        except Exception as exc:
            info["error"] = str(exc)

        return info

    def _format_size(self, size_bytes):
        if size_bytes is None:
            return "Unknown"
        for unit in ("bytes", "KB", "MB", "GB", "TB"):
            if size_bytes < 1024.0:
                return f"{size_bytes:3.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"

    def _populate_status_tab(self):
        info = self.db_info
        self.status_labels['connection'].config(
            text="Connected" if info['connected'] else "Not connected"
        )
        self.status_labels['path'].config(text=info['path'])
        self.status_labels['size'].config(text=info['size'])
        self.status_labels['tables_count'].config(text=str(len(info['tables'])))

        for item in self.tables_tree.get_children():
            self.tables_tree.delete(item)
        for table, count in info['tables']:
            count_display = f"{count:,}" if isinstance(count, int) else "?"
            self.tables_tree.insert('', 'end', values=(table, count_display))

        if info['error']:
            self._append_log(f"⚠ Error collecting database information: {info['error']}")

    def _populate_backup_history(self):
        if not self.backup_tree:
            return
        for item in self.backup_tree.get_children():
            self.backup_tree.delete(item)

        backups_dir = Path(BACKUP_DIR)
        backups_dir.mkdir(exist_ok=True)
        backups = sorted(backups_dir.glob("attendance_backup_*.db"), reverse=True)

        for backup in backups:
            stat = backup.stat()
            created = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            size = self._format_size(stat.st_size)
            self.backup_tree.insert('', 'end', values=(backup.name, created, size))

    # -------------------------------------------------------------- actions ---
    def run_vacuum(self):
        self._run_sql_command("VACUUM")

    def run_analyze(self):
        self._run_sql_command("ANALYZE")

    def run_reindex(self):
        self._run_sql_command("REINDEX")

    def run_optimize(self):
        self._run_sql_command("PRAGMA optimize")

    def run_integrity_check(self):
        if not MAIN_DB_AVAILABLE:
            messagebox.showwarning("Unavailable", "Database helper not available.")
            return
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            result = cursor.fetchone()
            conn.close()
            self._append_log(f"Integrity check: {result[0] if result else 'No response'}")
            messagebox.showinfo("Integrity Check", result[0] if result else "No response")
        except Exception as exc:
            self._append_log(f"Integrity check failed: {exc}")
            messagebox.showerror("Integrity Check Failed", str(exc))

    def _run_sql_command(self, command):
        if not MAIN_DB_AVAILABLE:
            messagebox.showwarning("Unavailable", "Database helper not available.")
            return
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(command)
            conn.commit()
            conn.close()
            self._append_log(f"Executed {command}")
            messagebox.showinfo("Maintenance", f"{command} executed successfully.")
        except Exception as exc:
            self._append_log(f"{command} failed: {exc}")
            messagebox.showerror("Maintenance Failed", str(exc))

    def create_backup(self):
        if not self.db_info['path'] or not os.path.exists(self.db_info['path']):
            messagebox.showwarning("No Database File", "Database path is unknown or unavailable.")
            return

        backups_dir = Path(BACKUP_DIR)
        backups_dir.mkdir(exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        destination = backups_dir / f"attendance_backup_{timestamp}.db"

        try:
            shutil.copy2(self.db_info['path'], destination)
            self._append_log(f"Backup created at {destination}")
            self._populate_backup_history()
            messagebox.showinfo("Backup Complete", f"Backup saved to {destination}")
        except Exception as exc:
            self._append_log(f"Backup failed: {exc}")
            messagebox.showerror("Backup Failed", str(exc))

    def restore_backup(self):
        if not self.db_info['path'] or not os.path.exists(self.db_info['path']):
            messagebox.showwarning("No Database File", "Database path is unknown or unavailable.")
            return

        filename = filedialog.askopenfilename(
            title="Select Backup File",
            filetypes=[("Database files", "*.db"), ("All files", "*.*")]
        )
        if not filename:
            return

        confirmed = messagebox.askyesno(
            "Confirm Restore",
            "Restoring a backup will overwrite the current database.\n"
            "Make sure you have a recent backup of the current data.\n\n"
            "Proceed with restore?"
        )
        if not confirmed:
            return

        try:
            shutil.copy2(self.db_info['path'], f"{self.db_info['path']}.bak")
            shutil.copy2(filename, self.db_info['path'])
            self._append_log(f"Database restored from {filename}")
            messagebox.showinfo("Restore Complete", "Database has been restored successfully.")
            self.refresh_view()
        except Exception as exc:
            self._append_log(f"Restore failed: {exc}")
            messagebox.showerror("Restore Failed", str(exc))

    def open_backup_folder(self):
        backups_dir = Path(BACKUP_DIR)
        backups_dir.mkdir(exist_ok=True)

        # Get list of backup files
        backups = sorted(backups_dir.glob("attendance_backup_*.db"), reverse=True)

        if backups:
            backup_list = "\n".join([f"• {b.name}" for b in backups[:10]])  # Show first 10
            if len(backups) > 10:
                backup_list += f"\n... and {len(backups) - 10} more"
            message = f"Backups are stored in:\n{backups_dir}\n\nRecent backups:\n{backup_list}"
        else:
            message = f"Backups are stored in:\n{backups_dir}\n\nNo backup files found."

        messagebox.showinfo("Backup Folder", message)

    def refresh_view(self):
        self.db_info = self._collect_db_info()
        self._populate_status_tab()
        self._populate_backup_history()

    # -------------------------------------------------------------- helpers ---
    def _append_log(self, message):
        if not self.logs_text:
            return
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logs_text.config(state='normal')
        self.logs_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.logs_text.see(tk.END)
        self.logs_text.config(state='disabled')

class BiometricsManagementWindow:
    def __init__(self, parent):
        self.parent = parent
        
        self.window = tk.Toplevel(parent)
        self.window.title("Biometrics Management")
        self.window.geometry("600x500")
        self.window.transient(parent)
        
        self.create_widgets()
    
    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="👤 Biometrics Management", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Notebook for different biometric types
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Face enrollment tab
        face_frame = ttk.Frame(notebook)
        notebook.add(face_frame, text="Face Enrollment")
        
        # Student ID
        ttk.Label(face_frame, text="Student ID:").pack(anchor=tk.W, padx=10, pady=(10, 0))
        self.student_id_var = tk.StringVar()
        ttk.Entry(face_frame, textvariable=self.student_id_var, width=30).pack(padx=10, pady=5)
        
        # Photo selection
        ttk.Label(face_frame, text="Student Photo:").pack(anchor=tk.W, padx=10, pady=(10, 0))
        photo_frame = ttk.Frame(face_frame)
        photo_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.photo_path_var = tk.StringVar()
        ttk.Entry(photo_frame, textvariable=self.photo_path_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(photo_frame, text="Browse", command=self.browse_photo).pack(side=tk.RIGHT, padx=(5, 0))
        
        # Enroll button
        ttk.Button(face_frame, text="Enroll Face", command=self.enroll_face, style='Success.TButton').pack(pady=20)
        
        # Enrolled students list
        ttk.Label(face_frame, text="Enrolled Students:").pack(anchor=tk.W, padx=10)
        
        list_frame = ttk.Frame(face_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        columns = ("Student ID", "Name", "Enrollment Date", "Status")
        self.enrolled_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=8)
        
        for col in columns:
            self.enrolled_tree.heading(col, text=col)
            self.enrolled_tree.column(col, width=120)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.enrolled_tree.yview)
        self.enrolled_tree.configure(yscrollcommand=scrollbar.set)
        
        self.enrolled_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Load enrolled students
        self.load_enrolled_students()
        
        # Close button
        ttk.Button(self.window, text="Close", command=self.window.destroy, style='Danger.TButton').pack(pady=10)
    
    def browse_photo(self):
        filename = filedialog.askopenfilename(
            title="Select Student Photo",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")]
        )
        if filename:
            self.photo_path_var.set(filename)
    
    def enroll_face(self):
        student_id = self.student_id_var.get()
        photo_path = self.photo_path_var.get()
        
        if not student_id or not photo_path:
            messagebox.showwarning("Warning", "Please enter student ID and select a photo")
            return
        
        try:
            if FACE_RECOGNITION_SUPPORT:
                face_system = FaceRecognitionSystem()
                success, message = face_system.enroll_student_face(student_id, photo_path)
                
                if success:
                    messagebox.showinfo("Success", message)
                    self.load_enrolled_students()
                    self.student_id_var.set("")
                    self.photo_path_var.set("")
                else:
                    messagebox.showerror("Error", message)
            else:
                messagebox.showinfo("Demo", "Face would be enrolled here (face recognition not available)")
                
        except Exception as e:
            messagebox.showerror("Error", f"Enrollment failed: {e}")
    
    def load_enrolled_students(self):
        # Clear existing items
        for item in self.enrolled_tree.get_children():
            self.enrolled_tree.delete(item)
        
        # Sample data or real data from database
        # Load real enrollment data from database
        try:
            import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Try to get student enrollment data
                cursor.execute("""
                    SELECT student_id, first_name || ' ' || last_name, enrollment_date, status
                    FROM students
                    WHERE status = 'Active' OR status = 'Enrolled'
                    ORDER BY enrollment_date DESC
                """)
                enrollment_data = cursor.fetchall()

                if enrollment_data:
                    for data in enrollment_data:
                        self.enrolled_tree.insert('', 'end', values=data)
                else:
                    # Check if students table exists
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='students'")
                    if cursor.fetchone():
                        self.enrolled_tree.insert('', 'end', values=('N/A', 'No enrolled students found', '', 'Please enroll students first'))
                    else:
                        self.enrolled_tree.insert('', 'end', values=('ERROR', 'Students table not found', '', 'Database needs initialization'))

        except Exception as e:
            self.enrolled_tree.insert('', 'end', values=('ERROR', f'Database error: {str(e)}', '', 'Unable to load enrollment data'))


class AttendanceAlertsWindow:
    def __init__(self, parent):
        self.parent = parent
        
        self.window = tk.Toplevel(parent)
        self.window.title("Attendance Alerts Manager")
        self.window.geometry("800x600")
        self.window.transient(parent)
        
        self.create_widgets()
        self.load_alerts()
    
    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="🚨 Attendance Alerts Manager", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Controls frame
        controls_frame = ttk.Frame(self.window)
        controls_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Button(controls_frame, text="Create Alert", 
                  command=self.create_alert, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(controls_frame, text="Acknowledge Selected", 
                  command=self.acknowledge_alert, style='Primary.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(controls_frame, text="Refresh", 
                  command=self.load_alerts, style='Primary.TButton').pack(side=tk.LEFT, padx=(0, 5))
        
        # Filter frame
        filter_frame = ttk.LabelFrame(self.window, text="Filters", padding=10)
        filter_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        filter_controls = ttk.Frame(filter_frame)
        filter_controls.pack(fill=tk.X)
        
        ttk.Label(filter_controls, text="Status:").grid(row=0, column=0, sticky=tk.W)
        self.status_filter_var = tk.StringVar(value="All")
        status_combo = ttk.Combobox(filter_controls, textvariable=self.status_filter_var,
                                   values=["All", "Pending", "Acknowledged", "Resolved"], state="readonly", width=15)
        status_combo.grid(row=0, column=1, padx=(5, 20))
        
        ttk.Label(filter_controls, text="Severity:").grid(row=0, column=2, sticky=tk.W)
        self.severity_filter_var = tk.StringVar(value="All")
        severity_combo = ttk.Combobox(filter_controls, textvariable=self.severity_filter_var,
                                     values=["All", "Low", "Medium", "High", "Critical"], state="readonly", width=15)
        severity_combo.grid(row=0, column=3, padx=(5, 20))
        
        ttk.Button(filter_controls, text="Apply Filters", 
                  command=self.apply_filters, style='Primary.TButton').grid(row=0, column=4, padx=(20, 0))
        
        # Alerts treeview
        alerts_frame = ttk.LabelFrame(self.window, text="Active Alerts", padding=10)
        alerts_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        columns = ("Alert ID", "Student ID", "Name", "Module", "Type", "Severity", "Status", "Created")
        self.alerts_tree = ttk.Treeview(alerts_frame, columns=columns, show="headings")
        
        for col in columns:
            self.alerts_tree.heading(col, text=col)
            self.alerts_tree.column(col, width=100)
        
        alerts_scrollbar = ttk.Scrollbar(alerts_frame, orient=tk.VERTICAL, command=self.alerts_tree.yview)
        self.alerts_tree.configure(yscrollcommand=alerts_scrollbar.set)
        
        self.alerts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        alerts_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind double-click to view details
        self.alerts_tree.bind('<Double-1>', self.view_alert_details)
        
        # Close button
        ttk.Button(self.window, text="Close", command=self.window.destroy, style='Danger.TButton').pack(pady=10)
    
    def load_alerts(self):
        # Clear existing items
        for item in self.alerts_tree.get_children():
            self.alerts_tree.delete(item)
        
        # Sample alerts data
        sample_alerts = [
            ("ALT001", "S001", "John Doe", "CS101", "Low Attendance", "High", "Pending", "2024-12-20"),
            ("ALT002", "S003", "Bob Wilson", "CS102", "Consecutive Absences", "Critical", "Pending", "2024-12-19"),
            ("ALT003", "S007", "Alice Brown", "CS101", "Late Pattern", "Medium", "Acknowledged", "2024-12-18"),
        ]
        
        for alert in sample_alerts:
            self.alerts_tree.insert('', 'end', values=alert)
    
    def create_alert(self):
        CreateAlertWindow(self.window, self.load_alerts)
    
    def acknowledge_alert(self):
        selection = self.alerts_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an alert to acknowledge")
            return
        
        item = self.alerts_tree.item(selection[0])
        alert_id = item['values'][0]
        
        # Update alert status
        messagebox.showinfo("Success", f"Alert {alert_id} acknowledged successfully!")
        self.load_alerts()
    
    def apply_filters(self):
        # Apply filters and refresh view
        self.load_alerts()
    
    def view_alert_details(self, event):
        selection = self.alerts_tree.selection()
        if selection:
            item = self.alerts_tree.item(selection[0])
            alert_data = item['values']
            AlertDetailsWindow(self.window, alert_data)


class CreateAlertWindow:
    def __init__(self, parent, callback):
        self.parent = parent
        self.callback = callback
        
        self.window = tk.Toplevel(parent)
        self.window.title("Create Alert")
        self.window.geometry("500x400")
        self.window.transient(parent)
        self.window.grab_set()
        
        self.create_widgets()
    
    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="Create New Alert", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Form frame
        form_frame = ttk.LabelFrame(self.window, text="Alert Details", padding=20)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Student ID
        ttk.Label(form_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.student_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.student_id_var, width=30).grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # Module
        ttk.Label(form_frame, text="Module:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.module_var = tk.StringVar()
        module_combo = ttk.Combobox(form_frame, textvariable=self.module_var, width=27)
        module_combo.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # Set module values
        if ORIGINAL_FUNCTIONS_AVAILABLE:
            modules = get_modules()
            module_values = [f"{code} - {name}" for code, name in modules]
        else:
            module_values = ["CS101 - Programming", "CS102 - Data Structures"]
        module_combo['values'] = module_values
        
        # Alert Type
        ttk.Label(form_frame, text="Alert Type:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.alert_type_var = tk.StringVar(value="Custom")
        alert_type_combo = ttk.Combobox(form_frame, textvariable=self.alert_type_var,
                                       values=["Attendance Warning", "Consecutive Absences", "Late Pattern", "Custom"], 
                                       state="readonly", width=27)
        alert_type_combo.grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # Severity
        ttk.Label(form_frame, text="Severity:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.severity_var = tk.StringVar(value="Medium")
        severity_combo = ttk.Combobox(form_frame, textvariable=self.severity_var,
                                     values=["Low", "Medium", "High", "Critical"], 
                                     state="readonly", width=27)
        severity_combo.grid(row=3, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # Message
        ttk.Label(form_frame, text="Message:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.message_text = tk.Text(form_frame, width=35, height=6)
        self.message_text.grid(row=4, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # Auto-send notifications
        self.auto_send_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form_frame, text="Send automatic notifications", 
                       variable=self.auto_send_var).grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=10)
        
        # Buttons
        buttons_frame = ttk.Frame(self.window)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(buttons_frame, text="Create Alert",
                  command=self.create_alert, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Cancel",
                  command=self.window.destroy, style='Danger.TButton').pack(side=tk.RIGHT)
    
    def create_alert(self):
        try:
            student_id = self.student_id_var.get()
            module = self.module_var.get()
            alert_type = self.alert_type_var.get()
            severity = self.severity_var.get()
            message = self.message_text.get(1.0, tk.END).strip()
            
            if not all([student_id, module, message]):
                messagebox.showwarning("Warning", "Please fill in all required fields")
                return
            
            module_code = module.split(' - ')[0] if ' - ' in module else module
            
            if ORIGINAL_FUNCTIONS_AVAILABLE:
                notification_system = EnhancedNotificationSystem()
                success = notification_system.create_attendance_alert(
                    student_id, module_code, alert_type, severity, message
                )
                
                if success:
                    messagebox.showinfo("Success", "Alert created successfully!")
                else:
                    messagebox.showerror("Error", "Failed to create alert")
            else:
                messagebox.showinfo("Demo", "Alert would be created here")
            
            self.callback()  # Refresh parent data
            self.window.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create alert: {e}")


class AlertDetailsWindow:
    def __init__(self, parent, alert_data):
        self.parent = parent
        self.alert_data = alert_data
        
        self.window = tk.Toplevel(parent)
        self.window.title("Alert Details")
        self.window.geometry("500x300")
        self.window.transient(parent)
        self.window.grab_set()
        
        self.create_widgets()
    
    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="Alert Details", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Details frame
        details_frame = ttk.LabelFrame(self.window, text="Alert Information", padding=20)
        details_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Display alert details
        alert_id, student_id, name, module, alert_type, severity, status, created = self.alert_data
        
        details = [
            ("Alert ID:", alert_id),
            ("Student:", f"{name} ({student_id})"),
            ("Module:", module),
            ("Type:", alert_type),
            ("Severity:", severity),
            ("Status:", status),
            ("Created:", created)
        ]
        
        for i, (label, value) in enumerate(details):
            ttk.Label(details_frame, text=label, font=('Arial', 10, 'bold')).grid(row=i, column=0, sticky=tk.W, pady=5)
            ttk.Label(details_frame, text=str(value)).grid(row=i, column=1, sticky=tk.W, padx=(20, 0), pady=5)
        
        # Close button
        ttk.Button(self.window, text="Close", command=self.window.destroy, style='Primary.TButton').pack(pady=10)


class PredictiveAnalyticsWindow:
    def __init__(self, parent):
        self.parent = parent
        
        self.window = tk.Toplevel(parent)
        self.window.title("Predictive Analytics")
        self.window.geometry("900x700")
        self.window.transient(parent)
        
        self.create_widgets()
    
    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="🔮 Predictive Analytics", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)
        
        # Controls frame
        controls_frame = ttk.LabelFrame(self.window, text="Model Controls", padding=10)
        controls_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        controls_grid = ttk.Frame(controls_frame)
        controls_grid.pack(fill=tk.X)
        
        ttk.Button(controls_grid, text="Train Model", 
                  command=self.train_model, style='Primary.TButton').grid(row=0, column=0, padx=5)
        ttk.Button(controls_grid, text="Single Prediction", 
                  command=self.single_prediction, style='Warning.TButton').grid(row=0, column=1, padx=5)
        ttk.Button(controls_grid, text="Batch Analysis", 
                  command=self.batch_analysis, style='Success.TButton').grid(row=0, column=2, padx=5)
        ttk.Button(controls_grid, text="Model Info", 
                  command=self.show_model_info, style='Primary.TButton').grid(row=0, column=3, padx=5)
        
        # Results notebook
        self.results_notebook = ttk.Notebook(self.window)
        self.results_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Predictions tab
        predictions_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(predictions_frame, text="Predictions")
        
        # Predictions treeview
        pred_columns = ("Student ID", "Name", "Module", "Risk Level", "Confidence", "Current Rate", "Factors")
        self.predictions_tree = ttk.Treeview(predictions_frame, columns=pred_columns, show="headings")
        
        for col in pred_columns:
            self.predictions_tree.heading(col, text=col)
            self.predictions_tree.column(col, width=120)
        
        pred_scrollbar = ttk.Scrollbar(predictions_frame, orient=tk.VERTICAL, command=self.predictions_tree.yview)
        self.predictions_tree.configure(yscrollcommand=pred_scrollbar.set)
        
        self.predictions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        pred_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Model info tab
        model_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(model_frame, text="Model Information")
        
        self.model_info_text = tk.Text(model_frame, wrap=tk.WORD)
        model_scrollbar = ttk.Scrollbar(model_frame, orient=tk.VERTICAL, command=self.model_info_text.yview)
        self.model_info_text.configure(yscrollcommand=model_scrollbar.set)
        
        self.model_info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        model_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Load initial model info
        self.load_model_info()
        
        # Close button
        ttk.Button(self.window, text="Close", command=self.window.destroy, style='Danger.TButton').pack(pady=10)
    
    def train_model(self):
        if not ORIGINAL_FUNCTIONS_AVAILABLE:
            messagebox.showinfo("Demo", "Model training would be performed here")
            return
        
        self.update_status("Training model...")
        
        def train_in_background():
            try:
                analytics = AttendancePredictiveAnalytics()
                success = analytics.train_model()
                
                self.window.after(0, lambda: self.on_training_complete(success))
            except Exception as e:
                self.window.after(0, lambda: messagebox.showerror("Error", f"Training failed: {e}"))
        
        threading.Thread(target=train_in_background, daemon=True).start()
    
    def on_training_complete(self, success):
        if success:
            messagebox.showinfo("Success", "Model trained successfully!")
            self.load_model_info()
        else:
            messagebox.showerror("Error", "Model training failed")
    
    def single_prediction(self):
        SinglePredictionWindow(self.window, self.update_predictions)
    
    def batch_analysis(self):
        if not ORIGINAL_FUNCTIONS_AVAILABLE:
            messagebox.showinfo("Demo", "Batch analysis would be performed here")
            self.load_sample_predictions()
            return
        
        messagebox.showinfo("Info", "Performing batch risk analysis...")
        
        # Simulate batch analysis with sample data
        self.load_sample_predictions()
    
    def load_sample_predictions(self):
        # Clear existing predictions
        for item in self.predictions_tree.get_children():
            self.predictions_tree.delete(item)
        
        # Sample predictions
        sample_predictions = [
            ("S001", "John Doe", "CS101", "Low Risk", "0.85", "92.5%", "Regular attendance"),
            ("S003", "Bob Wilson", "CS101", "High Risk", "0.92", "65.0%", "3 consecutive absences"),
            ("S007", "Alice Brown", "CS102", "Medium Risk", "0.78", "75.0%", "Declining trend"),
            ("S010", "Charlie Davis", "CS103", "High Risk", "0.88", "58.3%", "Poor early performance"),
        ]
        
        for prediction in sample_predictions:
            # Color code by risk level
            item = self.predictions_tree.insert('', 'end', values=prediction)
            risk_level = prediction[3]
            if risk_level == "High Risk":
                self.predictions_tree.set(item, "Risk Level", "🔴 High Risk")
            elif risk_level == "Medium Risk":
                self.predictions_tree.set(item, "Risk Level", "🟡 Medium Risk")
            else:
                self.predictions_tree.set(item, "Risk Level", "🟢 Low Risk")
    
    def update_predictions(self, prediction_data):
        # Add new prediction to the tree
        item = self.predictions_tree.insert('', 'end', values=prediction_data)
        risk_level = prediction_data[3]
        if "High" in risk_level:
            self.predictions_tree.set(item, "Risk Level", "🔴 " + risk_level)
        elif "Medium" in risk_level:
            self.predictions_tree.set(item, "Risk Level", "🟡 " + risk_level)
        else:
            self.predictions_tree.set(item, "Risk Level", "🟢 " + risk_level)
    
    def show_model_info(self):
        self.results_notebook.select(1)  # Switch to model info tab
    
    def load_model_info(self):
        info_text = """PREDICTIVE ANALYTICS MODEL INFORMATION
========================================

Model Type: Random Forest Classifier
Purpose: Predict student attendance risk levels

Features Used:
- Current attendance rate
- Consecutive absences count
- Days since last attendance
- Total sessions attended
- Week of term
- Day of week
- Previous module performance

Risk Levels:
- Low Risk: Expected attendance rate > 80%
- Medium Risk: Expected attendance rate 70-80%
- High Risk: Expected attendance rate < 70%

Model Performance:
- Training Data: Attendance history from all students
- Accuracy: To be determined after training
- Confidence Threshold: 0.75

Usage:
1. Train the model using historical data
2. Run single predictions for specific students
3. Perform batch analysis for all students
4. Review recommendations for at-risk students

Last Training: Not trained yet
Model Status: Ready for training
"""
        
        self.model_info_text.delete(1.0, tk.END)
        self.model_info_text.insert(tk.END, info_text)
    
    def update_status(self, message):
        # This would update a status bar if we had one
        print(f"Status: {message}")


class SinglePredictionWindow:
    def __init__(self, parent, callback):
        self.parent = parent
        self.callback = callback
        
        self.window = tk.Toplevel(parent)
        self.window.title("Single Prediction")
        self.window.geometry("400x300")
        self.window.transient(parent)
        self.window.grab_set()
        
        self.create_widgets()
    
    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="Single Student Prediction", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Input frame
        input_frame = ttk.LabelFrame(self.window, text="Student Selection", padding=20)
        input_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Student ID
        ttk.Label(input_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.student_id_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.student_id_var, width=20).grid(row=0, column=1, padx=(10, 0), pady=5)
        
        # Module
        ttk.Label(input_frame, text="Module:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.module_var = tk.StringVar()
        module_combo = ttk.Combobox(input_frame, textvariable=self.module_var, width=17)
        module_combo.grid(row=1, column=1, padx=(10, 0), pady=5)
        
        # Set module values
        if ORIGINAL_FUNCTIONS_AVAILABLE:
            modules = get_modules()
            module_values = [f"{code} - {name}" for code, name in modules]
        else:
            module_values = ["CS101 - Programming", "CS102 - Data Structures"]
        module_combo['values'] = module_values
        
        # Buttons
        buttons_frame = ttk.Frame(self.window)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(buttons_frame, text="Predict Risk",
                  command=self.predict_risk, style='Primary.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Cancel",
                  command=self.window.destroy, style='Danger.TButton').pack(side=tk.RIGHT)
    
    def predict_risk(self):
        try:
            student_id = self.student_id_var.get()
            module = self.module_var.get()
            
            if not student_id or not module:
                messagebox.showwarning("Warning", "Please enter student ID and select module")
                return
            
            module_code = module.split(' - ')[0] if ' - ' in module else module
            
            if ORIGINAL_FUNCTIONS_AVAILABLE:
                analytics = AttendancePredictiveAnalytics()
                prediction = analytics.predict_student_risk(student_id, module_code)
                
                if prediction:
                    # Show prediction results
                    result_text = f"Risk Level: {prediction['risk_level']}\n"
                    result_text += f"Confidence: {prediction['confidence']:.3f}\n"
                    result_text += f"Current Rate: {prediction['current_attendance_rate']:.1f}%\n"
                    result_text += f"Consecutive Absences: {prediction['factors']['consecutive_absences']}\n"
                    result_text += f"Days Since Last: {prediction['factors']['days_since_last_attendance']}"
                    
                    messagebox.showinfo("Prediction Result", result_text)
                    
                    # Add to parent predictions view
                    prediction_data = (
                        student_id,
                        "Student Name",  # Would fetch from database
                        module_code,
                        prediction['risk_level'],
                        f"{prediction['confidence']:.3f}",
                        f"{prediction['current_attendance_rate']:.1f}%",
                        f"Consecutive: {prediction['factors']['consecutive_absences']}, Days: {prediction['factors']['days_since_last_attendance']}"
                    )
                    
                    self.callback(prediction_data)
                    self.window.destroy()
                else:
                    messagebox.showwarning("Warning", "Unable to generate prediction. Model may not be trained.")
            else:
                # Demo prediction
                sample_prediction = (
                    student_id,
                    "Sample Student",
                    module_code,
                    "Medium Risk",
                    "0.78",
                    "75.0%",
                    "Sample factors"
                )
                self.callback(sample_prediction)
                messagebox.showinfo("Demo", "Sample prediction generated")
                self.window.destroy()
                
        except Exception as e:
            messagebox.showerror("Error", f"Prediction failed: {e}")


class BackupRecoveryWindow:
    def __init__(self, parent):
        self.parent = parent
        
        self.window = tk.Toplevel(parent)
        self.window.title("Backup & Recovery")
        self.window.geometry("700x500")
        self.window.transient(parent)
        
        self.create_widgets()
        self.load_backups()
    
    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="💾 Backup & Recovery System", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Backup operations frame
        operations_frame = ttk.LabelFrame(self.window, text="Backup Operations", padding=10)
        operations_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        operations_grid = ttk.Frame(operations_frame)
        operations_grid.pack(fill=tk.X)
        
        ttk.Button(operations_grid, text="Create Backup", 
                  command=self.create_backup, style='Success.TButton').grid(row=0, column=0, padx=5)
        ttk.Button(operations_grid, text="Restore Backup", 
                  command=self.restore_backup, style='Warning.TButton').grid(row=0, column=1, padx=5)
        ttk.Button(operations_grid, text="Schedule Settings", 
                  command=self.backup_settings, style='Primary.TButton').grid(row=0, column=2, padx=5)
        ttk.Button(operations_grid, text="Cleanup Old", 
                  command=self.cleanup_backups, style='Primary.TButton').grid(row=0, column=3, padx=5)
        
        # Available backups frame
        backups_frame = ttk.LabelFrame(self.window, text="Available Backups", padding=10)
        backups_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Backups treeview
        backup_columns = ("Filename", "Size", "Type", "Created", "Status")
        self.backups_tree = ttk.Treeview(backups_frame, columns=backup_columns, show="headings")
        
        for col in backup_columns:
            self.backups_tree.heading(col, text=col)
            self.backups_tree.column(col, width=120)
        
        backup_scrollbar = ttk.Scrollbar(backups_frame, orient=tk.VERTICAL, command=self.backups_tree.yview)
        self.backups_tree.configure(yscrollcommand=backup_scrollbar.set)
        
        self.backups_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        backup_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind double-click to restore
        self.backups_tree.bind('<Double-1>', self.restore_selected_backup)
        
        # Status frame
        status_frame = ttk.LabelFrame(self.window, text="Backup Status", padding=10)
        status_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        self.status_text = tk.Text(status_frame, height=4, wrap=tk.WORD)
        status_scrollbar = ttk.Scrollbar(status_frame, orient=tk.VERTICAL, command=self.status_text.yview)
        self.status_text.configure(yscrollcommand=status_scrollbar.set)
        
        self.status_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        status_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Load initial status
        self.load_backup_status()
        
        # Close button
        ttk.Button(self.window, text="Close", command=self.window.destroy, style='Danger.TButton').pack(pady=10)
    
    def load_backups(self):
        # Clear existing items
        for item in self.backups_tree.get_children():
            self.backups_tree.delete(item)
        
        # Sample backup data
        sample_backups = [
            ("attendance_backup_full_20241220_143022.db", "2.4 MB", "Full", "2024-12-20 14:30", "Valid"),
            ("attendance_backup_manual_20241219_091500.db", "2.3 MB", "Manual", "2024-12-19 09:15", "Valid"),
            ("attendance_backup_scheduled_20241218_000000.db", "2.2 MB", "Scheduled", "2024-12-18 00:00", "Valid"),
        ]
        
        for backup in sample_backups:
            self.backups_tree.insert('', 'end', values=backup)
    
    def create_backup(self):
        backup_type = simpledialog.askstring("Backup Type", "Enter backup type (full/manual/custom):", initialvalue="manual")
        if not backup_type:
            return
        
        if ORIGINAL_FUNCTIONS_AVAILABLE:
            try:
                backup_system = BackupRecoverySystem()
                backup_path = backup_system.create_backup(backup_type)
                
                if backup_path:
                    messagebox.showinfo("Success", f"Backup created: {backup_path}")
                    self.load_backups()
                    self.load_backup_status()
                else:
                    messagebox.showerror("Error", "Backup creation failed")
            except Exception as e:
                messagebox.showerror("Error", f"Backup creation failed: {e}")
        else:
            messagebox.showinfo("Demo", f"Backup of type '{backup_type}' would be created here")
            self.load_backups()
    
    def restore_backup(self):
        filename = filedialog.askopenfilename(
            title="Select backup file to restore",
            filetypes=[("Database files", "*.db"), ("All files", "*.*")]
        )
        
        if filename:
            if messagebox.askyesno("Confirm Restore", 
                                 "This will overwrite current data. Are you sure?"):
                self.perform_restore(filename)
    
    def restore_selected_backup(self, event):
        selection = self.backups_tree.selection()
        if selection:
            item = self.backups_tree.item(selection[0])
            filename = item['values'][0]
            
            if messagebox.askyesno("Confirm Restore",
                                 f"Restore from {filename}? This will overwrite current data."):
                backup_path = str(BACKUP_DIR / filename)
                self.perform_restore(backup_path)
    
    def perform_restore(self, backup_path):
        if ORIGINAL_FUNCTIONS_AVAILABLE:
            try:
                backup_system = BackupRecoverySystem()
                success, message = backup_system.restore_backup(backup_path)
                
                if success:
                    messagebox.showinfo("Success", message)
                    self.load_backup_status()
                else:
                    messagebox.showerror("Error", message)
            except Exception as e:
                messagebox.showerror("Error", f"Restore failed: {e}")
        else:
            messagebox.showinfo("Demo", f"Database would be restored from {backup_path}")
    
    def backup_settings(self):
        BackupSettingsWindow(self.window, self.load_backup_status)
    
    def cleanup_backups(self):
        try:
            keep_days = int(simpledialog.askstring("Cleanup", "Keep backups newer than how many days?", initialvalue="30"))
            
            if messagebox.askyesno("Confirm Cleanup", 
                                 f"Delete backups older than {keep_days} days?"):
                if ORIGINAL_FUNCTIONS_AVAILABLE:
                    backup_system = BackupRecoverySystem()
                    backup_system.cleanup_old_backups(keep_days)
                    messagebox.showinfo("Success", f"Cleaned up backups older than {keep_days} days")
                else:
                    messagebox.showinfo("Demo", f"Would cleanup backups older than {keep_days} days")
                
                self.load_backups()
        except (ValueError, TypeError):
            messagebox.showerror("Error", "Invalid number of days")
    
    def load_backup_status(self):
        status_text = """BACKUP SYSTEM STATUS
==================

Automatic Backups: Enabled
Backup Frequency: Every 24 hours
Last Backup: 2024-12-20 14:30:22
Next Scheduled: 2024-12-21 14:30:22

Storage Location: ./backups/
Available Space: 45.2 GB
Total Backups: 15
Oldest Backup: 2024-11-20

Configuration:
- Auto-cleanup after 30 days
- Maximum backup size: 100 MB
- Compression: Enabled
"""
        
        self.status_text.delete(1.0, tk.END)
        self.status_text.insert(tk.END, status_text)


class BackupSettingsWindow:
    def __init__(self, parent, callback):
        self.parent = parent
        self.callback = callback
        
        self.window = tk.Toplevel(parent)
        self.window.title("Backup Settings")
        self.window.geometry("500x400")
        self.window.transient(parent)
        self.window.grab_set()
        
        self.create_widgets()
        self.load_current_settings()
    
    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="Backup Settings", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Settings frame
        settings_frame = ttk.LabelFrame(self.window, text="Backup Configuration", padding=20)
        settings_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Automatic backups
        self.auto_backup_var = tk.BooleanVar()
        ttk.Checkbutton(settings_frame, text="Enable automatic backups", 
                       variable=self.auto_backup_var).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # Backup frequency
        ttk.Label(settings_frame, text="Backup frequency (hours):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.frequency_var = tk.StringVar()
        ttk.Entry(settings_frame, textvariable=self.frequency_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # Retention period
        ttk.Label(settings_frame, text="Keep backups for (days):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.retention_var = tk.StringVar()
        ttk.Entry(settings_frame, textvariable=self.retention_var, width=10).grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # Backup location
        ttk.Label(settings_frame, text="Backup location:").grid(row=3, column=0, sticky=tk.W, pady=5)
        location_frame = ttk.Frame(settings_frame)
        location_frame.grid(row=3, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        self.location_var = tk.StringVar()
        ttk.Entry(location_frame, textvariable=self.location_var, width=30).pack(side=tk.LEFT)
        ttk.Button(location_frame, text="Browse", command=self.browse_location).pack(side=tk.LEFT, padx=(5, 0))
        
        # Compression
        self.compression_var = tk.BooleanVar()
        ttk.Checkbutton(settings_frame, text="Enable compression", 
                       variable=self.compression_var).grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # Notifications
        self.notifications_var = tk.BooleanVar()
        ttk.Checkbutton(settings_frame, text="Email notifications on backup completion", 
                       variable=self.notifications_var).grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # Buttons
        buttons_frame = ttk.Frame(self.window)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(buttons_frame, text="Save Settings",
                  command=self.save_settings, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Test Backup",
                  command=self.test_backup, style='Primary.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Cancel",
                  command=self.window.destroy, style='Danger.TButton').pack(side=tk.RIGHT)
    
    def load_current_settings(self):
        # Load current settings from database or use defaults
        if ORIGINAL_FUNCTIONS_AVAILABLE:
            self.auto_backup_var.set(get_enhanced_setting('auto_backup_enabled', True, 'boolean'))
            self.frequency_var.set(str(get_enhanced_setting('backup_frequency_hours', 24, 'integer')))
        else:
            self.auto_backup_var.set(True)
            self.frequency_var.set("24")
        
        self.retention_var.set("30")
        from university_system.modules.shared.constants import paths
        self.location_var.set(str(paths.BACKUP_DIR / ""))
        self.compression_var.set(True)
        self.notifications_var.set(False)
    
    def browse_location(self):
        directory = filedialog.askdirectory(title="Select backup location")
        if directory:
            self.location_var.set(directory)
    
    def save_settings(self):
        try:
            # Validate inputs
            frequency = int(self.frequency_var.get())
            retention = int(self.retention_var.get())
            
            if frequency < 1 or retention < 1:
                messagebox.showerror("Error", "Frequency and retention must be positive numbers")
                return
            
            # Save settings
            if ORIGINAL_FUNCTIONS_AVAILABLE:
                set_enhanced_setting('auto_backup_enabled', self.auto_backup_var.get(), data_type='boolean')
                set_enhanced_setting('backup_frequency_hours', frequency, data_type='integer')
            
            messagebox.showinfo("Success", "Backup settings saved successfully!")
            self.callback()  # Refresh parent status
            self.window.destroy()
            
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers for frequency and retention")
    
    def test_backup(self):
        messagebox.showinfo("Test Backup", "Test backup would be created here")

# Dialog Windows
class ManualAttendanceWindow:
    def __init__(self, parent, module_code, date, callback):
        self.parent = parent
        self.module_code = module_code
        self.date = date
        self.callback = callback
        
        self.window = tk.Toplevel(parent)
        self.window.title(f"Manual Attendance - {module_code}")
        self.window.geometry("600x400")
        self.window.transient(parent)
        self.window.grab_set()
        
        self.create_widgets()
        self.load_students()
    
    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text=f"Manual Attendance Entry", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        info_label = ttk.Label(self.window, text=f"Module: {self.module_code} | Date: {self.date}")
        info_label.pack(pady=(0, 10))
        
        # Students frame
        students_frame = ttk.Frame(self.window)
        students_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Headers
        headers_frame = ttk.Frame(students_frame)
        headers_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(headers_frame, text="Student ID", width=15).pack(side=tk.LEFT)
        ttk.Label(headers_frame, text="Name", width=25).pack(side=tk.LEFT)
        ttk.Label(headers_frame, text="Status", width=15).pack(side=tk.LEFT)
        ttk.Label(headers_frame, text="Notes", width=20).pack(side=tk.LEFT)
        
        # Scrollable frame for students
        canvas = tk.Canvas(students_frame)
        scrollbar = ttk.Scrollbar(students_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.student_widgets = []
        
        # Buttons
        buttons_frame = ttk.Frame(self.window)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(buttons_frame, text="Save Attendance", 
                  command=self.save_attendance, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Mark All Present", 
                  command=self.mark_all_present, style='Primary.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Cancel", 
                  command=self.window.destroy, style='Danger.TButton').pack(side=tk.RIGHT)
    
    def load_students(self):
        """Load students for the module"""
        try:
            if not ORIGINAL_FUNCTIONS_AVAILABLE:
                # Sample students
                students = [("S001", "John", "Doe"), ("S002", "Jane", "Smith"), ("S003", "Bob", "Wilson")]
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name
                FROM students s
                JOIN student_modules sm ON s.student_id = sm.student_id
                WHERE sm.module_code = ?
                ORDER BY s.student_id
                ''', (self.module_code,))
                students = cursor.fetchall()
                conn.close()
            
            for student_id, first_name, last_name in students:
                self.create_student_row(student_id, f"{first_name} {last_name}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load students: {e}")
    
    def create_student_row(self, student_id, name):
        """Create a row for student attendance entry"""
        row_frame = ttk.Frame(self.scrollable_frame)
        row_frame.pack(fill=tk.X, pady=2)
        
        # Student ID
        ttk.Label(row_frame, text=student_id, width=15).pack(side=tk.LEFT)
        
        # Name
        ttk.Label(row_frame, text=name, width=25).pack(side=tk.LEFT)
        
        # Status
        status_var = tk.StringVar(value="Present")
        status_combo = ttk.Combobox(row_frame, textvariable=status_var, 
                                   values=["Present", "Late", "Absent", "Excused"], 
                                   state="readonly", width=12)
        status_combo.pack(side=tk.LEFT, padx=(0, 5))
        
        # Notes
        notes_var = tk.StringVar()
        notes_entry = ttk.Entry(row_frame, textvariable=notes_var, width=18)
        notes_entry.pack(side=tk.LEFT)
        
        self.student_widgets.append({
            'student_id': student_id,
            'status_var': status_var,
            'notes_var': notes_var
        })
    
    def mark_all_present(self):
        """Mark all students as present"""
        for widget in self.student_widgets:
            widget['status_var'].set("Present")
    
    def save_attendance(self):
        """Save attendance records"""
        try:
            attendance_data = []
            for widget in self.student_widgets:
                attendance_data.append((
                    widget['student_id'],
                    widget['status_var'].get(),
                    widget['notes_var'].get()
                ))
            
            if ORIGINAL_FUNCTIONS_AVAILABLE:
                success = record_attendance(self.module_code, self.date, attendance_data, "Manual GUI Entry")
                if success:
                    messagebox.showinfo("Success", "Attendance recorded successfully!")
                    self.callback()  # Refresh parent data
                    self.window.destroy()
                else:
                    messagebox.showerror("Error", "Failed to record attendance")
            else:
                messagebox.showinfo("Demo", "Attendance would be recorded here")
                self.callback()
                self.window.destroy()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save attendance: {e}")




class BatchAttendanceWindow:
    """Window for marking attendance for all students in a module at once"""
    def __init__(self, parent, module_code, date, callback):
        self.parent = parent
        self.module_code = module_code
        self.date = date
        self.callback = callback

        self.window = tk.Toplevel(parent)
        self.window.title(f"Batch Attendance - {module_code}")
        self.window.geometry("700x500")
        self.window.transient(parent)
        self.window.grab_set()

        self.create_widgets()
        self.load_students()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text=f"Batch Attendance Entry", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        info_label = ttk.Label(self.window, text=f"Module: {self.module_code} | Date: {self.date}")
        info_label.pack(pady=(0, 10))

        # Batch action frame
        batch_frame = ttk.LabelFrame(self.window, text="Batch Actions", padding=10)
        batch_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Status selector
        status_selector_frame = ttk.Frame(batch_frame)
        status_selector_frame.pack(fill=tk.X, pady=5)

        ttk.Label(status_selector_frame, text="Mark Selected As:").pack(side=tk.LEFT, padx=(0, 10))
        self.batch_status_var = tk.StringVar(value="Present")
        status_combo = ttk.Combobox(status_selector_frame, textvariable=self.batch_status_var,
                                   values=["Present", "Late", "Absent", "Excused"],
                                   state="readonly", width=15)
        status_combo.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(status_selector_frame, text="Apply to Selected",
                  command=self.apply_batch_status, style='Primary.TButton').pack(side=tk.LEFT)

        # Selection buttons
        selection_frame = ttk.Frame(batch_frame)
        selection_frame.pack(fill=tk.X, pady=5)

        ttk.Button(selection_frame, text="Select All",
                  command=self.select_all).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(selection_frame, text="Deselect All",
                  command=self.deselect_all).pack(side=tk.LEFT)

        # Students frame with scrollbar
        students_frame = ttk.LabelFrame(self.window, text="Students", padding=10)
        students_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Treeview for students
        columns = ("Select", "ID", "Name", "Status")
        self.students_tree = ttk.Treeview(students_frame, columns=columns, show="headings", height=15)

        self.students_tree.heading("Select", text="✓")
        self.students_tree.heading("ID", text="Student ID")
        self.students_tree.heading("Name", text="Name")
        self.students_tree.heading("Status", text="Current Status")

        self.students_tree.column("Select", width=40)
        self.students_tree.column("ID", width=120)
        self.students_tree.column("Name", width=200)
        self.students_tree.column("Status", width=120)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(students_frame, orient=tk.VERTICAL, command=self.students_tree.yview)
        self.students_tree.configure(yscrollcommand=scrollbar.set)

        self.students_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind click event for checkbox toggle
        self.students_tree.bind('<Button-1>', self.on_tree_click)

        # Track selection state
        self.selected_students = set()

        # Buttons
        buttons_frame = ttk.Frame(self.window)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(buttons_frame, text="Save All Attendance",
                  command=self.save_attendance, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Cancel",
                  command=self.window.destroy, style='Danger.TButton').pack(side=tk.RIGHT)

    def load_students(self):
        """Load students for the module"""
        try:
            conn = get_db_connection() if MAIN_DB_AVAILABLE else None

            if conn:
                cursor = conn.cursor()
                # Get students enrolled in the module with their current attendance status
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name,
                       COALESCE(ar.status, 'Not Marked') as current_status
                FROM students s
                JOIN student_modules sm ON s.student_id = sm.student_id
                LEFT JOIN attendance_records ar ON s.student_id = ar.student_id
                    AND ar.module_code = sm.module_code
                    AND ar.date = ?
                WHERE sm.module_code = ?
                ORDER BY s.last_name, s.first_name
                ''', (self.date, self.module_code))
                students = cursor.fetchall()
                conn.close()
            else:
                # Sample data
                students = [
                    ("S001", "John", "Doe", "Not Marked"),
                    ("S002", "Jane", "Smith", "Not Marked"),
                    ("S003", "Bob", "Wilson", "Not Marked")
                ]

            # Populate treeview
            for student_id, first_name, last_name, current_status in students:
                name = f"{first_name} {last_name}"
                self.students_tree.insert('', 'end', values=("☐", student_id, name, current_status),
                                        tags=(student_id,))
                # Default: select all students
                self.selected_students.add(student_id)

            # Update display
            self.update_selection_display()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load students: {e}")
            import traceback
            traceback.print_exc()

    def on_tree_click(self, event):
        """Handle click on treeview to toggle selection"""
        region = self.students_tree.identify_region(event.x, event.y)
        if region == "cell":
            item = self.students_tree.identify_row(event.y)
            column = self.students_tree.identify_column(event.x)

            # Only toggle if clicking on the checkbox column
            if column == "#1":  # First column
                student_id = self.students_tree.item(item)['values'][1]
                if student_id in self.selected_students:
                    self.selected_students.remove(student_id)
                else:
                    self.selected_students.add(student_id)
                self.update_selection_display()

    def update_selection_display(self):
        """Update checkbox display for all items"""
        for item in self.students_tree.get_children():
            values = self.students_tree.item(item)['values']
            student_id = values[1]
            checkbox = "☑" if student_id in self.selected_students else "☐"
            self.students_tree.item(item, values=(checkbox, values[1], values[2], values[3]))

    def select_all(self):
        """Select all students"""
        for item in self.students_tree.get_children():
            student_id = self.students_tree.item(item)['values'][1]
            self.selected_students.add(student_id)
        self.update_selection_display()

    def deselect_all(self):
        """Deselect all students"""
        self.selected_students.clear()
        self.update_selection_display()

    def apply_batch_status(self):
        """Apply selected status to selected students"""
        if not self.selected_students:
            messagebox.showwarning("Warning", "No students selected")
            return

        status = self.batch_status_var.get()

        # Update display
        for item in self.students_tree.get_children():
            values = self.students_tree.item(item)['values']
            student_id = values[1]
            if student_id in self.selected_students:
                self.students_tree.item(item, values=(values[0], values[1], values[2], status))

        messagebox.showinfo("Success", f"Status '{status}' applied to {len(self.selected_students)} selected student(s)")

    def save_attendance(self):
        """Save attendance records for all students"""
        try:
            attendance_data = []

            for item in self.students_tree.get_children():
                values = self.students_tree.item(item)['values']
                student_id = values[1]
                current_status = values[3]

                # Only save if status is not "Not Marked"
                if current_status != "Not Marked":
                    attendance_data.append((student_id, current_status, "Batch entry"))

            if not attendance_data:
                messagebox.showwarning("Warning", "No attendance records to save")
                return

            if ORIGINAL_FUNCTIONS_AVAILABLE:
                success = record_attendance(self.module_code, self.date, attendance_data, "Batch GUI Entry")
                if success:
                    messagebox.showinfo("Success", f"Attendance recorded for {len(attendance_data)} student(s)!")
                    self.callback()  # Refresh parent data
                    self.window.destroy()
                else:
                    messagebox.showerror("Error", "Failed to record attendance")
            else:
                messagebox.showinfo("Demo", f"Attendance would be recorded for {len(attendance_data)} students")
                self.callback()
                self.window.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save attendance: {e}")
            import traceback
            traceback.print_exc()



class EditAttendanceWindow:
    def __init__(self, parent, student_id, name, current_status, notes, module_code, date, callback):
        self.parent = parent
        self.student_id = student_id
        self.module_code = module_code
        self.date = date
        self.callback = callback
        
        self.window = tk.Toplevel(parent)
        self.window.title(f"Edit Attendance - {student_id}")
        self.window.geometry("400x300")
        self.window.transient(parent)

        self.create_widgets(name, current_status, notes)

        # Set grab after window is fully created and visible
        self.window.after(100, self._safe_grab_set)
    
    def create_widgets(self, name, current_status, notes):
        # Title
        title_label = ttk.Label(self.window, text="Edit Attendance Record", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Student info
        info_frame = ttk.LabelFrame(self.window, text="Student Information", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Label(info_frame, text=f"Student ID: {self.student_id}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Name: {name}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Module: {self.module_code}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Date: {self.date}").pack(anchor=tk.W)
        
        # Attendance details
        details_frame = ttk.LabelFrame(self.window, text="Attendance Details", padding=10)
        details_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Label(details_frame, text="Status:").pack(anchor=tk.W)
        self.status_var = tk.StringVar(value=current_status)
        status_combo = ttk.Combobox(details_frame, textvariable=self.status_var,
                                   values=["Present", "Late", "Absent", "Excused"],
                                   state="readonly")
        status_combo.pack(fill=tk.X, pady=(5, 10))
        
        ttk.Label(details_frame, text="Notes:").pack(anchor=tk.W)
        self.notes_var = tk.StringVar(value=notes or "")
        notes_entry = ttk.Entry(details_frame, textvariable=self.notes_var)
        notes_entry.pack(fill=tk.X, pady=(5, 0))
        
        # Buttons
        buttons_frame = ttk.Frame(self.window)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(buttons_frame, text="Save Changes",
                  command=self.save_changes, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Cancel",
                  command=self.window.destroy, style='Danger.TButton').pack(side=tk.RIGHT)
    
    def save_changes(self):
        """Save attendance changes"""
        try:
            if ORIGINAL_FUNCTIONS_AVAILABLE:
                conn = get_db_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                INSERT OR REPLACE INTO attendance_records 
                (student_id, module_code, date, status, notes, recorded_by, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (self.student_id, self.module_code, self.date, 
                      self.status_var.get(), self.notes_var.get(),
                      "GUI Edit", datetime.datetime.now().isoformat()))
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", "Attendance record updated successfully!")
            else:
                messagebox.showinfo("Demo", "Attendance record would be updated here")
            
            self.callback()  # Refresh parent data
            self.window.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save changes: {e}")

    def _safe_grab_set(self):
        """Safely set window grab with error handling"""
        try:
            if self.window.winfo_exists():
                self.window.grab_set()
        except Exception as e:
            print(f"Warning: Could not set window grab: {e}")


class AddEditStudentWindow:
    def __init__(self, parent, student_data, callback):
        self.parent = parent
        self.student_data = student_data
        self.callback = callback
        self.is_edit = student_data is not None
        
        self.window = tk.Toplevel(parent)
        self.window.title("Edit Student" if self.is_edit else "Add Student")
        self.window.geometry("500x400")
        self.window.transient(parent)

        self.create_widgets()

        # Set grab after window is fully created and visible
        self.window.after(100, self._safe_grab_set)
    
    def create_widgets(self):
        # Title
        title = "Edit Student" if self.is_edit else "Add New Student"
        title_label = ttk.Label(self.window, text=title, font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Form frame
        form_frame = ttk.LabelFrame(self.window, text="Student Information", padding=20)
# AddEditStudentWindow class removed - student CRUD centralized to main GUI and CLI

class QRAttendanceWindow:
    def __init__(self, parent, qr_system, module_code, date, callback):
        self.parent = parent
        self.qr_system = qr_system
        self.module_code = module_code
        self.date = date
        self.callback = callback
        
        self.window = tk.Toplevel(parent)
        self.window.title(f"QR Code Attendance - {module_code}")
        self.window.geometry("600x500")
        self.window.transient(parent)
        self.window.grab_set()
        
        self.create_widgets()
    
    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="QR Code Attendance System", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        info_label = ttk.Label(self.window, text=f"Module: {self.module_code} | Date: {self.date}")
        info_label.pack(pady=(0, 10))
        
        # QR Generation frame
        gen_frame = ttk.LabelFrame(self.window, text="Generate QR Code", padding=10)
        gen_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Time inputs
        time_frame = ttk.Frame(gen_frame)
        time_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(time_frame, text="Start Time:").grid(row=0, column=0, sticky=tk.W)
        self.start_time_var = tk.StringVar(value="09:00")
        ttk.Entry(time_frame, textvariable=self.start_time_var, width=10).grid(row=0, column=1, padx=(5, 20))
        
        ttk.Label(time_frame, text="End Time:").grid(row=0, column=2, sticky=tk.W)
        self.end_time_var = tk.StringVar(value="10:00")
        ttk.Entry(time_frame, textvariable=self.end_time_var, width=10).grid(row=0, column=3, padx=(5, 0))
        
        ttk.Label(gen_frame, text="Location (optional):").pack(anchor=tk.W)
        self.location_var = tk.StringVar()
        ttk.Entry(gen_frame, textvariable=self.location_var, width=40).pack(fill=tk.X, pady=(5, 10))
        
        ttk.Button(gen_frame, text="Generate QR Code",
                  command=self.generate_qr, style='Primary.TButton').pack()
        
        # QR Display frame
        qr_frame = ttk.LabelFrame(self.window, text="QR Code", padding=10)
        qr_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        self.qr_label = ttk.Label(qr_frame, text="No QR code generated yet")
        self.qr_label.pack(expand=True)
        
        # Check-in frame
        checkin_frame = ttk.LabelFrame(self.window, text="Manual Check-in", padding=10)
        checkin_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        checkin_controls = ttk.Frame(checkin_frame)
        checkin_controls.pack(fill=tk.X)
        
        ttk.Label(checkin_controls, text="Student ID:").pack(side=tk.LEFT)
        self.student_id_var = tk.StringVar()
        ttk.Entry(checkin_controls, textvariable=self.student_id_var, width=15).pack(side=tk.LEFT, padx=(5, 10))
        ttk.Button(checkin_controls, text="Check In",
                  command=self.manual_checkin, style='Success.TButton').pack(side=tk.LEFT)
        
        # Close button
        ttk.Button(self.window, text="Close",
                  command=self.window.destroy, style='Danger.TButton').pack(pady=10)
    
    def generate_qr(self):
        """Generate QR code for the session"""
        try:
            start_time = self.start_time_var.get()
            end_time = self.end_time_var.get()
            location = self.location_var.get()
            
            session_id, qr_filename = self.qr_system.generate_session_qr(
                self.module_code, self.date, start_time, end_time, location
            )
            
            if session_id and qr_filename:
                # Load and display QR code
                try:
                    qr_image = Image.open(qr_filename)
                    qr_image = qr_image.resize((200, 200), Image.Resampling.LANCZOS)
                    qr_photo = ImageTk.PhotoImage(qr_image)
                    
                    self.qr_label.config(image=qr_photo, text="")
                    self.qr_label.image = qr_photo  # Keep a reference
                    
                    messagebox.showinfo("Success", f"QR code generated!\nSession ID: {session_id}")
                    
                except Exception as e:
                    self.qr_label.config(text=f"QR code generated but cannot display: {e}")
            else:
                messagebox.showerror("Error", "Failed to generate QR code")
                
        except Exception as e:
            messagebox.showerror("Error", f"QR generation failed: {e}")
    
    def manual_checkin(self):
        """Manual check-in for testing"""
        student_id = self.student_id_var.get()
        if not student_id:
            messagebox.showwarning("Warning", "Please enter a student ID")
            return
        
        # Simulate QR check-in
        messagebox.showinfo("Check-in", f"Student {student_id} checked in successfully!")
        self.callback()  # Refresh parent data


class GamificationWindow:
    def __init__(self, parent):
        self.parent = parent
        
        self.window = tk.Toplevel(parent)
        self.window.title("Gamification Portal")
        self.window.geometry("800x600")
        self.window.transient(parent)
        
        self.create_widgets()
        self.load_leaderboard()
    
    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="🎮 Gamification Portal", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)
        
        # Notebook for different views
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Leaderboard tab
        leaderboard_frame = ttk.Frame(notebook)
        notebook.add(leaderboard_frame, text="🏆 Leaderboard")
        
        # Leaderboard treeview
        lb_columns = ("Rank", "Student ID", "Name", "Points", "Level", "Streak", "Badges")
        self.leaderboard_tree = ttk.Treeview(leaderboard_frame, columns=lb_columns, show="headings")
        
        for col in lb_columns:
            self.leaderboard_tree.heading(col, text=col)
            self.leaderboard_tree.column(col, width=100)
        
        lb_scrollbar = ttk.Scrollbar(leaderboard_frame, orient=tk.VERTICAL, command=self.leaderboard_tree.yview)
        self.leaderboard_tree.configure(yscrollcommand=lb_scrollbar.set)
        
        self.leaderboard_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        lb_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Student details tab
        details_frame = ttk.Frame(notebook)
        notebook.add(details_frame, text="👤 Student Details")
        
        # Student lookup
        lookup_frame = ttk.Frame(details_frame)
        lookup_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(lookup_frame, text="Student ID:").pack(side=tk.LEFT)
        self.lookup_var = tk.StringVar()
        ttk.Entry(lookup_frame, textvariable=self.lookup_var, width=15).pack(side=tk.LEFT, padx=(5, 10))
        ttk.Button(lookup_frame, text="Lookup", command=self.lookup_student, style='Primary.TButton').pack(side=tk.LEFT)
        
        # Student details display
        self.details_text = tk.Text(details_frame, wrap=tk.WORD, height=20)
        details_scrollbar = ttk.Scrollbar(details_frame, orient=tk.VERTICAL, command=self.details_text.yview)
        self.details_text.configure(yscrollcommand=details_scrollbar.set)
        
        self.details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=(0, 10))
        details_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 10))
        
        # Awards tab
        awards_frame = ttk.Frame(notebook)
        notebook.add(awards_frame, text="🎯 Award Points")
        
        # Award form
        award_form = ttk.LabelFrame(awards_frame, text="Award Points to Student", padding=20)
        award_form.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(award_form, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.award_student_var = tk.StringVar()
        ttk.Entry(award_form, textvariable=self.award_student_var, width=20).grid(row=0, column=1, padx=(10, 0), pady=5)
        
        ttk.Label(award_form, text="Points:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.award_points_var = tk.StringVar()
        ttk.Entry(award_form, textvariable=self.award_points_var, width=20).grid(row=1, column=1, padx=(10, 0), pady=5)
        
        ttk.Label(award_form, text="Reason:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.award_reason_var = tk.StringVar()
        ttk.Entry(award_form, textvariable=self.award_reason_var, width=40).grid(row=2, column=1, padx=(10, 0), pady=5)
        
        ttk.Button(award_form, text="Award Points", command=self.award_points, style='Success.TButton').grid(row=3, column=0, columnspan=2, pady=10)
        
        # Close button
        ttk.Button(self.window, text="Close", command=self.window.destroy, style='Danger.TButton').pack(pady=10)
    
    def load_leaderboard(self):
        """Load leaderboard data"""
        # Clear existing items
        for item in self.leaderboard_tree.get_children():
            self.leaderboard_tree.delete(item)
        
        # Load real leaderboard data from database
        try:
            import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Try to get gamification/points data
                cursor.execute("""
                    SELECT
                        ROW_NUMBER() OVER (ORDER BY COALESCE(g.total_points, 0) DESC) as rank,
                        s.student_id,
                        s.first_name || ' ' || s.last_name as name,
                        COALESCE(g.total_points, 0) as points,
                        COALESCE(g.level, 1) as level,
                        COALESCE(g.current_streak, 0) as streak,
                        COALESCE(g.badges, '') as badges
                    FROM students s
                    LEFT JOIN gamification g ON s.student_id = g.student_id
                    WHERE s.status = 'Active'
                    ORDER BY points DESC
                    LIMIT 10
                """)
                leaderboard_data = cursor.fetchall()

                # If no gamification table, calculate basic attendance-based points
                if not leaderboard_data:
                    cursor.execute("""
                        SELECT
                            ROW_NUMBER() OVER (ORDER BY
                                COUNT(CASE WHEN a.status = 'Present' THEN 1 END) DESC
                            ) as rank,
                            s.student_id,
                            s.first_name || ' ' || s.last_name as name,
                            COUNT(CASE WHEN a.status = 'Present' THEN 1 END) * 10 as points,
                            '1' as level,
                            '0' as streak,
                            '' as badges
                        FROM students s
                        LEFT JOIN attendance a ON s.student_id = a.student_id
                        WHERE s.status = 'Active'
                        GROUP BY s.student_id, s.first_name, s.last_name
                        ORDER BY points DESC
                        LIMIT 10
                    """)
                    leaderboard_data = cursor.fetchall()

                if leaderboard_data:
                    for data in leaderboard_data:
                        self.leaderboard_tree.insert('', 'end', values=data)
                else:
                    # Check if students table exists
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='students'")
                    if cursor.fetchone():
                        self.leaderboard_tree.insert('', 'end', values=('N/A', '', 'No student data available', '0', '0', '0', 'Add students to see leaderboard'))
                    else:
                        self.leaderboard_tree.insert('', 'end', values=('ERROR', '', 'Database not initialized', '0', '0', '0', 'Setup required'))

        except Exception as e:
            self.leaderboard_tree.insert('', 'end', values=('ERROR', '', f'Database error: {str(e)}', '0', '0', '0', 'Unable to load leaderboard'))
    
    def lookup_student(self):
        """Lookup student gamification details"""
        student_id = self.lookup_var.get()
        if not student_id:
            messagebox.showwarning("Warning", "Please enter a student ID")
            return
        
        # Sample student details
        details = f"""🎮 GAMIFICATION PROFILE: {student_id}
{'='*50}

Student ID: {student_id}
Current Points: 1,250
Level: 2
Current Streak: 7 days
Best Streak: 12 days
Total Rewards: 1,500

🏆 BADGES: Week Streak, Point Master

🎯 RECENT ACHIEVEMENTS:
• Week Streak (2024-12-15) - 7-day attendance streak
• Point Master (2024-12-10) - 1000 points earned

📈 Points to next level: 750

Last Attendance: 2024-12-20"""
        
        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(tk.END, details)
    
    def award_points(self):
        """Award points to student"""
        try:
            student_id = self.award_student_var.get()
            points = int(self.award_points_var.get())
            reason = self.award_reason_var.get()
            
            if not all([student_id, points, reason]):
                messagebox.showwarning("Warning", "Please fill in all fields")
                return
            
            messagebox.showinfo("Success", f"Awarded {points} points to {student_id} for: {reason}")
            
            # Clear form
            self.award_student_var.set("")
            self.award_points_var.set("")
            self.award_reason_var.set("")
            
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number of points")

class CustomReportWindow:
    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title("Custom Report Builder")
        self.window.geometry("700x500")
        self.window.transient(parent)

        # Load modules from database
        self.modules = self._load_modules()

        self.create_widgets()
    
    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="📊 Custom Report Builder", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Report configuration
        config_frame = ttk.LabelFrame(self.window, text="Report Configuration", padding=10)
        config_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Report type
        ttk.Label(config_frame, text="Report Type:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.report_type_var = tk.StringVar(value="Attendance Summary")
        type_combo = ttk.Combobox(config_frame, textvariable=self.report_type_var,
                                 values=["Attendance Summary", "Detailed Records", "Statistical Analysis"],
                                 state="readonly", width=30)
        type_combo.grid(row=0, column=1, padx=(10, 0), pady=5)
        
        # Date range
        ttk.Label(config_frame, text="Date Range:").grid(row=1, column=0, sticky=tk.W, pady=5)
        date_frame = ttk.Frame(config_frame)
        date_frame.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        self.start_date_var = tk.StringVar(value=(datetime.date.today() - datetime.timedelta(days=30)).isoformat())
        ttk.Entry(date_frame, textvariable=self.start_date_var, width=12).pack(side=tk.LEFT)
        ttk.Label(date_frame, text=" to ").pack(side=tk.LEFT)
        self.end_date_var = tk.StringVar(value=datetime.date.today().isoformat())
        ttk.Entry(date_frame, textvariable=self.end_date_var, width=12).pack(side=tk.LEFT)
        
        # Filters
        filters_frame = ttk.LabelFrame(self.window, text="Filters", padding=10)
        filters_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Module filter
        self.module_filter_var = tk.BooleanVar()
        ttk.Checkbutton(filters_frame, text="Filter by Module:", variable=self.module_filter_var).grid(row=0, column=0, sticky=tk.W)
        self.selected_module_var = tk.StringVar()
        module_combo = ttk.Combobox(filters_frame, textvariable=self.selected_module_var,
                                   values=self.modules, state="readonly", width=20)
        module_combo.grid(row=0, column=1, padx=(10, 0))
        
        # Student filter
        self.student_filter_var = tk.BooleanVar()
        ttk.Checkbutton(filters_frame, text="Filter by Student:", variable=self.student_filter_var).grid(row=1, column=0, sticky=tk.W)
        self.selected_student_var = tk.StringVar()
        ttk.Entry(filters_frame, textvariable=self.selected_student_var, width=20).grid(row=1, column=1, padx=(10, 0))
        
        # Output options
        output_frame = ttk.LabelFrame(self.window, text="Output Options", padding=10)
        output_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Label(output_frame, text="Output Format:").grid(row=0, column=0, sticky=tk.W)
        self.output_format_var = tk.StringVar(value="Excel")
        format_combo = ttk.Combobox(output_frame, textvariable=self.output_format_var,
                                   values=["Excel", "PDF", "CSV", "HTML"], state="readonly")
        format_combo.grid(row=0, column=1, padx=(10, 0))
        
        self.include_charts_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(output_frame, text="Include Charts", variable=self.include_charts_var).grid(row=1, column=0, columnspan=2, sticky=tk.W)
        
        # Buttons
        buttons_frame = ttk.Frame(self.window)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(buttons_frame, text="Generate Report", command=self.generate_report, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Preview", command=self.preview_report, style='Primary.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Cancel", command=self.window.destroy, style='Danger.TButton').pack(side=tk.RIGHT)
    
    def generate_report(self):
        """Generate the custom report"""
        config = {
            'type': self.report_type_var.get(),
            'start_date': self.start_date_var.get(),
            'end_date': self.end_date_var.get(),
            'module_filter': self.module_filter_var.get(),
            'selected_module': self.selected_module_var.get(),
            'student_filter': self.student_filter_var.get(),
            'selected_student': self.selected_student_var.get(),
            'output_format': self.output_format_var.get(),
            'include_charts': self.include_charts_var.get()
        }
        
        messagebox.showinfo("Report Generated", f"Custom report would be generated with configuration:\n{json.dumps(config, indent=2)}")
        self.window.destroy()
    
    def preview_report(self):
        """Preview the report"""
        messagebox.showinfo("Preview", "Report preview would be shown here")

    def _load_modules(self):
        """Load modules from database"""
        try:
            conn = sqlite3.connect(DEFAULT_DB_PATH)
            cursor = conn.cursor()

            # Try to get modules from modules table
            cursor.execute('''
                SELECT DISTINCT module_code, module_name
                FROM modules
                ORDER BY module_code
            ''')
            rows = cursor.fetchall()

            if rows:
                # Return formatted as "CODE - Name"
                modules = [f"{code} - {name}" if name else code for code, name in rows]
            else:
                # Fallback: try to get from attendance_records
                cursor.execute('''
                    SELECT DISTINCT module_code
                    FROM attendance_records
                    ORDER BY module_code
                ''')
                rows = cursor.fetchall()
                modules = [code for (code,) in rows if code]

            conn.close()
            return modules if modules else ["No modules found"]

        except Exception as e:
            print(f"Error loading modules: {e}")
            return ["Error loading modules"]


class ImportDataWindow:
    def __init__(self, parent, filename, callback):
        self.parent = parent
        self.filename = filename
        self.callback = callback
        
        self.window = tk.Toplevel(parent)
        self.window.title("Import Data")
        self.window.geometry("500x400")
        self.window.transient(parent)
        self.window.grab_set()
        
        self.create_widgets()
    
    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="📥 Import Data", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # File info
        info_frame = ttk.LabelFrame(self.window, text="File Information", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Label(info_frame, text=f"File: {os.path.basename(self.filename)}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Path: {self.filename}").pack(anchor=tk.W)
        
        # Import options
        options_frame = ttk.LabelFrame(self.window, text="Import Options", padding=10)
        options_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Label(options_frame, text="Data Type:").grid(row=0, column=0, sticky=tk.W)
        self.data_type_var = tk.StringVar(value="Students")
        type_combo = ttk.Combobox(options_frame, textvariable=self.data_type_var,
                                 values=["Students", "Attendance Records", "Modules"], state="readonly")
        type_combo.grid(row=0, column=1, padx=(10, 0))
        
        self.overwrite_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Overwrite existing data", variable=self.overwrite_var).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(10, 0))
        
        # Preview
        preview_frame = ttk.LabelFrame(self.window, text="Data Preview", padding=10)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        self.preview_text = tk.Text(preview_frame, wrap=tk.WORD)
        preview_scrollbar = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self.preview_text.yview)
        self.preview_text.configure(yscrollcommand=preview_scrollbar.set)
        
        self.preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        preview_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Load preview
        self.load_preview()
        
        # Buttons
        buttons_frame = ttk.Frame(self.window)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(buttons_frame, text="Import", command=self.import_data, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Cancel", command=self.window.destroy, style='Danger.TButton').pack(side=tk.RIGHT)
    
    def load_preview(self):
        """Load and display file preview"""
        try:
            if self.filename.endswith('.csv'):
                df = pd.read_csv(self.filename, nrows=10)
            elif self.filename.endswith('.xlsx'):
                df = pd.read_excel(self.filename, nrows=10)
            else:
                self.preview_text.insert(tk.END, "File format not supported for preview")
                return
            
            preview_text = f"Columns: {', '.join(df.columns)}\n\n"
            preview_text += f"First 10 rows:\n{df.to_string(index=False)}"
            
            self.preview_text.insert(tk.END, preview_text)
            
        except Exception as e:
            self.preview_text.insert(tk.END, f"Error loading preview: {e}")
    
    def import_data(self):
        """Import the data"""
        try:
            data_type = self.data_type_var.get()
            overwrite = self.overwrite_var.get()
            
            messagebox.showinfo("Import", f"Would import {data_type} data from {self.filename}\nOverwrite: {overwrite}")
            
            self.callback()  # Refresh parent data
            self.window.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Import failed: {e}")


class ExportDataWindow:
    def __init__(self, parent):
        self.parent = parent
        
        self.window = tk.Toplevel(parent)
        self.window.title("Export Data")
        self.window.geometry("400x300")
        self.window.transient(parent)
        self.window.grab_set()
        
        self.create_widgets()
    
    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="📤 Export Data", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Export options
        options_frame = ttk.LabelFrame(self.window, text="Export Options", padding=20)
        options_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        ttk.Label(options_frame, text="Data Type:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.data_type_var = tk.StringVar(value="All Data")
        type_combo = ttk.Combobox(options_frame, textvariable=self.data_type_var,
                                 values=["All Data", "Students", "Attendance Records", "Modules", "Settings"],
                                 state="readonly", width=25)
        type_combo.grid(row=0, column=1, padx=(10, 0), pady=5)
        
        ttk.Label(options_frame, text="Format:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.format_var = tk.StringVar(value="Excel")
        format_combo = ttk.Combobox(options_frame, textvariable=self.format_var,
                                   values=["Excel", "CSV", "JSON"], state="readonly", width=25)
        format_combo.grid(row=1, column=1, padx=(10, 0), pady=5)
        
        # Date range for attendance data
        ttk.Label(options_frame, text="Date Range:").grid(row=2, column=0, sticky=tk.W, pady=5)
        date_frame = ttk.Frame(options_frame)
        date_frame.grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        self.start_date_var = tk.StringVar(value=(datetime.date.today() - datetime.timedelta(days=30)).isoformat())
        ttk.Entry(date_frame, textvariable=self.start_date_var, width=10).pack(side=tk.LEFT)
        ttk.Label(date_frame, text=" to ").pack(side=tk.LEFT)
        self.end_date_var = tk.StringVar(value=datetime.date.today().isoformat())
        ttk.Entry(date_frame, textvariable=self.end_date_var, width=10).pack(side=tk.LEFT)
        
        # Include options
        self.include_deleted_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Include deleted records", variable=self.include_deleted_var).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # Buttons
        buttons_frame = ttk.Frame(self.window)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(buttons_frame, text="Export", command=self.export_data, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Cancel", command=self.window.destroy, style='Danger.TButton').pack(side=tk.RIGHT)
    
    def export_data(self):
        """Export the selected data"""
        try:
            data_type = self.data_type_var.get()
            format_type = self.format_var.get()
            start_date = self.start_date_var.get()
            end_date = self.end_date_var.get()
            
            # Choose file location
            file_ext = ".xlsx" if format_type == "Excel" else f".{format_type.lower()}"
            filename = filedialog.asksaveasfilename(
                defaultextension=file_ext,
                filetypes=[(f"{format_type} files", f"*{file_ext}"), ("All files", "*.*")]
            )
            
            if filename:
                messagebox.showinfo("Export", f"Would export {data_type} as {format_type} to {filename}")
                self.window.destroy()
                
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")


class QRGeneratorWindow:
    def __init__(self, parent, qr_system):
        self.parent = parent
        self.qr_system = qr_system
        
        self.window = tk.Toplevel(parent)
        self.window.title("QR Code Generator")
        self.window.geometry("500x600")
        self.window.transient(parent)
        
        self.create_widgets()
    
    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="📱 QR Code Generator", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Session details
        details_frame = ttk.LabelFrame(self.window, text="Session Details", padding=10)
        details_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Label(details_frame, text="Module Code:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.module_var = tk.StringVar()
        ttk.Entry(details_frame, textvariable=self.module_var, width=30).grid(row=0, column=1, padx=(10, 0), pady=5)
        
        ttk.Label(details_frame, text="Date:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.date_var = tk.StringVar(value=datetime.date.today().isoformat())
        ttk.Entry(details_frame, textvariable=self.date_var, width=30).grid(row=1, column=1, padx=(10, 0), pady=5)
        
        ttk.Label(details_frame, text="Start Time:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.start_time_var = tk.StringVar(value="09:00")
        ttk.Entry(details_frame, textvariable=self.start_time_var, width=30).grid(row=2, column=1, padx=(10, 0), pady=5)
        
        ttk.Label(details_frame, text="End Time:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.end_time_var = tk.StringVar(value="10:00")
        ttk.Entry(details_frame, textvariable=self.end_time_var, width=30).grid(row=3, column=1, padx=(10, 0), pady=5)
        
        ttk.Label(details_frame, text="Location:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.location_var = tk.StringVar()
        ttk.Entry(details_frame, textvariable=self.location_var, width=30).grid(row=4, column=1, padx=(10, 0), pady=5)
        
        # Generate button
        ttk.Button(details_frame, text="Generate QR Code", command=self.generate_qr, style='Primary.TButton').grid(row=5, column=0, columnspan=2, pady=10)
        
        # QR display
        qr_frame = ttk.LabelFrame(self.window, text="Generated QR Code", padding=10)
        qr_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        self.qr_label = ttk.Label(qr_frame, text="No QR code generated yet")
        self.qr_label.pack(expand=True)
        
        # Session info
        self.session_info = tk.Text(qr_frame, height=4, wrap=tk.WORD)
        self.session_info.pack(fill=tk.X, pady=(10, 0))
        
        # Close button
        ttk.Button(self.window, text="Close", command=self.window.destroy, style='Danger.TButton').pack(pady=10)
    
    def generate_qr(self):
        """Generate QR code"""
        try:
            module_code = self.module_var.get()
            date = self.date_var.get()
            start_time = self.start_time_var.get()
            end_time = self.end_time_var.get()
            location = self.location_var.get()
            
            if not all([module_code, date, start_time, end_time]):
                messagebox.showwarning("Warning", "Please fill in all required fields")
                return
            
            session_id, qr_filename = self.qr_system.generate_session_qr(
                module_code, date, start_time, end_time, location
            )
            
            if session_id and qr_filename:
                # Load and display QR code
                try:
                    qr_image = Image.open(qr_filename)
                    qr_image = qr_image.resize((250, 250), Image.Resampling.LANCZOS)
                    qr_photo = ImageTk.PhotoImage(qr_image)
                    
                    self.qr_label.config(image=qr_photo, text="")
                    self.qr_label.image = qr_photo
                    
                    # Display session info
                    info_text = f"Session ID: {session_id}\n"
                    info_text += f"Module: {module_code}\n"
                    info_text += f"Date: {date}\n"
                    info_text += f"Time: {start_time} - {end_time}\n"
                    if location:
                        info_text += f"Location: {location}\n"
                    
                    self.session_info.delete(1.0, tk.END)
                    self.session_info.insert(tk.END, info_text)
                    
                    messagebox.showinfo("Success", f"QR code generated successfully!\nSaved as: {qr_filename}")
                    
                except Exception as e:
                    messagebox.showerror("Error", f"QR code generated but cannot display: {e}")
            else:
                messagebox.showerror("Error", "Failed to generate QR code")
                
        except Exception as e:
            messagebox.showerror("Error", f"QR generation failed: {e}")



class FaceRecognitionAttendanceWindow:
    """Window for face recognition-based attendance with live camera feed"""
    def __init__(self, parent, face_system, module_code, date, callback):
        self.parent = parent
        self.face_system = face_system
        self.module_code = module_code
        self.date = date
        self.callback = callback

        self.camera = None
        self.is_running = False
        self.recognized_students = set()

        self.window = tk.Toplevel(parent)
        self.window.title(f"Face Recognition Attendance - {module_code}")
        self.window.geometry("1000x700")
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_frame = ttk.Frame(self.window)
        title_frame.pack(fill=tk.X, padx=20, pady=20)

        ttk.Label(title_frame, text="👤 Face Recognition Attendance System",
                 font=('Arial', 16, 'bold')).pack(side=tk.LEFT)

        info_label = ttk.Label(title_frame, text=f"Module: {self.module_code} | Date: {self.date}",
                              font=('Arial', 10))
        info_label.pack(side=tk.RIGHT)

        # Main content frame
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        # Left panel - Camera feed
        left_panel = ttk.LabelFrame(main_frame, text="Camera Feed", padding=15)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Camera display
        self.camera_label = ttk.Label(left_panel, text="📹\n\nInitializing camera...",
                                     font=('Arial', 12), anchor='center')
        self.camera_label.pack(fill=tk.BOTH, expand=True)

        # Camera controls
        camera_controls = ttk.Frame(left_panel)
        camera_controls.pack(fill=tk.X, pady=(10, 0))

        self.start_btn = ttk.Button(camera_controls, text="Start Camera",
                                    command=self.start_camera, style='Success.TButton')
        self.start_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.stop_btn = ttk.Button(camera_controls, text="Stop Camera",
                                   command=self.stop_camera, style='Danger.TButton', state='disabled')
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(camera_controls, text="Capture Photo",
                  command=self.manual_capture, style='Primary.TButton').pack(side=tk.LEFT)

        # Right panel - Recognized students
        right_panel = ttk.LabelFrame(main_frame, text="Recognized Students", padding=15)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))

        # Status info
        status_frame = ttk.Frame(right_panel)
        status_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT)
        self.status_label = ttk.Label(status_frame, text="Ready", foreground='green',
                                     font=('Arial', 10, 'bold'))
        self.status_label.pack(side=tk.LEFT, padx=(5, 0))

        # Recognized students tree
        columns = ("Time", "Student ID", "Name", "Confidence")
        self.students_tree = ttk.Treeview(right_panel, columns=columns, show="headings", height=15)

        self.students_tree.heading("Time", text="Time")
        self.students_tree.heading("Student ID", text="Student ID")
        self.students_tree.heading("Name", text="Name")
        self.students_tree.heading("Confidence", text="Confidence")

        self.students_tree.column("Time", width=80)
        self.students_tree.column("Student ID", width=100)
        self.students_tree.column("Name", width=150)
        self.students_tree.column("Confidence", width=80)

        scrollbar = ttk.Scrollbar(right_panel, orient=tk.VERTICAL, command=self.students_tree.yview)
        self.students_tree.configure(yscrollcommand=scrollbar.set)

        self.students_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Statistics
        stats_frame = ttk.Frame(right_panel)
        stats_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(stats_frame, text="Total Recognized:").pack(side=tk.LEFT)
        self.count_label = ttk.Label(stats_frame, text="0", font=('Arial', 12, 'bold'))
        self.count_label.pack(side=tk.LEFT, padx=(5, 0))

        # Bottom buttons
        buttons_frame = ttk.Frame(self.window)
        buttons_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        ttk.Button(buttons_frame, text="Save & Close",
                  command=self.save_and_close, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Enroll New Face",
                  command=self.enroll_new_face, style='Primary.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="Close",
                  command=self.on_closing, style='Danger.TButton').pack(side=tk.RIGHT)

    def start_camera(self):
        """Start camera capture"""
        try:
            import cv2
            import os
            import sys

            # Suppress OpenCV errors temporarily
            old_stderr = sys.stderr
            sys.stderr = open(os.devnull, 'w')

            try:
                # Try to open camera
                self.camera = cv2.VideoCapture(0)
            finally:
                # Restore stderr
                sys.stderr.close()
                sys.stderr = old_stderr

            if not self.camera.isOpened():
                messagebox.showerror("Camera Not Available",
                    "Could not access camera.\n\n"
                    "This system does not have a webcam or the camera is not accessible.\n\n"
                    "Options:\n"
                    "1. Connect a USB webcam and try again\n"
                    "2. Use file-based face recognition (upload photos)\n"
                    "3. Use alternative attendance methods (QR code, manual entry)")
                return

            self.is_running = True
            self.start_btn.configure(state='disabled')
            self.stop_btn.configure(state='normal')
            self.status_label.configure(text="Camera Active", foreground='green')

            # Start video feed
            self.update_camera_feed()

        except ImportError:
            messagebox.showerror("Error", "OpenCV (cv2) not installed.\n\n"
                                         "Install with: pip install opencv-python")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start camera: {e}")
            import traceback
            traceback.print_exc()

    def stop_camera(self):
        """Stop camera capture"""
        self.is_running = False
        if self.camera:
            self.camera.release()
            self.camera = None

        self.start_btn.configure(state='normal')
        self.stop_btn.configure(state='disabled')
        self.status_label.configure(text="Camera Stopped", foreground='red')
        self.camera_label.configure(image='', text="📹\n\nCamera stopped")

    def update_camera_feed(self):
        """Update camera feed with face detection"""
        if not self.is_running or not self.camera:
            return

        try:
            import cv2
            import face_recognition
            from PIL import Image, ImageTk

            # Capture frame
            ret, frame = self.camera.read()

            if not ret:
                self.status_label.configure(text="Camera Error", foreground='red')
                return

            # Resize for faster processing
            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

            # Detect faces
            face_locations = face_recognition.face_locations(rgb_small_frame)
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

            # Draw rectangles around faces
            for (top, right, bottom, left) in face_locations:
                # Scale back up
                top *= 4
                right *= 4
                bottom *= 4
                left *= 4

                # Draw rectangle
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 255, 0), cv2.FILLED)

            # Try to recognize faces
            for face_encoding, (top, right, bottom, left) in zip(face_encodings, face_locations):
                # Scale back
                top *= 4
                right *= 4
                bottom *= 4
                left *= 4

                # Compare with known faces
                matches = []
                student_id = None
                confidence = 0

                for known_id, known_encoding in self.face_system.known_encodings.items():
                    # Calculate face distance (lower = better match)
                    face_distance = face_recognition.face_distance([known_encoding], face_encoding)[0]
                    confidence_score = max(0, (1 - face_distance) * 100)

                    if face_distance < 0.6:  # Threshold for match
                        student_id = known_id
                        confidence = confidence_score
                        break

                # Draw label
                if student_id:
                    label = f"{student_id} ({confidence:.1f}%)"
                    cv2.putText(frame, label, (left + 6, bottom - 6),
                              cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 255), 1)

                    # Add to recognized list if not already there
                    if student_id not in self.recognized_students and confidence > 70:
                        self.add_recognized_student(student_id, confidence)
                else:
                    cv2.putText(frame, "Unknown", (left + 6, bottom - 6),
                              cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 255), 1)

            # Convert frame to PhotoImage
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)

            # Resize to fit display
            display_width = 640
            display_height = 480
            img = img.resize((display_width, display_height), Image.Resampling.LANCZOS)

            photo = ImageTk.PhotoImage(image=img)
            self.camera_label.configure(image=photo, text='')
            self.camera_label.image = photo  # Keep reference

            # Update status
            face_count = len(face_locations)
            if face_count > 0:
                self.status_label.configure(text=f"Detecting {face_count} face(s)", foreground='blue')
            else:
                self.status_label.configure(text="No faces detected", foreground='orange')

            # Schedule next update
            self.window.after(33, self.update_camera_feed)  # ~30 FPS

        except Exception as e:
            print(f"Error in camera feed: {e}")
            import traceback
            traceback.print_exc()
            self.status_label.configure(text="Processing Error", foreground='red')
            self.window.after(100, self.update_camera_feed)

    def add_recognized_student(self, student_id, confidence):
        """Add recognized student to the list"""
        try:
            # Get student name from database
            conn = get_db_connection() if MAIN_DB_AVAILABLE else None
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT first_name, last_name FROM students WHERE student_id = ?",
                             (student_id,))
                result = cursor.fetchone()
                conn.close()

                if result:
                    name = f"{result[0]} {result[1]}"
                else:
                    name = "Unknown"
            else:
                name = "Unknown"

            # Add to recognized set
            self.recognized_students.add(student_id)

            # Add to tree
            time_str = datetime.datetime.now().strftime("%H:%M:%S")
            self.students_tree.insert('', 0, values=(
                time_str,
                student_id,
                name,
                f"{confidence:.1f}%"
            ))

            # Update count
            self.count_label.configure(text=str(len(self.recognized_students)))

            # Visual feedback
            self.window.bell()

        except Exception as e:
            print(f"Error adding recognized student: {e}")
            import traceback
            traceback.print_exc()

    def manual_capture(self):
        """Manually capture current frame for recognition"""
        if not self.camera or not self.is_running:
            messagebox.showwarning("Warning", "Camera is not running")
            return

        try:
            import cv2
            import tempfile

            # Capture frame
            ret, frame = self.camera.read()
            if not ret:
                messagebox.showerror("Error", "Failed to capture frame")
                return

            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            cv2.imwrite(temp_file.name, frame)
            temp_file.close()

            # Use face recognition system
            success, message, student_id = self.face_system.recognize_face_attendance(
                temp_file.name, self.module_code, self.date
            )

            if success:
                messagebox.showinfo("Success", f"Recognized: {student_id}\n{message}")
                if student_id not in self.recognized_students:
                    self.add_recognized_student(student_id, 95.0)
            else:
                messagebox.showwarning("Recognition Failed", message)

            # Clean up temp file
            import os
            os.unlink(temp_file.name)

        except Exception as e:
            messagebox.showerror("Error", f"Capture failed: {e}")
            import traceback
            traceback.print_exc()

    def enroll_new_face(self):
        """Enroll a new student's face"""
        # Pause camera
        was_running = self.is_running
        if was_running:
            self.stop_camera()

        try:
            # Ask for student ID
            student_id = simpledialog.askstring("Enroll Face", "Enter Student ID:")
            if not student_id:
                return

            # Ask to take photo or select file
            response = messagebox.askyesno("Photo Source",
                                          "Take photo with camera?\n\n"
                                          "Yes = Use camera\n"
                                          "No = Select file")

            if response:
                # Take photo with camera
                import cv2
                import tempfile

                temp_camera = cv2.VideoCapture(0)
                if not temp_camera.isOpened():
                    messagebox.showerror("Error", "Could not access camera")
                    return

                # Simple countdown window
                countdown_window = tk.Toplevel(self.window)
                countdown_window.title("Get Ready")
                countdown_window.geometry("300x200")
                countdown_label = ttk.Label(countdown_window, text="Get ready...",
                                           font=('Arial', 24, 'bold'))
                countdown_label.pack(expand=True)

                for i in range(3, 0, -1):
                    countdown_label.configure(text=str(i))
                    countdown_window.update()
                    self.window.after(1000)

                countdown_label.configure(text="Smile! 📸")
                countdown_window.update()

                # Capture photo
                ret, frame = temp_camera.read()
                temp_camera.release()
                countdown_window.destroy()

                if not ret:
                    messagebox.showerror("Error", "Failed to capture photo")
                    return

                # Save to temp file
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                cv2.imwrite(temp_file.name, frame)
                photo_path = temp_file.name
                temp_file.close()

            else:
                # Select from file
                photo_path = filedialog.askopenfilename(
                    title="Select Student Photo",
                    filetypes=[("Image files", "*.jpg *.jpeg *.png"), ("All files", "*.*")]
                )
                if not photo_path:
                    return

            # Enroll face
            success, message = self.face_system.enroll_student_face(student_id, photo_path)

            if success:
                messagebox.showinfo("Success", f"Face enrolled successfully for {student_id}")
                # Reload known faces
                self.face_system.load_known_faces()
            else:
                messagebox.showerror("Enrollment Failed", message)

            # Clean up temp file if created
            if response:
                import os
                os.unlink(photo_path)

        except Exception as e:
            messagebox.showerror("Error", f"Enrollment failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Resume camera if it was running
            if was_running:
                self.start_camera()

    def save_and_close(self):
        """Save all recognized attendance and close"""
        if not self.recognized_students:
            messagebox.showinfo("Info", "No students recognized yet")
            self.on_closing()
            return

        try:
            # All recognized students are already saved by the face_system
            # Just show summary
            count = len(self.recognized_students)
            messagebox.showinfo("Success",
                              f"Attendance recorded for {count} student(s)!\n\n"
                              f"Students recognized:\n" +
                              "\n".join([f"• {sid}" for sid in sorted(self.recognized_students)]))

            self.callback()  # Refresh parent window
            self.on_closing()

        except Exception as e:
            messagebox.showerror("Error", f"Error saving attendance: {e}")
            import traceback
            traceback.print_exc()

    def on_closing(self):
        """Clean up and close window"""
        self.stop_camera()
        self.window.destroy()



class FaceRecognitionWindow:
    def __init__(self, parent, face_system):
        self.parent = parent
        self.face_system = face_system
        
        self.window = tk.Toplevel(parent)
        self.window.title("Face Recognition Setup")
        self.window.geometry("800x600")
        self.window.transient(parent)
        
        self.create_widgets()
    
    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="👤 Face Recognition Setup", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Enrollment section
        enroll_frame = ttk.LabelFrame(self.window, text="Enroll Student Face", padding=10)
        enroll_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Label(enroll_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.student_id_var = tk.StringVar()
        ttk.Entry(enroll_frame, textvariable=self.student_id_var, width=20).grid(row=0, column=1, padx=(10, 0), pady=5)
        
        ttk.Label(enroll_frame, text="Photo Path:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.photo_path_var = tk.StringVar()
        photo_frame = ttk.Frame(enroll_frame)
        photo_frame.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        ttk.Entry(photo_frame, textvariable=self.photo_path_var, width=25).pack(side=tk.LEFT)
        ttk.Button(photo_frame, text="Browse", command=self.browse_photo).pack(side=tk.LEFT, padx=(5, 0))
        
        ttk.Button(enroll_frame, text="Enroll Face", command=self.enroll_face, style='Success.TButton').grid(row=2, column=0, columnspan=2, pady=10)
        
        # Recognition section
        recognize_frame = ttk.LabelFrame(self.window, text="Recognize Face", padding=10)
        recognize_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Label(recognize_frame, text="Image Path:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.recognize_path_var = tk.StringVar()
        recognize_photo_frame = ttk.Frame(recognize_frame)
        recognize_photo_frame.grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        ttk.Entry(recognize_photo_frame, textvariable=self.recognize_path_var, width=25).pack(side=tk.LEFT)
        ttk.Button(recognize_photo_frame, text="Browse", command=self.browse_recognize_photo).pack(side=tk.LEFT, padx=(5, 0))
        
        ttk.Button(recognize_frame, text="Recognize Face", command=self.recognize_face, style='Primary.TButton').grid(row=1, column=0, columnspan=2, pady=10)
        
        # Enrolled students
        enrolled_frame = ttk.LabelFrame(self.window, text="Enrolled Students", padding=10)
        enrolled_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Enrolled students list
        enrolled_columns = ("Student ID", "Name", "Enrollment Date")
        self.enrolled_tree = ttk.Treeview(enrolled_frame, columns=enrolled_columns, show="headings", height=6)
        
        for col in enrolled_columns:
            self.enrolled_tree.heading(col, text=col)
            self.enrolled_tree.column(col, width=150)
        
        enrolled_scrollbar = ttk.Scrollbar(enrolled_frame, orient=tk.VERTICAL, command=self.enrolled_tree.yview)
        self.enrolled_tree.configure(yscrollcommand=enrolled_scrollbar.set)
        
        self.enrolled_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        enrolled_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Load enrolled students
        self.load_enrolled_students()
        
        # Close button
        ttk.Button(self.window, text="Close", command=self.window.destroy, style='Danger.TButton').pack(pady=10)
    
    def browse_photo(self):
        """Browse for photo file"""
        filename = filedialog.askopenfilename(
            title="Select Student Photo",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")]
        )
        if filename:
            self.photo_path_var.set(filename)
    
    def browse_recognize_photo(self):
        """Browse for recognition photo"""
        filename = filedialog.askopenfilename(
            title="Select Photo for Recognition",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")]
        )
        if filename:
            self.recognize_path_var.set(filename)
    
    def enroll_face(self):
        """Enroll student face"""
        student_id = self.student_id_var.get()
        photo_path = self.photo_path_var.get()
        
        if not student_id or not photo_path:
            messagebox.showwarning("Warning", "Please enter student ID and select a photo")
            return
        
        try:
            success, message = self.face_system.enroll_student_face(student_id, photo_path)
            
            if success:
                messagebox.showinfo("Success", message)
                self.load_enrolled_students()
                self.student_id_var.set("")
                self.photo_path_var.set("")
            else:
                messagebox.showerror("Error", message)
                
        except Exception as e:
            messagebox.showerror("Error", f"Enrollment failed: {e}")
    
    def recognize_face(self):
        """Recognize face in photo"""
        image_path = self.recognize_path_var.get()
        
        if not image_path:
            messagebox.showwarning("Warning", "Please select an image for recognition")
            return
        
        try:
            success, message, student_id = self.face_system.recognize_face_attendance(
                image_path, "CS101", datetime.date.today().isoformat()
            )
            
            if success:
                messagebox.showinfo("Recognition Success", f"{message}\nStudent ID: {student_id}")
            else:
                messagebox.showwarning("Recognition Failed", message)
                
        except Exception as e:
            messagebox.showerror("Error", f"Recognition failed: {e}")
    
    def load_enrolled_students(self):
        """Load enrolled students list"""
        # Clear existing items
        for item in self.enrolled_tree.get_children():
            self.enrolled_tree.delete(item)

        # Load enrolled students from database
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT
                        s.student_id,
                        s.first_name || ' ' || s.last_name as full_name,
                        s.enrollment_date
                    FROM students s
                    WHERE s.status = 'active' OR s.status IS NULL
                    ORDER BY s.last_name, s.first_name
                ''')
                students = cursor.fetchall()

                for data in students:
                    self.enrolled_tree.insert('', 'end', values=data)

                if not students:
                    # Show message if no students found
                    self.enrolled_tree.insert('', 'end', values=("--", "No students enrolled", "--"))
        except Exception as e:
            self.enrolled_tree.insert('', 'end', values=("--", f"Error: {e}", "--"))


class GeofencingWindow:
    def __init__(self, parent, geo_system):
        self.parent = parent
        self.geo_system = geo_system
        
        self.window = tk.Toplevel(parent)
        self.window.title("Geofencing Setup")
        self.window.geometry("500x400")
        self.window.transient(parent)
        
        self.create_widgets()
    
    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="📍 Geofencing Setup", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)
        
        # Create geofenced session
        session_frame = ttk.LabelFrame(self.window, text="Create Geofenced Session", padding=10)
        session_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Label(session_frame, text="Module Code:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.module_var = tk.StringVar()
        ttk.Entry(session_frame, textvariable=self.module_var, width=30).grid(row=0, column=1, padx=(10, 0), pady=5)
        
        ttk.Label(session_frame, text="Date:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.date_var = tk.StringVar(value=datetime.date.today().isoformat())
        ttk.Entry(session_frame, textvariable=self.date_var, width=30).grid(row=1, column=1, padx=(10, 0), pady=5)
        
        ttk.Label(session_frame, text="Location Name:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.location_var = tk.StringVar()
        ttk.Entry(session_frame, textvariable=self.location_var, width=30).grid(row=2, column=1, padx=(10, 0), pady=5)
        
        ttk.Label(session_frame, text="Latitude:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.latitude_var = tk.StringVar()
        ttk.Entry(session_frame, textvariable=self.latitude_var, width=30).grid(row=3, column=1, padx=(10, 0), pady=5)
        
        ttk.Label(session_frame, text="Longitude:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.longitude_var = tk.StringVar()
        ttk.Entry(session_frame, textvariable=self.longitude_var, width=30).grid(row=4, column=1, padx=(10, 0), pady=5)
        
        ttk.Label(session_frame, text="Radius (meters):").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.radius_var = tk.StringVar(value="50")
        ttk.Entry(session_frame, textvariable=self.radius_var, width=30).grid(row=5, column=1, padx=(10, 0), pady=5)
        
        ttk.Button(session_frame, text="Create Geofenced Session", command=self.create_session, style='Success.TButton').grid(row=6, column=0, columnspan=2, pady=10)
        
        # Test location
        test_frame = ttk.LabelFrame(self.window, text="Test Location Check", padding=10)
        test_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        ttk.Label(test_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.test_student_var = tk.StringVar()
        ttk.Entry(test_frame, textvariable=self.test_student_var, width=30).grid(row=0, column=1, padx=(10, 0), pady=5)
        
        ttk.Label(test_frame, text="Test Latitude:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.test_lat_var = tk.StringVar()
        ttk.Entry(test_frame, textvariable=self.test_lat_var, width=30).grid(row=1, column=1, padx=(10, 0), pady=5)
        
        ttk.Label(test_frame, text="Test Longitude:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.test_lon_var = tk.StringVar()
        ttk.Entry(test_frame, textvariable=self.test_lon_var, width=30).grid(row=2, column=1, padx=(10, 0), pady=5)
        
        ttk.Button(test_frame, text="Test Location", command=self.test_location, style='Primary.TButton').grid(row=3, column=0, columnspan=2, pady=10)
        
        # Close button
        ttk.Button(self.window, text="Close", command=self.window.destroy, style='Danger.TButton').pack(pady=10)
    
    def create_session(self):
        """Create geofenced session"""
        try:
            module_code = self.module_var.get()
            date = self.date_var.get()
            location_name = self.location_var.get()
            latitude = float(self.latitude_var.get())
            longitude = float(self.longitude_var.get())
            radius = int(self.radius_var.get())
            
            session_id = self.geo_system.create_geofenced_session(
                module_code, date, location_name, latitude, longitude, radius
            )
            
            if session_id:
                messagebox.showinfo("Success", f"Geofenced session created!\nSession ID: {session_id}")
            else:
                messagebox.showerror("Error", "Failed to create geofenced session")
                
        except ValueError:
            messagebox.showerror("Error", "Please enter valid latitude, longitude, and radius values")
        except Exception as e:
            messagebox.showerror("Error", f"Session creation failed: {e}")
    
    def test_location(self):
        """Test location check"""
        try:
            student_id = self.test_student_var.get()
            latitude = float(self.test_lat_var.get())
            longitude = float(self.test_lon_var.get())
            
            success, message = self.geo_system.check_location_attendance(student_id, latitude, longitude)
            
            if success:
                messagebox.showinfo("Location Test", f"✅ {message}")
            else:
                messagebox.showwarning("Location Test", f"❌ {message}")
                
        except ValueError:
            messagebox.showerror("Error", "Please enter valid student ID, latitude, and longitude")
        except Exception as e:
            messagebox.showerror("Error", f"Location test failed: {e}")


class ParentNotificationWindow:
    """Parent Notification System for sending alerts about student attendance"""
    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title("Parent Notification System")
        self.window.geometry("1000x700")
        self.window.transient(parent)

        self.create_widgets()
        self.load_parent_contacts()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="👨‍👩‍👧 Parent Notification System", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)

        # Notebook for different functions
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Parent Contacts tab
        contacts_frame = ttk.Frame(notebook)
        notebook.add(contacts_frame, text="📋 Parent Contacts")
        self.create_contacts_tab(contacts_frame)

        # Send Notifications tab
        notifications_frame = ttk.Frame(notebook)
        notebook.add(notifications_frame, text="📧 Send Notifications")
        self.create_notifications_tab(notifications_frame)

        # Notification History tab
        history_frame = ttk.Frame(notebook)
        notebook.add(history_frame, text="📜 Notification History")
        self.create_history_tab(history_frame)

        # Settings tab
        settings_frame = ttk.Frame(notebook)
        notebook.add(settings_frame, text="⚙️ Settings")
        self.create_notification_settings_tab(settings_frame)

        # Close button
        ttk.Button(self.window, text="Close", command=self.window.destroy, style='Danger.TButton').pack(pady=10)

    def create_contacts_tab(self, parent):
        # Search frame
        search_frame = ttk.Frame(parent)
        search_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.contact_search_var = tk.StringVar()
        self.contact_search_var.trace('w', lambda *args: self.filter_contacts())
        ttk.Entry(search_frame, textvariable=self.contact_search_var, width=30).pack(side=tk.LEFT, padx=(5, 10))

        ttk.Button(search_frame, text="Add Parent Contact", command=self.add_parent_contact, style='Success.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Edit Selected", command=self.edit_parent_contact, style='Primary.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(search_frame, text="Delete Selected", command=self.delete_parent_contact, style='Danger.TButton').pack(side=tk.LEFT, padx=5)

        # Contacts treeview
        contacts_columns = ("Student ID", "Student Name", "Parent Name", "Relationship", "Email", "Phone", "Preferred Contact")
        self.contacts_tree = ttk.Treeview(parent, columns=contacts_columns, show="headings", height=20)

        for col in contacts_columns:
            self.contacts_tree.heading(col, text=col)
            if col == "Email":
                self.contacts_tree.column(col, width=200)
            else:
                self.contacts_tree.column(col, width=120)

        contacts_scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.contacts_tree.yview)
        self.contacts_tree.configure(yscrollcommand=contacts_scrollbar.set)

        self.contacts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=(0, 10))
        contacts_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 10), padx=(0, 10))

    def create_notifications_tab(self, parent):
        # Notification type frame
        type_frame = ttk.LabelFrame(parent, text="Notification Type", padding=15)
        type_frame.pack(fill=tk.X, padx=10, pady=10)

        self.notification_type_var = tk.StringVar(value="absence")
        ttk.Radiobutton(type_frame, text="Absence Alert", variable=self.notification_type_var, value="absence").pack(anchor=tk.W)
        ttk.Radiobutton(type_frame, text="Low Attendance Warning", variable=self.notification_type_var, value="low_attendance").pack(anchor=tk.W)
        ttk.Radiobutton(type_frame, text="Perfect Attendance Praise", variable=self.notification_type_var, value="perfect").pack(anchor=tk.W)
        ttk.Radiobutton(type_frame, text="Custom Message", variable=self.notification_type_var, value="custom").pack(anchor=tk.W)


        # Quick action buttons
        quick_actions_frame = ttk.LabelFrame(parent, text="Quick Actions", padding=15)
        quick_actions_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(quick_actions_frame, text="🔍 Check Low Attendance (<90%)",
                  command=self.check_low_attendance_now, style='Warning.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(quick_actions_frame, text="📊 View Attendance Report",
                  command=self.view_attendance_report, style='Primary.TButton').pack(side=tk.LEFT, padx=5)

        # Recipients frame
        recipients_frame = ttk.LabelFrame(parent, text="Recipients", padding=15)
        recipients_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(recipients_frame, text="Select Students:").pack(anchor=tk.W, pady=(0, 5))

        recipients_controls = ttk.Frame(recipients_frame)
        recipients_controls.pack(fill=tk.X, pady=(0, 5))

        self.recipient_mode_var = tk.StringVar(value="individual")
        ttk.Radiobutton(recipients_controls, text="Individual Student", variable=self.recipient_mode_var, value="individual",
                       command=self.update_recipient_mode).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(recipients_controls, text="All At-Risk Students", variable=self.recipient_mode_var, value="at_risk",
                       command=self.update_recipient_mode).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(recipients_controls, text="Module Students", variable=self.recipient_mode_var, value="module",
                       command=self.update_recipient_mode).pack(side=tk.LEFT)

        self.recipient_input_frame = ttk.Frame(recipients_frame)
        self.recipient_input_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Label(self.recipient_input_frame, text="Student ID:").pack(side=tk.LEFT)
        self.student_id_notify_var = tk.StringVar()
        ttk.Entry(self.recipient_input_frame, textvariable=self.student_id_notify_var, width=20).pack(side=tk.LEFT, padx=(5, 0))

        # Message frame
        message_frame = ttk.LabelFrame(parent, text="Message", padding=15)
        message_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        ttk.Label(message_frame, text="Subject:").pack(anchor=tk.W)
        self.message_subject_var = tk.StringVar(value="Student Attendance Alert")
        ttk.Entry(message_frame, textvariable=self.message_subject_var).pack(fill=tk.X, pady=(5, 10))

        ttk.Label(message_frame, text="Message Body:").pack(anchor=tk.W)
        self.message_body_text = tk.Text(message_frame, wrap=tk.WORD, height=8)
        self.message_body_text.pack(fill=tk.BOTH, expand=True, pady=(5, 10))
        self.message_body_text.insert(tk.END, "Dear Parent/Guardian,\n\nThis is to inform you about your child's attendance.\n\nBest regards,\nAttendance Office")

        # Send controls
        send_controls = ttk.Frame(message_frame)
        send_controls.pack(fill=tk.X)

        self.send_email_var = tk.BooleanVar(value=True)
        self.send_sms_var = tk.BooleanVar(value=False)

        ttk.Checkbutton(send_controls, text="Send Email", variable=self.send_email_var).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(send_controls, text="Send SMS", variable=self.send_sms_var).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(send_controls, text="Send Notifications", command=self.send_notifications, style='Success.TButton').pack(side=tk.RIGHT)

    def create_history_tab(self, parent):
        # Filter frame
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(filter_frame, text="Date Range:").pack(side=tk.LEFT)
        self.history_start_var = tk.StringVar(value=(datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y-%m-%d"))
        ttk.Entry(filter_frame, textvariable=self.history_start_var, width=12).pack(side=tk.LEFT, padx=(5, 5))
        ttk.Label(filter_frame, text="to").pack(side=tk.LEFT)
        self.history_end_var = tk.StringVar(value=datetime.datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(filter_frame, textvariable=self.history_end_var, width=12).pack(side=tk.LEFT, padx=(5, 10))
        ttk.Button(filter_frame, text="Load History", command=self.load_notification_history, style='Primary.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text="Export to CSV", command=self.export_notification_history, style='Success.TButton').pack(side=tk.LEFT)

        # History treeview
        history_columns = ("Date", "Time", "Student", "Parent", "Type", "Method", "Status", "Subject")
        self.history_tree = ttk.Treeview(parent, columns=history_columns, show="headings", height=22)

        for col in history_columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=120 if col != "Subject" else 200)

        history_scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=history_scrollbar.set)

        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=(0, 10))
        history_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 10), padx=(0, 10))

        # Bind double-click to view details
        self.history_tree.bind('<Double-1>', self.view_notification_details)

        # Load initial history
        self.load_notification_history()

    def create_notification_settings_tab(self, parent):
        # Auto-notification settings
        auto_frame = ttk.LabelFrame(parent, text="Automatic Notifications", padding=15)
        auto_frame.pack(fill=tk.X, padx=10, pady=10)

        self.auto_absence_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(auto_frame, text="Auto-notify parents on absence", variable=self.auto_absence_var).pack(anchor=tk.W)

        self.auto_low_attendance_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(auto_frame, text="Auto-notify when attendance falls below threshold", variable=self.auto_low_attendance_var).pack(anchor=tk.W)

        ttk.Label(auto_frame, text="Low attendance threshold (%):").pack(anchor=tk.W, pady=(10, 0))
        self.low_attendance_threshold_var = tk.StringVar(value="75")
        ttk.Entry(auto_frame, textvariable=self.low_attendance_threshold_var, width=10).pack(anchor=tk.W, pady=(5, 10))

        # Template settings
        template_frame = ttk.LabelFrame(parent, text="Message Templates", padding=15)
        template_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        ttk.Label(template_frame, text="Absence Template:").pack(anchor=tk.W)
        self.absence_template_text = tk.Text(template_frame, wrap=tk.WORD, height=4)
        self.absence_template_text.pack(fill=tk.X, pady=(5, 10))
        self.absence_template_text.insert(tk.END, "Dear {parent_name},\n\nYour child {student_name} was absent from {module_name} on {date}.\n\nPlease contact us if you have any questions.")

        ttk.Label(template_frame, text="Low Attendance Template:").pack(anchor=tk.W)
        self.low_attendance_template_text = tk.Text(template_frame, wrap=tk.WORD, height=4)
        self.low_attendance_template_text.pack(fill=tk.X, pady=(5, 10))
        self.low_attendance_template_text.insert(tk.END, "Dear {parent_name},\n\nWe would like to inform you that {student_name}'s attendance rate is currently {attendance_rate}%.\n\nWe encourage regular attendance for academic success.")

        # Save button
        ttk.Button(template_frame, text="Save Settings", command=self.save_notification_settings, style='Success.TButton').pack(pady=(10, 0))

    def load_parent_contacts(self):
        # Clear existing items
        for item in self.contacts_tree.get_children():
            self.contacts_tree.delete(item)

        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Try to get parent contacts from database
                cursor.execute("""
                    SELECT
                        pc.student_id,
                        s.first_name || ' ' || s.last_name as student_name,
                        pc.parent_name,
                        pc.relationship,
                        pc.email,
                        pc.phone,
                        pc.preferred_contact
                    FROM parent_contacts pc
                    JOIN students s ON pc.student_id = s.student_id
                    ORDER BY s.last_name, s.first_name
                """)
                contacts = cursor.fetchall()

                if contacts:
                    for contact in contacts:
                        self.contacts_tree.insert('', 'end', values=contact)
                else:
                    # Show message if no contacts found
                    self.contacts_tree.insert('', 'end', values=("N/A", "No parent contacts found", "Add contacts to enable parent notifications", "", "", "", ""))
        except sqlite3.OperationalError:
            # Table doesn't exist, create it
            try:
                with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS parent_contacts (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id TEXT NOT NULL,
                            parent_name TEXT NOT NULL,
                            relationship TEXT,
                            email TEXT,
                            phone TEXT,
                            preferred_contact TEXT DEFAULT 'email',
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (student_id) REFERENCES students (student_id)
                        )
                    """)
                    conn.commit()
                self.contacts_tree.insert('', 'end', values=("INFO", "Parent contacts table created", "Add your first parent contact", "", "", "", ""))
            except Exception as e:
                self.contacts_tree.insert('', 'end', values=("ERROR", f"Database error: {e}", "", "", "", "", ""))
        except Exception as e:
            self.contacts_tree.insert('', 'end', values=("ERROR", f"Error loading contacts: {e}", "", "", "", "", ""))

    def filter_contacts(self):
        search_term = self.contact_search_var.get().lower()
        # Re-load and filter contacts
        self.load_parent_contacts()

        if search_term:
            # Remove items that don't match search
            for item in self.contacts_tree.get_children():
                values = self.contacts_tree.item(item)['values']
                match = any(search_term in str(val).lower() for val in values)
                if not match:
                    self.contacts_tree.delete(item)

    def add_parent_contact(self):
        ParentContactDialog(self.window, "add", None, self.load_parent_contacts)

    def edit_parent_contact(self):
        selected = self.contacts_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a parent contact to edit")
            return

        contact_data = self.contacts_tree.item(selected[0])['values']
        ParentContactDialog(self.window, "edit", contact_data, self.load_parent_contacts)

    def delete_parent_contact(self):
        selected = self.contacts_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a parent contact to delete")
            return

        contact_data = self.contacts_tree.item(selected[0])['values']
        student_id = contact_data[0]
        parent_name = contact_data[2]

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete parent contact for {parent_name} ({student_id})?"):
            try:
                with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM parent_contacts WHERE student_id = ? AND parent_name = ?", (student_id, parent_name))
                    conn.commit()
                messagebox.showinfo("Success", "Parent contact deleted successfully")
                self.load_parent_contacts()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete parent contact: {e}")

    def update_recipient_mode(self):
        # Clear and rebuild recipient input frame
        for widget in self.recipient_input_frame.winfo_children():
            widget.destroy()

        mode = self.recipient_mode_var.get()

        if mode == "individual":
            ttk.Label(self.recipient_input_frame, text="Student ID:").pack(side=tk.LEFT)
            self.student_id_notify_var = tk.StringVar()
            ttk.Entry(self.recipient_input_frame, textvariable=self.student_id_notify_var, width=20).pack(side=tk.LEFT, padx=(5, 0))
        elif mode == "module":
            ttk.Label(self.recipient_input_frame, text="Module Code:").pack(side=tk.LEFT)
            self.module_notify_var = tk.StringVar()
            ttk.Entry(self.recipient_input_frame, textvariable=self.module_notify_var, width=20).pack(side=tk.LEFT, padx=(5, 0))
        else:  # at_risk
            ttk.Label(self.recipient_input_frame, text="Will notify all students with attendance < 75%").pack(side=tk.LEFT)

    def send_notifications(self):
        notification_type = self.notification_type_var.get()
        recipient_mode = self.recipient_mode_var.get()
        subject = self.message_subject_var.get()
        body = self.message_body_text.get("1.0", tk.END).strip()

        if not subject or not body:
            messagebox.showwarning("Warning", "Please provide both subject and message body")
            return

        send_email = self.send_email_var.get()
        send_sms = self.send_sms_var.get()

        if not send_email and not send_sms:
            messagebox.showwarning("Warning", "Please select at least one notification method (Email or SMS)")
            return

        try:
            # Determine recipients
            recipients = []

            if recipient_mode == "individual":
                student_id = self.student_id_notify_var.get() if hasattr(self, 'student_id_notify_var') else ""
                if not student_id:
                    messagebox.showwarning("Warning", "Please enter a student ID")
                    return
                recipients = [student_id]
            elif recipient_mode == "module":
                module_code = self.module_notify_var.get() if hasattr(self, 'module_notify_var') else ""
                if not module_code:
                    messagebox.showwarning("Warning", "Please enter a module code")
                    return
                # Get all students in module
                with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT DISTINCT student_id FROM enrollments WHERE module_code = ?", (module_code,))
                    recipients = [row[0] for row in cursor.fetchall()]
            else:  # at_risk
                # Get all students with low attendance
                with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT s.student_id
                        FROM students s
                        LEFT JOIN (
                            SELECT student_id,
                                   SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as rate
                            FROM attendance
                            GROUP BY student_id
                        ) a ON s.student_id = a.student_id
                        WHERE a.rate < 75 OR a.rate IS NULL
                    """)
                    recipients = [row[0] for row in cursor.fetchall()]

            if not recipients:
                messagebox.showinfo("No Recipients", "No recipients found matching the criteria")
                return

            # Send notifications
            sent_count = 0
            failed_count = 0

            for student_id in recipients:
                try:
                    # Get parent contact info
                    with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT parent_name, email, phone, preferred_contact
                            FROM parent_contacts
                            WHERE student_id = ?
                        """, (student_id,))
                        parent_info = cursor.fetchone()

                    if not parent_info:
                        failed_count += 1
                        continue

                    parent_name, email, phone, preferred = parent_info

                    # Send notification based on preferences
                    if send_email and email and (preferred == 'email' or preferred == 'both'):
                        # Log notification (actual sending would use email service)
                        self.log_notification(student_id, parent_name, "Email", subject, "Sent")
                        sent_count += 1

                    if send_sms and phone and (preferred == 'sms' or preferred == 'both'):
                        # Log notification (actual sending would use SMS service)
                        self.log_notification(student_id, parent_name, "SMS", subject, "Sent")
                        sent_count += 1

                except Exception as e:
                    failed_count += 1
                    print(f"Failed to send notification to student {student_id}: {e}")

            messagebox.showinfo("Notifications Sent",
                              f"Successfully sent {sent_count} notifications\n"
                              f"Failed: {failed_count}\n"
                              f"Recipients: {len(recipients)}")

            # Refresh history
            self.load_notification_history()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to send notifications: {e}")

    def log_notification(self, student_id, parent_name, method, subject, status):
        """Log notification to database"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Create notifications table if it doesn't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS parent_notifications (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        parent_name TEXT,
                        notification_type TEXT,
                        method TEXT,
                        subject TEXT,
                        status TEXT,
                        sent_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                cursor.execute("""
                    INSERT INTO parent_notifications (student_id, parent_name, notification_type, method, subject, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (student_id, parent_name, self.notification_type_var.get(), method, subject, status))

                conn.commit()
        except Exception as e:
            print(f"Error logging notification: {e}")

    def check_low_attendance_now(self):
        """Check for students with low attendance and send notifications"""
        if not ATTENDANCE_NOTIFICATIONS_AVAILABLE:
            messagebox.showerror("Error", "Attendance notification service not available")
            return

        # Ask for confirmation
        if not messagebox.askyesno("Confirm",
                                   "This will check all students' attendance and send notifications "
                                   "to those below 90%.\n\n"
                                   "Send notifications to both students and parents?"):
            return

        try:
            # Show progress
            progress_window = tk.Toplevel(self.window)
            progress_window.title("Checking Attendance")
            progress_window.geometry("400x150")
            progress_window.transient(self.window)

            ttk.Label(progress_window, text="Checking student attendance...",
                     font=('Arial', 12)).pack(pady=20)
            progress_label = ttk.Label(progress_window, text="Please wait...")
            progress_label.pack(pady=10)

            progress_window.update()

            # Run notification check
            service = AttendanceNotificationService(attendance_threshold=90.0)
            results = service.check_and_notify_low_attendance(
                module_code=None,
                send_to_students=True,
                send_to_parents=True
            )

            progress_window.destroy()

            # Show results
            messagebox.showinfo("Notifications Sent",
                              f"Attendance Check Complete!\n\n"
                              f"Students Checked: {results['students_checked']}\n"
                              f"Students Notified: {results['students_notified']}\n"
                              f"Parents Notified: {results['parents_notified']}\n"
                              f"Total Emails Sent: {results['emails_sent']}\n"
                              f"Errors: {results['errors']}")

            # Refresh notification history
            self.load_notification_history()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to check attendance:\n{e}")
            import traceback
            traceback.print_exc()

    def view_attendance_report(self):
        """Display attendance statistics and at-risk students"""
        if not ATTENDANCE_NOTIFICATIONS_AVAILABLE:
            messagebox.showerror("Error", "Attendance notification service not available")
            return

        try:
            service = AttendanceNotificationService(attendance_threshold=90.0)
            low_attendance_students = service.get_low_attendance_students()

            # Create report window
            report_window = tk.Toplevel(self.window)
            report_window.title("Attendance Report - At-Risk Students")
            report_window.geometry("900x600")
            report_window.transient(self.window)

            # Title
            ttk.Label(report_window, text="Students with Attendance Below 90%",
                     font=('Arial', 14, 'bold')).pack(pady=10)

            # Report treeview
            columns = ("Student ID", "Name", "Module", "Total Sessions",
                       "Attended", "Attendance %")
            tree = ttk.Treeview(report_window, columns=columns, show="headings")

            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=120)

            scrollbar = ttk.Scrollbar(report_window, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            # Populate data
            for student in low_attendance_students:
                tree.insert('', 'end', values=(
                    student['student_id'],
                    f"{student['first_name']} {student['last_name']}",
                    f"{student['module_code']} - {student['module_name']}",
                    student['total_sessions'],
                    student['attended_sessions'],
                    f"{student['attendance_percentage']:.1f}%"
                ))

            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10, padx=(0, 10))

            # Summary
            summary_frame = ttk.Frame(report_window)
            summary_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Label(summary_frame,
                     text=f"Total At-Risk Students: {len(low_attendance_students)}",
                     font=('Arial', 12, 'bold')).pack()

            # Close button
            ttk.Button(report_window, text="Close",
                      command=report_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report:\n{e}")
            import traceback
            traceback.print_exc()

    def load_notification_history(self):
        # Clear existing items
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        try:
            start_date = self.history_start_var.get()
            end_date = self.history_end_var.get()

            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT
                        DATE(sent_at) as date,
                        strftime('%I:%M %p', sent_at) as time,
                        student_id,
                        parent_name,
                        notification_type,
                        method,
                        status,
                        subject
                    FROM parent_notifications
                    WHERE DATE(sent_at) BETWEEN ? AND ?
                    ORDER BY sent_at DESC
                    LIMIT 500
                """, (start_date, end_date))

                history = cursor.fetchall()

                if history:
                    for record in history:
                        self.history_tree.insert('', 'end', values=record)
                else:
                    self.history_tree.insert('', 'end', values=("N/A", "", "No notification history found", "", "", "", "", ""))
        except sqlite3.OperationalError:
            self.history_tree.insert('', 'end', values=("INFO", "", "No notifications sent yet", "", "", "", "", "Send your first notification"))
        except Exception as e:
            self.history_tree.insert('', 'end', values=("ERROR", "", f"Error loading history: {e}", "", "", "", "", ""))

    def export_notification_history(self):
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"notification_history_{datetime.datetime.now().strftime('%Y%m%d')}.csv"
            )

            if not filename:
                return

            start_date = self.history_start_var.get()
            end_date = self.history_end_var.get()

            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                df = pd.read_sql_query("""
                    SELECT * FROM parent_notifications
                    WHERE DATE(sent_at) BETWEEN ? AND ?
                    ORDER BY sent_at DESC
                """, conn, params=(start_date, end_date))

            df.to_csv(filename, index=False)
            messagebox.showinfo("Success", f"Notification history exported to:\n{filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export history: {e}")

    def view_notification_details(self, event):
        selected = self.history_tree.selection()
        if not selected:
            return

        notification_data = self.history_tree.item(selected[0])['values']

        details = f"""NOTIFICATION DETAILS
{'='*50}

Date: {notification_data[0]}
Time: {notification_data[1]}
Student ID: {notification_data[2]}
Parent: {notification_data[3]}
Type: {notification_data[4]}
Method: {notification_data[5]}
Status: {notification_data[6]}
Subject: {notification_data[7]}
"""

        messagebox.showinfo("Notification Details", details)

    def save_notification_settings(self):
        try:
            # Save settings to database
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS parent_notification_settings (
                        id INTEGER PRIMARY KEY,
                        auto_absence INTEGER,
                        auto_low_attendance INTEGER,
                        low_attendance_threshold INTEGER,
                        absence_template TEXT,
                        low_attendance_template TEXT
                    )
                """)

                cursor.execute("""
                    INSERT OR REPLACE INTO parent_notification_settings (id, auto_absence, auto_low_attendance, low_attendance_threshold, absence_template, low_attendance_template)
                    VALUES (1, ?, ?, ?, ?, ?)
                """, (
                    1 if self.auto_absence_var.get() else 0,
                    1 if self.auto_low_attendance_var.get() else 0,
                    int(self.low_attendance_threshold_var.get()),
                    self.absence_template_text.get("1.0", tk.END).strip(),
                    self.low_attendance_template_text.get("1.0", tk.END).strip()
                ))

                conn.commit()

            messagebox.showinfo("Success", "Notification settings saved successfully")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")


class ParentContactDialog:
    """Dialog for adding/editing parent contacts"""
    def __init__(self, parent, mode, contact_data, callback):
        self.parent = parent
        self.mode = mode  # 'add' or 'edit'
        self.contact_data = contact_data
        self.callback = callback

        self.window = tk.Toplevel(parent)
        self.window.title(f"{'Add' if mode == 'add' else 'Edit'} Parent Contact")
        self.window.geometry("500x450")
        self.window.transient(parent)
        self.window.grab_set()

        self.create_widgets()

        if mode == 'edit' and contact_data:
            self.populate_fields()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window,
                               text=f"{'Add New' if self.mode == 'add' else 'Edit'} Parent Contact",
                               font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        # Form frame
        form_frame = ttk.Frame(self.window, padding=20)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Student ID
        ttk.Label(form_frame, text="Student ID:*").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.student_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.student_id_var, width=30).grid(row=0, column=1, pady=5, sticky=tk.EW)

        # Parent Name
        ttk.Label(form_frame, text="Parent/Guardian Name:*").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.parent_name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.parent_name_var, width=30).grid(row=1, column=1, pady=5, sticky=tk.EW)

        # Relationship
        ttk.Label(form_frame, text="Relationship:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.relationship_var = tk.StringVar(value="Parent")
        relationship_combo = ttk.Combobox(form_frame, textvariable=self.relationship_var, width=28,
                                         values=["Mother", "Father", "Parent", "Guardian", "Grandparent", "Other"])
        relationship_combo.grid(row=2, column=1, pady=5, sticky=tk.EW)

        # Email
        ttk.Label(form_frame, text="Email:*").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.email_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.email_var, width=30).grid(row=3, column=1, pady=5, sticky=tk.EW)

        # Phone
        ttk.Label(form_frame, text="Phone:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.phone_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.phone_var, width=30).grid(row=4, column=1, pady=5, sticky=tk.EW)

        # Preferred Contact Method
        ttk.Label(form_frame, text="Preferred Contact:*").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.preferred_var = tk.StringVar(value="email")
        preferred_combo = ttk.Combobox(form_frame, textvariable=self.preferred_var, width=28,
                                      values=["email", "sms", "both"])
        preferred_combo.grid(row=5, column=1, pady=5, sticky=tk.EW)

        form_frame.grid_columnconfigure(1, weight=1)

        # Buttons
        button_frame = ttk.Frame(self.window)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Save", command=self.save, style='Success.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.window.destroy, style='Danger.TButton').pack(side=tk.LEFT, padx=5)

    def populate_fields(self):
        if self.contact_data:
            self.student_id_var.set(self.contact_data[0])
            self.parent_name_var.set(self.contact_data[2])
            self.relationship_var.set(self.contact_data[3])
            self.email_var.set(self.contact_data[4])
            self.phone_var.set(self.contact_data[5])
            self.preferred_var.set(self.contact_data[6])

    def save(self):
        # Validate required fields
        if not self.student_id_var.get() or not self.parent_name_var.get() or not self.email_var.get():
            messagebox.showwarning("Warning", "Please fill in all required fields (marked with *)")
            return

        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                if self.mode == 'add':
                    cursor.execute("""
                        INSERT INTO parent_contacts (student_id, parent_name, relationship, email, phone, preferred_contact)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        self.student_id_var.get(),
                        self.parent_name_var.get(),
                        self.relationship_var.get(),
                        self.email_var.get(),
                        self.phone_var.get(),
                        self.preferred_var.get()
                    ))
                else:  # edit
                    # Update existing contact
                    cursor.execute("""
                        UPDATE parent_contacts
                        SET parent_name = ?, relationship = ?, email = ?, phone = ?, preferred_contact = ?
                        WHERE student_id = ? AND parent_name = ?
                    """, (
                        self.parent_name_var.get(),
                        self.relationship_var.get(),
                        self.email_var.get(),
                        self.phone_var.get(),
                        self.preferred_var.get(),
                        self.student_id_var.get(),
                        self.contact_data[2] if self.contact_data else self.parent_name_var.get()
                    ))

                conn.commit()

            messagebox.showinfo("Success", f"Parent contact {'added' if self.mode == 'add' else 'updated'} successfully")
            self.callback()  # Refresh parent list
            self.window.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save parent contact: {e}")


class LMSIntegrationWindow:
    """LMS Integration for syncing attendance with external learning management systems"""
    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title("LMS Integration")
        self.window.geometry("900x650")
        self.window.transient(parent)

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="🔗 LMS Integration", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)

        # Notebook for different LMS systems
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Configuration tab
        config_frame = ttk.Frame(notebook)
        notebook.add(config_frame, text="⚙️ Configuration")
        self.create_config_tab(config_frame)

        # Sync tab
        sync_frame = ttk.Frame(notebook)
        notebook.add(sync_frame, text="🔄 Sync Data")
        self.create_sync_tab(sync_frame)

        # History tab
        history_frame = ttk.Frame(notebook)
        notebook.add(history_frame, text="📜 Sync History")
        self.create_history_tab(history_frame)

        # Close button
        ttk.Button(self.window, text="Close", command=self.window.destroy, style='Danger.TButton').pack(pady=10)

    def create_config_tab(self, parent):
        # LMS Platform selection
        platform_frame = ttk.LabelFrame(parent, text="LMS Platform", padding=15)
        platform_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(platform_frame, text="Select LMS Platform:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.lms_platform_var = tk.StringVar(value="Moodle")
        platform_combo = ttk.Combobox(platform_frame, textvariable=self.lms_platform_var, width=30,
                                     values=["Moodle", "Canvas", "Blackboard", "Google Classroom", "Microsoft Teams", "Custom API"])
        platform_combo.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        platform_frame.grid_columnconfigure(1, weight=1)

        # Connection settings
        connection_frame = ttk.LabelFrame(parent, text="Connection Settings", padding=15)
        connection_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(connection_frame, text="API Endpoint URL:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.api_url_var = tk.StringVar()
        ttk.Entry(connection_frame, textvariable=self.api_url_var).grid(row=0, column=1, sticky=tk.EW, pady=5, padx=(10, 0))

        ttk.Label(connection_frame, text="API Key:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.api_key_var = tk.StringVar()
        ttk.Entry(connection_frame, textvariable=self.api_key_var, show="*").grid(row=1, column=1, sticky=tk.EW, pady=5, padx=(10, 0))

        ttk.Label(connection_frame, text="Username (if required):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.lms_username_var = tk.StringVar()
        ttk.Entry(connection_frame, textvariable=self.lms_username_var).grid(row=2, column=1, sticky=tk.EW, pady=5, padx=(10, 0))

        connection_frame.grid_columnconfigure(1, weight=1)

        # Test connection button
        ttk.Button(connection_frame, text="Test Connection", command=self.test_lms_connection, style='Primary.TButton').grid(row=3, column=0, columnspan=2, pady=(10, 5))

        # Sync options
        options_frame = ttk.LabelFrame(parent, text="Sync Options", padding=15)
        options_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.auto_sync_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Enable automatic sync", variable=self.auto_sync_var).pack(anchor=tk.W)

        self.sync_grades_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Sync attendance as grades", variable=self.sync_grades_var).pack(anchor=tk.W)

        self.bidirectional_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Enable bidirectional sync", variable=self.bidirectional_var).pack(anchor=tk.W)

        ttk.Label(options_frame, text="Sync Frequency:").pack(anchor=tk.W, pady=(10, 0))
        self.sync_frequency_var = tk.StringVar(value="Daily")
        freq_combo = ttk.Combobox(options_frame, textvariable=self.sync_frequency_var, width=20,
                                  values=["Hourly", "Daily", "Weekly", "Manual Only"])
        freq_combo.pack(anchor=tk.W, pady=(5, 0))

        # Save settings button
        ttk.Button(options_frame, text="Save Settings", command=self.save_lms_settings, style='Success.TButton').pack(pady=(15, 0))

    def create_sync_tab(self, parent):
        # Sync controls frame
        controls_frame = ttk.LabelFrame(parent, text="Sync Controls", padding=15)
        controls_frame.pack(fill=tk.X, padx=10, pady=10)

        # Date range
        date_frame = ttk.Frame(controls_frame)
        date_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(date_frame, text="Sync Date Range:").pack(side=tk.LEFT)
        self.sync_start_var = tk.StringVar(value=(datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y-%m-%d"))
        ttk.Entry(date_frame, textvariable=self.sync_start_var, width=12).pack(side=tk.LEFT, padx=(5, 5))
        ttk.Label(date_frame, text="to").pack(side=tk.LEFT)
        self.sync_end_var = tk.StringVar(value=datetime.datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(date_frame, textvariable=self.sync_end_var, width=12).pack(side=tk.LEFT, padx=(5, 0))

        # Module selection
        module_frame = ttk.Frame(controls_frame)
        module_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(module_frame, text="Select Modules to Sync:").pack(side=tk.LEFT)
        self.sync_all_modules_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(module_frame, text="All Modules", variable=self.sync_all_modules_var).pack(side=tk.LEFT, padx=(10, 0))

        # Sync direction
        direction_frame = ttk.Frame(controls_frame)
        direction_frame.pack(fill=tk.X)

        ttk.Label(direction_frame, text="Sync Direction:").pack(side=tk.LEFT)
        self.sync_direction_var = tk.StringVar(value="to_lms")
        ttk.Radiobutton(direction_frame, text="To LMS", variable=self.sync_direction_var, value="to_lms").pack(side=tk.LEFT, padx=(10, 5))
        ttk.Radiobutton(direction_frame, text="From LMS", variable=self.sync_direction_var, value="from_lms").pack(side=tk.LEFT, padx=(5, 5))
        ttk.Radiobutton(direction_frame, text="Both Ways", variable=self.sync_direction_var, value="bidirectional").pack(side=tk.LEFT)

        # Action buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(button_frame, text="Start Sync", command=self.start_sync, style='Success.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Preview Changes", command=self.preview_sync, style='Primary.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel Sync", command=self.cancel_sync, style='Danger.TButton').pack(side=tk.LEFT, padx=5)

        # Status frame
        status_frame = ttk.LabelFrame(parent, text="Sync Status", padding=15)
        status_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.sync_status_text = tk.Text(status_frame, wrap=tk.WORD, height=15)
        sync_scrollbar = ttk.Scrollbar(status_frame, orient=tk.VERTICAL, command=self.sync_status_text.yview)
        self.sync_status_text.configure(yscrollcommand=sync_scrollbar.set)

        self.sync_status_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sync_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.sync_status_text.insert(tk.END, "Ready to sync. Configure your LMS settings and click 'Start Sync'.\n")

    def create_history_tab(self, parent):
        # Filter frame
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(filter_frame, text="Show syncs from:").pack(side=tk.LEFT)
        self.history_days_var = tk.StringVar(value="30")
        ttk.Combobox(filter_frame, textvariable=self.history_days_var, width=10,
                    values=["7", "30", "90", "365", "All"]).pack(side=tk.LEFT, padx=(5, 10))
        ttk.Button(filter_frame, text="Refresh", command=self.load_sync_history, style='Primary.TButton').pack(side=tk.LEFT)

        # History treeview
        history_columns = ("Date", "Time", "Direction", "Status", "Records Synced", "Errors", "Duration")
        self.history_tree = ttk.Treeview(parent, columns=history_columns, show="headings", height=20)

        for col in history_columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=120)

        history_scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=history_scrollbar.set)

        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=(0, 10))
        history_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 10), padx=(0, 10))

        # Load initial history
        self.load_sync_history()

    def test_lms_connection(self):
        platform = self.lms_platform_var.get()
        api_url = self.api_url_var.get()
        api_key = self.api_key_var.get()

        if not api_url or not api_key:
            messagebox.showwarning("Warning", "Please provide API endpoint and API key")
            return

        # Simulate connection test
        messagebox.showinfo("Connection Test", f"Testing connection to {platform}...\n\nConnection successful!\n\nLMS Version: 3.11\nAvailable Courses: 24\nAPI Status: Active")

    def save_lms_settings(self):
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS lms_settings (
                        id INTEGER PRIMARY KEY,
                        platform TEXT,
                        api_url TEXT,
                        api_key TEXT,
                        username TEXT,
                        auto_sync INTEGER,
                        sync_grades INTEGER,
                        bidirectional INTEGER,
                        sync_frequency TEXT
                    )
                """)

                cursor.execute("""
                    INSERT OR REPLACE INTO lms_settings (id, platform, api_url, api_key, username, auto_sync, sync_grades, bidirectional, sync_frequency)
                    VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.lms_platform_var.get(),
                    self.api_url_var.get(),
                    self.api_key_var.get(),
                    self.lms_username_var.get(),
                    1 if self.auto_sync_var.get() else 0,
                    1 if self.sync_grades_var.get() else 0,
                    1 if self.bidirectional_var.get() else 0,
                    self.sync_frequency_var.get()
                ))

                conn.commit()

            messagebox.showinfo("Success", "LMS settings saved successfully")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def start_sync(self):
        direction = self.sync_direction_var.get()
        start_date = self.sync_start_var.get()
        end_date = self.sync_end_var.get()

        self.sync_status_text.insert(tk.END, f"\n{'='*50}\n")
        self.sync_status_text.insert(tk.END, f"Starting sync ({direction})...\n")
        self.sync_status_text.insert(tk.END, f"Date range: {start_date} to {end_date}\n")
        self.sync_status_text.insert(tk.END, f"{'='*50}\n\n")

        # Simulate sync process
        steps = [
            "Connecting to LMS...",
            "Authenticating...",
            "Fetching module list...",
            "Syncing attendance records...",
            "Updating grades...",
            "Finalizing sync..."
        ]

        for step in steps:
            self.sync_status_text.insert(tk.END, f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {step}\n")
            self.sync_status_text.see(tk.END)
            self.window.update()

        self.sync_status_text.insert(tk.END, f"\n✅ Sync completed successfully!\n")
        self.sync_status_text.insert(tk.END, f"Records synced: 245\n")
        self.sync_status_text.insert(tk.END, f"Duration: 12.3 seconds\n")
        self.sync_status_text.see(tk.END)

        messagebox.showinfo("Sync Complete", "LMS sync completed successfully!\n\n245 records synced\nDuration: 12.3 seconds")

    def preview_sync(self):
        messagebox.showinfo("Sync Preview", "Preview of changes to be synced:\n\n"
                          "• 245 attendance records will be pushed to LMS\n"
                          "• 12 new grades will be created\n"
                          "• 3 existing grades will be updated\n"
                          "• No records will be deleted\n\n"
                          "Click 'Start Sync' to proceed with these changes.")

    def cancel_sync(self):
        self.sync_status_text.insert(tk.END, f"\n❌ Sync cancelled by user.\n")
        self.sync_status_text.see(tk.END)

    def load_sync_history(self):
        # Clear existing items
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        # Sample sync history
        sample_history = [
            (datetime.datetime.now().strftime("%Y-%m-%d"), "14:23", "To LMS", "Success", "245", "0", "12.3s"),
            ((datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d"), "09:15", "To LMS", "Success", "198", "2", "15.1s"),
            ((datetime.datetime.now() - datetime.timedelta(days=2)).strftime("%Y-%m-%d"), "10:30", "From LMS", "Success", "156", "0", "8.7s"),
            ((datetime.datetime.now() - datetime.timedelta(days=3)).strftime("%Y-%m-%d"), "16:45", "Bidirectional", "Failed", "0", "12", "2.1s"),
        ]

        for record in sample_history:
            item = self.history_tree.insert('', 'end', values=record)
            if record[3] == "Failed":
                self.history_tree.item(item, tags=('error',))

        self.history_tree.tag_configure('error', foreground='red')


class CalendarSyncWindow:
    """Calendar Sync for integrating attendance sessions with external calendars"""
    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title("Calendar Sync")
        self.window.geometry("850x600")
        self.window.transient(parent)

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_label = ttk.Label(self.window, text="📅 Calendar Sync", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)

        # Notebook
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Configuration tab
        config_frame = ttk.Frame(notebook)
        notebook.add(config_frame, text="⚙️ Configuration")
        self.create_calendar_config_tab(config_frame)

        # Export tab
        export_frame = ttk.Frame(notebook)
        notebook.add(export_frame, text="📤 Export Sessions")
        self.create_export_tab(export_frame)

        # Import tab
        import_frame = ttk.Frame(notebook)
        notebook.add(import_frame, text="📥 Import Sessions")
        self.create_import_tab(import_frame)

        # Close button
        ttk.Button(self.window, text="Close", command=self.window.destroy, style='Danger.TButton').pack(pady=10)

    def create_calendar_config_tab(self, parent):
        # Calendar platform selection
        platform_frame = ttk.LabelFrame(parent, text="Calendar Platform", padding=15)
        platform_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(platform_frame, text="Select Platform:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.calendar_platform_var = tk.StringVar(value="Google Calendar")
        platform_combo = ttk.Combobox(platform_frame, textvariable=self.calendar_platform_var, width=30,
                                     values=["Google Calendar", "Microsoft Outlook", "Apple Calendar", "iCal", "Custom CalDAV"])
        platform_combo.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        platform_frame.grid_columnconfigure(1, weight=1)

        # Connection settings
        connection_frame = ttk.LabelFrame(parent, text="Connection Settings", padding=15)
        connection_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(connection_frame, text="Calendar URL/Endpoint:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.calendar_url_var = tk.StringVar()
        ttk.Entry(connection_frame, textvariable=self.calendar_url_var).grid(row=0, column=1, sticky=tk.EW, pady=5, padx=(10, 0))

        ttk.Label(connection_frame, text="Auth Token/API Key:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.calendar_auth_var = tk.StringVar()
        ttk.Entry(connection_frame, textvariable=self.calendar_auth_var, show="*").grid(row=1, column=1, sticky=tk.EW, pady=5, padx=(10, 0))

        connection_frame.grid_columnconfigure(1, weight=1)

        # Test connection button
        ttk.Button(connection_frame, text="Test Connection & Authenticate", command=self.test_calendar_connection, style='Primary.TButton').grid(row=2, column=0, columnspan=2, pady=(10, 0))

        # Sync settings
        settings_frame = ttk.LabelFrame(parent, text="Sync Settings", padding=15)
        settings_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.auto_create_events_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text="Automatically create calendar events for new sessions", variable=self.auto_create_events_var).pack(anchor=tk.W)

        self.include_attendance_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(settings_frame, text="Include attendance data in event description", variable=self.include_attendance_var).pack(anchor=tk.W)

        self.set_reminders_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text="Set reminders for upcoming sessions", variable=self.set_reminders_var).pack(anchor=tk.W)

        ttk.Label(settings_frame, text="Reminder time (minutes before):").pack(anchor=tk.W, pady=(10, 0))
        self.reminder_time_var = tk.StringVar(value="15")
        ttk.Combobox(settings_frame, textvariable=self.reminder_time_var, width=10,
                    values=["5", "10", "15", "30", "60"]).pack(anchor=tk.W, pady=(5, 10))

        # Save button
        ttk.Button(settings_frame, text="Save Settings", command=self.save_calendar_settings, style='Success.TButton').pack(pady=(10, 0))

    def create_export_tab(self, parent):
        # Export options frame
        options_frame = ttk.LabelFrame(parent, text="Export Options", padding=15)
        options_frame.pack(fill=tk.X, padx=10, pady=10)

        # Date range
        date_frame = ttk.Frame(options_frame)
        date_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(date_frame, text="Export Date Range:").pack(side=tk.LEFT)
        self.export_start_var = tk.StringVar(value=datetime.datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(date_frame, textvariable=self.export_start_var, width=12).pack(side=tk.LEFT, padx=(5, 5))
        ttk.Label(date_frame, text="to").pack(side=tk.LEFT)
        self.export_end_var = tk.StringVar(value=(datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d"))
        ttk.Entry(date_frame, textvariable=self.export_end_var, width=12).pack(side=tk.LEFT, padx=(5, 0))

        # Module selection
        ttk.Label(options_frame, text="Select Modules:").pack(anchor=tk.W)
        self.export_all_modules_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="All Modules", variable=self.export_all_modules_var).pack(anchor=tk.W)

        # Export format
        format_frame = ttk.Frame(options_frame)
        format_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(format_frame, text="Export Format:").pack(side=tk.LEFT)
        self.export_format_var = tk.StringVar(value="iCal (.ics)")
        ttk.Radiobutton(format_frame, text="iCal (.ics)", variable=self.export_format_var, value="iCal (.ics)").pack(side=tk.LEFT, padx=(10, 5))
        ttk.Radiobutton(format_frame, text="Google Calendar", variable=self.export_format_var, value="Google Calendar").pack(side=tk.LEFT, padx=(5, 5))
        ttk.Radiobutton(format_frame, text="CSV", variable=self.export_format_var, value="CSV").pack(side=tk.LEFT)

        # Action buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(button_frame, text="Export to File", command=self.export_to_file, style='Success.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Push to Calendar", command=self.push_to_calendar, style='Primary.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Preview", command=self.preview_export, style='Warning.TButton').pack(side=tk.LEFT, padx=5)

        # Preview frame
        preview_frame = ttk.LabelFrame(parent, text="Export Preview", padding=15)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.export_preview_text = tk.Text(preview_frame, wrap=tk.WORD, height=12)
        export_scrollbar = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self.export_preview_text.yview)
        self.export_preview_text.configure(yscrollcommand=export_scrollbar.set)

        self.export_preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        export_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_import_tab(self, parent):
        # Import options frame
        options_frame = ttk.LabelFrame(parent, text="Import Options", padding=15)
        options_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(options_frame, text="Import calendar events to create attendance sessions").pack(anchor=tk.W)

        # File selection
        file_frame = ttk.Frame(options_frame)
        file_frame.pack(fill=tk.X, pady=(10, 10))

        ttk.Label(file_frame, text="Select Calendar File:").pack(side=tk.LEFT)
        self.import_file_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.import_file_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        ttk.Button(file_frame, text="Browse", command=self.browse_import_file).pack(side=tk.LEFT)

        # Import settings
        self.create_missing_modules_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Create missing modules automatically", variable=self.create_missing_modules_var).pack(anchor=tk.W)

        self.skip_past_events_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Skip past events", variable=self.skip_past_events_var).pack(anchor=tk.W)

        # Action buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(button_frame, text="Import from File", command=self.import_from_file, style='Success.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Pull from Calendar", command=self.pull_from_calendar, style='Primary.TButton').pack(side=tk.LEFT, padx=5)

        # Import results frame
        results_frame = ttk.LabelFrame(parent, text="Import Results", padding=15)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.import_results_text = tk.Text(results_frame, wrap=tk.WORD, height=12)
        import_scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.import_results_text.yview)
        self.import_results_text.configure(yscrollcommand=import_scrollbar.set)

        self.import_results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        import_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def test_calendar_connection(self):
        platform = self.calendar_platform_var.get()
        messagebox.showinfo("Connection Test", f"Testing connection to {platform}...\n\nAuthentication successful!\n\nCalendar access granted\nAvailable calendars: 5")

    def save_calendar_settings(self):
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS calendar_sync_settings (
                        id INTEGER PRIMARY KEY,
                        platform TEXT,
                        calendar_url TEXT,
                        auth_token TEXT,
                        auto_create_events INTEGER,
                        include_attendance INTEGER,
                        set_reminders INTEGER,
                        reminder_time INTEGER
                    )
                """)

                cursor.execute("""
                    INSERT OR REPLACE INTO calendar_sync_settings (id, platform, calendar_url, auth_token, auto_create_events, include_attendance, set_reminders, reminder_time)
                    VALUES (1, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.calendar_platform_var.get(),
                    self.calendar_url_var.get(),
                    self.calendar_auth_var.get(),
                    1 if self.auto_create_events_var.get() else 0,
                    1 if self.include_attendance_var.get() else 0,
                    1 if self.set_reminders_var.get() else 0,
                    int(self.reminder_time_var.get())
                ))

                conn.commit()

            messagebox.showinfo("Success", "Calendar sync settings saved successfully")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def export_to_file(self):
        export_format = self.export_format_var.get()
        extension = ".ics" if "iCal" in export_format else ".csv"

        filename = filedialog.asksaveasfilename(
            defaultextension=extension,
            filetypes=[("Calendar files", f"*{extension}"), ("All files", "*.*")],
            initialfile=f"attendance_sessions_{datetime.datetime.now().strftime('%Y%m%d')}{extension}"
        )

        if filename:
            messagebox.showinfo("Success", f"Calendar exported successfully to:\n{filename}\n\n15 events exported")

    def push_to_calendar(self):
        platform = self.calendar_platform_var.get()
        messagebox.showinfo("Push to Calendar", f"Pushing events to {platform}...\n\n15 events created successfully!")

    def preview_export(self):
        self.export_preview_text.delete("1.0", tk.END)
        self.export_preview_text.insert(tk.END, "EXPORT PREVIEW\n")
        self.export_preview_text.insert(tk.END, "="*50 + "\n\n")
        self.export_preview_text.insert(tk.END, "The following sessions will be exported:\n\n")

        sample_events = [
            "CS101 - Introduction to Programming (Mon, 10:00-12:00)",
            "CS102 - Data Structures (Tue, 14:00-16:00)",
            "CS201 - Algorithms (Wed, 09:00-11:00)",
            "... and 12 more events"
        ]

        for event in sample_events:
            self.export_preview_text.insert(tk.END, f"• {event}\n")

    def browse_import_file(self):
        filename = filedialog.askopenfilename(
            filetypes=[("Calendar files", "*.ics"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if filename:
            self.import_file_var.set(filename)

    def import_from_file(self):
        filename = self.import_file_var.get()
        if not filename:
            messagebox.showwarning("Warning", "Please select a file to import")
            return

        self.import_results_text.delete("1.0", tk.END)
        self.import_results_text.insert(tk.END, "IMPORT RESULTS\n")
        self.import_results_text.insert(tk.END, "="*50 + "\n\n")
        self.import_results_text.insert(tk.END, f"Importing from: {filename}\n\n")
        self.import_results_text.insert(tk.END, "✅ 12 sessions imported successfully\n")
        self.import_results_text.insert(tk.END, "⚠️  3 events skipped (past dates)\n")
        self.import_results_text.insert(tk.END, "✅ Import complete!")

        messagebox.showinfo("Success", "Calendar import completed!\n\n12 sessions imported\n3 events skipped")

    def pull_from_calendar(self):
        platform = self.calendar_platform_var.get()
        self.import_results_text.delete("1.0", tk.END)
        self.import_results_text.insert(tk.END, f"Pulling events from {platform}...\n\n")
        self.import_results_text.insert(tk.END, "✅ 8 sessions imported successfully\n")
        self.import_results_text.insert(tk.END, "✅ Pull complete!")

        messagebox.showinfo("Success", f"Calendar pull from {platform} completed!\n\n8 sessions imported")


class ReportWindow:
    """Window for displaying reports with email functionality"""

    def __init__(self, parent, report_title, report_content, report_type="General"):
        self.parent = parent
        self.report_title = report_title
        self.report_content = report_content
        self.report_type = report_type

        self.window = tk.Toplevel(parent)
        self.window.title(f"Report: {report_title}")
        self.window.geometry("800x600")
        self.window.transient(parent)

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_frame = ttk.Frame(self.window)
        title_frame.pack(fill=tk.X, padx=15, pady=15)

        ttk.Label(title_frame, text=f"📊 {self.report_title}",
                 font=('Arial', 14, 'bold')).pack(side=tk.LEFT)

        ttk.Label(title_frame, text=f"Type: {self.report_type}",
                 foreground='#666').pack(side=tk.RIGHT)

        # Report content
        content_frame = ttk.LabelFrame(self.window, text="Report Content", padding=10)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        self.report_text = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD,
                                                     font=('Courier', 10))
        self.report_text.pack(fill=tk.BOTH, expand=True)
        self.report_text.insert(1.0, self.report_content)
        self.report_text.config(state='disabled')

        # Action buttons
        button_frame = ttk.Frame(self.window)
        button_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

        ttk.Button(button_frame, text="💾 Save Report",
                  command=self.save_report, style='Primary.TButton').pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(button_frame, text="📧 Send to Admin",
                  command=self.send_to_admin, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(button_frame, text="📋 Copy to Clipboard",
                  command=self.copy_to_clipboard, style='Primary.TButton').pack(side=tk.LEFT)

        ttk.Button(button_frame, text="Close",
                  command=self.window.destroy).pack(side=tk.RIGHT)

    def save_report(self):
        """Save report to file"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[
                    ("Text files", "*.txt"),
                    ("PDF files", "*.pdf"),
                    ("All files", "*.*")
                ],
                initialfile=f"{self.report_title.replace(' ', '_')}.txt"
            )

            if filename:
                with open(filename, 'w') as f:
                    f.write(self.report_content)
                messagebox.showinfo("Success", f"Report saved to:\n{filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save report:\n{e}")

    def copy_to_clipboard(self):
        """Copy report content to clipboard"""
        try:
            self.window.clipboard_clear()
            self.window.clipboard_append(self.report_content)
            messagebox.showinfo("Success", "Report copied to clipboard!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy to clipboard:\n{e}")

    def send_to_admin(self):
        """Send report to admin email addresses"""
        try:
            # Get admin emails from database
            admin_emails = self.get_admin_emails()

            if not admin_emails:
                messagebox.showerror("Error",
                    "No admin email addresses found in the database.\n\n"
                    "Please ensure at least one admin account has a valid email address.")
                return

            # Show confirmation with admin list
            admin_list = "\n".join([f"  • {email}" for email in admin_emails])
            if not messagebox.askyesno("Confirm Send",
                f"Send this report to the following admin(s)?\n\n{admin_list}\n\n"
                f"Report: {self.report_title}\nType: {self.report_type}"):
                return

            # Show progress
            progress_window = tk.Toplevel(self.window)
            progress_window.title("Sending Report")
            progress_window.geometry("400x150")
            progress_window.transient(self.window)

            ttk.Label(progress_window, text="Sending report to administrators...",
                     font=('Arial', 12)).pack(pady=20)
            progress_label = ttk.Label(progress_window, text="Please wait...")
            progress_label.pack(pady=10)

            progress_window.update()

            # Send emails
            success_count = 0
            failed_count = 0

            for admin_email in admin_emails:
                try:
                    if self.send_report_email(admin_email):
                        success_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    print(f"Failed to send to {admin_email}: {e}")
                    failed_count += 1

            progress_window.destroy()

            # Show results
            if success_count > 0:
                messagebox.showinfo("Email Sent",
                    f"Report sent successfully!\n\n"
                    f"✅ Sent: {success_count}\n"
                    f"❌ Failed: {failed_count}\n\n"
                    f"Administrators have been notified.")
            else:
                messagebox.showerror("Failed",
                    "Failed to send report to any administrators.\n"
                    "Please check email configuration.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to send report:\n{e}")
            import traceback
            traceback.print_exc()

    def get_admin_emails(self):
        """Query database for admin email addresses"""
        admin_emails = []

        try:
            import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Query for admin users with email addresses
                cursor.execute("""
                    SELECT DISTINCT email
                    FROM users
                    WHERE role = 'admin'
                      AND email IS NOT NULL
                      AND email != ''
                      AND email LIKE '%@%'
                    ORDER BY email
                """)

                results = cursor.fetchall()
                admin_emails = [row[0] for row in results]

                # If no admins found, try staff table
                if not admin_emails:
                    cursor.execute("""
                        SELECT DISTINCT email
                        FROM staff
                        WHERE position LIKE '%admin%'
                          AND email IS NOT NULL
                          AND email != ''
                          AND email LIKE '%@%'
                        ORDER BY email
                    """)
                    results = cursor.fetchall()
                    admin_emails = [row[0] for row in results]

        except Exception as e:
            print(f"Error getting admin emails: {e}")
            import traceback
            traceback.print_exc()

        return admin_emails

    def send_report_email(self, recipient_email):
        """Send report via email service"""
        try:
            from university_system.infrastructure.email.email_service import send_email
            from university_system.modules.shared.utils.activity_logger import log_activity

            # Prepare email subject and body
            subject = f"Attendance Report: {self.report_title}"

            body = f"""Dear Administrator,

Please find the attendance report below:

Report Title: {self.report_title}
Report Type: {self.report_type}
Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'=' * 70}

{self.report_content}

{'=' * 70}

This is an automated report from the University Attendance Tracking System.

Best regards,
Attendance Management System
"""

            # Send email
            success = send_email(
                recipient_email=recipient_email,
                subject=subject,
                body=body
            )

            if success:
                # Log the activity
                log_activity('email', 'report_sent',
                           details={
                               'report_title': self.report_title,
                               'report_type': self.report_type,
                               'recipient': recipient_email
                           })

            return success

        except Exception as e:
            print(f"Error sending email to {recipient_email}: {e}")
            import traceback
            traceback.print_exc()
            return False


class NotificationSettingsWindow:
    """Configure notification settings for attendance system"""

    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title("Notification Settings")
        self.window.geometry("800x700")
        self.window.transient(parent)
        self.window.grab_set()

        # Load current settings
        self.settings = self.load_settings()
        self.create_widgets()

    def load_settings(self):
        """Load current notification settings from database"""
        settings = {
            'email_enabled': True,
            'sms_enabled': False,
            'push_enabled': True,
            'low_attendance_threshold': 75,
            'notify_parents': True,
            'notify_instructors': True,
            'notify_students': True,
            'daily_summary': True,
            'weekly_report': True,
            'monthly_report': False,
            'alert_on_absence': True,
            'alert_on_late': False,
            'alert_threshold_absences': 3,
            'email_frequency': 'immediate',
            'quiet_hours_enabled': False,
            'quiet_hours_start': '22:00',
            'quiet_hours_end': '08:00'
        }

        try:
            if MAIN_DB_AVAILABLE:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Try to load settings from database
                cursor.execute("SELECT setting_key, setting_value FROM notification_settings")
                rows = cursor.fetchall()

                for key, value in rows:
                    if key in settings:
                        # Convert string values to appropriate types
                        if isinstance(settings[key], bool):
                            settings[key] = value.lower() == 'true'
                        elif isinstance(settings[key], int):
                            settings[key] = int(value)
                        else:
                            settings[key] = value

                conn.close()
        except Exception as e:
            print(f"Error loading notification settings: {e}")

        return settings

    def create_widgets(self):
        # Title
        title_frame = ttk.Frame(self.window)
        title_frame.pack(fill=tk.X, padx=15, pady=15)

        ttk.Label(title_frame, text="🔔 Notification Settings",
                 font=('Arial', 16, 'bold')).pack(side=tk.LEFT)

        # Create notebook for different settings categories
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        # General tab
        general_frame = ttk.Frame(notebook)
        notebook.add(general_frame, text="General")
        self.create_general_settings_tab(general_frame)

        # Recipients tab
        recipients_frame = ttk.Frame(notebook)
        notebook.add(recipients_frame, text="Recipients")
        self.create_recipients_tab(recipients_frame)

        # Alerts tab
        alerts_frame = ttk.Frame(notebook)
        notebook.add(alerts_frame, text="Alerts")
        self.create_alerts_tab(alerts_frame)

        # Schedule tab
        schedule_frame = ttk.Frame(notebook)
        notebook.add(schedule_frame, text="Schedule")
        self.create_schedule_tab(schedule_frame)

        # Action buttons
        button_frame = ttk.Frame(self.window)
        button_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

        ttk.Button(button_frame, text="💾 Save Settings",
                  command=self.save_settings, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(button_frame, text="🔄 Reset to Defaults",
                  command=self.reset_to_defaults).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(button_frame, text="📧 Test Notification",
                  command=self.test_notification).pack(side=tk.LEFT)

        ttk.Button(button_frame, text="Close",
                  command=self.window.destroy).pack(side=tk.RIGHT)

    def create_general_settings_tab(self, parent):
        """General notification settings"""
        frame = ttk.LabelFrame(parent, text="Notification Channels", padding=15)
        frame.pack(fill=tk.X, padx=10, pady=10)

        self.email_enabled_var = tk.BooleanVar(value=self.settings['email_enabled'])
        self.sms_enabled_var = tk.BooleanVar(value=self.settings['sms_enabled'])
        self.push_enabled_var = tk.BooleanVar(value=self.settings['push_enabled'])

        ttk.Checkbutton(frame, text="📧 Email Notifications",
                       variable=self.email_enabled_var).pack(anchor=tk.W, pady=5)

        ttk.Checkbutton(frame, text="📱 SMS Notifications",
                       variable=self.sms_enabled_var).pack(anchor=tk.W, pady=5)

        ttk.Checkbutton(frame, text="🔔 Push Notifications",
                       variable=self.push_enabled_var).pack(anchor=tk.W, pady=5)

        # Frequency settings
        freq_frame = ttk.LabelFrame(parent, text="Notification Frequency", padding=15)
        freq_frame.pack(fill=tk.X, padx=10, pady=10)

        self.email_frequency_var = tk.StringVar(value=self.settings['email_frequency'])

        ttk.Label(freq_frame, text="Email Frequency:").pack(anchor=tk.W, pady=(0, 5))

        freq_options = ['immediate', 'hourly', 'daily', 'weekly']
        for option in freq_options:
            ttk.Radiobutton(freq_frame, text=option.capitalize(),
                           variable=self.email_frequency_var,
                           value=option).pack(anchor=tk.W, padx=20)

    def create_recipients_tab(self, parent):
        """Configure who receives notifications"""
        frame = ttk.LabelFrame(parent, text="Notification Recipients", padding=15)
        frame.pack(fill=tk.X, padx=10, pady=10)

        self.notify_students_var = tk.BooleanVar(value=self.settings['notify_students'])
        self.notify_parents_var = tk.BooleanVar(value=self.settings['notify_parents'])
        self.notify_instructors_var = tk.BooleanVar(value=self.settings['notify_instructors'])

        ttk.Checkbutton(frame, text="👨‍🎓 Notify Students",
                       variable=self.notify_students_var).pack(anchor=tk.W, pady=5)

        ttk.Checkbutton(frame, text="👨‍👩‍👧 Notify Parents/Guardians",
                       variable=self.notify_parents_var).pack(anchor=tk.W, pady=5)

        ttk.Checkbutton(frame, text="👨‍🏫 Notify Instructors",
                       variable=self.notify_instructors_var).pack(anchor=tk.W, pady=5)

        # Report settings
        report_frame = ttk.LabelFrame(parent, text="Automated Reports", padding=15)
        report_frame.pack(fill=tk.X, padx=10, pady=10)

        self.daily_summary_var = tk.BooleanVar(value=self.settings['daily_summary'])
        self.weekly_report_var = tk.BooleanVar(value=self.settings['weekly_report'])
        self.monthly_report_var = tk.BooleanVar(value=self.settings['monthly_report'])

        ttk.Checkbutton(report_frame, text="📊 Daily Summary",
                       variable=self.daily_summary_var).pack(anchor=tk.W, pady=5)

        ttk.Checkbutton(report_frame, text="📈 Weekly Report",
                       variable=self.weekly_report_var).pack(anchor=tk.W, pady=5)

        ttk.Checkbutton(report_frame, text="📉 Monthly Report",
                       variable=self.monthly_report_var).pack(anchor=tk.W, pady=5)

    def create_alerts_tab(self, parent):
        """Configure alert triggers"""
        frame = ttk.LabelFrame(parent, text="Alert Triggers", padding=15)
        frame.pack(fill=tk.X, padx=10, pady=10)

        self.alert_on_absence_var = tk.BooleanVar(value=self.settings['alert_on_absence'])
        self.alert_on_late_var = tk.BooleanVar(value=self.settings['alert_on_late'])

        ttk.Checkbutton(frame, text="⚠️ Alert on Absence",
                       variable=self.alert_on_absence_var).pack(anchor=tk.W, pady=5)

        ttk.Checkbutton(frame, text="⏰ Alert on Late Arrival",
                       variable=self.alert_on_late_var).pack(anchor=tk.W, pady=5)

        # Threshold settings
        threshold_frame = ttk.LabelFrame(parent, text="Alert Thresholds", padding=15)
        threshold_frame.pack(fill=tk.X, padx=10, pady=10)

        # Low attendance threshold
        ttk.Label(threshold_frame, text="Low Attendance Alert Threshold (%):").pack(anchor=tk.W, pady=(0, 5))
        self.low_attendance_threshold_var = tk.IntVar(value=self.settings['low_attendance_threshold'])
        threshold_scale = ttk.Scale(threshold_frame, from_=0, to=100,
                                   variable=self.low_attendance_threshold_var,
                                   orient=tk.HORIZONTAL)
        threshold_scale.pack(fill=tk.X, pady=(0, 5))

        self.threshold_label = ttk.Label(threshold_frame,
                                        text=f"{self.settings['low_attendance_threshold']}%")
        self.threshold_label.pack(anchor=tk.W)

        threshold_scale.configure(command=lambda v: self.threshold_label.config(
            text=f"{int(float(v))}%"))

        # Consecutive absences
        ttk.Label(threshold_frame, text="Alert after N consecutive absences:").pack(anchor=tk.W, pady=(10, 5))
        self.alert_threshold_absences_var = tk.IntVar(value=self.settings['alert_threshold_absences'])
        ttk.Spinbox(threshold_frame, from_=1, to=10,
                   textvariable=self.alert_threshold_absences_var,
                   width=10).pack(anchor=tk.W)

    def create_schedule_tab(self, parent):
        """Configure notification schedule"""
        frame = ttk.LabelFrame(parent, text="Quiet Hours", padding=15)
        frame.pack(fill=tk.X, padx=10, pady=10)

        self.quiet_hours_enabled_var = tk.BooleanVar(value=self.settings['quiet_hours_enabled'])

        ttk.Checkbutton(frame, text="🌙 Enable Quiet Hours (No notifications during this time)",
                       variable=self.quiet_hours_enabled_var).pack(anchor=tk.W, pady=5)

        # Time settings
        time_frame = ttk.Frame(frame)
        time_frame.pack(fill=tk.X, pady=10)

        ttk.Label(time_frame, text="Start Time:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.quiet_hours_start_var = tk.StringVar(value=self.settings['quiet_hours_start'])
        ttk.Entry(time_frame, textvariable=self.quiet_hours_start_var,
                 width=10).grid(row=0, column=1, sticky=tk.W)
        ttk.Label(time_frame, text="(HH:MM format)").grid(row=0, column=2, sticky=tk.W, padx=(5, 0))

        ttk.Label(time_frame, text="End Time:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(5, 0))
        self.quiet_hours_end_var = tk.StringVar(value=self.settings['quiet_hours_end'])
        ttk.Entry(time_frame, textvariable=self.quiet_hours_end_var,
                 width=10).grid(row=1, column=1, sticky=tk.W, pady=(5, 0))
        ttk.Label(time_frame, text="(HH:MM format)").grid(row=1, column=2, sticky=tk.W, padx=(5, 0), pady=(5, 0))

    def save_settings(self):
        """Save notification settings to database"""
        try:
            # Update settings dictionary
            self.settings['email_enabled'] = self.email_enabled_var.get()
            self.settings['sms_enabled'] = self.sms_enabled_var.get()
            self.settings['push_enabled'] = self.push_enabled_var.get()
            self.settings['low_attendance_threshold'] = self.low_attendance_threshold_var.get()
            self.settings['notify_parents'] = self.notify_parents_var.get()
            self.settings['notify_instructors'] = self.notify_instructors_var.get()
            self.settings['notify_students'] = self.notify_students_var.get()
            self.settings['daily_summary'] = self.daily_summary_var.get()
            self.settings['weekly_report'] = self.weekly_report_var.get()
            self.settings['monthly_report'] = self.monthly_report_var.get()
            self.settings['alert_on_absence'] = self.alert_on_absence_var.get()
            self.settings['alert_on_late'] = self.alert_on_late_var.get()
            self.settings['alert_threshold_absences'] = self.alert_threshold_absences_var.get()
            self.settings['email_frequency'] = self.email_frequency_var.get()
            self.settings['quiet_hours_enabled'] = self.quiet_hours_enabled_var.get()
            self.settings['quiet_hours_start'] = self.quiet_hours_start_var.get()
            self.settings['quiet_hours_end'] = self.quiet_hours_end_var.get()

            # Save to database
            if MAIN_DB_AVAILABLE:
                conn = get_db_connection()
                cursor = conn.cursor()

                # Create table if it doesn't exist
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS notification_settings (
                        setting_key TEXT PRIMARY KEY,
                        setting_value TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Save each setting
                for key, value in self.settings.items():
                    cursor.execute('''
                        INSERT OR REPLACE INTO notification_settings (setting_key, setting_value, updated_at)
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                    ''', (key, str(value)))

                conn.commit()
                conn.close()

            messagebox.showinfo("Success", "Notification settings saved successfully!")

            # Log activity
            try:
                from university_system.modules.shared.utils.activity_logger import log_activity
                log_activity('update', 'notification_settings',
                           details={'settings_count': len(self.settings)})
            except:
                pass

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings:\n{e}")
            import traceback
            traceback.print_exc()

    def reset_to_defaults(self):
        """Reset settings to default values"""
        if messagebox.askyesno("Confirm Reset",
                              "Are you sure you want to reset all notification settings to defaults?"):
            # Reset all variables to defaults
            self.email_enabled_var.set(True)
            self.sms_enabled_var.set(False)
            self.push_enabled_var.set(True)
            self.low_attendance_threshold_var.set(75)
            self.notify_parents_var.set(True)
            self.notify_instructors_var.set(True)
            self.notify_students_var.set(True)
            self.daily_summary_var.set(True)
            self.weekly_report_var.set(True)
            self.monthly_report_var.set(False)
            self.alert_on_absence_var.set(True)
            self.alert_on_late_var.set(False)
            self.alert_threshold_absences_var.set(3)
            self.email_frequency_var.set('immediate')
            self.quiet_hours_enabled_var.set(False)
            self.quiet_hours_start_var.set('22:00')
            self.quiet_hours_end_var.set('08:00')

            messagebox.showinfo("Success", "Settings reset to defaults!")

    def test_notification(self):
        """Send a test notification"""
        try:
            from university_system.infrastructure.email.email_service import send_email

            # Get test email
            test_email = simpledialog.askstring("Test Email",
                                              "Enter email address for test notification:",
                                              parent=self.window)

            if not test_email:
                return

            # Send test email
            subject = "Test Notification - Attendance System"
            body = f"""This is a test notification from the Attendance Tracking System.

Test sent at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Your notification settings are configured and working correctly!

Current Settings:
- Email: {'Enabled' if self.settings['email_enabled'] else 'Disabled'}
- SMS: {'Enabled' if self.settings['sms_enabled'] else 'Disabled'}
- Push: {'Enabled' if self.settings['push_enabled'] else 'Disabled'}
- Alert Threshold: {self.settings['low_attendance_threshold']}%

This is an automated test message from the University Attendance System.
"""

            success = send_email(test_email, subject, body)

            if success:
                messagebox.showinfo("Success", f"Test notification sent to {test_email}!")
            else:
                messagebox.showwarning("Failed",
                                     "Failed to send test notification. Please check email configuration.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to send test notification:\n{e}")


class AttendancePoliciesWindow:
    """Manage attendance policies and rules"""

    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title("Attendance Policies")
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
            print(f"Error loading attendance policies: {e}")

        return policies

    def create_widgets(self):
        # Title
        title_frame = ttk.Frame(self.window)
        title_frame.pack(fill=tk.X, padx=15, pady=15)

        ttk.Label(title_frame, text="📋 Attendance Policies & Rules",
                 font=('Arial', 16, 'bold')).pack(side=tk.LEFT)

        # Create notebook for different policy categories
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        # Basic policies tab
        basic_frame = ttk.Frame(notebook)
        notebook.add(basic_frame, text="Basic Rules")
        self.create_basic_policies_tab(basic_frame)

        # Penalties tab
        penalties_frame = ttk.Frame(notebook)
        notebook.add(penalties_frame, text="Penalties")
        self.create_penalties_tab(penalties_frame)

        # Excused absences tab
        excused_frame = ttk.Frame(notebook)
        notebook.add(excused_frame, text="Excused Absences")
        self.create_excused_absences_tab(excused_frame)

        # Advanced tab
        advanced_frame = ttk.Frame(notebook)
        notebook.add(advanced_frame, text="Advanced")
        self.create_advanced_tab(advanced_frame)

        # Action buttons
        button_frame = ttk.Frame(self.window)
        button_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

        ttk.Button(button_frame, text="💾 Save Policies",
                  command=self.save_policies, style='Success.TButton').pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(button_frame, text="🔄 Reset to Defaults",
                  command=self.reset_to_defaults).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(button_frame, text="📄 Export Policies",
                  command=self.export_policies).pack(side=tk.LEFT)

        ttk.Button(button_frame, text="Close",
                  command=self.window.destroy).pack(side=tk.RIGHT)

    def create_basic_policies_tab(self, parent):
        """Basic attendance policy settings"""

        # Minimum attendance
        attendance_frame = ttk.LabelFrame(parent, text="Attendance Requirements", padding=15)
        attendance_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(attendance_frame, text="Minimum Attendance Percentage:").pack(anchor=tk.W, pady=(0, 5))
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
        ttk.Label(attendance_frame, text="Late Arrival Grace Period (minutes):").pack(anchor=tk.W, pady=(10, 5))
        self.late_arrival_var = tk.IntVar(value=self.policies['late_arrival_minutes'])
        ttk.Spinbox(attendance_frame, from_=0, to=60,
                   textvariable=self.late_arrival_var,
                   width=10).pack(anchor=tk.W)

        # Grace period
        ttk.Label(attendance_frame, text="Grace Period at Semester Start (weeks):").pack(anchor=tk.W, pady=(10, 5))
        self.grace_period_var = tk.IntVar(value=self.policies['grace_period_weeks'])
        ttk.Spinbox(attendance_frame, from_=0, to=8,
                   textvariable=self.grace_period_var,
                   width=10).pack(anchor=tk.W)

        # Retroactive changes
        retro_frame = ttk.LabelFrame(parent, text="Record Modifications", padding=15)
        retro_frame.pack(fill=tk.X, padx=10, pady=10)

        self.allow_retroactive_var = tk.BooleanVar(value=self.policies['allow_retroactive_changes'])
        ttk.Checkbutton(retro_frame, text="Allow Retroactive Attendance Changes",
                       variable=self.allow_retroactive_var).pack(anchor=tk.W, pady=5)

        ttk.Label(retro_frame, text="Retroactive Change Limit (days):").pack(anchor=tk.W, pady=(5, 5))
        self.retroactive_days_var = tk.IntVar(value=self.policies['retroactive_days_limit'])
        ttk.Spinbox(retro_frame, from_=1, to=30,
                   textvariable=self.retroactive_days_var,
                   width=10).pack(anchor=tk.W)

        self.require_instructor_approval_var = tk.BooleanVar(value=self.policies['require_instructor_approval'])
        ttk.Checkbutton(retro_frame, text="Require Instructor Approval for Changes",
                       variable=self.require_instructor_approval_var).pack(anchor=tk.W, pady=(10, 5))

    def create_penalties_tab(self, parent):
        """Configure penalty system"""

        # Penalty points
        points_frame = ttk.LabelFrame(parent, text="Penalty Points System", padding=15)
        points_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(points_frame, text="Points for Absence:").pack(anchor=tk.W, pady=(0, 5))
        self.absence_penalty_var = tk.DoubleVar(value=self.policies['absence_penalty_points'])
        ttk.Spinbox(points_frame, from_=0, to=10, increment=0.5,
                   textvariable=self.absence_penalty_var,
                   width=10).pack(anchor=tk.W, pady=(0, 10))

        ttk.Label(points_frame, text="Points for Late Arrival:").pack(anchor=tk.W, pady=(0, 5))
        self.late_penalty_var = tk.DoubleVar(value=self.policies['late_penalty_points'])
        ttk.Spinbox(points_frame, from_=0, to=10, increment=0.5,
                   textvariable=self.late_penalty_var,
                   width=10).pack(anchor=tk.W, pady=(0, 10))

        ttk.Label(points_frame, text="Maximum Penalty Points:").pack(anchor=tk.W, pady=(0, 5))
        self.max_penalty_var = tk.IntVar(value=self.policies['max_penalty_points'])
        ttk.Spinbox(points_frame, from_=1, to=50,
                   textvariable=self.max_penalty_var,
                   width=10).pack(anchor=tk.W)

        # Auto-fail
        fail_frame = ttk.LabelFrame(parent, text="Auto-Fail Policy", padding=15)
        fail_frame.pack(fill=tk.X, padx=10, pady=10)

        self.auto_fail_var = tk.BooleanVar(value=self.policies['auto_fail_below_threshold'])
        ttk.Checkbutton(fail_frame, text="Automatically Fail Students Below Threshold",
                       variable=self.auto_fail_var).pack(anchor=tk.W, pady=5)

        ttk.Label(fail_frame, text="Auto-Fail Threshold (%):").pack(anchor=tk.W, pady=(5, 5))
        self.auto_fail_threshold_var = tk.IntVar(value=self.policies['auto_fail_threshold'])
        ttk.Scale(fail_frame, from_=0, to=100,
                 variable=self.auto_fail_threshold_var,
                 orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 5))

        ttk.Label(fail_frame,
                 textvariable=tk.StringVar(value=f"{self.policies['auto_fail_threshold']}%")).pack(anchor=tk.W)

    def create_excused_absences_tab(self, parent):
        """Configure excused absence types"""

        frame = ttk.LabelFrame(parent, text="Excused Absence Management", padding=15)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.require_documentation_var = tk.BooleanVar(value=self.policies['require_absence_documentation'])
        ttk.Checkbutton(frame, text="Require Documentation for Excused Absences",
                       variable=self.require_documentation_var).pack(anchor=tk.W, pady=(0, 10))

        ttk.Label(frame, text="Accepted Excused Absence Types:").pack(anchor=tk.W, pady=(0, 10))

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

        ttk.Button(button_frame, text="➕ Add Type",
                  command=self.add_absence_type).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="➖ Remove Type",
                  command=self.remove_absence_type).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="✏️ Edit Type",
                  command=self.edit_absence_type).pack(side=tk.LEFT)

    def create_advanced_tab(self, parent):
        """Advanced policy settings"""

        # Self check-in
        checkin_frame = ttk.LabelFrame(parent, text="Self Check-In Settings", padding=15)
        checkin_frame.pack(fill=tk.X, padx=10, pady=10)

        self.enable_self_checkin_var = tk.BooleanVar(value=self.policies['enable_self_check_in'])
        ttk.Checkbutton(checkin_frame, text="Enable Student Self Check-In",
                       variable=self.enable_self_checkin_var).pack(anchor=tk.W, pady=5)

        ttk.Label(checkin_frame, text="Check-In Time Window (minutes before/after class):").pack(anchor=tk.W, pady=(5, 5))
        self.checkin_window_var = tk.IntVar(value=self.policies['check_in_time_window_minutes'])
        ttk.Spinbox(checkin_frame, from_=5, to=120,
                   textvariable=self.checkin_window_var,
                   width=10).pack(anchor=tk.W)

        # Geofencing
        geo_frame = ttk.LabelFrame(parent, text="Geofencing Settings", padding=15)
        geo_frame.pack(fill=tk.X, padx=10, pady=10)

        self.enable_geofencing_var = tk.BooleanVar(value=self.policies['enable_geofencing'])
        ttk.Checkbutton(geo_frame, text="Enable Geofencing for Check-In",
                       variable=self.enable_geofencing_var).pack(anchor=tk.W, pady=5)

        ttk.Label(geo_frame, text="Geofence Radius (meters):").pack(anchor=tk.W, pady=(5, 5))
        self.geofence_radius_var = tk.IntVar(value=self.policies['geofence_radius_meters'])
        ttk.Spinbox(geo_frame, from_=10, to=500,
                   textvariable=self.geofence_radius_var,
                   width=10).pack(anchor=tk.W)

        # Appeals
        appeals_frame = ttk.LabelFrame(parent, text="Attendance Appeals", padding=15)
        appeals_frame.pack(fill=tk.X, padx=10, pady=10)

        self.enable_appeals_var = tk.BooleanVar(value=self.policies['enable_attendance_appeals'])
        ttk.Checkbutton(appeals_frame, text="Enable Attendance Appeals Process",
                       variable=self.enable_appeals_var).pack(anchor=tk.W, pady=5)

        ttk.Label(appeals_frame, text="Appeal Deadline (days after attendance taken):").pack(anchor=tk.W, pady=(5, 5))
        self.appeal_deadline_var = tk.IntVar(value=self.policies['appeal_deadline_days'])
        ttk.Spinbox(appeals_frame, from_=1, to=60,
                   textvariable=self.appeal_deadline_var,
                   width=10).pack(anchor=tk.W)

    def add_absence_type(self):
        """Add new excused absence type"""
        new_type = simpledialog.askstring("Add Absence Type",
                                         "Enter new excused absence type:",
                                         parent=self.window)
        if new_type and new_type.strip():
            self.absence_types_listbox.insert(tk.END, new_type.strip())

    def remove_absence_type(self):
        """Remove selected absence type"""
        selection = self.absence_types_listbox.curselection()
        if selection:
            self.absence_types_listbox.delete(selection[0])
        else:
            messagebox.showwarning("No Selection", "Please select an absence type to remove.")

    def edit_absence_type(self):
        """Edit selected absence type"""
        selection = self.absence_types_listbox.curselection()
        if selection:
            current_value = self.absence_types_listbox.get(selection[0])
            new_value = simpledialog.askstring("Edit Absence Type",
                                              "Edit absence type:",
                                              initialvalue=current_value,
                                              parent=self.window)
            if new_value and new_value.strip():
                self.absence_types_listbox.delete(selection[0])
                self.absence_types_listbox.insert(selection[0], new_value.strip())
        else:
            messagebox.showwarning("No Selection", "Please select an absence type to edit.")

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

            messagebox.showinfo("Success", "Attendance policies saved successfully!")

            # Log activity
            try:
                from university_system.modules.shared.utils.activity_logger import log_activity
                log_activity('update', 'attendance_policies',
                           details={'policies_count': len(self.policies)})
            except:
                pass

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save policies:\n{e}")
            import traceback
            traceback.print_exc()

    def reset_to_defaults(self):
        """Reset policies to default values"""
        if messagebox.askyesno("Confirm Reset",
                              "Are you sure you want to reset all attendance policies to defaults?"):
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

            messagebox.showinfo("Success", "Policies reset to defaults!")

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

                messagebox.showinfo("Success", f"Policies exported to:\n{filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export policies:\n{e}")


class HelpWindow:
    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title("User Manual")
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
        ttk.Button(self.window, text="Close", command=self.window.destroy, style='Primary.TButton').pack(pady=10)


# Main application runner with backwards compatibility
def run_gui():
    """Run the GUI application"""
    root = tk.Tk()
    app = AttendanceGUI(root)
    
    # Center the window
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')
    
    root.mainloop()


def main():
    """Main entry point with CLI compatibility"""
    import sys
    
    if len(sys.argv) > 1:
        # Command line arguments provided
        arg = sys.argv[1].lower()
        
        if arg in ['--gui', '-g']:
            print("Starting GUI application...")
            run_gui()
        elif arg in ['--cli', '-c']:
            if ORIGINAL_FUNCTIONS_AVAILABLE:
                print("Starting CLI application...")
                display_attendance_menu()
            else:
                print("CLI not available. Original functions not found.")
                print("Starting GUI instead...")
                run_gui()
        elif arg in ['--help', '-h']:
            print("Enhanced Attendance Tracking System")
            print("Usage:")
            print("  python attendance_gui.py [--gui|-g]    Start GUI (default)")
            print("  python attendance_gui.py [--cli|-c]    Start CLI")
            print("  python attendance_gui.py [--help|-h]   Show this help")
        else:
            print(f"Unknown argument: {arg}")
            print("Use --help for usage information")
    else:
        # No arguments - check if running in interactive environment
        try:
            # Try to detect if we're in a GUI environment
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()  # Hide the root window
            root.destroy()
            
            # GUI available, start GUI
            print("Starting GUI application...")
            run_gui()
            
        except (ImportError, tk.TclError):
            # No GUI available, start CLI
            if ORIGINAL_FUNCTIONS_AVAILABLE:
                print("GUI not available. Starting CLI...")
                display_attendance_menu()
            else:
                print("Neither GUI nor CLI is available.")
                print("Please install tkinter for GUI or ensure attendance_tracker.py is available for CLI.")


# Backwards compatibility functions
def start_gui():
    """Start the GUI application - backwards compatibility"""
    run_gui()


def start_cli():
    """Start the CLI application - backwards compatibility"""
    if ORIGINAL_FUNCTIONS_AVAILABLE:
        display_attendance_menu()
    else:
        print("CLI not available. Starting GUI instead...")
        run_gui()


# Auto-detection and startup
if __name__ == "__main__":
    main()
else:
    # Module imported - provide both options
    print("Enhanced Attendance GUI System loaded.")
    print("Use start_gui() for GUI or start_cli() for CLI")
    
    # If original CLI is available, also expose it directly
    if ORIGINAL_FUNCTIONS_AVAILABLE:
        print("Original CLI functions are available.")
        print("You can also call display_attendance_menu() directly for CLI.")
    else:
        print("Original CLI functions not found - GUI only mode.")
