from university_system.infrastructure.database.db import DEFAULT_DB_PATH, get_connection, transaction  # injected
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
import sqlite3
# Import the original module scheduling functionality
# This ensures full backward compatibility
try:
    from university_system.modules.domain.academics.services.module_scheduling import (
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
        from university_system.modules.domain.academics.services.module_scheduling import (ModuleScheduler, DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES, display_enhanced_scheduling_menu)
    except Exception:
        class ModuleScheduler: pass

class ModuleSchedulingGUI:
    def set_auth(self, auth):
        """Optional; accept auth context from main app."""
        self._auth = auth
    def __init__(self, root):
        self.root = root
        self.root.title("Enhanced Module Scheduling System - GUI")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)
        
        # Initialize the backend scheduler
        self.scheduler = ModuleScheduler()

        # Run additional migrations for GUI compatibility
        self._migrate_database()

        # Configure styles
        self.setup_styles()
        
        # Create the main interface
        self.create_main_interface()
        
        # Status bar
        self.create_status_bar()
        
        # Load initial data
        self.refresh_all_data()
        
        # Bind close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_styles(self):
        """Configure ttk styles for better appearance"""
        style = ttk.Style()
        
        # Configure notebook styles
        style.configure('Main.TNotebook', tabposition='n')
        style.configure('Main.TNotebook.Tab', padding=[20, 8])
        
        # Configure treeview styles
        style.configure('Data.Treeview', rowheight=25)
        style.configure('Data.Treeview.Heading', font=('Arial', 10, 'bold'))
        
        # Configure button styles
        style.configure('Action.TButton', font=('Arial', 9, 'bold'))
        style.configure('Danger.TButton', foreground='red')
        style.configure('Success.TButton', foreground='green')
    
    def create_main_interface(self):
        """Create the main tabbed interface"""
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Top toolbar with Return to Home button
        toolbar_frame = ttk.Frame(main_frame)
        toolbar_frame.pack(fill=tk.X, pady=(0, 10))

        # Return to Main Menu button
        home_button = ttk.Button(toolbar_frame, text="🏠 Return to Main Menu",
                                command=self.return_to_main_menu, style='Action.TButton')
        home_button.pack(side=tk.LEFT, padx=5)

        # Activity Log button
        activity_button = ttk.Button(toolbar_frame, text="📋 Activity Log",
                                     command=self.open_activity_log_window, style='Action.TButton')
        activity_button.pack(side=tk.LEFT, padx=5)

        # Title label
        title_label = ttk.Label(toolbar_frame, text="Enhanced Module Scheduling System",
                               font=('Arial', 14, 'bold'))
        title_label.pack(side=tk.LEFT, padx=20)

        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame, style='Main.TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create all tabs
        self.create_dashboard_tab()
        self.create_schedules_tab()
        self.create_rooms_tab()
        self.create_instructors_tab()
        self.create_timetables_tab()
        self.create_analytics_tab()
        self.create_conflicts_tab()
        self.create_management_tab()
        self.create_settings_tab()
        self.create_modules_tab()

        # Menu bar
        self.create_menu_bar()
    
    def create_menu_bar(self):
        """Create the application menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Import CSV", command=self.import_csv)
        file_menu.add_command(label="Export All", command=self.export_all_data)
        file_menu.add_separator()
        file_menu.add_command(label="Backup", command=self.create_backup)
        file_menu.add_command(label="Restore", command=self.restore_backup)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)
        file_menu.add_separator()
        file_menu.add_command(label="Manage Modules", command=self.show_modules_tab)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Refresh All", command=self.refresh_all_data)
        view_menu.add_command(label="Grid View", command=self.show_grid_view)
        view_menu.add_separator()
        view_menu.add_command(label="CLI Mode", command=self.launch_cli_mode)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Interactive Scheduling Wizard", command=self.schedule_module_interactively)
        tools_menu.add_separator()
        tools_menu.add_command(label="Detect Conflicts", command=self.detect_all_conflicts)
        tools_menu.add_command(label="Data Validation", command=self.validate_data)
        tools_menu.add_command(label="Generate Reports", command=self.generate_reports)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="User Guide", command=self.show_help)
        help_menu.add_command(label="About", command=self.show_about)

    def show_modules_tab(self):
        """Switch to modules tab"""
        # Find the modules tab index and select it
        for i in range(self.notebook.index('end')):
            if 'Modules' in self.notebook.tab(i, 'text'):
                self.notebook.select(i)
                break
    
    def create_dashboard_tab(self):
        """Create the dashboard overview tab"""
        dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(dashboard_frame, text="📊 Dashboard")
        
        # Title
        title_label = ttk.Label(dashboard_frame, text="Module Scheduling System Dashboard", 
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)
        
        # Stats frame
        stats_frame = ttk.LabelFrame(dashboard_frame, text="System Overview", padding=15)
        stats_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Create stats grid
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.X)
        
        # Stats labels (will be updated by refresh_dashboard)
        self.stats_labels = {}
        stats = [
            ("Total Schedules", "schedules"),
            ("Active Rooms", "rooms"),
            ("Active Instructors", "instructors"),
            ("Conflicts", "conflicts")
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
        actions_frame = ttk.LabelFrame(dashboard_frame, text="Quick Actions", padding=15)
        actions_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Action buttons
        actions_grid = ttk.Frame(actions_frame)
        actions_grid.pack(fill=tk.X)
        
        action_buttons = [
            ("📅 Add Schedule", self.quick_add_schedule),
            ("🏢 Add Room", self.quick_add_room),
            ("👨‍🏫 Add Instructor", self.quick_add_instructor),
            ("📚 Add Module", self.quick_add_module),  # NEW
            ("📊 Generate Report", self.quick_generate_report),
            ("⚠️ Check Conflicts", self.detect_all_conflicts),
            ("💾 Backup System", self.create_backup)
        ]        
        for i, (text, command) in enumerate(action_buttons):
            row = i // 3
            col = i % 3
            
            btn = ttk.Button(actions_grid, text=text, command=command, style='Action.TButton')
            btn.grid(row=row, column=col, padx=10, pady=5, sticky="ew")
        
        for i in range(3):
            actions_grid.columnconfigure(i, weight=1)
        
        # Recent activity frame
        activity_frame = ttk.LabelFrame(dashboard_frame, text="Recent Activity", padding=15)
        activity_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Activity list
        self.activity_text = scrolledtext.ScrolledText(activity_frame, height=10, state=tk.DISABLED)
        self.activity_text.pack(fill=tk.BOTH, expand=True)

    def _analyze_peak_usage(self):
        """Analyze peak usage times"""
        with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
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

    def _analyze_module_distribution(self):
        """Analyze module scheduling distribution"""
        with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
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

    def get_system_setting(self, key, default=None):
        """Get a system setting value"""
        with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT value FROM system_settings WHERE key = ?', (key,))
            result = cursor.fetchone()

            return result[0] if result else default

    def quick_add_module(self):
        """Quick add module from dashboard"""
        self.notebook.select(2)  # Switch to modules tab (adjust index as needed)
        self.show_add_module_dialog()
    
    def create_schedules_tab(self):
        """Create the schedules management tab"""
        schedules_frame = ttk.Frame(self.notebook)
        self.notebook.add(schedules_frame, text="📅 Schedules")
        
        # Controls frame
        controls_frame = ttk.Frame(schedules_frame)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Add schedule button
        ttk.Button(controls_frame, text="➕ Add New Schedule", 
                  command=self.show_add_schedule_dialog).pack(side=tk.LEFT, padx=5)
        
        # Edit/Delete buttons
        ttk.Button(controls_frame, text="✏️ Edit Selected",
                  command=self.edit_selected_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="🗑️ Delete Selected",
                  command=self.delete_selected_schedule, style='Danger.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="🔄 Refresh",
                  command=self.refresh_schedules).pack(side=tk.LEFT, padx=5)
        
        # Search frame
        search_frame = ttk.Frame(controls_frame)
        search_frame.pack(side=tk.RIGHT, padx=5)
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.schedule_search_var = tk.StringVar()
        self.schedule_search_var.trace('w', self.filter_schedules)
        search_entry = ttk.Entry(search_frame, textvariable=self.schedule_search_var, width=20)
        search_entry.pack(side=tk.LEFT, padx=5)
        
        # Schedules treeview
        tree_frame = ttk.Frame(schedules_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        columns = ("ID", "Module", "Module Name", "Day", "Time", "Room", "Instructor", "Type")
        self.schedules_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", style='Data.Treeview')
        
        # Configure columns
        for col in columns:
            self.schedules_tree.heading(col, text=col)
            if col == "ID":
                self.schedules_tree.column(col, width=50)
            elif col == "Module Name":
                self.schedules_tree.column(col, width=200)
            else:
                self.schedules_tree.column(col, width=100)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.schedules_tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.schedules_tree.xview)
        self.schedules_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Pack treeview and scrollbars
        self.schedules_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Double-click to edit
        self.schedules_tree.bind("<Double-1>", lambda e: self.edit_selected_schedule())
    
    def create_rooms_tab(self):
        """Create the rooms management tab"""
        rooms_frame = ttk.Frame(self.notebook)
        self.notebook.add(rooms_frame, text="🏢 Rooms")
        
        # Controls frame
        controls_frame = ttk.Frame(rooms_frame)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(controls_frame, text="➕ Add New Room",
                  command=self.show_add_room_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="✏️ Edit Selected",
                  command=self.edit_selected_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="🗑️ Deactivate Selected",
                  command=self.deactivate_selected_room, style='Danger.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="♻️ Reactivate Selected",
                  command=self.reactivate_selected_room, style='Success.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="🔄 Refresh",
                  command=self.refresh_rooms).pack(side=tk.LEFT, padx=5)
        
        # Search
        search_frame = ttk.Frame(controls_frame)
        search_frame.pack(side=tk.RIGHT, padx=5)
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.room_search_var = tk.StringVar()
        self.room_search_var.trace('w', self.filter_rooms)
        ttk.Entry(search_frame, textvariable=self.room_search_var, width=20).pack(side=tk.LEFT, padx=5)
        
        # Rooms treeview
        tree_frame = ttk.Frame(rooms_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        columns = ("ID", "Building", "Room", "Capacity", "Type", "Equipment", "Status")
        self.rooms_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", style='Data.Treeview')
        
        for col in columns:
            self.rooms_tree.heading(col, text=col)
            if col == "ID":
                self.rooms_tree.column(col, width=50)
            elif col == "Equipment":
                self.rooms_tree.column(col, width=200)
            else:
                self.rooms_tree.column(col, width=100)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.rooms_tree.yview)
        self.rooms_tree.configure(yscrollcommand=v_scrollbar.set)
        
        self.rooms_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.rooms_tree.bind("<Double-1>", lambda e: self.edit_selected_room())
    
    def create_instructors_tab(self):
        """Create the instructors management tab"""
        instructors_frame = ttk.Frame(self.notebook)
        self.notebook.add(instructors_frame, text="👨‍🏫 Instructors")
        
        # Controls frame
        controls_frame = ttk.Frame(instructors_frame)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(controls_frame, text="➕ Add New Instructor",
                  command=self.show_add_instructor_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="✏️ Edit Selected",
                  command=self.edit_selected_instructor).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="📊 Workload Report",
                  command=self.show_workload_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="🔄 Refresh",
                  command=self.refresh_instructors).pack(side=tk.LEFT, padx=5)
        
        # Search
        search_frame = ttk.Frame(controls_frame)
        search_frame.pack(side=tk.RIGHT, padx=5)
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.instructor_search_var = tk.StringVar()
        self.instructor_search_var.trace('w', self.filter_instructors)
        ttk.Entry(search_frame, textvariable=self.instructor_search_var, width=20).pack(side=tk.LEFT, padx=5)
        
        # Instructors treeview
        tree_frame = ttk.Frame(instructors_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        columns = ("ID", "Name", "Email", "Department", "Max Hours", "Current Hours", "Status")
        self.instructors_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", style='Data.Treeview')
        
        for col in columns:
            self.instructors_tree.heading(col, text=col)
            if col == "ID":
                self.instructors_tree.column(col, width=50)
            elif col in ["Email", "Name"]:
                self.instructors_tree.column(col, width=150)
            else:
                self.instructors_tree.column(col, width=100)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.instructors_tree.yview)
        self.instructors_tree.configure(yscrollcommand=v_scrollbar.set)
        
        self.instructors_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.instructors_tree.bind("<Double-1>", lambda e: self.edit_selected_instructor())
    
    def create_timetables_tab(self):
        """Create the timetables generation tab"""
        timetables_frame = ttk.Frame(self.notebook)
        self.notebook.add(timetables_frame, text="📋 Timetables")
        
        # Left panel for controls
        left_panel = ttk.Frame(timetables_frame)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        
        # Student timetable section
        student_frame = ttk.LabelFrame(left_panel, text="Student Timetables", padding=10)
        student_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(student_frame, text="Student ID:").pack(anchor=tk.W)
        self.student_id_var = tk.StringVar()
        ttk.Entry(student_frame, textvariable=self.student_id_var, width=20).pack(fill=tk.X, pady=2)
        
        ttk.Button(student_frame, text="Generate Student Timetable", 
                  command=self.generate_student_timetable).pack(fill=tk.X, pady=2)
        ttk.Button(student_frame, text="Check Student Conflicts", 
                  command=self.check_student_conflicts).pack(fill=tk.X, pady=2)
        
        # Instructor timetable section
        instructor_frame = ttk.LabelFrame(left_panel, text="Instructor Timetables", padding=10)
        instructor_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(instructor_frame, text="Instructor ID:").pack(anchor=tk.W)
        self.instructor_id_var = tk.StringVar()
        ttk.Entry(instructor_frame, textvariable=self.instructor_id_var, width=20).pack(fill=tk.X, pady=2)
        
        ttk.Button(instructor_frame, text="Generate Instructor Timetable", 
                  command=self.generate_instructor_timetable).pack(fill=tk.X, pady=2)
        
        # Export options
        export_frame = ttk.LabelFrame(left_panel, text="Export Options", padding=10)
        export_frame.pack(fill=tk.X, pady=5)
        
        self.export_format_var = tk.StringVar(value="PDF")
        formats = ["PDF", "CSV", "Excel", "iCal"]
        
        for fmt in formats:
            ttk.Radiobutton(export_frame, text=fmt, variable=self.export_format_var, 
                           value=fmt).pack(anchor=tk.W)
        
        ttk.Button(export_frame, text="Export Last Generated", 
                  command=self.export_last_timetable).pack(fill=tk.X, pady=5)
        
        # Right panel for timetable display
        right_panel = ttk.Frame(timetables_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Timetable display area
        display_frame = ttk.LabelFrame(right_panel, text="Timetable Display", padding=10)
        display_frame.pack(fill=tk.BOTH, expand=True)

        # Create canvas with scrollbars for grid view
        canvas = tk.Canvas(display_frame)
        v_scrollbar = ttk.Scrollbar(display_frame, orient=tk.VERTICAL, command=canvas.yview)
        h_scrollbar = ttk.Scrollbar(display_frame, orient=tk.HORIZONTAL, command=canvas.xview)

        self.timetable_frame = ttk.Frame(canvas)
        self.timetable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.timetable_frame, anchor="nw")
        canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

    def log_activity(self, message):
        """Alias for update_activity_log for backward compatibility"""
        self.update_activity_log(message)
    
    def create_analytics_tab(self):
        """Create the analytics and reporting tab"""
        analytics_frame = ttk.Frame(self.notebook)
        self.notebook.add(analytics_frame, text="📊 Analytics")
        
        # Controls frame
        controls_frame = ttk.Frame(analytics_frame)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(controls_frame, text="🏢 Room Utilization", 
                  command=self.show_room_utilization).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="👨‍🏫 Instructor Workload", 
                  command=self.show_instructor_workload).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="📈 Peak Usage", 
                  command=self.show_peak_usage).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="📊 Generate Charts", 
                  command=self.generate_charts).pack(side=tk.LEFT, padx=5)
        
        # Analytics display area
        display_frame = ttk.LabelFrame(analytics_frame, text="Analytics Results", padding=10)
        display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.analytics_text = scrolledtext.ScrolledText(display_frame, font=('Courier', 10))
        self.analytics_text.pack(fill=tk.BOTH, expand=True)
    
    def create_conflicts_tab(self):
        """Create the conflicts management tab"""
        conflicts_frame = ttk.Frame(self.notebook)
        self.notebook.add(conflicts_frame, text="⚠️ Conflicts")
        
        # Controls frame
        controls_frame = ttk.Frame(conflicts_frame)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(controls_frame, text="🔍 Detect All Conflicts", 
                  command=self.detect_all_conflicts).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="✅ Resolve Selected", 
                  command=self.resolve_selected_conflict).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="🔄 Refresh", 
                  command=self.refresh_conflicts).pack(side=tk.LEFT, padx=5)
        
        # Conflicts treeview
        tree_frame = ttk.Frame(conflicts_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        columns = ("ID", "Type", "Description", "Status", "Detected Date")
        self.conflicts_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", style='Data.Treeview')
        
        for col in columns:
            self.conflicts_tree.heading(col, text=col)
            if col == "Description":
                self.conflicts_tree.column(col, width=400)
            else:
                self.conflicts_tree.column(col, width=120)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.conflicts_tree.yview)
        self.conflicts_tree.configure(yscrollcommand=v_scrollbar.set)
        
        self.conflicts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def create_management_tab(self):
        """Create the data management tab"""
        management_frame = ttk.Frame(self.notebook)
        self.notebook.add(management_frame, text="💾 Management")
        
        # Backup section
        backup_frame = ttk.LabelFrame(management_frame, text="Backup & Restore", padding=15)
        backup_frame.pack(fill=tk.X, padx=20, pady=10)
        
        backup_buttons = ttk.Frame(backup_frame)
        backup_buttons.pack(fill=tk.X)
        
        ttk.Button(backup_buttons, text="💾 Create Backup", 
                  command=self.create_backup).pack(side=tk.LEFT, padx=5)
        ttk.Button(backup_buttons, text="📂 List Backups", 
                  command=self.list_backups).pack(side=tk.LEFT, padx=5)
        ttk.Button(backup_buttons, text="🔄 Restore Backup", 
                  command=self.restore_backup).pack(side=tk.LEFT, padx=5)
        
        # Data validation section
        validation_frame = ttk.LabelFrame(management_frame, text="Data Validation", padding=15)
        validation_frame.pack(fill=tk.X, padx=20, pady=10)
        
        validation_buttons = ttk.Frame(validation_frame)
        validation_buttons.pack(fill=tk.X)
        
        ttk.Button(validation_buttons, text="🔍 Validate Data", 
                  command=self.validate_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(validation_buttons, text="🧹 Clean Orphaned Records", 
                  command=self.clean_orphaned_records).pack(side=tk.LEFT, padx=5)
        ttk.Button(validation_buttons, text="🔧 Repair Issues", 
                  command=self.repair_issues).pack(side=tk.LEFT, padx=5)
        
        # Import/Export section
        import_export_frame = ttk.LabelFrame(management_frame, text="Import & Export", padding=15)
        import_export_frame.pack(fill=tk.X, padx=20, pady=10)
        
        import_export_buttons = ttk.Frame(import_export_frame)
        import_export_buttons.pack(fill=tk.X)
        
        ttk.Button(import_export_buttons, text="📥 Import CSV", 
                  command=self.import_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(import_export_buttons, text="📤 Export All Data", 
                  command=self.export_all_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(import_export_buttons, text="📊 Generate Reports", 
                  command=self.generate_reports).pack(side=tk.LEFT, padx=5)
        
        # Templates section
        templates_frame = ttk.LabelFrame(management_frame, text="Schedule Templates", padding=15)
        templates_frame.pack(fill=tk.X, padx=20, pady=10)
        
        templates_buttons = ttk.Frame(templates_frame)
        templates_buttons.pack(fill=tk.X)
        
        ttk.Button(templates_buttons, text="💾 Save as Template", 
                  command=self.save_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(templates_buttons, text="📂 Load Template", 
                  command=self.load_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(templates_buttons, text="📋 List Templates", 
                  command=self.list_templates).pack(side=tk.LEFT, padx=5)
        
        # Activity log
        log_frame = ttk.LabelFrame(management_frame, text="Activity Log", padding=15)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)
    
    def create_settings_tab(self):
        """Create the settings tab"""
        settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(settings_frame, text="⚙️ Settings")
        
        # System settings
        system_frame = ttk.LabelFrame(settings_frame, text="System Settings", padding=15)
        system_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Institution name
        ttk.Label(system_frame, text="Institution Name:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.institution_var = tk.StringVar()
        ttk.Entry(system_frame, textvariable=self.institution_var, width=30).grid(row=0, column=1, padx=5, pady=5)
        
        # Semester dates
        ttk.Label(system_frame, text="Semester Start:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.semester_start_var = tk.StringVar()
        ttk.Entry(system_frame, textvariable=self.semester_start_var, width=30).grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(system_frame, text="Semester End:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.semester_end_var = tk.StringVar()
        ttk.Entry(system_frame, textvariable=self.semester_end_var, width=30).grid(row=2, column=1, padx=5, pady=5)
        
        # Default session duration
        ttk.Label(system_frame, text="Default Session Duration (min):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.session_duration_var = tk.StringVar()
        ttk.Entry(system_frame, textvariable=self.session_duration_var, width=30).grid(row=3, column=1, padx=5, pady=5)
        
        # Email notifications
        self.email_notifications_var = tk.BooleanVar()
        ttk.Checkbutton(system_frame, text="Enable Email Notifications", 
                       variable=self.email_notifications_var).grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        # Auto backup
        self.auto_backup_var = tk.BooleanVar()
        ttk.Checkbutton(system_frame, text="Enable Automatic Backups", 
                       variable=self.auto_backup_var).grid(row=5, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        # Save settings button
        ttk.Button(system_frame, text="💾 Save Settings", 
                  command=self.save_settings).grid(row=6, column=0, columnspan=2, pady=10)
        
        # Holidays management
        holidays_frame = ttk.LabelFrame(settings_frame, text="Holidays Management", padding=15)
        holidays_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Holiday controls
        holiday_controls = ttk.Frame(holidays_frame)
        holiday_controls.pack(fill=tk.X, pady=5)
        
        ttk.Button(holiday_controls, text="➕ Add Holiday", 
                  command=self.add_holiday).pack(side=tk.LEFT, padx=5)
        ttk.Button(holiday_controls, text="📅 View Calendar", 
                  command=self.view_calendar).pack(side=tk.LEFT, padx=5)
        
        # Holidays list
        holidays_tree_frame = ttk.Frame(holidays_frame)
        holidays_tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        columns = ("Name", "Start Date", "End Date", "Recurring", "Description")
        self.holidays_tree = ttk.Treeview(holidays_tree_frame, columns=columns, show="headings", height=8)
        
        for col in columns:
            self.holidays_tree.heading(col, text=col)
            if col == "Description":
                self.holidays_tree.column(col, width=200)
            else:
                self.holidays_tree.column(col, width=120)
        
        # Scrollbar for holidays
        holidays_scrollbar = ttk.Scrollbar(holidays_tree_frame, orient=tk.VERTICAL, command=self.holidays_tree.yview)
        self.holidays_tree.configure(yscrollcommand=holidays_scrollbar.set)
        
        self.holidays_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        holidays_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def create_status_bar(self):
        """Create the status bar at the bottom"""
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=2)
        
        # Status label
        self.status_label = ttk.Label(self.status_bar, text="Ready", relief=tk.SUNKEN)
        self.status_label.pack(side=tk.LEFT, padx=2)
        
        # Database status
        self.db_status_label = ttk.Label(self.status_bar, text="Database: Connected", relief=tk.SUNKEN)
        self.db_status_label.pack(side=tk.RIGHT, padx=2)
        
        # CLI button
        ttk.Button(self.status_bar, text="CLI Mode", command=self.launch_cli_mode).pack(side=tk.RIGHT, padx=2)
    
    # Data loading and refreshing methods
    def refresh_all_data(self):
        """Refresh all data in the interface"""
        try:
            self.update_status("Refreshing data...")
            self.refresh_dashboard()
            self.refresh_schedules()
            self.refresh_rooms()
            self.refresh_instructors()
            self.refresh_conflicts()
            self.refresh_holidays()
            self.load_settings()
            self.refresh_modules()
            self.update_status("Data refreshed successfully")
        except Exception as e:
            self.update_status(f"Error refreshing data: {str(e)}")
            messagebox.showerror("Error", f"Failed to refresh data: {str(e)}")
    
    def refresh_dashboard(self):
        """Update dashboard statistics"""
        try:
            from university_system.infrastructure.database.db import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
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
            messagebox.showerror("Error", f"Failed to refresh dashboard: {str(e)}")
    
    def refresh_schedules(self):
        """Refresh the schedules treeview"""
        try:
            # Clear existing items
            for item in self.schedules_tree.get_children():
                self.schedules_tree.delete(item)
            
            # Get schedule data from backend
            from university_system.infrastructure.database.db import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT ms.id, ms.module_code, m.module_name, ms.day_of_week,
                       ms.start_time, ms.end_time, r.building, r.room_number,
                       i.first_name, i.last_name, ms.session_type
                FROM module_schedule ms
                LEFT JOIN rooms r ON ms.room_id = r.id
                LEFT JOIN instructors i ON ms.instructor_id = i.id
                LEFT JOIN modules m ON ms.module_code = m.module_code
                ORDER BY ms.module_code, ms.day_of_week, ms.start_time
                ''')

                schedules = cursor.fetchall()
            
            # Populate treeview
            for schedule in schedules:
                schedule_id, module_code, module_name, day, start_time, end_time, building, room_number, first_name, last_name, session_type = schedule
                module_name = module_name or "Unknown"
                time_slot = f"{start_time}-{end_time}"
                room_str = f"{building}-{room_number}" if building and room_number else "TBA"
                instructor = f"{first_name} {last_name}" if first_name and last_name else "TBA"
                
                self.schedules_tree.insert("", tk.END, values=(
                    schedule_id, module_code, module_name, day, time_slot, room_str, instructor, session_type
                ))
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh schedules: {str(e)}")
    
    def refresh_rooms(self):
        """Refresh the rooms treeview"""
        try:
            # Clear existing items
            for item in self.rooms_tree.get_children():
                self.rooms_tree.delete(item)
            
            from university_system.infrastructure.database.db import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT id, room_number, building, capacity, room_type, equipment, is_active
                FROM rooms
                ORDER BY building, room_number
                ''')

                rooms = cursor.fetchall()
            
            for room in rooms:
                room_id, room_number, building, capacity, room_type, equipment, is_active = room
                status = "Active" if is_active else "Inactive"
                equipment = equipment or "N/A"
                
                self.rooms_tree.insert("", tk.END, values=(
                    room_id, building, room_number, capacity, room_type, equipment, status
                ))
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh rooms: {str(e)}")
    
    def refresh_instructors(self):
        """Refresh the instructors treeview"""
        try:
            # Clear existing items
            for item in self.instructors_tree.get_children():
                self.instructors_tree.delete(item)
            
            from university_system.infrastructure.database.db import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT i.id, i.first_name, i.last_name, i.email, i.department,
                       COALESCE(i.max_hours_per_week, i.max_courses_per_semester * 8, 40) as max_hours_per_week,
                       CASE WHEN i.status = 'Active' THEN 1 ELSE COALESCE(i.is_active, 1) END as is_active,
                       COALESCE(SUM(CASE
                           WHEN ms.end_time IS NOT NULL AND ms.start_time IS NOT NULL
                           THEN (CAST(SUBSTR(ms.end_time, 1, 2) AS INTEGER) * 60 + CAST(SUBSTR(ms.end_time, 4, 2) AS INTEGER)) -
                                (CAST(SUBSTR(ms.start_time, 1, 2) AS INTEGER) * 60 + CAST(SUBSTR(ms.start_time, 4, 2) AS INTEGER))
                           ELSE 0 END) / 60.0, 0) as current_hours
                FROM instructors i
                LEFT JOIN module_schedule ms ON i.id = ms.instructor_id
                GROUP BY i.id
                ORDER BY i.last_name, i.first_name
                ''')

                instructors = cursor.fetchall()
            
            for instructor in instructors:
                instructor_id, first_name, last_name, email, department, max_hours, is_active, current_hours = instructor
                full_name = f"{first_name} {last_name}"
                status = "Active" if is_active else "Inactive"
                current_hours = round(current_hours or 0, 1)
                
                self.instructors_tree.insert("", tk.END, values=(
                    instructor_id, full_name, email, department, max_hours, current_hours, status
                ))
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh instructors: {str(e)}")
    
    def refresh_conflicts(self):
        """Refresh the conflicts treeview"""
        try:
            # Clear existing items
            for item in self.conflicts_tree.get_children():
                self.conflicts_tree.delete(item)
            
            conflicts = self.scheduler._get_all_conflicts()
            
            for conflict in conflicts:
                status = "Resolved" if conflict['resolved'] else "Active"
                detected_date = conflict['detected_date'][:19] if conflict['detected_date'] else "Unknown"
                
                self.conflicts_tree.insert("", tk.END, values=(
                    conflict['id'], conflict['type'], conflict['description'], status, detected_date
                ))
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh conflicts: {str(e)}")
    
    def refresh_holidays(self):
        """Refresh the holidays treeview"""
        try:
            # Clear existing items
            for item in self.holidays_tree.get_children():
                self.holidays_tree.delete(item)
            
            from university_system.infrastructure.database.db import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT holiday_name, start_date, end_date, recurring, description
                FROM holidays
                ORDER BY start_date
                ''')

                holidays = cursor.fetchall()
            
            for holiday in holidays:
                name, start_date, end_date, recurring, description = holiday
                recurring_str = "Yes" if recurring else "No"
                description = description or ""
                
                self.holidays_tree.insert("", tk.END, values=(
                    name, start_date, end_date, recurring_str, description
                ))
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh holidays: {str(e)}")
    
    def load_settings(self):
        """Load system settings into the interface"""
        try:
            # Load settings from backend
            self.institution_var.set(self.scheduler.get_system_setting('institution_name', 'University'))
            self.semester_start_var.set(self.scheduler.get_system_setting('semester_start', ''))
            self.semester_end_var.set(self.scheduler.get_system_setting('semester_end', ''))
            self.session_duration_var.set(self.scheduler.get_system_setting('default_session_duration', '60'))
            
            email_notifications = self.scheduler.get_system_setting('email_notifications', 'False') == 'True'
            self.email_notifications_var.set(email_notifications)
            
            auto_backup = self.scheduler.get_system_setting('auto_backup', 'True') == 'True'
            self.auto_backup_var.set(auto_backup)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load settings: {str(e)}")
    
    # Dialog methods for adding/editing data
    def show_add_schedule_dialog(self):
        """Show dialog for adding a new schedule"""
        dialog = AddScheduleDialog(self.root, self.scheduler)
        if dialog.result:
            self.refresh_schedules()
            self.refresh_dashboard()
            self.update_activity_log("New schedule added")
    
    def show_add_room_dialog(self):
        """Show dialog for adding a new room"""
        dialog = AddRoomDialog(self.root, self.scheduler)
        if dialog.result:
            self.refresh_rooms()
            self.refresh_dashboard()
            self.update_activity_log("New room added")
    
    def show_add_instructor_dialog(self):
        """Show dialog for adding a new instructor"""
        dialog = AddInstructorDialog(self.root, self.scheduler)
        if dialog.result:
            self.refresh_instructors()
            self.refresh_dashboard()
            self.update_activity_log("New instructor added")
    
    # Quick action methods
    def quick_add_schedule(self):
        """Quick add schedule from dashboard"""
        self.notebook.select(1)  # Switch to schedules tab
        self.show_add_schedule_dialog()
    
    def quick_add_room(self):
        """Quick add room from dashboard"""
        self.notebook.select(2)  # Switch to rooms tab
        self.show_add_room_dialog()
    
    def quick_add_instructor(self):
        """Quick add instructor from dashboard"""
        self.notebook.select(3)  # Switch to instructors tab
        self.show_add_instructor_dialog()
    
    def quick_generate_report(self):
        """Quick generate report from dashboard"""
        self.notebook.select(5)  # Switch to analytics tab
        self.show_room_utilization()
    
    # Search/filter methods
    def filter_schedules(self, *args):
        """Filter schedules based on search term"""
        search_term = self.schedule_search_var.get().lower()
        
        # Clear current items
        for item in self.schedules_tree.get_children():
            self.schedules_tree.delete(item)
        
        if not search_term:
            self.refresh_schedules()
            return
        
        # Refresh with filter
        try:
            from university_system.infrastructure.database.db import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT ms.id, ms.module_code, m.module_name, ms.day_of_week,
                       ms.start_time, ms.end_time, r.building, r.room_number,
                       i.first_name, i.last_name, ms.session_type
                FROM module_schedule ms
                LEFT JOIN rooms r ON ms.room_id = r.id
                LEFT JOIN instructors i ON ms.instructor_id = i.id
                LEFT JOIN modules m ON ms.module_code = m.module_code
                WHERE LOWER(ms.module_code) LIKE ?
                   OR LOWER(m.module_name) LIKE ?
                   OR LOWER(ms.day_of_week) LIKE ?
                   OR LOWER(ms.session_type) LIKE ?
                   OR LOWER(i.first_name) LIKE ?
                   OR LOWER(i.last_name) LIKE ?
                ORDER BY ms.module_code, ms.day_of_week, ms.start_time
                ''', [f'%{search_term}%'] * 6)

                schedules = cursor.fetchall()
            
            for schedule in schedules:
                schedule_id, module_code, module_name, day, start_time, end_time, building, room_number, first_name, last_name, session_type = schedule
                module_name = module_name or "Unknown"
                time_slot = f"{start_time}-{end_time}"
                room_str = f"{building}-{room_number}" if building and room_number else "TBA"
                instructor = f"{first_name} {last_name}" if first_name and last_name else "TBA"
                
                self.schedules_tree.insert("", tk.END, values=(
                    schedule_id, module_code, module_name, day, time_slot, room_str, instructor, session_type
                ))
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to filter schedules: {str(e)}")
    
    def filter_rooms(self, *args):
        """Filter rooms based on search term"""
        search_term = self.room_search_var.get().lower()
        
        # Clear current items
        for item in self.rooms_tree.get_children():
            self.rooms_tree.delete(item)
        
        if not search_term:
            self.refresh_rooms()
            return
        
        try:
            from university_system.infrastructure.database.db import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT id, room_number, building, capacity, room_type, equipment, is_active
                FROM rooms
                WHERE LOWER(room_number) LIKE ?
                   OR LOWER(building) LIKE ?
                   OR LOWER(room_type) LIKE ?
                   OR LOWER(equipment) LIKE ?
                ORDER BY building, room_number
                ''', [f'%{search_term}%'] * 4)

                rooms = cursor.fetchall()
            
            for room in rooms:
                room_id, room_number, building, capacity, room_type, equipment, is_active = room
                status = "Active" if is_active else "Inactive"
                equipment = equipment or "N/A"
                
                self.rooms_tree.insert("", tk.END, values=(
                    room_id, building, room_number, capacity, room_type, equipment, status
                ))
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to filter rooms: {str(e)}")
    
    def filter_instructors(self, *args):
        """Filter instructors based on search term"""
        search_term = self.instructor_search_var.get().lower()
        
        # Clear current items
        for item in self.instructors_tree.get_children():
            self.instructors_tree.delete(item)
        
        if not search_term:
            self.refresh_instructors()
            return
        
        try:
            from university_system.infrastructure.database.db import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT i.id, i.first_name, i.last_name, i.email, i.department,
                       COALESCE(i.max_hours_per_week, i.max_courses_per_semester * 8, 40) as max_hours_per_week,
                       CASE WHEN i.status = 'Active' THEN 1 ELSE COALESCE(i.is_active, 1) END as is_active,
                       COALESCE(SUM(CASE
                           WHEN ms.end_time IS NOT NULL AND ms.start_time IS NOT NULL
                           THEN (CAST(SUBSTR(ms.end_time, 1, 2) AS INTEGER) * 60 + CAST(SUBSTR(ms.end_time, 4, 2) AS INTEGER)) -
                                (CAST(SUBSTR(ms.start_time, 1, 2) AS INTEGER) * 60 + CAST(SUBSTR(ms.start_time, 4, 2) AS INTEGER))
                           ELSE 0 END) / 60.0, 0) as current_hours
                FROM instructors i
                LEFT JOIN module_schedule ms ON i.id = ms.instructor_id
                WHERE LOWER(i.first_name) LIKE ?
                   OR LOWER(i.last_name) LIKE ?
                   OR LOWER(i.email) LIKE ?
                   OR LOWER(i.department) LIKE ?
                GROUP BY i.id
                ORDER BY i.last_name, i.first_name
                ''', [f'%{search_term}%'] * 4)

                instructors = cursor.fetchall()
            
            for instructor in instructors:
                instructor_id, first_name, last_name, email, department, max_hours, is_active, current_hours = instructor
                full_name = f"{first_name} {last_name}"
                status = "Active" if is_active else "Inactive"
                current_hours = round(current_hours or 0, 1)
                
                self.instructors_tree.insert("", tk.END, values=(
                    instructor_id, full_name, email, department, max_hours, current_hours, status
                ))
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to filter instructors: {str(e)}")
    
    # Edit/delete methods
    def edit_selected_schedule(self):
        """Edit the selected schedule"""
        selected = self.schedules_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a schedule to edit.")
            return
        
        schedule_data = self.schedules_tree.item(selected[0])['values']
        schedule_id = schedule_data[0]
        
        dialog = EditScheduleDialog(self.root, self.scheduler, schedule_id)
        if dialog.result:
            self.refresh_schedules()
            self.update_activity_log(f"Schedule {schedule_id} updated")
    
    def delete_selected_schedule(self):
        """Delete the selected schedule"""
        selected = self.schedules_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a schedule to delete.")
            return
        
        schedule_data = self.schedules_tree.item(selected[0])['values']
        schedule_id = schedule_data[0]
        module_code = schedule_data[1]
        
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the schedule for {module_code}?"):
            try:
                from university_system.infrastructure.database.db import sqlite3
                with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM module_schedule WHERE id = ?', (schedule_id,))
                    conn.commit()
                
                self.refresh_schedules()
                self.refresh_dashboard()
                self.update_activity_log(f"Schedule {schedule_id} deleted")
                messagebox.showinfo("Success", "Schedule deleted successfully.")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete schedule: {str(e)}")
    
    def edit_selected_room(self):
        """Edit the selected room"""
        selected = self.rooms_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a room to edit.")
            return
        
        room_data = self.rooms_tree.item(selected[0])['values']
        room_id = room_data[0]
        
        dialog = EditRoomDialog(self.root, self.scheduler, room_id)
        if dialog.result:
            self.refresh_rooms()
            self.update_activity_log(f"Room {room_id} updated")
    
    def deactivate_selected_room(self):
        """Deactivate the selected room with session checking and reassignment"""
        selected = self.rooms_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a room to deactivate.")
            return

        room_data = self.rooms_tree.item(selected[0])['values']
        room_id = room_data[0]
        room_name = f"{room_data[1]}-{room_data[2]}"

        try:
            from university_system.infrastructure.database.db import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Check if room has scheduled sessions
                cursor.execute('''
                    SELECT ms.id, ms.module_code, ms.day_of_week, ms.start_time, ms.end_time, ms.session_type
                    FROM module_schedule ms
                    WHERE ms.room_id = ?
                    ORDER BY ms.day_of_week, ms.start_time
                ''', (room_id,))

                affected_sessions = cursor.fetchall()

                if affected_sessions:
                    # Show message listing affected sessions
                    session_list = "\n".join([
                        f"- {s[1]} ({s[5]}) on {s[2]} at {s[3]}-{s[4]}"
                        for s in affected_sessions
                    ])

                    message = f"Room {room_name} has {len(affected_sessions)} scheduled session(s):\n\n{session_list}\n\n"
                    message += "Do you want to proceed? The system will attempt to reassign sessions to other available rooms."

                    if not messagebox.askyesno("Confirm Deactivate", message):
                        return

                    # Try to reassign sessions to available rooms
                    reassigned = []
                    failed_reassignments = []

                    for session in affected_sessions:
                        session_id, module_code, day, start_time, end_time, session_type = session

                        # Find an available room for this time slot
                        cursor.execute('''
                            SELECT r.id, r.building, r.room_number, r.capacity
                            FROM rooms r
                            WHERE r.is_active = 1
                            AND r.id != ?
                            AND r.id NOT IN (
                                SELECT room_id FROM module_schedule
                                WHERE day_of_week = ?
                                AND start_time = ?
                                AND room_id IS NOT NULL
                            )
                            ORDER BY r.capacity
                            LIMIT 1
                        ''', (room_id, day, start_time))

                        available_room = cursor.fetchone()

                        if available_room:
                            new_room_id, new_building, new_room_num, capacity = available_room
                            new_room_name = f"{new_building}-{new_room_num}"

                            # Update the session with new room
                            cursor.execute('''
                                UPDATE module_schedule
                                SET room_id = ?
                                WHERE id = ?
                            ''', (new_room_id, session_id))

                            reassigned.append({
                                'module': module_code,
                                'session_type': session_type,
                                'day': day,
                                'time': f"{start_time}-{end_time}",
                                'old_room': room_name,
                                'new_room': new_room_name
                            })

                            # Send email notifications
                            self._send_room_change_notifications(
                                module_code, day, start_time, end_time,
                                room_name, new_room_name
                            )
                        else:
                            failed_reassignments.append({
                                'module': module_code,
                                'day': day,
                                'time': f"{start_time}-{end_time}"
                            })

                    # Deactivate the room
                    cursor.execute('UPDATE rooms SET is_active = 0 WHERE id = ?', (room_id,))
                    conn.commit()

                    # Show result message
                    result_msg = f"Room {room_name} has been deactivated.\n\n"

                    if reassigned:
                        result_msg += f"Successfully reassigned {len(reassigned)} session(s):\n"
                        for r in reassigned[:5]:  # Show first 5
                            result_msg += f"- {r['module']} ({r['session_type']}) {r['day']} {r['time']}: {r['old_room']} → {r['new_room']}\n"
                        if len(reassigned) > 5:
                            result_msg += f"... and {len(reassigned) - 5} more\n"
                        result_msg += "\nEmail notifications sent to affected students and lecturers.\n"

                    if failed_reassignments:
                        result_msg += f"\n⚠️ Warning: {len(failed_reassignments)} session(s) could not be reassigned (no available rooms):\n"
                        for f in failed_reassignments:
                            result_msg += f"- {f['module']} {f['day']} {f['time']}\n"
                        result_msg += "\nThese sessions will need manual room assignment."

                    messagebox.showinfo("Room Deactivated", result_msg)
                else:
                    # No sessions, just deactivate
                    if messagebox.askyesno("Confirm Deactivate", f"Are you sure you want to deactivate room {room_name}?"):
                        cursor.execute('UPDATE rooms SET is_active = 0 WHERE id = ?', (room_id,))
                        conn.commit()
                        messagebox.showinfo("Success", f"Room {room_name} deactivated successfully.")

            self.refresh_rooms()
            self.refresh_dashboard()
            self.update_activity_log(f"Room {room_name} deactivated")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to deactivate room: {str(e)}")

    def reactivate_selected_room(self):
        """Reactivate the selected room"""
        selected = self.rooms_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a room to reactivate.")
            return

        room_data = self.rooms_tree.item(selected[0])['values']
        room_id = room_data[0]
        room_name = f"{room_data[1]}-{room_data[2]}"
        room_status = room_data[6]

        # Check if room is already active
        if room_status == "Active":
            messagebox.showinfo("Info", f"Room {room_name} is already active.")
            return

        if messagebox.askyesno("Confirm Reactivate", f"Are you sure you want to reactivate room {room_name}?"):
            try:
                from university_system.infrastructure.database.db import sqlite3
                with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                    cursor = conn.cursor()
                    cursor.execute('UPDATE rooms SET is_active = 1 WHERE id = ?', (room_id,))
                    conn.commit()

                self.refresh_rooms()
                self.refresh_dashboard()
                self.update_activity_log(f"Room {room_name} reactivated")
                messagebox.showinfo("Success", f"Room {room_name} reactivated successfully.")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to reactivate room: {str(e)}")

    def _send_room_change_notifications(self, module_code, day, start_time, end_time, old_room, new_room):
        """Send email notifications to students and lecturers about room change"""
        try:
            from university_system.infrastructure.database.db import sqlite3

            # Import email service
            try:
                from university_system.infrastructure.email.email_service import send_email
            except ImportError:
                # Email service not available, skip notification
                return

            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Get students enrolled in this module
                cursor.execute('''
                    SELECT DISTINCT s.email, s.first_name, s.last_name
                    FROM students s
                    INNER JOIN enrollments e ON s.id = e.student_id
                    INNER JOIN modules m ON e.module_id = m.id
                    WHERE m.module_code = ?
                    AND s.email IS NOT NULL
                ''', (module_code,))

                students = cursor.fetchall()

                # Get lecturers for this module
                cursor.execute('''
                    SELECT DISTINCT i.email, i.first_name, i.last_name
                    FROM instructors i
                    INNER JOIN module_schedule ms ON i.id = ms.instructor_id
                    WHERE ms.module_code = ?
                    AND i.email IS NOT NULL
                ''', (module_code,))

                lecturers = cursor.fetchall()

                # Send emails to students
                from university_system.infrastructure.email.template_utils import render_template
                for email, first_name, last_name in students:
                    if email:
                        try:
                            subject, body = render_template("room_change_notice", {
                                "student_name": f"{first_name} {last_name}",
                                "module_code": module_code,
                                "day": day,
                                "start_time": start_time,
                                "end_time": end_time,
                                "old_room": old_room,
                                "new_room": new_room
                            })
                            if subject and body:
                                send_email(email, subject, body)
                        except Exception:
                            pass  # Continue even if individual email fails

                # Send emails to lecturers
                for email, first_name, last_name in lecturers:
                    if email:
                        personalized_body = body.replace("Dear Recipient", f"Dear {first_name} {last_name}")
                        try:
                            send_email(email, subject, personalized_body)
                        except Exception:
                            pass

        except Exception as e:
            # Don't fail the entire operation if email fails
            self.update_activity_log(f"Failed to send email notifications: {str(e)}")
    
    def edit_selected_instructor(self):
        """Edit the selected instructor"""
        selected = self.instructors_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an instructor to edit.")
            return
        
        instructor_data = self.instructors_tree.item(selected[0])['values']
        instructor_id = instructor_data[0]
        
        dialog = EditInstructorDialog(self.root, self.scheduler, instructor_id)
        if dialog.result:
            self.refresh_instructors()
            self.update_activity_log(f"Instructor {instructor_id} updated")
    
    # Timetable generation methods
    def generate_student_timetable(self):
        """Generate timetable for a student"""
        student_id = self.student_id_var.get().strip()
        if not student_id:
            messagebox.showwarning("Warning", "Please enter a student ID.")
            return

        try:
            # Check if student exists
            from university_system.infrastructure.database.db import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?', (student_id,))
                student = cursor.fetchone()

            if not student:
                messagebox.showerror("Error", f"Student ID {student_id} does not exist.")
                return

            student_name = f"{student[0]} {student[1]}"

            # Get schedule data
            schedule_data = self.scheduler._get_student_schedule_data(student_id)

            if not schedule_data:
                # Clear and show message
                for widget in self.timetable_frame.winfo_children():
                    widget.destroy()
                tk.Label(self.timetable_frame, text=f"No schedule found for student {student_id}",
                        font=('Arial', 12)).pack(pady=20)
                return

            # Display timetable in grid view
            self._display_timetable_grid(schedule_data, f"Timetable for {student_name} ({student_id})")

            # Check for conflicts
            conflicts = self.scheduler.check_student_conflicts(student_id)
            if conflicts:
                conflict_label = tk.Label(self.timetable_frame, text=f"⚠️ {len(conflicts)} scheduling conflict(s) detected",
                                         font=('Arial', 10, 'bold'), fg='red')
                conflict_label.pack(pady=10)

            self.update_activity_log(f"Generated timetable for student {student_id}")
            self.last_timetable_data = schedule_data  # Store for export
            self.last_timetable_type = 'student'
            self.last_timetable_id = student_id

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate student timetable: {str(e)}")
    
    def generate_instructor_timetable(self):
        """Generate timetable for an instructor"""
        instructor_id_str = self.instructor_id_var.get().strip()
        if not instructor_id_str:
            messagebox.showwarning("Warning", "Please enter an instructor ID.")
            return

        try:
            instructor_id = int(instructor_id_str)

            # Check if instructor exists
            from university_system.infrastructure.database.db import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT first_name, last_name FROM instructors WHERE id = ?', (instructor_id,))
                instructor = cursor.fetchone()

            if not instructor:
                messagebox.showerror("Error", f"Instructor ID {instructor_id} does not exist.")
                return

            first_name, last_name = instructor
            instructor_name = f"{first_name} {last_name}"

            # Get schedule data
            schedule_data = self.scheduler._get_instructor_schedule_data(instructor_id)

            if not schedule_data:
                # Clear and show message
                for widget in self.timetable_frame.winfo_children():
                    widget.destroy()
                tk.Label(self.timetable_frame, text=f"No schedule found for instructor {instructor_name}",
                        font=('Arial', 12)).pack(pady=20)
                return

            # Display timetable in grid view
            self._display_timetable_grid(schedule_data, f"Timetable for {instructor_name} (ID: {instructor_id})")

            self.update_activity_log(f"Generated timetable for instructor {instructor_name}")
            self.last_timetable_data = schedule_data  # Store for export
            self.last_timetable_type = 'instructor'
            self.last_timetable_id = instructor_id

        except ValueError:
            messagebox.showerror("Error", "Invalid instructor ID. Please enter a number.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate instructor timetable: {str(e)}")

    def _display_timetable_grid(self, schedule_data, title):
        """Display timetable in grid format matching the grid view"""
        # Clear existing content
        for widget in self.timetable_frame.winfo_children():
            widget.destroy()

        # Title
        title_label = tk.Label(self.timetable_frame, text=title, font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        # Create grid data structure
        grid_data = {}
        for day in DAYS_OF_WEEK:
            grid_data[day] = {}
            for time_slot in TIME_SLOTS:
                grid_data[day][time_slot] = []

        # Populate grid with schedule data
        for entry in schedule_data:
            day = entry.get('day', entry.get('day_of_week', ''))
            start_time = entry.get('start_time', '')

            if not day or not start_time:
                continue

            # Find the closest time slot
            try:
                closest_slot = min(TIME_SLOTS, key=lambda x: abs(int(x[:2]) - int(start_time[:2])))
            except:
                continue

            session_info = {
                'module': entry.get('module_code', 'N/A'),
                'type': entry.get('session_type', 'Session'),
                'room': entry.get('room', 'TBA'),
                'time': f"{entry.get('start_time', '')}-{entry.get('end_time', '')}"
            }

            if day in grid_data and closest_slot in grid_data[day]:
                grid_data[day][closest_slot].append(session_info)

        # Create grid frame
        grid_frame = tk.Frame(self.timetable_frame)
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Header row - Time column
        time_header = tk.Label(grid_frame, text="Time", font=('Arial', 10, 'bold'),
                              relief=tk.SOLID, borderwidth=2, bg='#4a90e2', fg='white',
                              width=10, height=2)
        time_header.grid(row=0, column=0, padx=1, pady=1, sticky="nsew")

        # Day headers
        for col, day in enumerate(DAYS_OF_WEEK, 1):
            day_header = tk.Label(grid_frame, text=day, font=('Arial', 10, 'bold'),
                                 relief=tk.SOLID, borderwidth=2, bg='#4a90e2', fg='white',
                                 width=18, height=2)
            day_header.grid(row=0, column=col, padx=1, pady=1, sticky="nsew")

        # Create time slots and schedule cells
        for row, time_slot in enumerate(TIME_SLOTS, 1):
            # Time label
            time_label = tk.Label(grid_frame, text=time_slot, font=('Arial', 9, 'bold'),
                                 relief=tk.SOLID, borderwidth=2, bg='#e8f4f8',
                                 width=10, height=4)
            time_label.grid(row=row, column=0, padx=1, pady=1, sticky="nsew")

            # Schedule cells for each day
            for col, day in enumerate(DAYS_OF_WEEK, 1):
                entries = grid_data[day][time_slot]

                # Create cell frame
                cell_frame = tk.Frame(grid_frame, relief=tk.SOLID, borderwidth=2,
                                     bg='#d4edda' if entries else 'white',
                                     width=160, height=80)
                cell_frame.grid(row=row, column=col, padx=1, pady=1, sticky="nsew")
                cell_frame.grid_propagate(False)

                if entries:
                    # Inner container
                    inner_frame = tk.Frame(cell_frame, bg='#d4edda')
                    inner_frame.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)

                    # Display entries
                    for i, entry in enumerate(entries):
                        if i < 2:  # Limit to 2 entries per cell
                            session_box = tk.Frame(inner_frame, relief=tk.RAISED, borderwidth=1,
                                                  bg='#c3e6cb', padx=2, pady=2)
                            session_box.pack(fill=tk.X, pady=1)

                            # Module code
                            module_label = tk.Label(session_box, text=entry['module'],
                                                   font=('Arial', 8, 'bold'),
                                                   bg='#c3e6cb', fg='#155724')
                            module_label.pack(anchor='w')

                            # Session type
                            type_label = tk.Label(session_box, text=entry['type'],
                                                 font=('Arial', 7),
                                                 bg='#c3e6cb', fg='#155724')
                            type_label.pack(anchor='w')

                            # Room
                            room_label = tk.Label(session_box, text=f"Room: {entry['room']}",
                                                 font=('Arial', 6),
                                                 bg='#c3e6cb', fg='#155724')
                            room_label.pack(anchor='w')

                    if len(entries) > 2:
                        more_label = tk.Label(inner_frame, text=f"+ {len(entries)-2} more...",
                                             font=('Arial', 7, 'italic'),
                                             bg='#d4edda', fg='#155724')
                        more_label.pack(anchor='w', pady=2)

    def check_student_conflicts(self):
        """Check for conflicts in student's schedule"""
        student_id = self.student_id_var.get().strip()
        if not student_id:
            messagebox.showwarning("Warning", "Please enter a student ID.")
            return
        
        try:
            conflicts = self.scheduler.check_student_conflicts(student_id)
            
            self.timetable_text.delete(1.0, tk.END)
            
            if not conflicts:
                self.timetable_text.insert(tk.END, f"No scheduling conflicts found for student {student_id}")
            else:
                self.timetable_text.insert(tk.END, f"Scheduling Conflicts for Student {student_id}\n")
                self.timetable_text.insert(tk.END, "=" * 80 + "\n")
                
                for i, conflict in enumerate(conflicts, 1):
                    module1 = conflict['module1']
                    module2 = conflict['module2']
                    
                    self.timetable_text.insert(tk.END, f"Conflict {i}:\n")
                    self.timetable_text.insert(tk.END, f"  Module 1: {module1['code']} - {module1['name']}\n")
                    self.timetable_text.insert(tk.END, f"            {module1['day']} {module1['time']} in {module1['room']}\n")
                    self.timetable_text.insert(tk.END, f"  Module 2: {module2['code']} - {module2['name']}\n")
                    self.timetable_text.insert(tk.END, f"            {module2['day']} {module2['time']} in {module2['room']}\n")
                    self.timetable_text.insert(tk.END, "-" * 80 + "\n")
            
            self.update_activity_log(f"Checked conflicts for student {student_id}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to check student conflicts: {str(e)}")
    
    def export_last_timetable(self):
        """Export the last generated timetable"""
        # Check if we have timetable data stored
        if not hasattr(self, 'last_timetable_data') or not self.last_timetable_data:
            messagebox.showwarning("Warning", "No timetable to export. Please generate a timetable first.")
            return

        format_type = self.export_format_var.get()

        try:
            if format_type == "iCal":
                self._export_timetable_to_ical(self.last_timetable_data)
            elif format_type == "PDF":
                self._export_timetable_to_pdf(self.last_timetable_data)
            elif format_type == "CSV":
                self._export_timetable_to_csv(self.last_timetable_data)
            elif format_type == "Excel":
                self._export_timetable_to_excel(self.last_timetable_data)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export timetable: {str(e)}")
    
    # Analytics methods
    def show_room_utilization(self):
        """Show room utilization analytics"""
        try:
            self.analytics_text.delete(1.0, tk.END)
            self.analytics_text.insert(tk.END, "Generating room utilization report...\n")
            self.root.update()
            
            # Get room utilization data
            room_data = self.scheduler.generate_room_utilization_report('data')
            
            if not room_data:
                self.analytics_text.insert(tk.END, "No room data available.")
                return
            
            self.analytics_text.delete(1.0, tk.END)
            self.analytics_text.insert(tk.END, "Room Utilization Analytics\n")
            self.analytics_text.insert(tk.END, "=" * 100 + "\n")
            self.analytics_text.insert(tk.END, f"{'Room':<15} {'Type':<15} {'Capacity':<10} {'Sessions':<10} {'Utilization':<12} {'Avg Duration':<12}\n")
            self.analytics_text.insert(tk.END, "-" * 100 + "\n")
            
            for room in room_data:
                line = f"{room['Room']:<15} {room['Type']:<15} {room['Capacity']:<10} {room['Sessions']:<10} {room['Utilization Rate (%)']:<12} {room['Avg Duration (min)']:<12}\n"
                self.analytics_text.insert(tk.END, line)
            
            self.analytics_text.insert(tk.END, "=" * 100 + "\n")
            
            # Summary statistics
            if room_data:
                avg_utilization = sum(room['Utilization Rate (%)'] for room in room_data) / len(room_data)
                self.analytics_text.insert(tk.END, f"\nSummary:\n")
                self.analytics_text.insert(tk.END, f"Total Rooms: {len(room_data)}\n")
                self.analytics_text.insert(tk.END, f"Average Utilization: {avg_utilization:.2f}%\n")
                
                most_utilized = max(room_data, key=lambda x: x['Utilization Rate (%)'])
                least_utilized = min(room_data, key=lambda x: x['Utilization Rate (%)'])
                self.analytics_text.insert(tk.END, f"Most Utilized: {most_utilized['Room']} ({most_utilized['Utilization Rate (%)']}%)\n")
                self.analytics_text.insert(tk.END, f"Least Utilized: {least_utilized['Room']} ({least_utilized['Utilization Rate (%)']}%)\n")
            
            self.update_activity_log("Generated room utilization report")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate room utilization report: {str(e)}")
    
    def show_instructor_workload(self):
        """Show instructor workload analytics"""
        try:
            self.analytics_text.delete(1.0, tk.END)
            self.analytics_text.insert(tk.END, "Generating instructor workload report...\n")
            self.root.update()
            
            # Get workload data
            workload_data = self.scheduler.generate_instructor_workload_report('data')
            
            if not workload_data:
                self.analytics_text.insert(tk.END, "No instructor data available.")
                return
            
            self.analytics_text.delete(1.0, tk.END)
            self.analytics_text.insert(tk.END, "Instructor Workload Analytics\n")
            self.analytics_text.insert(tk.END, "=" * 120 + "\n")
            self.analytics_text.insert(tk.END, f"{'Instructor':<25} {'Department':<15} {'Sessions':<10} {'Hours':<8} {'Max':<8} {'Load %':<8} {'Status':<12}\n")
            self.analytics_text.insert(tk.END, "-" * 120 + "\n")
            
            for instructor in workload_data:
                line = f"{instructor['Instructor']:<25} {instructor['Department']:<15} {instructor['Sessions']:<10} {instructor['Total Hours']:<8} {instructor['Max Hours']:<8} {instructor['Workload (%)']:<8} {instructor['Status']:<12}\n"
                self.analytics_text.insert(tk.END, line)
            
            self.analytics_text.insert(tk.END, "=" * 120 + "\n")
            
            # Highlight overloaded instructors
            overloaded = [i for i in workload_data if i['Status'] == 'Overloaded']
            if overloaded:
                self.analytics_text.insert(tk.END, f"\nWARNING: {len(overloaded)} instructor(s) are overloaded!\n")
                for instructor in overloaded:
                    self.analytics_text.insert(tk.END, f"  - {instructor['Instructor']}: {instructor['Workload (%)']}% workload\n")
            
            self.update_activity_log("Generated instructor workload report")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate instructor workload report: {str(e)}")
    
    def show_workload_report(self):
        """Show workload report and switch to analytics tab"""
        self.notebook.select(5)  # Switch to analytics tab
        self.show_instructor_workload()
    
    def show_peak_usage(self):
        """Show peak usage analysis"""
        try:
            self.analytics_text.delete(1.0, tk.END)
            self.analytics_text.insert(tk.END, "Peak Usage Analysis\n")
            self.analytics_text.insert(tk.END, "=" * 60 + "\n")
            
            peak_times = self.scheduler._analyze_peak_usage()
            
            for day, times in peak_times.items():
                self.analytics_text.insert(tk.END, f"{day}: {', '.join(times) if times else 'No data'}\n")
            
            # Module distribution
            module_stats = self.scheduler._analyze_module_distribution()
            self.analytics_text.insert(tk.END, f"\nModule Distribution:\n")
            self.analytics_text.insert(tk.END, f"Total Modules: {module_stats['total']}\n")
            self.analytics_text.insert(tk.END, f"Most Common Session Type: {module_stats['most_common_type']}\n")
            self.analytics_text.insert(tk.END, f"Average Sessions per Module: {module_stats['avg_sessions']:.2f}\n")
            
            self.update_activity_log("Generated peak usage analysis")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate peak usage analysis: {str(e)}")
    
    def generate_charts(self):
        """Generate visual charts"""
        try:
            self.update_status("Generating charts...")
            chart_path = self.scheduler.generate_utilization_charts()
            
            if chart_path and os.path.exists(chart_path):
                if messagebox.askyesno("Charts Generated", f"Charts generated successfully!\n\nPath: {chart_path}\n\nWould you like to open the charts?"):
                    webbrowser.open(f"file://{os.path.abspath(chart_path)}")
                
                self.update_activity_log("Generated utilization charts")
            else:
                messagebox.showinfo("Info", "Charts generated. Check the analytics folder.")
            
            self.update_status("Ready")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate charts: {str(e)}")
            self.update_status("Ready")
    
    # Conflict management methods
    def detect_all_conflicts(self):
        """Detect all scheduling conflicts"""
        try:
            self.update_status("Detecting conflicts...")
            
            conflicts = self.scheduler.detect_all_conflicts()
            
            self.refresh_conflicts()
            self.refresh_dashboard()
            
            messagebox.showinfo("Conflicts Detection", f"Detection complete.\nFound {len(conflicts)} conflicts.")
            
            self.update_activity_log(f"Detected {len(conflicts)} conflicts")
            self.update_status("Ready")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to detect conflicts: {str(e)}")
            self.update_status("Ready")
    
    def resolve_selected_conflict(self):
        """Resolve the selected conflict"""
        selected = self.conflicts_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a conflict to resolve.")
            return
        
        conflict_data = self.conflicts_tree.item(selected[0])['values']
        conflict_id = conflict_data[0]
        
        # Show resolution dialog
        resolution_notes = tk.simpledialog.askstring("Resolve Conflict", 
                                                    "Enter resolution notes:", 
                                                    parent=self.root)
        
        if resolution_notes:
            try:
                self.scheduler.resolve_conflict(conflict_id, resolution_notes)
                self.refresh_conflicts()
                self.refresh_dashboard()
                self.update_activity_log(f"Resolved conflict {conflict_id}")
                messagebox.showinfo("Success", "Conflict resolved successfully.")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to resolve conflict: {str(e)}")
    
    # Management methods
    def create_backup(self):
        """Create a database backup"""
        try:
            backup_name = tk.simpledialog.askstring("Create Backup", 
                                                   "Enter backup name (optional):", 
                                                   parent=self.root)
            
            description = tk.simpledialog.askstring("Create Backup", 
                                                   "Enter description (optional):", 
                                                   parent=self.root)
            
            self.update_status("Creating backup...")
            
            if backup_name:
                backup_path = self.scheduler.create_backup(backup_name, description or "")
            else:
                backup_path = self.scheduler.create_backup(description=description or "")
            
            if backup_path:
                messagebox.showinfo("Success", f"Backup created successfully!\nPath: {backup_path}")
                self.update_activity_log("Created database backup")
            else:
                messagebox.showerror("Error", "Failed to create backup.")
            
            self.update_status("Ready")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create backup: {str(e)}")
            self.update_status("Ready")
    
    def list_backups(self):
        """List all available backups"""
        try:
            self.log_text.config(state=tk.NORMAL)
            self.log_text.delete(1.0, tk.END)
            
            # Get backup list
            from university_system.infrastructure.database.db import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT backup_name, backup_date, backup_size, description
                FROM backups
                ORDER BY backup_date DESC
                ''')

                backups = cursor.fetchall()
            
            if not backups:
                self.log_text.insert(tk.END, "No backups found.\n")
            else:
                self.log_text.insert(tk.END, "Available Backups:\n")
                self.log_text.insert(tk.END, "=" * 80 + "\n")
                self.log_text.insert(tk.END, f"{'Name':<25} {'Date':<20} {'Size (KB)':<12} {'Description':<20}\n")
                self.log_text.insert(tk.END, "-" * 80 + "\n")
                
                for backup in backups:
                    name, date, size, desc = backup
                    backup_date = datetime.fromisoformat(date).strftime("%Y-%m-%d %H:%M")
                    size_kb = round(size / 1024, 2) if size else 0
                    desc = desc or "N/A"
                    self.log_text.insert(tk.END, f"{name:<25} {backup_date:<20} {size_kb:<12} {desc:<20}\n")
                
                self.log_text.insert(tk.END, "=" * 80 + "\n")
            
            self.log_text.config(state=tk.DISABLED)
            self.notebook.select(7)  # Switch to management tab
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to list backups: {str(e)}")
    
    def restore_backup(self):
        """Restore from a backup"""
        try:
            # First list backups
            self.list_backups()
            
            backup_name = tk.simpledialog.askstring("Restore Backup", 
                                                   "Enter backup name to restore:", 
                                                   parent=self.root)
            
            if backup_name:
                if messagebox.askyesno("Confirm Restore", 
                                     f"This will replace the current database with the backup '{backup_name}'.\n\nAre you sure you want to continue?"):
                    
                    self.update_status("Restoring backup...")
                    
                    success = self.scheduler.restore_backup(backup_name)
                    
                    if success:
                        messagebox.showinfo("Success", f"Database restored from backup: {backup_name}")
                        self.refresh_all_data()
                        self.update_activity_log(f"Restored from backup: {backup_name}")
                    else:
                        messagebox.showerror("Error", "Failed to restore backup.")
                    
                    self.update_status("Ready")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to restore backup: {str(e)}")
            self.update_status("Ready")
    
    def validate_data(self):
        """Validate data consistency"""
        try:
            self.update_status("Validating data...")
            
            issues = self.scheduler.validate_data_consistency()
            
            self.log_text.config(state=tk.NORMAL)
            self.log_text.delete(1.0, tk.END)
            
            if issues:
                self.log_text.insert(tk.END, "Data Consistency Issues Found:\n")
                self.log_text.insert(tk.END, "=" * 50 + "\n")
                for i, issue in enumerate(issues, 1):
                    self.log_text.insert(tk.END, f"{i}. {issue}\n")
                self.log_text.insert(tk.END, "=" * 50 + "\n")
                
                if messagebox.askyesno("Issues Found", f"Found {len(issues)} data consistency issues.\n\nWould you like to fix them automatically?"):
                    self.clean_orphaned_records()
            else:
                self.log_text.insert(tk.END, "No data consistency issues found.\n")
                messagebox.showinfo("Validation Complete", "No data consistency issues found.")
            
            self.log_text.config(state=tk.DISABLED)
            self.notebook.select(7)  # Switch to management tab
            
            self.update_activity_log("Performed data validation")
            self.update_status("Ready")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to validate data: {str(e)}")
            self.update_status("Ready")
    
    def clean_orphaned_records(self):
        """Clean orphaned records"""
        try:
            self.update_status("Cleaning orphaned records...")
            
            self.scheduler.clean_orphaned_records()
            
            messagebox.showinfo("Success", "Orphaned records cleaned successfully.")
            self.refresh_all_data()
            self.update_activity_log("Cleaned orphaned records")
            self.update_status("Ready")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to clean orphaned records: {str(e)}")
            self.update_status("Ready")
    
    def repair_issues(self):
        """Repair common data issues"""
        try:
            self.update_status("Repairing issues...")
            
            # Run validation and cleanup
            issues = self.scheduler.validate_data_consistency()
            if issues:
                self.scheduler.clean_orphaned_records()
                messagebox.showinfo("Success", "Common issues repaired.")
            else:
                messagebox.showinfo("Info", "No issues found to repair.")
            
            self.refresh_all_data()
            self.update_activity_log("Repaired data issues")
            self.update_status("Ready")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to repair issues: {str(e)}")
            self.update_status("Ready")
    
    def import_csv(self):
        """Import schedules from CSV file"""
        try:
            file_path = filedialog.askopenfilename(
                title="Select CSV file to import",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            
            if file_path:
                self.update_status("Importing CSV...")
                
                success = self.scheduler.import_schedules_from_csv(file_path)
                
                if success:
                    messagebox.showinfo("Success", "CSV imported successfully!")
                    self.refresh_all_data()
                    self.update_activity_log(f"Imported data from {os.path.basename(file_path)}")
                else:
                    messagebox.showerror("Error", "Failed to import CSV file.")
                
                self.update_status("Ready")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import CSV: {str(e)}")
            self.update_status("Ready")
    
    def export_all_data(self):
        """Export all schedule data"""
        try:
            self.update_status("Exporting data...")
            
            filename = self.scheduler.export_all_schedules_to_csv()
            
            if filename:
                if messagebox.askyesno("Export Complete", f"Data exported successfully!\n\nFile: {filename}\n\nWould you like to open the file location?"):
                    folder_path = os.path.dirname(os.path.abspath(filename))
                    webbrowser.open(f"file://{folder_path}")
                
                self.update_activity_log("Exported all schedule data")
            else:
                messagebox.showerror("Error", "Failed to export data.")
            
            self.update_status("Ready")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export data: {str(e)}")
            self.update_status("Ready")
    
    def generate_reports(self):
        """Generate comprehensive reports"""
        try:
            self.update_status("Generating reports...")
            
            # Generate PDF reports
            room_report = self.scheduler.generate_room_utilization_report('pdf')
            workload_report = self.scheduler.generate_instructor_workload_report('pdf')
            
            reports = []
            if room_report:
                reports.append(f"Room Utilization: {room_report}")
            if workload_report:
                reports.append(f"Instructor Workload: {workload_report}")
            
            if reports:
                report_list = "\n".join(reports)
                if messagebox.askyesno("Reports Generated", f"Reports generated successfully!\n\n{report_list}\n\nWould you like to open the reports folder?"):
                    folder_path = os.path.dirname(os.path.abspath(room_report))
                    webbrowser.open(f"file://{folder_path}")
                
                self.update_activity_log("Generated comprehensive reports")
            else:
                messagebox.showerror("Error", "Failed to generate reports.")
            
            self.update_status("Ready")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate reports: {str(e)}")
            self.update_status("Ready")
    
    # Template methods
    def save_template(self):
        """Save current schedule as template"""
        try:
            template_name = tk.simpledialog.askstring("Save Template", 
                                                     "Enter template name:", 
                                                     parent=self.root)
            
            if template_name:
                description = tk.simpledialog.askstring("Save Template", 
                                                       "Enter description (optional):", 
                                                       parent=self.root)
                
                success = self.scheduler.save_schedule_template(template_name, description or "")
                
                if success:
                    messagebox.showinfo("Success", f"Template '{template_name}' saved successfully!")
                    self.update_activity_log(f"Saved template: {template_name}")
                else:
                    messagebox.showerror("Error", "Failed to save template.")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save template: {str(e)}")
    
    def load_template(self):
        """Load a schedule template"""
        try:
            # First list templates
            self.list_templates()
            
            template_name = tk.simpledialog.askstring("Load Template", 
                                                     "Enter template name to load:", 
                                                     parent=self.root)
            
            if template_name:
                clear_existing = messagebox.askyesno("Load Template", 
                                                   "Clear existing schedules before loading template?")
                
                success = self.scheduler.load_schedule_template(template_name, clear_existing)
                
                if success:
                    messagebox.showinfo("Success", f"Template '{template_name}' loaded successfully!")
                    self.refresh_all_data()
                    self.update_activity_log(f"Loaded template: {template_name}")
                else:
                    messagebox.showerror("Error", "Failed to load template.")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load template: {str(e)}")
    
    def list_templates(self):
        """List all available templates"""
        try:
            self.log_text.config(state=tk.NORMAL)
            self.log_text.delete(1.0, tk.END)
            
            from university_system.infrastructure.database.db import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT template_name, description, created_date, created_by
                FROM schedule_templates
                ORDER BY created_date DESC
                ''')

                templates = cursor.fetchall()
            
            if not templates:
                self.log_text.insert(tk.END, "No schedule templates found.\n")
            else:
                self.log_text.insert(tk.END, "Schedule Templates:\n")
                self.log_text.insert(tk.END, "=" * 80 + "\n")
                self.log_text.insert(tk.END, f"{'Name':<20} {'Description':<30} {'Created':<15} {'By':<10}\n")
                self.log_text.insert(tk.END, "-" * 80 + "\n")
                
                for template in templates:
                    name, desc, created, created_by = template
                    created_date = datetime.fromisoformat(created).strftime("%Y-%m-%d")
                    desc = desc or "N/A"
                    self.log_text.insert(tk.END, f"{name:<20} {desc[:28]:<30} {created_date:<15} {created_by:<10}\n")
                
                self.log_text.insert(tk.END, "=" * 80 + "\n")
            
            self.log_text.config(state=tk.DISABLED)
            self.notebook.select(7)  # Switch to management tab
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to list templates: {str(e)}")
    
    # Settings methods
    def save_settings(self):
        """Save system settings"""
        try:
            # Save all settings
            self.scheduler.update_system_setting('institution_name', self.institution_var.get())
            self.scheduler.update_system_setting('semester_start', self.semester_start_var.get())
            self.scheduler.update_system_setting('semester_end', self.semester_end_var.get())
            self.scheduler.update_system_setting('default_session_duration', self.session_duration_var.get())
            self.scheduler.update_system_setting('email_notifications', str(self.email_notifications_var.get()))
            self.scheduler.update_system_setting('auto_backup', str(self.auto_backup_var.get()))
            
            messagebox.showinfo("Success", "Settings saved successfully!")
            self.update_activity_log("System settings updated")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {str(e)}")
    
    def add_holiday(self):
        """Add a new holiday"""
        dialog = AddHolidayDialog(self.root, self.scheduler)
        if dialog.result:
            self.refresh_holidays()
            self.update_activity_log("Holiday added")

            # Also add to academic calendar GUI if available
            try:
                self._sync_holiday_to_academic_calendar()
            except Exception as e:
                print(f"Note: Could not sync to academic calendar: {e}")

    def _sync_holiday_to_academic_calendar(self):
        """Sync holidays with the academic calendar GUI"""
        try:
            # Import academic calendar manager
            from university_system.modules.domain.academics.services.academic_calendar import AcademicCalendarManager

            calendar_manager = AcademicCalendarManager()

            # Get the most recently added holiday
            from university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, holiday_name, start_date, end_date, description, recurring
                    FROM holidays
                    ORDER BY id DESC
                    LIMIT 1
                ''')
                holiday = cursor.fetchone()

            if holiday:
                holiday_id, name, start_date, end_date, description, recurring = holiday

                # Check if this holiday already exists in academic calendar
                event_title = f"Holiday: {name}"

                # Add as an event to the academic calendar
                # The academic calendar has its own events table
                try:
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        # Check if calendar_events table exists
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='calendar_events'")
                        if cursor.fetchone():
                            # Add event to calendar
                            cursor.execute('''
                                INSERT OR IGNORE INTO calendar_events (title, description, start_date, end_date, event_type, is_recurring)
                                VALUES (?, ?, ?, ?, 'holiday', ?)
                            ''', (event_title, description or '', start_date, end_date or start_date, 1 if recurring else 0))
                            conn.commit()
                except Exception as e:
                    print(f"Could not sync to calendar_events: {e}")

        except Exception as e:
            print(f"Error syncing holiday to academic calendar: {e}")

    def view_calendar(self):
        """View academic calendar - opens the full academic calendar GUI"""
        try:
            # Try to launch the academic calendar GUI
            from university_system.modules.domain.academics.gui.academic_calendar_gui import CalendarGUI

            # Create calendar GUI in a new top-level window
            calendar_window = tk.Toplevel(self.root)
            calendar_window.title("Academic Calendar")
            calendar_window.geometry("1200x800")

            # Initialize calendar GUI
            try:
                calendar_gui = CalendarGUI(parent_window=calendar_window)
                self.update_activity_log("Opened Academic Calendar")
                return
            except Exception as e:
                print(f"Could not load full calendar GUI: {e}")
                # Fall back to basic view
                calendar_window.destroy()
                calendar_window = tk.Toplevel(self.root)
                calendar_window.title("Academic Calendar - Basic View")
                calendar_window.geometry("600x400")
            
            # Calendar display
            calendar_text = scrolledtext.ScrolledText(calendar_window, font=('Courier', 10))
            calendar_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Get current month's holidays
            from university_system.infrastructure.database.db import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                current_month = datetime.now().strftime("%Y-%m")
                cursor.execute('''
                SELECT holiday_name, start_date, end_date, description
                FROM holidays
                WHERE start_date LIKE ?
                ORDER BY start_date
                ''', (f"{current_month}%",))

                holidays = cursor.fetchall()
            
            calendar_text.insert(tk.END, f"Academic Calendar - {datetime.now().strftime('%B %Y')}\n")
            calendar_text.insert(tk.END, "=" * 60 + "\n")
            
            if holidays:
                for holiday in holidays:
                    name, start, end, desc = holiday
                    if start == end:
                        calendar_text.insert(tk.END, f"{start}: {name}\n")
                    else:
                        calendar_text.insert(tk.END, f"{start} to {end}: {name}\n")
                    if desc:
                        calendar_text.insert(tk.END, f"  {desc}\n")
                    calendar_text.insert(tk.END, "\n")
            else:
                calendar_text.insert(tk.END, "No holidays scheduled for this month.\n")
            
            calendar_text.insert(tk.END, "=" * 60 + "\n")
            calendar_text.config(state=tk.DISABLED)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to view calendar: {str(e)}")
    
    # Utility methods
    def show_grid_view(self):
        """Show schedule in grid view"""
        GridViewWindow(self.root, self.scheduler)
    
    def launch_cli_mode(self):
        """Launch the CLI mode in a separate window"""
        try:
            # Create a new window for CLI mode
            cli_window = tk.Toplevel(self.root)
            cli_window.title("CLI Mode - Enhanced Module Scheduling System")
            cli_window.geometry("800x600")
            
            # CLI text area
            cli_frame = ttk.Frame(cli_window)
            cli_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            ttk.Label(cli_frame, text="Command Line Interface Mode", font=('Arial', 14, 'bold')).pack(pady=5)
            
            # Instructions
            instructions = """
Available Commands:
- Type 'help' for full command list
- Type 'menu' to show the main menu
- Type 'exit' to close CLI mode

Note: This is a simplified CLI interface. For full CLI functionality,
run the original Python script directly from the command line.
            """
            
            ttk.Label(cli_frame, text=instructions, justify=tk.LEFT).pack(pady=5)
            
            # CLI output area
            cli_output = scrolledtext.ScrolledText(cli_frame, height=20, font=('Courier', 10))
            cli_output.pack(fill=tk.BOTH, expand=True, pady=5)
            
            # CLI input
            input_frame = ttk.Frame(cli_frame)
            input_frame.pack(fill=tk.X, pady=5)
            
            ttk.Label(input_frame, text="Command:").pack(side=tk.LEFT)
            cli_input = ttk.Entry(input_frame)
            cli_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            
            def execute_cli_command():
                command = cli_input.get().strip().lower()
                cli_input.delete(0, tk.END)
                
                cli_output.insert(tk.END, f"> {command}\n")
                
                if command == 'exit':
                    cli_window.destroy()
                elif command == 'help':
                    help_text = """
Available Commands:
- help: Show this help message
- menu: Show main menu options
- stats: Show system statistics
- conflicts: Check for conflicts
- backup: Create a backup
- exit: Close CLI mode

For full CLI functionality, run the original script from command line.
                    """
                    cli_output.insert(tk.END, help_text + "\n")
                elif command == 'menu':
                    cli_output.insert(tk.END, "Main menu options available in the GUI tabs above.\n")
                elif command == 'stats':
                    try:
                        from university_system.infrastructure.database.db import sqlite3
                        with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                            cursor = conn.cursor()

                            cursor.execute("SELECT COUNT(*) FROM module_schedule")
                            schedules = cursor.fetchone()[0]
                            cursor.execute("SELECT COUNT(*) FROM rooms WHERE is_active = 1")
                            rooms = cursor.fetchone()[0]
                            cursor.execute("SELECT COUNT(*) FROM instructors WHERE CASE WHEN status = 'Active' THEN 1 ELSE COALESCE(is_active, 1) END = 1")
                            instructors = cursor.fetchone()[0]
                        
                        stats_text = f"""
System Statistics:
- Total Schedules: {schedules}
- Active Rooms: {rooms}
- Active Instructors: {instructors}
                        """
                        cli_output.insert(tk.END, stats_text + "\n")
                    except Exception as e:
                        cli_output.insert(tk.END, f"Error getting stats: {e}\n")
                elif command == 'conflicts':
                    try:
                        conflicts = self.scheduler.detect_all_conflicts()
                        cli_output.insert(tk.END, f"Detected {len(conflicts)} conflicts.\n")
                    except Exception as e:
                        cli_output.insert(tk.END, f"Error detecting conflicts: {e}\n")
                elif command == 'backup':
                    try:
                        backup_path = self.scheduler.create_backup(description="CLI backup")
                        if backup_path:
                            cli_output.insert(tk.END, f"Backup created: {backup_path}\n")
                        else:
                            cli_output.insert(tk.END, "Failed to create backup.\n")
                    except Exception as e:
                        cli_output.insert(tk.END, f"Error creating backup: {e}\n")
                else:
                    cli_output.insert(tk.END, f"Unknown command: {command}\nType 'help' for available commands.\n")
                
                cli_output.see(tk.END)
            
            ttk.Button(input_frame, text="Execute", command=execute_cli_command).pack(side=tk.RIGHT)
            
            # Bind Enter key
            cli_input.bind('<Return>', lambda e: execute_cli_command())
            
            cli_output.insert(tk.END, "Enhanced Module Scheduling System - CLI Mode\n")
            cli_output.insert(tk.END, "Type 'help' for available commands.\n\n")
            
            cli_input.focus()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch CLI mode: {str(e)}")

    def create_modules_tab(self):
        """Create the modules management tab"""
        modules_frame = ttk.Frame(self.notebook)
        self.notebook.add(modules_frame, text="📚 Modules")
        
        # Controls frame
        controls_frame = ttk.Frame(modules_frame)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(controls_frame, text="➕ Add New Module", 
                  command=self.show_add_module_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="✏️ Edit Selected", 
                  command=self.edit_selected_module).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="🗑️ Delete Selected", 
                  command=self.delete_selected_module, style='Danger.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="📊 Generate Report", 
                  command=self.generate_module_report).pack(side=tk.LEFT, padx=5)
        
        # Search
        search_frame = ttk.Frame(controls_frame)
        search_frame.pack(side=tk.RIGHT, padx=5)
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.module_search_var = tk.StringVar()
        self.module_search_var.trace('w', self.filter_modules)
        ttk.Entry(search_frame, textvariable=self.module_search_var, width=20).pack(side=tk.LEFT, padx=5)
        
        # Modules treeview
        tree_frame = ttk.Frame(modules_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        columns = ("ID", "Code", "Name", "Credits", "Semester", "Type", "Instructor")
        self.modules_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", style='Data.Treeview')
        
        for col in columns:
            self.modules_tree.heading(col, text=col)
            if col == "ID":
                self.modules_tree.column(col, width=50)
            elif col == "Name":
                self.modules_tree.column(col, width=200)
            else:
                self.modules_tree.column(col, width=100)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.modules_tree.yview)
        self.modules_tree.configure(yscrollcommand=v_scrollbar.set)
        
        self.modules_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.modules_tree.bind("<Double-1>", lambda e: self.edit_selected_module())

    def get_all_modules(self):
        """Get all modules from the database"""
        with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
            cursor = conn.cursor()
            # Use the implicit rowid as the module identifier.  Many parts of the
            # system define a modules table without an explicit id column.  Selecting
            # rowid as "id" provides a stable unique integer for each row and
            # preserves compatibility with code that expects an id field.
            cursor.execute('SELECT rowid AS id, module_code, module_name, module_type FROM modules')
            modules = cursor.fetchall()
        
        result = []
        for module in modules:
            result.append({
                'id': module[0],
                'code': module[1],
                'name': module[2],
                'credits': '',  # Not available in modules table
                'semester': '',  # Not available in modules table
                'type': module[3],
                'instructor': ''  # Not available in modules table
            })
        
        return result

    def add_module(self, module_data):
        """Add a new module with course association"""
        with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
            cursor = conn.cursor()

            # Extract course code from the formatted string "CODE - Name"
            course_info = module_data.get('course', '')
            course_code = course_info.split(' - ')[0] if ' - ' in course_info else course_info

            cursor.execute('''
            INSERT INTO modules (module_code, module_name, module_type, credits, semester, department)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                module_data['code'],
                module_data['name'],
                module_data['type'],
                int(module_data.get('credits', 3)),
                module_data.get('semester', 'Fall'),
                course_code
            ))

            conn.commit()

    def update_module(self, module_id, module_data):
        """Update module data"""
        with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
            cursor = conn.cursor()

            cursor.execute('''
            UPDATE modules
            SET module_code=?, module_name=?, module_type=?
            WHERE rowid=?
            ''', (module_data['code'], module_data['name'], module_data['type'], module_id))

            conn.commit()

    def delete_module(self, module_id):
        """Delete a module and handle foreign key constraints"""
        with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
            cursor = conn.cursor()

            # First, get the module_code for the module being deleted
            cursor.execute('SELECT module_code FROM modules WHERE rowid = ?', (module_id,))
            result = cursor.fetchone()
            if not result:
                raise Exception("Module not found")

            module_code = result[0]

            # Check for dependencies in various tables
            dependencies = []

            # Check module_schedule
            cursor.execute('SELECT COUNT(*) FROM module_schedule WHERE module_code = ?', (module_code,))
            if cursor.fetchone()[0] > 0:
                dependencies.append("module_schedule")

            # Check attendance if table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='attendance'")
            if cursor.fetchone():
                cursor.execute('SELECT COUNT(*) FROM attendance WHERE module_code = ?', (module_code,))
                if cursor.fetchone()[0] > 0:
                    dependencies.append("attendance")

            # Check document_repository if table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='document_repository'")
            if cursor.fetchone():
                cursor.execute('SELECT COUNT(*) FROM document_repository WHERE module_code = ?', (module_code,))
                if cursor.fetchone()[0] > 0:
                    dependencies.append("document_repository")

            # Check for other tables that might reference this module
            cursor.execute('''
            SELECT DISTINCT tbl_name FROM sqlite_master
            WHERE type='table' AND sql LIKE '%module_code%'
            AND tbl_name NOT IN ('modules', 'module_schedule', 'attendance', 'document_repository')
            ''')
            other_tables = cursor.fetchall()

            for (table_name,) in other_tables:
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM {table_name} WHERE module_code = ?', (module_code,))
                    if cursor.fetchone()[0] > 0:
                        dependencies.append(table_name)
                except Exception:
                    # Skip tables we can't query
                    pass

            # If there are dependencies, ask user what to do
            if dependencies:
                import tkinter.messagebox as mb
                response = mb.askyesnocancel(
                    "Dependencies Found",
                    f"Module {module_code} is referenced by the following tables:\n" +
                    "\n".join(f"- {dep}" for dep in dependencies) +
                    f"\n\nClick 'Yes' to delete the module and all related records.\n" +
                    f"Click 'No' to cancel deletion.\n" +
                    f"Click 'Cancel' to view dependencies first."
                )

                if response is None:  # Cancel
                    raise Exception("Deletion cancelled - dependencies exist")
                elif response is False:  # No
                    raise Exception("Deletion cancelled by user")
                else:  # Yes - proceed with cascade delete
                    # Delete related records first
                    if "module_schedule" in dependencies:
                        cursor.execute('DELETE FROM module_schedule WHERE module_code = ?', (module_code,))
                        print(f"Deleted module_schedule records for {module_code}")

                    if "attendance" in dependencies:
                        cursor.execute('DELETE FROM attendance WHERE module_code = ?', (module_code,))
                        print(f"Deleted attendance records for {module_code}")

                    if "document_repository" in dependencies:
                        cursor.execute('DELETE FROM document_repository WHERE module_code = ?', (module_code,))
                        print(f"Deleted document_repository records for {module_code}")

                    # Delete assignments and related data for this module
                    self.delete_assignments_for_module(cursor, module_code)

                    # Delete from other tables that reference this module
                    for table_name in dependencies:
                        if table_name not in ["module_schedule", "attendance", "document_repository"]:
                            try:
                                cursor.execute(f'DELETE FROM {table_name} WHERE module_code = ?', (module_code,))
                                print(f"Deleted {table_name} records for {module_code}")
                            except Exception as e:
                                print(f"Could not delete from {table_name}: {e}")

            # Finally delete the module itself
            cursor.execute('DELETE FROM modules WHERE rowid = ?', (module_id,))
            conn.commit()
            print(f"Successfully deleted module {module_code}")

    def delete_assignments_for_module(self, cursor, module_code):
        """Delete all assignments and related data for a specific module"""
        try:
            # Get all assignment IDs for this module
            cursor.execute('SELECT id FROM assignments WHERE module_code = ?', (module_code,))
            assignment_ids = [row[0] for row in cursor.fetchall()]

            if assignment_ids:
                # Delete assignment submissions first
                for assignment_id in assignment_ids:
                    cursor.execute('DELETE FROM assignment_submissions WHERE assignment_id = ?', (assignment_id,))

                # Delete peer reviews for these assignments
                for assignment_id in assignment_ids:
                    cursor.execute('DELETE FROM peer_reviews WHERE assignment_id = ?', (assignment_id,))

                # Delete extension requests for these assignments
                for assignment_id in assignment_ids:
                    cursor.execute('DELETE FROM extension_requests WHERE assignment_id = ?', (assignment_id,))

                # Delete the assignments themselves
                cursor.execute('DELETE FROM assignments WHERE module_code = ?', (module_code,))

                print(f"Deleted {len(assignment_ids)} assignments and related data for module {module_code}")

            # Also delete any assessments for this module (if assessments table exists)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='assessments'")
            if cursor.fetchone():
                cursor.execute('DELETE FROM assessments WHERE module_code = ?', (module_code,))
                print(f"Deleted assessments for module {module_code}")

        except Exception as e:
            print(f"Error deleting assignments for module {module_code}: {e}")

    def show_help(self):
        """Show user guide"""
        help_window = tk.Toplevel(self.root)
        help_window.title("User Guide")
        help_window.geometry("700x500")
        
        help_text = scrolledtext.ScrolledText(help_window, font=('Arial', 10))
        help_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        guide_content = """
ENHANCED MODULE SCHEDULING SYSTEM - USER GUIDE

OVERVIEW:
This system provides comprehensive module scheduling and timetable management
capabilities with advanced analytics, conflict detection, and reporting features.

MAIN FEATURES:

📊 DASHBOARD:
- View system statistics and overview
- Quick access to common actions
- Recent activity monitoring

📅 SCHEDULES:
- Add, edit, and delete module schedules
- Search and filter schedules
- Automatic conflict detection

🏢 ROOMS:
- Manage room information
- Track room utilization
- Room capacity and equipment details

👨‍🏫 INSTRUCTORS:
- Instructor information management
- Workload tracking and analysis
- Department organization

📋 TIMETABLES:
- Generate student and instructor timetables
- Multiple export formats (PDF, CSV, Excel, iCal)
- Conflict checking for students

📊 ANALYTICS:
- Room utilization reports
- Instructor workload analysis
- Peak usage statistics
- Visual charts and graphs

⚠️ CONFLICTS:
- Automatic conflict detection
- Room and instructor double-booking detection
- Student schedule conflict checking
- Conflict resolution tracking

💾 MANAGEMENT:
- Database backup and restore
- Data validation and repair
- Import/export capabilities
- Schedule templates

⚙️ SETTINGS:
- System configuration
- Holiday management
- Academic calendar
- Email notifications

GETTING STARTED:

1. Start by adding rooms in the Rooms tab
2. Add instructors in the Instructors tab
3. Create module schedules in the Schedules tab
4. Generate timetables in the Timetables tab
5. Use Analytics to monitor system usage
6. Check for conflicts regularly

TIPS:
- Use the search functionality to quickly find information
- Regular backups are recommended
- Check for conflicts after making schedule changes
- Use templates to save and reuse common schedule patterns

For technical support or additional features, refer to the original
command-line interface using the CLI Mode button.
        """
        
        help_text.insert(tk.END, guide_content)
        help_text.config(state=tk.DISABLED)
    
    def show_about(self):
        """Show about dialog"""
        about_text = """
Enhanced Module Scheduling System - GUI Version

A comprehensive solution for academic scheduling and timetable management.

Features:
• Advanced scheduling with conflict detection
• Analytics and reporting capabilities  
• Multiple export formats
• Data backup and validation
• Template management
• Visual charts and graphs

This GUI version maintains full backward compatibility with the original
command-line interface while providing an intuitive graphical interface.

Version: 2.0
Developer: Academic Systems Team
        """
        
        messagebox.showinfo("About", about_text)

    def refresh_modules(self):
        """Refresh the module list in the treeview"""
        # Clear existing rows
        for row in self.modules_tree.get_children():
            self.modules_tree.delete(row)

        try:
            modules = self.scheduler.get_all_modules()
        except Exception as e:
            self.log_activity(f"Error loading modules: {e}")
            return

        for m in modules:
            self.modules_tree.insert(
                "", tk.END, values=(
                    m.get("id", ""),
                    m.get("code", ""),
                    m.get("name", ""),
                    m.get("credits", ""),
                    m.get("semester", ""),
                    m.get("type", ""),
                    m.get("instructor", ""),
                )
            )

        self.log_activity("Modules refreshed")

    def get_available_courses(self):
        """Get list of available courses from the courses table"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT course_code, course_name FROM courses
                    WHERE status = 'active' AND course_code IS NOT NULL
                    AND course_code != ''
                    ORDER BY course_code
                ''')
                courses = cursor.fetchall()
                # Format as "CODE - Name" for display
                return [f"{code} - {name}" for code, name in courses] if courses else ["CS - Computer Science", "DS - Data Science"]
        except Exception as e:
            print(f"Error fetching courses: {e}")
            return ["CS - Computer Science", "DS - Data Science"]

    def show_add_module_dialog(self):
        """Dialog to add a new module with course selection"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add New Module")
        dialog.geometry("500x300")

        # Get available courses from the courses table
        available_courses = self.get_available_courses()

        fields = {
            "Code": tk.StringVar(),
            "Name": tk.StringVar(),
            "Type": tk.StringVar(),
            "Course": tk.StringVar(),
            "Credits": tk.StringVar(value="3"),
            "Semester": tk.StringVar(value="Fall"),
        }

        # Create form fields
        row = 0
        for label, var in fields.items():
            ttk.Label(dialog, text=label + ":").grid(row=row, column=0, sticky="w", padx=10, pady=5)

            if label == "Course":
                # Create dropdown for course selection
                course_combo = ttk.Combobox(dialog, textvariable=var, width=27)
                course_combo['values'] = available_courses
                course_combo.grid(row=row, column=1, padx=10, pady=5)
                if available_courses:
                    course_combo.set(available_courses[0])  # Set default selection
            elif label == "Type":
                # Create dropdown for module type
                type_combo = ttk.Combobox(dialog, textvariable=var, width=27)
                type_combo['values'] = ["Core", "Elective", "Lab", "Seminar", "Project"]
                type_combo.grid(row=row, column=1, padx=10, pady=5)
                type_combo.set("Core")  # Set default
            elif label == "Semester":
                # Create dropdown for semester
                semester_combo = ttk.Combobox(dialog, textvariable=var, width=27)
                semester_combo['values'] = ["Fall", "Spring", "Summer"]
                semester_combo.grid(row=row, column=1, padx=10, pady=5)
            else:
                ttk.Entry(dialog, textvariable=var, width=30).grid(row=row, column=1, padx=10, pady=5)
            row += 1

        def save():
            try:
                module_data = {k.lower(): v.get() for k, v in fields.items()}
                self.add_module(module_data)
                self.refresh_modules()
                self.log_activity(f"Module added: {module_data['code']} - {module_data['name']}")
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add module: {e}")

        ttk.Button(dialog, text="Save", command=save, style="Success.TButton").grid(
            row=len(fields), column=0, columnspan=2, pady=15
        )

    def edit_selected_module(self):
        """Edit the currently selected module"""
        selected = self.modules_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a module to edit.")
            return

        values = self.modules_tree.item(selected[0], "values")
        module_id = values[0]

        # Prefill with current values
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Module")
        dialog.geometry("400x200")

        fields = {
            "Code": tk.StringVar(value=values[1]),
            "Name": tk.StringVar(value=values[2]),
            "Type": tk.StringVar(value=values[5]),
        }

        for i, (label, var) in enumerate(fields.items()):
            ttk.Label(dialog, text=label + ":").grid(row=i, column=0, sticky="w", padx=10, pady=5)
            ttk.Entry(dialog, textvariable=var, width=30).grid(row=i, column=1, padx=10, pady=5)

        def save():
            try:
                updated_data = {k.lower(): v.get() for k, v in fields.items()}
                self.update_module(module_id, updated_data)
                self.refresh_modules()
                self.log_activity(f"Module updated: {updated_data['code']} - {updated_data['name']}")
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update module: {e}")

        ttk.Button(dialog, text="Save Changes", command=save, style="Success.TButton").grid(
            row=len(fields), column=0, columnspan=2, pady=15
        )

    def delete_selected_module(self):
        """Delete the selected module"""
        selected = self.modules_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a module to delete.")
            return

        values = self.modules_tree.item(selected[0], "values")
        module_id, module_code, module_name = values[0], values[1], values[2]

        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete module {module_code} - {module_name}?"
        )
        if not confirm:
            return

        try:
            self.delete_module(module_id)
            self.refresh_modules()
            self.log_activity(f"Module deleted: {module_code} - {module_name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete module: {e}")

    def filter_modules(self, *args):
        """Filter module list based on search entry"""
        query = self.module_search_var.get().lower()
        for row in self.modules_tree.get_children():
            values = self.modules_tree.item(row, "values")
            if any(query in str(v).lower() for v in values):
                self.modules_tree.reattach(row, "", "end")
            else:
                self.modules_tree.detach(row)

    def generate_module_report(self):
        """Generate a simple module report"""
        try:
            modules = self.scheduler.get_all_modules()
            if not modules:
                messagebox.showinfo("Report", "No modules available.")
                return

            report = "Module Report\n\n"
            for m in modules:
                report += f"{m.get('code')} - {m.get('name')} ({m.get('credits')} credits, Semester {m.get('semester')})\n"

            report_window = tk.Toplevel(self.root)
            report_window.title("Module Report")
            text = scrolledtext.ScrolledText(report_window, width=80, height=25)
            text.pack(fill=tk.BOTH, expand=True)
            text.insert(tk.END, report)
            text.config(state=tk.DISABLED)

            self.log_activity("Module report generated")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {e}")

    
    def update_status(self, message):
        """Update status bar message"""
        self.status_label.config(text=message)
        self.root.update()
    
    def update_activity_log(self, message):
        """Update activity log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        # Update dashboard activity
        self.activity_text.config(state=tk.NORMAL)
        self.activity_text.insert(1.0, log_entry)
        # Keep only last 100 lines
        lines = self.activity_text.get(1.0, tk.END).split('\n')
        if len(lines) > 100:
            self.activity_text.delete(1.0, tk.END)
            self.activity_text.insert(1.0, '\n'.join(lines[:100]))
        self.activity_text.config(state=tk.DISABLED)
        
        # Update management log
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(1.0, log_entry)
        lines = self.log_text.get(1.0, tk.END).split('\n')
        if len(lines) > 200:
            self.log_text.delete(1.0, tk.END)
            self.log_text.insert(1.0, '\n'.join(lines[:200]))
        self.log_text.config(state=tk.DISABLED)
    
    def _export_text_to_pdf(self, content):
        """Export text content to PDF"""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph
            from reportlab.lib.styles import getSampleStyleSheet
            
            filename = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")],
                title="Save PDF"
            )
            
            if filename:
                doc = SimpleDocTemplate(filename, pagesize=letter)
                styles = getSampleStyleSheet()
                story = []
                
                for line in content.split('\n'):
                    story.append(Paragraph(line or ' ', styles['Normal']))
                
                doc.build(story)
                messagebox.showinfo("Success", f"PDF exported to {filename}")
                
        except ImportError:
            messagebox.showerror("Error", "ReportLab library not available for PDF export.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export PDF: {str(e)}")
    
    def _export_text_to_csv(self, content):
        """Export text content to CSV"""
        try:
            import csv
            
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                title="Save CSV"
            )
            
            if filename:
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    for line in content.split('\n'):
                        if line.strip():
                            writer.writerow([line])
                
                messagebox.showinfo("Success", f"CSV exported to {filename}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export CSV: {str(e)}")
    
    def _export_text_to_excel(self, content):
        """Export text content to Excel"""
        try:
            import pandas as pd

            filename = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                title="Save Excel"
            )

            if filename:
                lines = [line for line in content.split('\n') if line.strip()]
                df = pd.DataFrame(lines, columns=['Content'])
                df.to_excel(filename, index=False)

                messagebox.showinfo("Success", f"Excel file exported to {filename}")

        except ImportError:
            messagebox.showerror("Error", "Pandas library not available for Excel export.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export Excel: {str(e)}")

    def _export_timetable_to_ical(self, timetable_data):
        """Export timetable to iCal format"""
        try:
            from datetime import datetime, timedelta
            import hashlib

            filename = filedialog.asksaveasfilename(
                defaultextension=".ics",
                filetypes=[("iCalendar files", "*.ics"), ("All files", "*.*")],
                title="Save iCalendar File"
            )

            if not filename:
                return

            # Generate iCal content
            ical_lines = [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//University Management System//Module Scheduling//EN",
                "CALSCALE:GREGORIAN",
                "METHOD:PUBLISH",
                "X-WR-CALNAME:Module Schedule",
                "X-WR-TIMEZONE:UTC"
            ]

            # Get current week's Monday as base date
            today = datetime.now()
            days_since_monday = today.weekday()
            monday = today - timedelta(days=days_since_monday)

            # Day name to offset mapping
            day_offsets = {
                'Monday': 0, 'Tuesday': 1, 'Wednesday': 2,
                'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6
            }

            # Create events for each session
            for entry in timetable_data:
                try:
                    day = entry.get('day', entry.get('day_of_week', ''))
                    start_time_str = entry.get('start_time', '')
                    end_time_str = entry.get('end_time', '')
                    module_code = entry.get('module_code', 'N/A')
                    session_type = entry.get('session_type', 'Session')
                    room = entry.get('room', 'TBA')

                    if not day or not start_time_str or not end_time_str:
                        continue

                    # Calculate the date for this event
                    day_offset = day_offsets.get(day, 0)
                    event_date = monday + timedelta(days=day_offset)

                    # Parse times
                    start_hour, start_min = map(int, start_time_str.split(':'))
                    end_hour, end_min = map(int, end_time_str.split(':'))

                    start_dt = event_date.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
                    end_dt = event_date.replace(hour=end_hour, minute=end_min, second=0, microsecond=0)

                    # Generate unique UID
                    uid_source = f"{module_code}-{day}-{start_time_str}-{end_time_str}"
                    uid = hashlib.md5(uid_source.encode()).hexdigest()

                    # Format timestamps for iCal (UTC format)
                    dtstart = start_dt.strftime("%Y%m%dT%H%M%S")
                    dtend = end_dt.strftime("%Y%m%dT%H%M%S")

                    # Add event
                    ical_lines.extend([
                        "BEGIN:VEVENT",
                        f"UID:{uid}@university.edu",
                        f"DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}",
                        f"DTSTART:{dtstart}",
                        f"DTEND:{dtend}",
                        f"SUMMARY:{module_code} - {session_type}",
                        f"LOCATION:{room}",
                        f"DESCRIPTION:{module_code} {session_type}\\nRoom: {room}",
                        "STATUS:CONFIRMED",
                        f"RRULE:FREQ=WEEKLY;COUNT=15",  # Repeat for 15 weeks (semester)
                        "END:VEVENT"
                    ])

                except Exception as e:
                    print(f"Error processing entry for iCal: {e}")
                    continue

            ical_lines.append("END:VCALENDAR")

            # Write to file
            with open(filename, 'w', encoding='utf-8') as f:
                f.write('\r\n'.join(ical_lines))

            messagebox.showinfo("Success", f"iCalendar file exported to {filename}\n\nYou can import this into Google Calendar, Outlook, Apple Calendar, or any calendar application.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export iCalendar: {str(e)}")

    def _export_timetable_to_pdf(self, timetable_data):
        """Export timetable to PDF"""
        try:
            from reportlab.lib.pagesizes import letter, landscape
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib import colors

            filename = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")],
                title="Save PDF"
            )

            if not filename:
                return

            doc = SimpleDocTemplate(filename, pagesize=landscape(letter))
            elements = []
            styles = getSampleStyleSheet()

            # Title
            title = Paragraph("Module Timetable", styles['Title'])
            elements.append(title)
            elements.append(Spacer(1, 20))

            # Convert timetable data to table format
            table_data = [['Day', 'Time', 'Module', 'Type', 'Room']]

            for entry in timetable_data:
                day = entry.get('day', entry.get('day_of_week', 'N/A'))
                time_str = f"{entry.get('start_time', '')}-{entry.get('end_time', '')}"
                module = entry.get('module_code', 'N/A')
                session_type = entry.get('session_type', 'N/A')
                room = entry.get('room', 'TBA')

                table_data.append([day, time_str, module, session_type, room])

            # Create table
            table = Table(table_data, colWidths=[100, 120, 100, 100, 120])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 14),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))

            elements.append(table)
            doc.build(elements)

            messagebox.showinfo("Success", f"PDF exported to {filename}")

        except ImportError:
            messagebox.showerror("Error", "ReportLab library not available for PDF export.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export PDF: {str(e)}")

    def _export_timetable_to_csv(self, timetable_data):
        """Export timetable to CSV"""
        try:
            import csv

            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
                title="Save CSV"
            )

            if not filename:
                return

            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Day', 'Start Time', 'End Time', 'Module Code', 'Session Type', 'Room'])

                for entry in timetable_data:
                    day = entry.get('day', entry.get('day_of_week', 'N/A'))
                    start_time = entry.get('start_time', '')
                    end_time = entry.get('end_time', '')
                    module = entry.get('module_code', 'N/A')
                    session_type = entry.get('session_type', 'N/A')
                    room = entry.get('room', 'TBA')

                    writer.writerow([day, start_time, end_time, module, session_type, room])

            messagebox.showinfo("Success", f"CSV exported to {filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export CSV: {str(e)}")

    def _export_timetable_to_excel(self, timetable_data):
        """Export timetable to Excel"""
        try:
            import pandas as pd

            filename = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                title="Save Excel"
            )

            if not filename:
                return

            # Convert to DataFrame
            data = []
            for entry in timetable_data:
                data.append({
                    'Day': entry.get('day', entry.get('day_of_week', 'N/A')),
                    'Start Time': entry.get('start_time', ''),
                    'End Time': entry.get('end_time', ''),
                    'Module Code': entry.get('module_code', 'N/A'),
                    'Session Type': entry.get('session_type', 'N/A'),
                    'Room': entry.get('room', 'TBA')
                })

            df = pd.DataFrame(data)
            df.to_excel(filename, index=False, engine='openpyxl')

            messagebox.showinfo("Success", f"Excel file exported to {filename}")

        except ImportError:
            messagebox.showerror("Error", "Pandas library not available for Excel export.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export Excel: {str(e)}")

    def on_closing(self):
        """Handle application closing"""
        if messagebox.askokcancel("Quit", "Do you want to quit the application?"):
            try:
                # Create final backup if auto-backup is enabled
                auto_backup = self.scheduler.get_system_setting('auto_backup', 'True')
                if auto_backup == 'True':
                    self.scheduler.create_backup(description="Application exit backup")

                self.root.destroy()
            except:
                self.root.destroy()

    def open_activity_log_window(self):
        """Open activity log in a new window"""
        try:
            # Create new window
            activity_window = tk.Toplevel(self.root)
            activity_window.title("Activity Log - Module Scheduling System")
            activity_window.geometry("1000x600")
            activity_window.transient(self.root)

            main_frame = ttk.Frame(activity_window, padding=10)
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Title
            title_label = ttk.Label(main_frame, text="System Activity Log", font=('Arial', 14, 'bold'))
            title_label.pack(pady=10)

            # Controls frame
            controls_frame = ttk.Frame(main_frame)
            controls_frame.pack(fill=tk.X, pady=5)

            ttk.Button(controls_frame, text="🔄 Refresh", command=lambda: self._refresh_activity_log(activity_tree)).pack(side=tk.LEFT, padx=5)
            ttk.Button(controls_frame, text="🗑️ Clear Old Logs", command=lambda: self._clear_old_activity_logs(activity_tree)).pack(side=tk.LEFT, padx=5)
            ttk.Button(controls_frame, text="📥 Export", command=lambda: self._export_activity_log()).pack(side=tk.LEFT, padx=5)

            # Activity log treeview
            tree_frame = ttk.Frame(main_frame)
            tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)

            columns = ("Timestamp", "Action", "Entity", "Details", "User")
            activity_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=20)

            for col in columns:
                activity_tree.heading(col, text=col)
                if col == "Details":
                    activity_tree.column(col, width=300)
                elif col == "Timestamp":
                    activity_tree.column(col, width=150)
                else:
                    activity_tree.column(col, width=120)

            scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=activity_tree.yview)
            activity_tree.configure(yscrollcommand=scrollbar.set)

            activity_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Load initial data
            self._refresh_activity_log(activity_tree)

            # Center window
            activity_window.update_idletasks()
            x = (activity_window.winfo_screenwidth() // 2) - (activity_window.winfo_width() // 2)
            y = (activity_window.winfo_screenheight() // 2) - (activity_window.winfo_height() // 2)
            activity_window.geometry(f"+{x}+{y}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open activity log: {str(e)}")

    def _refresh_activity_log(self, tree):
        """Refresh the activity log tree"""
        try:
            # Clear existing items
            for item in tree.get_children():
                tree.delete(item)

            # Get activity logs from database
            # Schema: id, user_id, username, action, details, timestamp, ip_address
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT timestamp, action, username, details, user_id
                    FROM activity_log
                    ORDER BY timestamp DESC
                    LIMIT 1000
                ''')
                logs = cursor.fetchall()

            for log in logs:
                timestamp, action, username, details, user_id = log
                # Parse details if JSON
                try:
                    import json
                    details_dict = json.loads(details) if details else {}
                    details_str = ', '.join([f"{k}: {v}" for k, v in details_dict.items()])
                except:
                    details_str = details if details else ''

                # Display format: Timestamp, Action, Entity (from details or action), Details, User
                entity = username or f"User {user_id}" if user_id else 'System'

                tree.insert("", tk.END, values=(
                    timestamp,
                    action,
                    entity,
                    details_str[:100] + ('...' if len(details_str) > 100 else ''),
                    username or user_id or 'System'
                ))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh activity log: {str(e)}")

    def _clear_old_activity_logs(self, tree):
        """Clear activity logs older than 30 days"""
        if not messagebox.askyesno("Confirm", "Clear activity logs older than 30 days?"):
            return

        try:
            from university_system.infrastructure.database.db import transaction
            from datetime import datetime, timedelta
            cutoff_date = (datetime.now() - timedelta(days=30)).isoformat()

            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM activity_log WHERE timestamp < ?', (cutoff_date,))
                deleted_count = cursor.rowcount

            messagebox.showinfo("Success", f"Deleted {deleted_count} old activity log entries.")
            self._refresh_activity_log(tree)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to clear old logs: {str(e)}")

    def _export_activity_log(self):
        """Export activity log to CSV"""
        try:
            from tkinter import filedialog
            import csv

            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )

            if not filename:
                return

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, user_id, username, action, details, timestamp, ip_address
                    FROM activity_log
                    ORDER BY timestamp DESC
                ''')
                logs = cursor.fetchall()

            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['ID', 'User ID', 'Username', 'Action', 'Details', 'Timestamp', 'IP Address'])
                writer.writerows(logs)

            messagebox.showinfo("Success", f"Activity log exported to {filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export activity log: {str(e)}")

    def return_to_main_menu(self):
        """Return to the main menu/GUI"""
        if messagebox.askyesno("Return to Main Menu", "Do you want to close this window and return to the main menu?"):
            try:
                # Try to open the main GUI if it exists
                try:
                    import subprocess
                    import sys
                    # Attempt to launch the main GUI
                    main_gui_path = Path(__file__).parent / 'main_gui.py'
                    if main_gui_path.exists():
                        subprocess.Popen([sys.executable, str(main_gui_path)])
                except Exception:
                    pass  # Main GUI may not exist or fail to launch

                # Close this window
                self.root.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to return to main menu: {str(e)}")

    def _migrate_database(self):
        """Migrate existing database tables to add missing columns for GUI compatibility"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Check and add missing columns to instructors table
                cursor.execute("PRAGMA table_info(instructors)")
                existing_columns = {row[1] for row in cursor.fetchall()}

                migrations = []
                if 'max_hours_per_week' not in existing_columns:
                    migrations.append("ALTER TABLE instructors ADD COLUMN max_hours_per_week INTEGER DEFAULT 40")
                if 'preferred_days' not in existing_columns:
                    migrations.append("ALTER TABLE instructors ADD COLUMN preferred_days TEXT")
                if 'preferred_times' not in existing_columns:
                    migrations.append("ALTER TABLE instructors ADD COLUMN preferred_times TEXT")
                if 'is_active' not in existing_columns:
                    migrations.append("ALTER TABLE instructors ADD COLUMN is_active BOOLEAN DEFAULT 1")
                if 'specialization' not in existing_columns:
                    migrations.append("ALTER TABLE instructors ADD COLUMN specialization TEXT DEFAULT ''")
                if 'max_courses_per_semester' not in existing_columns:
                    migrations.append("ALTER TABLE instructors ADD COLUMN max_courses_per_semester INTEGER DEFAULT 4")

                # Check if rooms table exists and add is_active column
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rooms'")
                if cursor.fetchone():
                    cursor.execute("PRAGMA table_info(rooms)")
                    existing_columns = {row[1] for row in cursor.fetchall()}
                    if 'is_active' not in existing_columns:
                        migrations.append("ALTER TABLE rooms ADD COLUMN is_active BOOLEAN DEFAULT 1")

                # Fix foreign key issues by ensuring modules table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='modules'")
                if not cursor.fetchone():
                    # Create modules table if it doesn't exist
                    cursor.execute('''
                    CREATE TABLE modules (
                        module_code TEXT PRIMARY KEY,
                        module_name TEXT NOT NULL,
                        description TEXT,
                        credits INTEGER DEFAULT 0,
                        instructor_id INTEGER,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (instructor_id) REFERENCES instructors (id)
                    )
                    ''')
                    print("Created modules table")

                # Check module_schedule table and fix foreign key references
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='module_schedule'")
                if cursor.fetchone():
                    # Check if there are any orphaned records in module_schedule
                    cursor.execute('''
                    SELECT DISTINCT module_code FROM module_schedule
                    WHERE module_code NOT IN (SELECT module_code FROM modules WHERE module_code IS NOT NULL)
                    ''')
                    orphaned_modules = cursor.fetchall()

                    # Insert missing modules
                    for (module_code,) in orphaned_modules:
                        if module_code:  # Only if module_code is not None/empty
                            cursor.execute('''
                            INSERT OR IGNORE INTO modules (module_code, module_name, is_active)
                            VALUES (?, ?, 1)
                            ''', (module_code, f"Module {module_code}"))
                            print(f"Added missing module: {module_code}")

                # Fix attendance table foreign key references
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='attendance'")
                if cursor.fetchone():
                    cursor.execute('''
                    SELECT DISTINCT module_code FROM attendance
                    WHERE module_code IS NOT NULL
                    AND module_code NOT IN (SELECT module_code FROM modules WHERE module_code IS NOT NULL)
                    ''')
                    orphaned_attendance_modules = cursor.fetchall()

                    for (module_code,) in orphaned_attendance_modules:
                        if module_code:
                            cursor.execute('''
                            INSERT OR IGNORE INTO modules (module_code, module_name, is_active)
                            VALUES (?, ?, 1)
                            ''', (module_code, f"Module {module_code}"))
                            print(f"Added missing module for attendance: {module_code}")

                # Fix document_repository table foreign key references
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='document_repository'")
                if cursor.fetchone():
                    cursor.execute('''
                    SELECT DISTINCT module_code FROM document_repository
                    WHERE module_code IS NOT NULL
                    AND module_code NOT IN (SELECT module_code FROM modules WHERE module_code IS NOT NULL)
                    ''')
                    orphaned_doc_modules = cursor.fetchall()

                    for (module_code,) in orphaned_doc_modules:
                        if module_code:
                            cursor.execute('''
                            INSERT OR IGNORE INTO modules (module_code, module_name, is_active)
                            VALUES (?, ?, 1)
                            ''', (module_code, f"Module {module_code}"))
                            print(f"Added missing module for document_repository: {module_code}")

                # Check for other tables that might reference modules
                cursor.execute('''
                SELECT DISTINCT tbl_name FROM sqlite_master
                WHERE type='table' AND sql LIKE '%module_code%'
                AND tbl_name NOT IN ('modules', 'module_schedule', 'attendance', 'document_repository')
                ''')
                other_tables = cursor.fetchall()

                for (table_name,) in other_tables:
                    try:
                        cursor.execute(f'''
                        SELECT DISTINCT module_code FROM {table_name}
                        WHERE module_code IS NOT NULL
                        AND module_code NOT IN (SELECT module_code FROM modules WHERE module_code IS NOT NULL)
                        ''')
                        orphaned_other_modules = cursor.fetchall()

                        for (module_code,) in orphaned_other_modules:
                            if module_code:
                                cursor.execute('''
                                INSERT OR IGNORE INTO modules (module_code, module_name, is_active)
                                VALUES (?, ?, 1)
                                ''', (module_code, f"Module {module_code}"))
                                print(f"Added missing module for {table_name}: {module_code}")
                    except Exception as e:
                        print(f"Could not check table {table_name}: {e}")

                # Only execute migrations if there are any needed
                if migrations:
                    # Execute all migrations
                    for migration in migrations:
                        try:
                            cursor.execute(migration)
                            print(f"GUI Migration executed: {migration}")
                        except sqlite3.Error as e:
                            # If migration fails, it might have been done already by the service
                            if "duplicate column name" in str(e).lower():
                                print(f"GUI Migration skipped (already exists): {migration}")
                            else:
                                print(f"GUI Migration failed: {migration} - {e}")

                    conn.commit()

        except Exception as e:
            print(f"GUI Migration error: {e}")

    # ==================== ADVANCED SCHEDULING FUNCTIONS ====================

    def suggest_optimal_time_slot(self, module_code, session_type, duration_minutes=60):
        """Suggest optimal time slots for a new schedule"""
        with get_connection() as conn:
            cursor = conn.cursor()

            # Get module information
            cursor.execute('SELECT module_code FROM modules WHERE module_code = ?', (module_code,))
            if not cursor.fetchone():
                messagebox.showerror("Error", f"Module {module_code} does not exist.")
                return []

            suggestions = []

            for day in DAYS_OF_WEEK:
                for time_slot in TIME_SLOTS:
                    # Calculate end time
                    start_hour, start_min = map(int, time_slot.split(':'))
                    end_time = datetime.strptime(time_slot, "%H:%M") + timedelta(minutes=duration_minutes)
                    end_time_str = end_time.strftime("%H:%M")

                    # Check availability
                    score = self._calculate_slot_score(day, time_slot, end_time_str, session_type)

                    if score > 0:  # Only suggest available slots
                        suggestions.append({
                            'day': day,
                            'start_time': time_slot,
                            'end_time': end_time_str,
                            'score': score,
                            'reasons': self._get_score_reasons(day, time_slot, session_type)
                        })

            # Sort by score (highest first)
            suggestions.sort(key=lambda x: x['score'], reverse=True)

            return suggestions[:10]  # Return top 10 suggestions

    def _calculate_slot_score(self, day, start_time, end_time, session_type):
        """Calculate a score for a time slot based on various factors"""
        with get_connection() as conn:
            cursor = conn.cursor()

            score = 100  # Start with base score

            # Check for conflicts
            cursor.execute('''
            SELECT COUNT(*) FROM module_schedule
            WHERE day_of_week = ? AND (
                (start_time < ? AND end_time > ?) OR
                (start_time < ? AND end_time > ?) OR
                (start_time >= ? AND end_time <= ?)
            )
            ''', (day, end_time, start_time, end_time, start_time, start_time, end_time))

            conflicts = cursor.fetchone()[0]
            if conflicts > 0:
                score = 0  # No score for conflicting slots
                return score

            # Bonus for popular time slots (but not too crowded)
            cursor.execute('''
            SELECT COUNT(*) FROM module_schedule
            WHERE day_of_week = ? AND start_time = ?
            ''', (day, start_time))

            same_time_count = cursor.fetchone()[0]
            if 1 <= same_time_count <= 3:  # Sweet spot
                score += 10
            elif same_time_count > 5:  # Too crowded
                score -= 20

            # Preference bonuses
            if session_type == 'Lecture' and start_time in ['09:00', '10:00', '11:00']:
                score += 15  # Morning lectures preferred
            elif session_type == 'Lab' and start_time in ['14:00', '15:00', '16:00']:
                score += 10  # Afternoon labs preferred

            # Day preferences
            if day in ['Tuesday', 'Wednesday', 'Thursday']:
                score += 5  # Mid-week preferred

            return score

    def _get_score_reasons(self, day, start_time, session_type):
        """Get human-readable reasons for the score"""
        reasons = []

        if session_type == 'Lecture' and start_time in ['09:00', '10:00', '11:00']:
            reasons.append("Good time for lectures")
        elif session_type == 'Lab' and start_time in ['14:00', '15:00', '16:00']:
            reasons.append("Preferred afternoon lab time")

        if day in ['Tuesday', 'Wednesday', 'Thursday']:
            reasons.append("Mid-week scheduling preferred")

        if start_time in ['09:00', '10:00']:
            reasons.append("Popular morning slot")

        return reasons

    def find_alternative_slots(self, day, start_time, end_time, room_type=None):
        """Find alternative time slots when conflicts occur"""
        alternatives = []

        # Try same day, different times
        for time_slot in TIME_SLOTS:
            if time_slot != start_time:
                duration = self._calculate_duration(start_time, end_time)
                alt_end = self._add_minutes_to_time(time_slot, duration)

                if self._is_slot_available(day, time_slot, alt_end):
                    alternatives.append({
                        'day': day,
                        'start_time': time_slot,
                        'end_time': alt_end,
                        'type': 'same_day'
                    })

        # Try same time, different days
        for alt_day in DAYS_OF_WEEK:
            if alt_day != day and self._is_slot_available(alt_day, start_time, end_time):
                alternatives.append({
                    'day': alt_day,
                    'start_time': start_time,
                    'end_time': end_time,
                    'type': 'same_time'
                })

        return alternatives

    def _calculate_duration(self, start_time, end_time):
        """Calculate duration in minutes between two times"""
        start = datetime.strptime(start_time, "%H:%M")
        end = datetime.strptime(end_time, "%H:%M")
        return int((end - start).total_seconds() / 60)

    def _add_minutes_to_time(self, time_str, minutes):
        """Add minutes to a time string"""
        time_obj = datetime.strptime(time_str, "%H:%M")
        new_time = time_obj + timedelta(minutes=minutes)
        return new_time.strftime("%H:%M")

    def _is_slot_available(self, day, start_time, end_time):
        """Check if a time slot is available"""
        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
            SELECT COUNT(*) FROM module_schedule
            WHERE day_of_week = ? AND (
                (start_time < ? AND end_time > ?) OR
                (start_time < ? AND end_time > ?) OR
                (start_time >= ? AND end_time <= ?)
            )
            ''', (day, end_time, start_time, end_time, start_time, start_time, end_time))

            conflicts = cursor.fetchone()[0]

            return conflicts == 0

    def schedule_module_interactively(self):
        """Interactive module scheduling wizard with optimal time slot suggestions"""
        # Create a dialog window for interactive scheduling
        dialog = tk.Toplevel(self.root)
        dialog.title("Interactive Module Scheduling Wizard")
        dialog.geometry("800x700")
        dialog.transient(self.root)
        dialog.grab_set()

        # Variables to store selections
        selected_module = tk.StringVar()
        selected_day = tk.StringVar()
        selected_session_type = tk.StringVar(value="Lecture")
        duration_var = tk.IntVar(value=60)

        # Main frame with scrollbar
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text="Module Scheduling Wizard",
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 20))

        # Step 1: Select Module
        step1_frame = ttk.LabelFrame(main_frame, text="Step 1: Select Module", padding="10")
        step1_frame.pack(fill=tk.X, pady=10)

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT module_code, module_name FROM modules ORDER BY module_code")
            modules = cursor.fetchall()

        module_options = [f"{code} - {name}" for code, name in modules]
        module_combo = ttk.Combobox(step1_frame, textvariable=selected_module,
                                   values=module_options, width=60, state='readonly')
        module_combo.pack(fill=tk.X, pady=5)
        if module_options:
            module_combo.current(0)

        # Step 2: Session Type and Duration
        step2_frame = ttk.LabelFrame(main_frame, text="Step 2: Session Type & Duration", padding="10")
        step2_frame.pack(fill=tk.X, pady=10)

        type_frame = ttk.Frame(step2_frame)
        type_frame.pack(fill=tk.X, pady=5)
        ttk.Label(type_frame, text="Session Type:").pack(side=tk.LEFT, padx=5)
        session_combo = ttk.Combobox(type_frame, textvariable=selected_session_type,
                                    values=SESSION_TYPES, width=20, state='readonly')
        session_combo.pack(side=tk.LEFT, padx=5)
        session_combo.current(0)

        duration_frame = ttk.Frame(step2_frame)
        duration_frame.pack(fill=tk.X, pady=5)
        ttk.Label(duration_frame, text="Duration (minutes):").pack(side=tk.LEFT, padx=5)
        duration_spin = ttk.Spinbox(duration_frame, from_=30, to=180, increment=15,
                                   textvariable=duration_var, width=10)
        duration_spin.pack(side=tk.LEFT, padx=5)

        # Step 3: Get Suggestions
        step3_frame = ttk.LabelFrame(main_frame, text="Step 3: Suggested Time Slots", padding="10")
        step3_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # Suggestions tree
        columns = ('Day', 'Start Time', 'End Time', 'Score', 'Reasons')
        suggestions_tree = ttk.Treeview(step3_frame, columns=columns, show='headings', height=10)

        for col in columns:
            suggestions_tree.heading(col, text=col)
            suggestions_tree.column(col, width=120 if col != 'Reasons' else 250)

        suggestions_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        # Scrollbar for suggestions
        suggestions_scroll = ttk.Scrollbar(step3_frame, orient=tk.VERTICAL,
                                          command=suggestions_tree.yview)
        suggestions_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        suggestions_tree.configure(yscrollcommand=suggestions_scroll.set)

        def get_suggestions():
            """Fetch and display suggestions"""
            suggestions_tree.delete(*suggestions_tree.get_children())

            module_text = selected_module.get()
            if not module_text:
                messagebox.showwarning("Warning", "Please select a module first.")
                return

            module_code = module_text.split(' - ')[0]
            session_type = selected_session_type.get()
            duration = duration_var.get()

            suggestions = self.suggest_optimal_time_slot(module_code, session_type, duration)

            for suggestion in suggestions:
                reasons_text = ', '.join(suggestion['reasons']) if suggestion['reasons'] else 'Available slot'
                suggestions_tree.insert('', tk.END, values=(
                    suggestion['day'],
                    suggestion['start_time'],
                    suggestion['end_time'],
                    suggestion['score'],
                    reasons_text
                ))

        # Get Suggestions button
        suggest_btn = ttk.Button(step3_frame, text="Get Optimal Time Slots",
                                command=get_suggestions, style='Action.TButton')
        suggest_btn.pack(pady=5)

        # Step 4: Finalize Scheduling
        step4_frame = ttk.LabelFrame(main_frame, text="Step 4: Finalize Schedule", padding="10")
        step4_frame.pack(fill=tk.X, pady=10)

        # Room and Instructor selection
        room_var = tk.StringVar()
        instructor_var = tk.StringVar()

        room_frame = ttk.Frame(step4_frame)
        room_frame.pack(fill=tk.X, pady=5)
        ttk.Label(room_frame, text="Room:").pack(side=tk.LEFT, padx=5)

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, building, room_number, room_type FROM rooms WHERE is_active = 1")
            rooms = cursor.fetchall()

        room_options = [f"{building}-{room_num} ({room_type})" for _, building, room_num, room_type in rooms]
        room_combo = ttk.Combobox(room_frame, textvariable=room_var,
                                 values=room_options, width=40, state='readonly')
        room_combo.pack(side=tk.LEFT, padx=5)
        if room_options:
            room_combo.current(0)

        instructor_frame = ttk.Frame(step4_frame)
        instructor_frame.pack(fill=tk.X, pady=5)
        ttk.Label(instructor_frame, text="Instructor:").pack(side=tk.LEFT, padx=5)

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, first_name, last_name, department FROM instructors WHERE is_active = 1")
            instructors = cursor.fetchall()

        instructor_options = [f"{first} {last} ({dept})" for _, first, last, dept in instructors]
        instructor_combo = ttk.Combobox(instructor_frame, textvariable=instructor_var,
                                       values=instructor_options, width=40, state='readonly')
        instructor_combo.pack(side=tk.LEFT, padx=5)
        if instructor_options:
            instructor_combo.current(0)

        def schedule_selected():
            """Schedule the module with selected time slot"""
            selection = suggestions_tree.selection()
            if not selection:
                messagebox.showwarning("Warning", "Please select a suggested time slot.")
                return

            item = suggestions_tree.item(selection[0])
            values = item['values']

            module_text = selected_module.get()
            module_code = module_text.split(' - ')[0]

            day = values[0]
            start_time = values[1]
            end_time = values[2]
            session_type = selected_session_type.get()

            # Get room and instructor IDs
            room_idx = room_combo.current()
            instructor_idx = instructor_combo.current()

            if room_idx < 0 or instructor_idx < 0:
                messagebox.showwarning("Warning", "Please select both room and instructor.")
                return

            room_id = rooms[room_idx][0]
            instructor_id = instructors[instructor_idx][0]

            # Add the schedule
            try:
                self.scheduler.add_module_schedule(
                    module_code, day, start_time, end_time,
                    room_id, instructor_id, session_type
                )
                messagebox.showinfo("Success", "Module scheduled successfully!")
                self.refresh_all_data()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to schedule module: {str(e)}")

        # Bottom buttons
        button_frame = ttk.Frame(step4_frame)
        button_frame.pack(fill=tk.X, pady=10)

        schedule_btn = ttk.Button(button_frame, text="Schedule Selected Slot",
                                 command=schedule_selected, style='Success.TButton')
        schedule_btn.pack(side=tk.LEFT, padx=5)

        cancel_btn = ttk.Button(button_frame, text="Cancel",
                               command=dialog.destroy)
        cancel_btn.pack(side=tk.LEFT, padx=5)


# Dialog classes for adding/editing data
class AddScheduleDialog:
    def __init__(self, parent, scheduler):
        self.parent = parent
        self.scheduler = scheduler
        self.result = False
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add New Schedule")
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)

        self.create_widgets()
        self.center_window()

        # Set grab after window is fully initialized and visible
        self.dialog.update_idletasks()  # Ensure window is ready
        try:
            self.dialog.grab_set()
        except tk.TclError:
            # If grab fails, continue without it - dialog will still work
            pass
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Module selection
        ttk.Label(main_frame, text="Module Code:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.module_var = tk.StringVar()
        module_combo = ttk.Combobox(main_frame, textvariable=self.module_var, width=30)
        
        # Load modules
        try:
            modules = self.scheduler._get_known_modules()
            module_combo['values'] = list(modules.keys())
        except:
            pass
        
        module_combo.grid(row=0, column=1, pady=5, sticky=tk.W)
        
        # Day of week
        ttk.Label(main_frame, text="Day of Week:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.day_var = tk.StringVar()
        day_combo = ttk.Combobox(main_frame, textvariable=self.day_var, values=DAYS_OF_WEEK, width=30)
        day_combo.grid(row=1, column=1, pady=5, sticky=tk.W)
        
        # Time
        ttk.Label(main_frame, text="Start Time:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.start_time_var = tk.StringVar()
        start_combo = ttk.Combobox(main_frame, textvariable=self.start_time_var, values=TIME_SLOTS, width=30)
        start_combo.grid(row=2, column=1, pady=5, sticky=tk.W)
        
        ttk.Label(main_frame, text="End Time:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.end_time_var = tk.StringVar()
        end_combo = ttk.Combobox(main_frame, textvariable=self.end_time_var, values=TIME_SLOTS, width=30)
        end_combo.grid(row=3, column=1, pady=5, sticky=tk.W)
        
        # Room
        ttk.Label(main_frame, text="Room:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.room_var = tk.StringVar()
        room_combo = ttk.Combobox(main_frame, textvariable=self.room_var, width=30)
        
        # Load rooms
        try:
            from university_system.infrastructure.database.db import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT id, building, room_number FROM rooms WHERE is_active = 1')
                rooms = cursor.fetchall()
            
            room_values = [f"{room[0]} - {room[1]}-{room[2]}" for room in rooms]
            room_combo['values'] = room_values
        except:
            pass
        
        room_combo.grid(row=4, column=1, pady=5, sticky=tk.W)
        
        # Instructor
        ttk.Label(main_frame, text="Instructor:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.instructor_var = tk.StringVar()
        instructor_combo = ttk.Combobox(main_frame, textvariable=self.instructor_var, width=30)
        
        # Load instructors
        try:
            from university_system.infrastructure.database.db import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, first_name, last_name FROM instructors WHERE CASE WHEN status = 'Active' THEN 1 ELSE COALESCE(is_active, 1) END = 1")
                instructors = cursor.fetchall()
            
            instructor_values = [f"{inst[0]} - {inst[1]} {inst[2]}" for inst in instructors]
            instructor_combo['values'] = instructor_values
        except:
            pass
        
        instructor_combo.grid(row=5, column=1, pady=5, sticky=tk.W)
        
        # Session type
        ttk.Label(main_frame, text="Session Type:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.session_type_var = tk.StringVar()
        session_combo = ttk.Combobox(main_frame, textvariable=self.session_type_var, values=SESSION_TYPES, width=30)
        session_combo.grid(row=6, column=1, pady=5, sticky=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=7, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Save", command=self.save_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def save_schedule(self):
        try:
            module_code = self.module_var.get()
            day = self.day_var.get()
            start_time = self.start_time_var.get()
            end_time = self.end_time_var.get()
            room_str = self.room_var.get()
            instructor_str = self.instructor_var.get()
            session_type = self.session_type_var.get()
            
            if not all([module_code, day, start_time, end_time, room_str, instructor_str, session_type]):
                messagebox.showerror("Error", "Please fill in all fields.")
                return
            
            # Extract IDs
            room_id = int(room_str.split(' - ')[0])
            instructor_id = int(instructor_str.split(' - ')[0])
            
            # Save schedule
            success = self.scheduler.add_module_schedule(
                module_code, day, start_time, end_time, room_id, instructor_id, session_type
            )
            
            if success:
                self.result = True
                self.dialog.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save schedule: {str(e)}")
    
    def center_window(self):
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class AddRoomDialog:
    def __init__(self, parent, scheduler):
        self.parent = parent
        self.scheduler = scheduler
        self.result = False
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add New Room")
        self.dialog.geometry("400x500")
        self.dialog.transient(parent)

        self.create_widgets()
        self.center_window()

        # Set grab after window is fully initialized and visible
        self.dialog.update_idletasks()  # Ensure window is ready
        try:
            self.dialog.grab_set()
        except tk.TclError:
            # If grab fails, continue without it - dialog will still work
            pass
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Room number
        ttk.Label(main_frame, text="Room Number:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.room_number_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.room_number_var, width=30).grid(row=0, column=1, pady=5)
        
        # Building
        ttk.Label(main_frame, text="Building:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.building_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.building_var, width=30).grid(row=1, column=1, pady=5)
        
        # Capacity
        ttk.Label(main_frame, text="Capacity:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.capacity_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.capacity_var, width=30).grid(row=2, column=1, pady=5)
        
        # Room type
        ttk.Label(main_frame, text="Room Type:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.room_type_var = tk.StringVar()
        ttk.Combobox(main_frame, textvariable=self.room_type_var, values=ROOM_TYPES, width=27).grid(row=3, column=1, pady=5)
        
        # Equipment
        ttk.Label(main_frame, text="Equipment:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.equipment_var = tk.StringVar()
        equipment_entry = tk.Text(main_frame, width=30, height=3)
        equipment_entry.grid(row=4, column=1, pady=5)
        self.equipment_text = equipment_entry
        
        # Notes
        ttk.Label(main_frame, text="Notes:").grid(row=5, column=0, sticky=tk.W, pady=5)
        notes_entry = tk.Text(main_frame, width=30, height=3)
        notes_entry.grid(row=5, column=1, pady=5)
        self.notes_text = notes_entry
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Save", command=self.save_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def save_room(self):
        try:
            room_number = self.room_number_var.get()
            building = self.building_var.get()
            capacity = int(self.capacity_var.get())
            room_type = self.room_type_var.get()
            equipment = self.equipment_text.get(1.0, tk.END).strip()
            notes = self.notes_text.get(1.0, tk.END).strip()
            
            if not all([room_number, building, str(capacity), room_type]):
                messagebox.showerror("Error", "Please fill in all required fields.")
                return
            
            room_id = self.scheduler.add_room(room_number, building, capacity, room_type, equipment, notes)
            
            if room_id:
                self.result = True
                self.dialog.destroy()
            
        except ValueError:
            messagebox.showerror("Error", "Capacity must be a number.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save room: {str(e)}")
    
    def center_window(self):
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class AddInstructorDialog:
    def __init__(self, parent, scheduler):
        self.parent = parent
        self.scheduler = scheduler
        self.result = False
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add New Instructor")
        self.dialog.geometry("500x550")
        self.dialog.transient(parent)

        self.create_widgets()
        self.center_window()

        # Set grab after window is fully initialized and visible
        self.dialog.update_idletasks()  # Ensure window is ready
        try:
            self.dialog.grab_set()
        except tk.TclError:
            # If grab fails, continue without it - dialog will still work
            pass
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Personal Information
        personal_frame = ttk.LabelFrame(main_frame, text="Personal Information", padding=10)
        personal_frame.pack(fill=tk.X, pady=5)

        ttk.Label(personal_frame, text="First Name:").grid(row=0, column=0, sticky=tk.W)
        self.first_name_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.first_name_var, width=25).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(personal_frame, text="Last Name:").grid(row=1, column=0, sticky=tk.W)
        self.last_name_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.last_name_var, width=25).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(personal_frame, text="Email:").grid(row=2, column=0, sticky=tk.W)
        self.email_var = tk.StringVar()
        ttk.Entry(personal_frame, textvariable=self.email_var, width=35).grid(row=2, column=1, sticky=tk.W, padx=5)

        # Professional Information
        prof_frame = ttk.LabelFrame(main_frame, text="Professional Information", padding=10)
        prof_frame.pack(fill=tk.X, pady=5)

        ttk.Label(prof_frame, text="Department:").grid(row=0, column=0, sticky=tk.W)
        self.department_var = tk.StringVar()
        ttk.Entry(prof_frame, textvariable=self.department_var, width=25).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(prof_frame, text="Specialization:").grid(row=1, column=0, sticky=tk.W)
        self.specialization_var = tk.StringVar()
        ttk.Entry(prof_frame, textvariable=self.specialization_var, width=35).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(prof_frame, text="Max Courses/Semester:").grid(row=2, column=0, sticky=tk.W)
        self.max_courses_var = tk.StringVar(value="4")
        ttk.Entry(prof_frame, textvariable=self.max_courses_var, width=10).grid(row=2, column=1, sticky=tk.W, padx=5)

        ttk.Label(prof_frame, text="Max Hours/Week:").grid(row=3, column=0, sticky=tk.W)
        self.max_hours_var = tk.StringVar(value="40")
        ttk.Entry(prof_frame, textvariable=self.max_hours_var, width=10).grid(row=3, column=1, sticky=tk.W, padx=5)

        # Scheduling Preferences
        sched_frame = ttk.LabelFrame(main_frame, text="Scheduling Preferences", padding=10)
        sched_frame.pack(fill=tk.X, pady=5)

        ttk.Label(sched_frame, text="Preferred Days:").grid(row=0, column=0, sticky=tk.W)
        self.preferred_days_var = tk.StringVar()
        ttk.Entry(sched_frame, textvariable=self.preferred_days_var, width=35).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Label(sched_frame, text="(comma-separated, e.g., Monday,Tuesday)", font=('Arial', 8)).grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(sched_frame, text="Preferred Times:").grid(row=2, column=0, sticky=tk.W)
        self.preferred_times_var = tk.StringVar()
        ttk.Entry(sched_frame, textvariable=self.preferred_times_var, width=35).grid(row=2, column=1, sticky=tk.W, padx=5)
        ttk.Label(sched_frame, text="(comma-separated, e.g., 09:00,10:00)", font=('Arial', 8)).grid(row=3, column=1, sticky=tk.W, padx=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Add Instructor", command=self.save_instructor).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def save_instructor(self):
        try:
            # Validate inputs
            first_name = self.first_name_var.get().strip()
            last_name = self.last_name_var.get().strip()
            email = self.email_var.get().strip()

            if not first_name or not last_name or not email:
                messagebox.showerror("Validation Error", "First name, last name, and email are required.")
                return

            # Validate email format
            import re
            email_pattern = r'^[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}$'
            if not re.match(email_pattern, email):
                messagebox.showerror("Validation Error", "Please enter a valid email address.")
                return

            department = self.department_var.get().strip()
            specialization = self.specialization_var.get().strip()

            try:
                max_courses = int(self.max_courses_var.get())
            except ValueError:
                messagebox.showerror("Validation Error", "Max courses must be a number.")
                return

            try:
                max_hours = int(self.max_hours_var.get())
            except ValueError:
                messagebox.showerror("Validation Error", "Max hours must be a number.")
                return

            preferred_days = self.preferred_days_var.get().strip()
            preferred_times = self.preferred_times_var.get().strip()

            # Use database directly instead of scheduler method for consistency
            from university_system.infrastructure.database.db import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Check for duplicate email
                cursor.execute("SELECT email FROM instructors WHERE email = ?", (email,))
                if cursor.fetchone():
                    messagebox.showerror("Duplicate Error", f"Email '{email}' already exists.")
                    return

                from datetime import datetime
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO instructors (first_name, last_name, email, department, specialization,
                                       max_courses_per_semester, max_hours_per_week, preferred_days,
                                       preferred_times, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (first_name, last_name, email, department, specialization, max_courses,
                      max_hours, preferred_days, preferred_times, timestamp, timestamp))

                conn.commit()

            self.result = True
            messagebox.showinfo("Success", f"Instructor {first_name} {last_name} added successfully.")
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save instructor: {str(e)}")
    
    def center_window(self):
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class EditScheduleDialog:
    def __init__(self, parent, scheduler, schedule_id):
        self.parent = parent
        self.scheduler = scheduler
        self.schedule_id = schedule_id
        self.result = False
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Schedule")
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)

        self.load_current_data()
        self.create_widgets()
        self.center_window()

        # Set grab after window is fully initialized and visible
        self.dialog.update_idletasks()  # Ensure window is ready
        try:
            self.dialog.grab_set()
        except tk.TclError:
            # If grab fails, continue without it - dialog will still work
            pass
    
    def load_current_data(self):
        """Load current schedule data"""
        try:
            from university_system.infrastructure.database.db import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT module_code, day_of_week, start_time, end_time, room_id, instructor_id, session_type
                FROM module_schedule WHERE id = ?
                ''', (self.schedule_id,))

                schedule = cursor.fetchone()
            
            if schedule:
                self.current_data = {
                    'module_code': schedule[0],
                    'day_of_week': schedule[1],
                    'start_time': schedule[2],
                    'end_time': schedule[3],
                    'room_id': schedule[4],
                    'instructor_id': schedule[5],
                    'session_type': schedule[6]
                }
            else:
                raise Exception("Schedule not found")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load schedule data: {str(e)}")
            self.dialog.destroy()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Module selection
        ttk.Label(main_frame, text="Module Code:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.module_var = tk.StringVar(value=self.current_data['module_code'])
        module_combo = ttk.Combobox(main_frame, textvariable=self.module_var, width=30)
        
        # Load modules
        try:
            modules = self.scheduler._get_known_modules()
            module_combo['values'] = list(modules.keys())
        except:
            pass
        
        module_combo.grid(row=0, column=1, pady=5, sticky=tk.W)
        
        # Day of week
        ttk.Label(main_frame, text="Day of Week:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.day_var = tk.StringVar(value=self.current_data['day_of_week'])
        day_combo = ttk.Combobox(main_frame, textvariable=self.day_var, values=DAYS_OF_WEEK, width=30)
        day_combo.grid(row=1, column=1, pady=5, sticky=tk.W)
        
        # Time
        ttk.Label(main_frame, text="Start Time:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.start_time_var = tk.StringVar(value=self.current_data['start_time'])
        start_combo = ttk.Combobox(main_frame, textvariable=self.start_time_var, values=TIME_SLOTS, width=30)
        start_combo.grid(row=2, column=1, pady=5, sticky=tk.W)
        
        ttk.Label(main_frame, text="End Time:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.end_time_var = tk.StringVar(value=self.current_data['end_time'])
        end_combo = ttk.Combobox(main_frame, textvariable=self.end_time_var, values=TIME_SLOTS, width=30)
        end_combo.grid(row=3, column=1, pady=5, sticky=tk.W)
        
        # Room
        ttk.Label(main_frame, text="Room:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.room_var = tk.StringVar()
        room_combo = ttk.Combobox(main_frame, textvariable=self.room_var, width=30)
        
        # Load rooms and set current
        try:
            from university_system.infrastructure.database.db import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT id, building, room_number FROM rooms WHERE is_active = 1')
                rooms = cursor.fetchall()
            
            room_values = [f"{room[0]} - {room[1]}-{room[2]}" for room in rooms]
            room_combo['values'] = room_values
            
            # Set current room
            for room in rooms:
                if room[0] == self.current_data['room_id']:
                    self.room_var.set(f"{room[0]} - {room[1]}-{room[2]}")
                    break
        except:
            pass
        
        room_combo.grid(row=4, column=1, pady=5, sticky=tk.W)
        
        # Instructor
        ttk.Label(main_frame, text="Instructor:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.instructor_var = tk.StringVar()
        instructor_combo = ttk.Combobox(main_frame, textvariable=self.instructor_var, width=30)
        
        # Load instructors and set current
        try:
            from university_system.infrastructure.database.db import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, first_name, last_name FROM instructors WHERE CASE WHEN status = 'Active' THEN 1 ELSE COALESCE(is_active, 1) END = 1")
                instructors = cursor.fetchall()
            
            instructor_values = [f"{inst[0]} - {inst[1]} {inst[2]}" for inst in instructors]
            instructor_combo['values'] = instructor_values
            
            # Set current instructor
            for inst in instructors:
                if inst[0] == self.current_data['instructor_id']:
                    self.instructor_var.set(f"{inst[0]} - {inst[1]} {inst[2]}")
                    break
        except:
            pass
        
        instructor_combo.grid(row=5, column=1, pady=5, sticky=tk.W)
        
        # Session type
        ttk.Label(main_frame, text="Session Type:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.session_type_var = tk.StringVar(value=self.current_data['session_type'])
        session_combo = ttk.Combobox(main_frame, textvariable=self.session_type_var, values=SESSION_TYPES, width=30)
        session_combo.grid(row=6, column=1, pady=5, sticky=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=7, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Update", command=self.update_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def update_schedule(self):
        try:
            # Get new values
            updates = {}

            if self.day_var.get() != self.current_data['day_of_week']:
                updates['day_of_week'] = self.day_var.get()

            if self.start_time_var.get() != self.current_data['start_time']:
                updates['start_time'] = self.start_time_var.get()

            if self.end_time_var.get() != self.current_data['end_time']:
                updates['end_time'] = self.end_time_var.get()

            room_str = self.room_var.get()
            if room_str:
                room_id = int(room_str.split(' - ')[0])
                if room_id != self.current_data['room_id']:
                    updates['room_id'] = room_id

            instructor_str = self.instructor_var.get()
            if instructor_str:
                instructor_id = int(instructor_str.split(' - ')[0])
                if instructor_id != self.current_data['instructor_id']:
                    updates['instructor_id'] = instructor_id

            if self.session_type_var.get() != self.current_data['session_type']:
                updates['session_type'] = self.session_type_var.get()

            if not updates:
                messagebox.showinfo("Info", "No changes detected.")
                return

            # Update schedule
            success = self.scheduler.update_module_schedule(self.schedule_id, **updates)

            if success:
                # Send email notifications for schedule changes
                try:
                    from university_system.infrastructure.email.email_service import send_schedule_change_notification

                    # Prepare new_data by merging current_data with updates
                    new_data = self.current_data.copy()
                    new_data.update(updates)

                    # Send notifications (runs in background, won't block UI)
                    import threading
                    notification_thread = threading.Thread(
                        target=send_schedule_change_notification,
                        args=(self.schedule_id, self.current_data, new_data)
                    )
                    notification_thread.daemon = True
                    notification_thread.start()

                except Exception as email_error:
                    print(f"Warning: Could not send email notifications: {email_error}")
                    # Don't fail the update if email fails

                self.result = True
                self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update schedule: {str(e)}")
    
    def center_window(self):
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class EditRoomDialog:
    def __init__(self, parent, scheduler, room_id):
        self.parent = parent
        self.scheduler = scheduler
        self.room_id = room_id
        self.result = False
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Room")
        self.dialog.geometry("400x500")
        self.dialog.transient(parent)

        self.load_current_data()
        self.create_widgets()
        self.center_window()

        # Set grab after window is fully initialized and visible
        self.dialog.update_idletasks()  # Ensure window is ready
        try:
            self.dialog.grab_set()
        except tk.TclError:
            # If grab fails, continue without it - dialog will still work
            pass
    
    def load_current_data(self):
        """Load current room data"""
        try:
            from university_system.infrastructure.database.db import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute('SELECT * FROM rooms WHERE id = ?', (self.room_id,))
                room = cursor.fetchone()
            
            if room:
                self.current_data = {
                    'room_number': room[1],
                    'building': room[2],
                    'capacity': room[3],
                    'room_type': room[4],
                    'equipment': room[5] or "",
                    'notes': room[6] or ""
                }
            else:
                raise Exception("Room not found")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load room data: {str(e)}")
            self.dialog.destroy()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Room number (read-only)
        ttk.Label(main_frame, text="Room Number:").grid(row=0, column=0, sticky=tk.W, pady=5)
        room_label = ttk.Label(main_frame, text=self.current_data['room_number'], font=('Arial', 10, 'bold'))
        room_label.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        # Building (read-only)
        ttk.Label(main_frame, text="Building:").grid(row=1, column=0, sticky=tk.W, pady=5)
        building_label = ttk.Label(main_frame, text=self.current_data['building'], font=('Arial', 10, 'bold'))
        building_label.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # Capacity
        ttk.Label(main_frame, text="Capacity:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.capacity_var = tk.StringVar(value=str(self.current_data['capacity']))
        ttk.Entry(main_frame, textvariable=self.capacity_var, width=30).grid(row=2, column=1, pady=5)
        
        # Room type
        ttk.Label(main_frame, text="Room Type:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.room_type_var = tk.StringVar(value=self.current_data['room_type'])
        ttk.Combobox(main_frame, textvariable=self.room_type_var, values=ROOM_TYPES, width=27).grid(row=3, column=1, pady=5)
        
        # Equipment
        ttk.Label(main_frame, text="Equipment:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.equipment_text = tk.Text(main_frame, width=30, height=3)
        self.equipment_text.grid(row=4, column=1, pady=5)
        self.equipment_text.insert(1.0, self.current_data['equipment'])
        
        # Notes
        ttk.Label(main_frame, text="Notes:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.notes_text = tk.Text(main_frame, width=30, height=3)
        self.notes_text.grid(row=5, column=1, pady=5)
        self.notes_text.insert(1.0, self.current_data['notes'])
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Update", command=self.update_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def update_room(self):
        try:
            new_capacity = int(self.capacity_var.get())
            new_equipment = self.equipment_text.get(1.0, tk.END).strip()
            new_notes = self.notes_text.get(1.0, tk.END).strip()

            from university_system.infrastructure.database.db import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                UPDATE rooms SET capacity = ?, equipment = ?, notes = ? WHERE id = ?
                ''', (new_capacity, new_equipment, new_notes, self.room_id))

                conn.commit()
            
            self.result = True
            self.dialog.destroy()
            messagebox.showinfo("Success", "Room updated successfully.")
            
        except ValueError:
            messagebox.showerror("Error", "Capacity must be a number.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update room: {str(e)}")
    
    def center_window(self):
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class EditInstructorDialog:
    def __init__(self, parent, scheduler, instructor_id):
        self.parent = parent
        self.scheduler = scheduler
        self.instructor_id = instructor_id
        self.result = False
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Instructor")
        self.dialog.geometry("400x500")
        self.dialog.transient(parent)

        self.load_current_data()
        self.create_widgets()
        self.center_window()

        # Set grab after window is fully initialized and visible
        self.dialog.update_idletasks()  # Ensure window is ready
        try:
            self.dialog.grab_set()
        except tk.TclError:
            # If grab fails, continue without it - dialog will still work
            pass
    
    def load_current_data(self):
        """Load current instructor data"""
        try:
            from university_system.infrastructure.database.db import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT id, first_name, last_name, email, department,
                       COALESCE(max_hours_per_week, max_courses_per_semester * 8, 40) as max_hours_per_week,
                       preferred_days, preferred_times
                FROM instructors WHERE id = ?
                ''', (self.instructor_id,))
                instructor = cursor.fetchone()
            
            if instructor:
                self.current_data = {
                    'first_name': instructor[1],
                    'last_name': instructor[2],
                    'email': instructor[3],
                    'department': instructor[4],
                    'max_hours_per_week': instructor[5],
                    'preferred_days': instructor[6] or "",
                    'preferred_times': instructor[7] or ""
                }
            else:
                raise Exception("Instructor not found")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load instructor data: {str(e)}")
            self.dialog.destroy()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Name (read-only)
        ttk.Label(main_frame, text="Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        name_label = ttk.Label(main_frame, text=f"{self.current_data['first_name']} {self.current_data['last_name']}", 
                              font=('Arial', 10, 'bold'))
        name_label.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        # Email
        ttk.Label(main_frame, text="Email:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.email_var = tk.StringVar(value=self.current_data['email'])
        ttk.Entry(main_frame, textvariable=self.email_var, width=30).grid(row=1, column=1, pady=5)
        
        # Department
        ttk.Label(main_frame, text="Department:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.department_var = tk.StringVar(value=self.current_data['department'])
        ttk.Entry(main_frame, textvariable=self.department_var, width=30).grid(row=2, column=1, pady=5)
        
        # Max hours
        ttk.Label(main_frame, text="Max Hours/Week:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.max_hours_var = tk.StringVar(value=str(self.current_data['max_hours_per_week']))
        ttk.Entry(main_frame, textvariable=self.max_hours_var, width=30).grid(row=3, column=1, pady=5)
        
        # Preferred days
        ttk.Label(main_frame, text="Preferred Days:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.preferred_days_var = tk.StringVar(value=self.current_data['preferred_days'])
        ttk.Entry(main_frame, textvariable=self.preferred_days_var, width=30).grid(row=4, column=1, pady=5)
        
        # Preferred times
        ttk.Label(main_frame, text="Preferred Times:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.preferred_times_var = tk.StringVar(value=self.current_data['preferred_times'])
        ttk.Entry(main_frame, textvariable=self.preferred_times_var, width=30).grid(row=5, column=1, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Update", command=self.update_instructor).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def update_instructor(self):
        try:
            new_email = self.email_var.get()
            new_department = self.department_var.get()
            new_max_hours = int(self.max_hours_var.get())
            new_preferred_days = self.preferred_days_var.get()
            new_preferred_times = self.preferred_times_var.get()

            from university_system.infrastructure.database.db import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Check which column exists for max hours
                cursor.execute("PRAGMA table_info(instructors)")
                columns = [column[1] for column in cursor.fetchall()]

                if 'max_hours_per_week' in columns:
                    cursor.execute('''
                    UPDATE instructors
                    SET email = ?, department = ?, max_hours_per_week = ?, preferred_days = ?, preferred_times = ?
                    WHERE id = ?
                    ''', (new_email, new_department, new_max_hours, new_preferred_days, new_preferred_times, self.instructor_id))
                elif 'max_courses_per_semester' in columns:
                    # Convert hours to courses (assuming 8 hours per course)
                    max_courses = max(1, round(float(new_max_hours) / 8))
                    cursor.execute('''
                    UPDATE instructors
                    SET email = ?, department = ?, max_courses_per_semester = ?, preferred_days = ?, preferred_times = ?
                    WHERE id = ?
                    ''', (new_email, new_department, max_courses, new_preferred_days, new_preferred_times, self.instructor_id))
                else:
                    # Fallback - update without max hours column
                    cursor.execute('''
                    UPDATE instructors
                    SET email = ?, department = ?, preferred_days = ?, preferred_times = ?
                    WHERE id = ?
                    ''', (new_email, new_department, new_preferred_days, new_preferred_times, self.instructor_id))

                conn.commit()
            
            self.result = True
            self.dialog.destroy()
            messagebox.showinfo("Success", "Instructor updated successfully.")
            
        except ValueError:
            messagebox.showerror("Error", "Max hours must be a number.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update instructor: {str(e)}")
    
    def center_window(self):
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class AddHolidayDialog:
    def __init__(self, parent, scheduler):
        self.parent = parent
        self.scheduler = scheduler
        self.result = False
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add Holiday")
        self.dialog.geometry("400x350")
        self.dialog.transient(parent)

        self.create_widgets()
        self.center_window()

        # Set grab after window is fully initialized and visible
        self.dialog.update_idletasks()  # Ensure window is ready
        try:
            self.dialog.grab_set()
        except tk.TclError:
            # If grab fails, continue without it - dialog will still work
            pass
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Holiday name
        ttk.Label(main_frame, text="Holiday Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var, width=30).grid(row=0, column=1, pady=5)
        
        # Start date
        ttk.Label(main_frame, text="Start Date:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.start_date_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.start_date_var, width=30).grid(row=1, column=1, pady=5)
        ttk.Label(main_frame, text="(YYYY-MM-DD format)", font=('Arial', 8)).grid(row=1, column=2, sticky=tk.W)
        
        # End date
        ttk.Label(main_frame, text="End Date:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.end_date_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.end_date_var, width=30).grid(row=2, column=1, pady=5)
        ttk.Label(main_frame, text="(leave blank if same as start)", font=('Arial', 8)).grid(row=2, column=2, sticky=tk.W)
        
        # Description
        ttk.Label(main_frame, text="Description:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.description_text = tk.Text(main_frame, width=30, height=3)
        self.description_text.grid(row=3, column=1, pady=5)
        
        # Recurring
        self.recurring_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Recurring annually", variable=self.recurring_var).grid(row=4, column=1, sticky=tk.W, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=3, pady=20)
        
        ttk.Button(button_frame, text="Save", command=self.save_holiday).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def save_holiday(self):
        try:
            name = self.name_var.get()
            start_date = self.start_date_var.get()
            end_date = self.end_date_var.get() or start_date
            description = self.description_text.get(1.0, tk.END).strip()
            recurring = self.recurring_var.get()
            
            if not all([name, start_date]):
                messagebox.showerror("Error", "Please fill in name and start date.")
                return
            
            # Validate date format
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
                if end_date != start_date:
                    datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD.")
                return
            
            self.scheduler.add_holiday(name, start_date, end_date, description, recurring)
            
            self.result = True
            self.dialog.destroy()
            messagebox.showinfo("Success", "Holiday added successfully.")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save holiday: {str(e)}")
    
    def center_window(self):
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")


class GridViewWindow:
    def __init__(self, parent, scheduler):
        self.parent = parent
        self.scheduler = scheduler
        
        self.window = tk.Toplevel(parent)
        self.window.title("Schedule Grid View")
        self.window.geometry("1200x800")
        self.window.transient(parent)
        
        self.create_grid_view()
        self.center_window()
    
    def create_grid_view(self):
        main_frame = ttk.Frame(self.window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Weekly Schedule Grid View", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)
        
        # Create grid frame with scrollbars
        grid_frame = ttk.Frame(main_frame)
        grid_frame.pack(fill=tk.BOTH, expand=True)
        
        # Canvas for scrolling
        canvas = tk.Canvas(grid_frame)
        v_scrollbar = ttk.Scrollbar(grid_frame, orient=tk.VERTICAL, command=canvas.yview)
        h_scrollbar = ttk.Scrollbar(grid_frame, orient=tk.HORIZONTAL, command=canvas.xview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Create the actual grid
        self.create_schedule_grid(scrollable_frame)
        
        # Pack scrollbars and canvas
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def create_schedule_grid(self, parent_frame):
        """Create the schedule grid with proper boxes"""
        try:
            # Get all schedules
            from university_system.infrastructure.database.db import sqlite3
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT ms.module_code, ms.day_of_week, ms.start_time, ms.end_time,
                       r.building, r.room_number, ms.session_type
                FROM module_schedule ms
                LEFT JOIN rooms r ON ms.room_id = r.id
                ORDER BY ms.day_of_week, ms.start_time
                ''')

                schedules = cursor.fetchall()

            # Create grid data structure
            grid_data = {}
            for day in DAYS_OF_WEEK:
                grid_data[day] = {}
                for time_slot in TIME_SLOTS:
                    grid_data[day][time_slot] = []

            # Populate grid with schedule data
            for schedule in schedules:
                module_code, day, start_time, end_time, building, room_number, session_type = schedule

                # Find the closest time slot
                closest_slot = min(TIME_SLOTS, key=lambda x: abs(int(x[:2]) - int(start_time[:2])))

                # Create session info
                room_str = f"{building}-{room_number}" if building and room_number else "TBA"
                session_info = {
                    'module': module_code,
                    'type': session_type,
                    'room': room_str,
                    'time': f"{start_time}-{end_time}"
                }

                if day in grid_data and closest_slot in grid_data[day]:
                    grid_data[day][closest_slot].append(session_info)

            # Create grid with proper boxes
            # Header row with time column
            time_header = tk.Label(parent_frame, text="Time", font=('Arial', 11, 'bold'),
                                   relief=tk.SOLID, borderwidth=2, bg='#4a90e2', fg='white',
                                   width=12, height=2)
            time_header.grid(row=0, column=0, padx=2, pady=2, sticky="nsew")

            # Day headers
            for col, day in enumerate(DAYS_OF_WEEK, 1):
                day_header = tk.Label(parent_frame, text=day, font=('Arial', 11, 'bold'),
                                      relief=tk.SOLID, borderwidth=2, bg='#4a90e2', fg='white',
                                      width=20, height=2)
                day_header.grid(row=0, column=col, padx=2, pady=2, sticky="nsew")

            # Create time slots and schedule cells
            for row, time_slot in enumerate(TIME_SLOTS, 1):
                # Time label with box
                time_label = tk.Label(parent_frame, text=time_slot, font=('Arial', 10, 'bold'),
                                      relief=tk.SOLID, borderwidth=2, bg='#e8f4f8',
                                      width=12, height=4)
                time_label.grid(row=row, column=0, padx=2, pady=2, sticky="nsew")

                # Schedule cells for each day
                for col, day in enumerate(DAYS_OF_WEEK, 1):
                    entries = grid_data[day][time_slot]

                    # Create cell frame with visible border
                    cell_frame = tk.Frame(parent_frame, relief=tk.SOLID, borderwidth=2,
                                         bg='#d4edda' if entries else 'white',
                                         width=180, height=100)
                    cell_frame.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
                    cell_frame.grid_propagate(False)

                    if entries:
                        # Create inner container for better padding
                        inner_frame = tk.Frame(cell_frame, bg='#d4edda')
                        inner_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

                        # Display schedule entries
                        for i, entry in enumerate(entries):
                            if i < 2:  # Limit to 2 entries per cell
                                # Create a box for each session
                                session_box = tk.Frame(inner_frame, relief=tk.RAISED, borderwidth=1,
                                                       bg='#c3e6cb', padx=3, pady=3)
                                session_box.pack(fill=tk.X, pady=2)

                                # Module code - bold and larger
                                module_label = tk.Label(session_box, text=entry['module'],
                                                        font=('Arial', 9, 'bold'),
                                                        bg='#c3e6cb', fg='#155724')
                                module_label.pack(anchor='w')

                                # Session type
                                type_label = tk.Label(session_box, text=entry['type'],
                                                      font=('Arial', 8),
                                                      bg='#c3e6cb', fg='#155724')
                                type_label.pack(anchor='w')

                                # Room
                                room_label = tk.Label(session_box, text=f"Room: {entry['room']}",
                                                      font=('Arial', 7),
                                                      bg='#c3e6cb', fg='#155724')
                                room_label.pack(anchor='w')

                                # Time
                                time_label = tk.Label(session_box, text=entry['time'],
                                                      font=('Arial', 7, 'italic'),
                                                      bg='#c3e6cb', fg='#155724')
                                time_label.pack(anchor='w')

                        if len(entries) > 2:
                            more_label = tk.Label(inner_frame, text=f"+ {len(entries)-2} more...",
                                                  font=('Arial', 7, 'italic'),
                                                  bg='#d4edda', fg='#155724')
                            more_label.pack(pady=2)
                    else:
                        # Empty cell indicator
                        empty_label = tk.Label(cell_frame, text="-", font=('Arial', 12),
                                               bg='white', fg='#cccccc')
                        empty_label.place(relx=0.5, rely=0.5, anchor='center')

            # Configure grid weights for proper resizing
            for i in range(len(TIME_SLOTS) + 1):
                parent_frame.grid_rowconfigure(i, weight=0, minsize=100)
            for i in range(len(DAYS_OF_WEEK) + 1):
                parent_frame.grid_columnconfigure(i, weight=0, minsize=180 if i > 0 else 100)

        except Exception as e:
            error_label = ttk.Label(parent_frame, text=f"Error creating grid: {str(e)}")
            error_label.pack(pady=20)
    
    def center_window(self):
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - (self.window.winfo_width() // 2)
        y = (self.window.winfo_screenheight() // 2) - (self.window.winfo_height() // 2)
        self.window.geometry(f"+{x}+{y}")


# Main application launcher
def main():
    """Main function to launch the GUI application"""
    try:
        # Check if the original module is available
        if not os.path.exists('module_scheduling.py'):
            print("Warning: module_scheduling.py not found. Some features may be limited.")
        
        # Create the main window
        root = tk.Tk()
        
        # Set application icon (if available)
        try:
            root.iconbitmap('icon.ico')  # You can add an icon file
        except:
            pass
        
        # Create and run the application
        app = ModuleSchedulingGUI(root)
        
        # Start the GUI event loop
        root.mainloop()
        
    except Exception as e:
        print(f"Error starting GUI application: {e}")
        print("\nTrying to launch CLI mode instead...")
        
        # Fallback to CLI mode if GUI fails
        try:
            from university_system.modules.domain.academics.services.module_scheduling import display_enhanced_scheduling_menu
            display_enhanced_scheduling_menu()
        except ImportError:
            print("CLI mode also unavailable. Please check your installation.")


def launch_gui():
    """Alternative launcher function"""
    main()


def launch_cli():
    """Launch CLI mode directly"""
    try:
        from university_system.modules.domain.academics.services.module_scheduling import display_enhanced_scheduling_menu
        display_enhanced_scheduling_menu()
    except ImportError:
        print("CLI mode not available. Please ensure module_scheduling.py is in the same directory.")


if __name__ == "__main__":
    import sys
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1].lower() in ['cli', 'command', 'terminal']:
            launch_cli()
        elif sys.argv[1].lower() in ['gui', 'window', 'interface']:
            launch_gui()
        elif sys.argv[1].lower() in ['help', '-h', '--help']:
            print("Enhanced Module Scheduling System")
            print("Usage:")
            print("  python gui_module_scheduler.py         # Launch GUI (default)")
            print("  python gui_module_scheduler.py gui     # Launch GUI explicitly")
            print("  python gui_module_scheduler.py cli     # Launch CLI mode")
            print("  python gui_module_scheduler.py help    # Show this help")
        else:
            print(f"Unknown argument: {sys.argv[1]}")
            print("Use 'help' for available options.")
    else:
        # Default to GUI mode
        main()

def create_desktop_shortcut():
    """Create a desktop shortcut for the application (Windows)"""
    try:
        import winshell
        from win32com.client import Dispatch
        
        desktop = winshell.desktop()
        path = os.path.join(desktop, "Module Scheduler.lnk")
        target = sys.executable
        wDir = os.path.dirname(os.path.abspath(__file__))
        icon = os.path.join(wDir, "icon.ico")
        
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(path)
        shortcut.Targetpath = target
        shortcut.Arguments = f'"{os.path.abspath(__file__)}"'
        shortcut.WorkingDirectory = wDir
        shortcut.IconLocation = icon if os.path.exists(icon) else target
        shortcut.save()
        
        print(f"Desktop shortcut created: {path}")
        
    except ImportError:
        print("winshell and pywin32 packages required for creating Windows shortcuts.")
    except Exception as e:
        print(f"Error creating desktop shortcut: {e}")


# Configuration and setup functions
def setup_application():
    """Setup application for first-time use"""
    try:
        # Create necessary directories
        directories = ['timetable_reports', 'backups', 'analytics', 'templates']
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
        
        # Initialize database if it doesn't exist
        if not os.path.exists(str(DEFAULT_DB_PATH)):
            print("Initializing database for first-time use...")
            scheduler = ModuleScheduler()
            print("Database initialized successfully.")
        
        print("Application setup complete!")
        
    except Exception as e:
        print(f"Error during application setup: {e}")


# Export the main classes and functions for external use
__all__ = [
    'ModuleSchedulingGUI',
    'main',
    'launch_gui',
    'launch_cli',
    'run_gui_with_database',
    'setup_application'
]

# Application metadata
__version__ = "2.0.0"
__author__ = "Academic Systems Team"
__description__ = "Enhanced Module Scheduling System - GUI Version"

# Ensure backward compatibility
try:
    from university_system.modules.domain.academics.services.module_scheduling import (
        ModuleScheduler, DAYS_OF_WEEK, ROOM_TYPES, SESSION_TYPES, TIME_SLOTS,
        display_enhanced_scheduling_menu
    )
except ImportError:
    print("Warning: Original module_scheduling module not found. Some features may be limited.")

def launch_module_scheduling_gui():
    """Launch the Module Scheduling GUI."""
    import tkinter as tk
    root = tk.Tk()
    app = ModuleSchedulingGUI(root)
    root.mainloop()

def run_gui_with_database(db_path=None):
    """Run the GUI with a specific database path for backward compatibility."""
    if db_path:
        import os
        os.environ['MODULE_SCHEDULING_DB_PATH'] = db_path
    launch_module_scheduling_gui()
