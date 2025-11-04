"""
Virtual Classroom Management GUI
Comprehensive interface for managing virtual classrooms, sessions, participants, and recordings
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime, timedelta
import json
from typing import Optional, Dict, List, Any

# Infrastructure imports
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.infrastructure.shared_context import get_auth, get_current_user
from university_system.modules.shared.constants import paths
from university_system.modules.shared.utils.activity_logger import log_activity

# Virtual classroom service imports
from university_system.modules.domain.academics.services.virtual_classroom.schema import (
    create_virtual_classroom_tables
)
from university_system.modules.domain.academics.services.virtual_classroom.classroom_manager import (
    VirtualClassroomManager
)
from university_system.modules.domain.academics.services.virtual_classroom.session_manager import (
    SessionManager
)
from university_system.modules.domain.academics.services.virtual_classroom.participant_manager import (
    ParticipantManager
)
from university_system.modules.domain.academics.services.virtual_classroom.recording_manager import (
    RecordingManager
)


class VirtualClassroomGUI:
    """Main GUI for Virtual Classroom Management"""

    def __init__(self, parent, auth=None):
        """Initialize the Virtual Classroom GUI

        Args:
            parent: Parent window (Toplevel or Tk)
            auth: UserAuth instance (optional, will use get_auth() if not provided)
        """
        self.parent = parent
        self.auth = auth if auth is not None else get_auth()

        # Check authentication - verify auth exists and user is logged in
        if not self.auth or not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to access Virtual Classroom Management.")
            if hasattr(parent, 'destroy'):
                parent.destroy()
            return

        # Initialize managers
        self.classroom_manager = VirtualClassroomManager()
        self.session_manager = SessionManager()
        self.participant_manager = ParticipantManager()
        self.recording_manager = RecordingManager()

        # Initialize database tables
        self._initialize_database()

        # Setup UI
        self._setup_window()
        self._create_widgets()

        # Load initial data
        self.refresh_all_data()

    def _initialize_database(self):
        """Initialize virtual classroom database tables"""
        try:
            with get_connection() as conn:
                create_virtual_classroom_tables(conn)
            log_activity('Virtual classroom tables initialized', 'system')
        except Exception as e:
            messagebox.showerror("Database Error",
                               f"Failed to initialize database tables: {str(e)}")
            print(f"Database initialization error: {e}")

    def _setup_window(self):
        """Configure window properties"""
        self.parent.title("Virtual Classroom Management")
        self.parent.geometry("1400x900")
        self.parent.minsize(1200, 800)

        # Configure grid weights
        self.parent.grid_rowconfigure(0, weight=1)
        self.parent.grid_columnconfigure(0, weight=1)

    def _create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.parent, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # Header frame with title and return button
        header_frame = ttk.Frame(main_frame)
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header_frame.grid_columnconfigure(0, weight=1)

        # Title
        title_label = ttk.Label(
            header_frame,
            text="Virtual Classroom Management",
            font=('Arial', 18, 'bold')
        )
        title_label.grid(row=0, column=0, sticky="w")

        # Return to Homepage button
        return_btn = ttk.Button(
            header_frame,
            text="🏠 Return to Homepage",
            command=self._return_to_homepage,
            style='Accent.TButton'
        )
        return_btn.grid(row=0, column=1, padx=(10, 0), sticky="e")

        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=1, column=0, sticky="nsew")

        # Create tabs
        self._create_classrooms_tab()
        self._create_sessions_tab()
        self._create_participants_tab()
        self._create_recordings_tab()
        self._create_analytics_tab()

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(
            main_frame,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        status_bar.grid(row=2, column=0, sticky="ew", pady=(5, 0))

    def _create_classrooms_tab(self):
        """Create the Classrooms management tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Classrooms")

        # Configure grid
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        # Toolbar
        toolbar = ttk.Frame(tab)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        ttk.Button(
            toolbar,
            text="Create Classroom",
            command=self._create_classroom_dialog
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            toolbar,
            text="Edit Selected",
            command=self._edit_classroom_dialog
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            toolbar,
            text="Delete Selected",
            command=self._delete_classroom
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            toolbar,
            text="Refresh",
            command=self._refresh_classrooms
        ).pack(side=tk.LEFT, padx=5)

        # Treeview for classrooms
        columns = ("ID", "Name", "Platform", "Instructor", "Max Participants", "Status")
        self.classrooms_tree = ttk.Treeview(tab, columns=columns, show="headings", height=20)

        for col in columns:
            self.classrooms_tree.heading(col, text=col, command=lambda c=col: self._sort_treeview(self.classrooms_tree, c, False))
            self.classrooms_tree.column(col, width=150)

        # Scrollbars
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self.classrooms_tree.yview)
        hsb = ttk.Scrollbar(tab, orient="horizontal", command=self.classrooms_tree.xview)
        self.classrooms_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Grid layout
        self.classrooms_tree.grid(row=1, column=0, sticky="nsew")
        vsb.grid(row=1, column=1, sticky="ns")
        hsb.grid(row=2, column=0, sticky="ew")

    def _create_sessions_tab(self):
        """Create the Sessions management tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Sessions")

        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        # Toolbar
        toolbar = ttk.Frame(tab)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        ttk.Button(
            toolbar,
            text="Schedule Session",
            command=self._schedule_session_dialog
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            toolbar,
            text="Start Session",
            command=self._start_session
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            toolbar,
            text="End Session",
            command=self._end_session
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            toolbar,
            text="View Details",
            command=self._view_session_details
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            toolbar,
            text="Refresh",
            command=self._refresh_sessions
        ).pack(side=tk.LEFT, padx=5)

        # Treeview for sessions
        columns = ("ID", "Classroom", "Type", "Start Time", "End Time", "Status")
        self.sessions_tree = ttk.Treeview(tab, columns=columns, show="headings", height=20)

        for col in columns:
            self.sessions_tree.heading(col, text=col, command=lambda c=col: self._sort_treeview(self.sessions_tree, c, False))
            self.sessions_tree.column(col, width=150)

        # Scrollbars
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self.sessions_tree.yview)
        hsb = ttk.Scrollbar(tab, orient="horizontal", command=self.sessions_tree.xview)
        self.sessions_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Grid layout
        self.sessions_tree.grid(row=1, column=0, sticky="nsew")
        vsb.grid(row=1, column=1, sticky="ns")
        hsb.grid(row=2, column=0, sticky="ew")

    def _create_participants_tab(self):
        """Create the Participants tracking tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Participants")

        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        # Toolbar
        toolbar = ttk.Frame(tab)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        ttk.Label(toolbar, text="Session:").pack(side=tk.LEFT, padx=5)

        self.participant_session_var = tk.StringVar()
        self.participant_session_combo = ttk.Combobox(
            toolbar,
            textvariable=self.participant_session_var,
            width=30,
            state="readonly"
        )
        self.participant_session_combo.pack(side=tk.LEFT, padx=5)
        self.participant_session_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_participants())

        ttk.Button(
            toolbar,
            text="Add Participant",
            command=self._add_participant_dialog
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            toolbar,
            text="Mark Attendance",
            command=self._mark_attendance_dialog
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            toolbar,
            text="Export Attendance",
            command=self._export_attendance
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            toolbar,
            text="Refresh",
            command=self._refresh_participants
        ).pack(side=tk.LEFT, padx=5)

        # Treeview for participants
        columns = ("ID", "User", "Type", "Join Time", "Duration", "Status", "Connection")
        self.participants_tree = ttk.Treeview(tab, columns=columns, show="headings", height=20)

        for col in columns:
            self.participants_tree.heading(col, text=col)
            self.participants_tree.column(col, width=120)

        # Scrollbars
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self.participants_tree.yview)
        hsb = ttk.Scrollbar(tab, orient="horizontal", command=self.participants_tree.xview)
        self.participants_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Grid layout
        self.participants_tree.grid(row=1, column=0, sticky="nsew")
        vsb.grid(row=1, column=1, sticky="ns")
        hsb.grid(row=2, column=0, sticky="ew")

    def _create_recordings_tab(self):
        """Create the Recordings management tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Recordings")

        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        # Toolbar
        toolbar = ttk.Frame(tab)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        ttk.Button(
            toolbar,
            text="Add Recording",
            command=self._add_recording_dialog
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            toolbar,
            text="View Recording",
            command=self._view_recording
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            toolbar,
            text="Delete Recording",
            command=self._delete_recording
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            toolbar,
            text="Refresh",
            command=self._refresh_recordings
        ).pack(side=tk.LEFT, padx=5)

        # Treeview for recordings
        columns = ("ID", "Session", "File Name", "Duration", "Size", "Views", "Public")
        self.recordings_tree = ttk.Treeview(tab, columns=columns, show="headings", height=20)

        for col in columns:
            self.recordings_tree.heading(col, text=col)
            self.recordings_tree.column(col, width=130)

        # Scrollbars
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self.recordings_tree.yview)
        hsb = ttk.Scrollbar(tab, orient="horizontal", command=self.recordings_tree.xview)
        self.recordings_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Grid layout
        self.recordings_tree.grid(row=1, column=0, sticky="nsew")
        vsb.grid(row=1, column=1, sticky="ns")
        hsb.grid(row=2, column=0, sticky="ew")

    def _create_analytics_tab(self):
        """Create the Analytics tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Analytics")

        # Analytics content
        analytics_frame = ttk.LabelFrame(tab, text="Session Analytics", padding="10")
        analytics_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Statistics labels
        self.stats_labels = {}
        stats = [
            ("Total Classrooms", "total_classrooms"),
            ("Active Sessions", "active_sessions"),
            ("Total Participants Today", "participants_today"),
            ("Total Recordings", "total_recordings"),
            ("Average Attendance Rate", "avg_attendance"),
            ("Peak Connection Time", "peak_time")
        ]

        for i, (label, key) in enumerate(stats):
            row = i // 2
            col = i % 2

            frame = ttk.Frame(analytics_frame)
            frame.grid(row=row, column=col, padx=10, pady=10, sticky="ew")

            ttk.Label(frame, text=f"{label}:", font=('Arial', 10, 'bold')).pack(anchor="w")
            value_label = ttk.Label(frame, text="Loading...", font=('Arial', 12))
            value_label.pack(anchor="w")
            self.stats_labels[key] = value_label

        # Refresh button
        ttk.Button(
            analytics_frame,
            text="Refresh Analytics",
            command=self._refresh_analytics
        ).grid(row=len(stats)//2 + 1, column=0, columnspan=2, pady=20)

    # ==================== Classroom Management Methods ====================

    def _create_classroom_dialog(self):
        """Open dialog to create a new classroom"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("Create Virtual Classroom")
        dialog.geometry("500x600")
        dialog.transient(self.parent)
        dialog.grab_set()

        # Main frame
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Form fields
        fields = {}
        row = 0

        # Session Name
        ttk.Label(main_frame, text="Session Name:*").grid(row=row, column=0, sticky="w", pady=5)
        fields['session_name'] = ttk.Entry(main_frame, width=40)
        fields['session_name'].grid(row=row, column=1, pady=5)
        row += 1

        # Platform
        ttk.Label(main_frame, text="Platform:*").grid(row=row, column=0, sticky="w", pady=5)
        fields['platform'] = ttk.Combobox(
            main_frame,
            values=["zoom", "teams", "meet", "webrtc"],
            state="readonly",
            width=38
        )
        fields['platform'].grid(row=row, column=1, pady=5)
        fields['platform'].current(0)
        row += 1

        # Instructor ID
        ttk.Label(main_frame, text="Instructor ID:*").grid(row=row, column=0, sticky="w", pady=5)
        fields['instructor_id'] = ttk.Entry(main_frame, width=40)
        fields['instructor_id'].grid(row=row, column=1, pady=5)
        row += 1

        # Course ID (optional)
        ttk.Label(main_frame, text="Course ID:").grid(row=row, column=0, sticky="w", pady=5)
        fields['course_id'] = ttk.Entry(main_frame, width=40)
        fields['course_id'].grid(row=row, column=1, pady=5)
        row += 1

        # Meeting Link
        ttk.Label(main_frame, text="Meeting Link:").grid(row=row, column=0, sticky="w", pady=5)
        fields['meeting_link'] = ttk.Entry(main_frame, width=40)
        fields['meeting_link'].grid(row=row, column=1, pady=5)
        row += 1

        # Meeting ID
        ttk.Label(main_frame, text="Meeting ID:").grid(row=row, column=0, sticky="w", pady=5)
        fields['meeting_id'] = ttk.Entry(main_frame, width=40)
        fields['meeting_id'].grid(row=row, column=1, pady=5)
        row += 1

        # Passcode
        ttk.Label(main_frame, text="Passcode:").grid(row=row, column=0, sticky="w", pady=5)
        fields['passcode'] = ttk.Entry(main_frame, width=40, show="*")
        fields['passcode'].grid(row=row, column=1, pady=5)
        row += 1

        # Max Participants
        ttk.Label(main_frame, text="Max Participants:").grid(row=row, column=0, sticky="w", pady=5)
        fields['max_participants'] = ttk.Spinbox(main_frame, from_=10, to=500, width=38)
        fields['max_participants'].set(100)
        fields['max_participants'].grid(row=row, column=1, pady=5)
        row += 1

        # Features checkboxes
        ttk.Label(main_frame, text="Features:").grid(row=row, column=0, sticky="nw", pady=5)
        features_frame = ttk.Frame(main_frame)
        features_frame.grid(row=row, column=1, sticky="w", pady=5)

        feature_vars = {}
        feature_names = ['whiteboard', 'breakout_rooms', 'recording', 'polling', 'chat', 'screen_sharing']
        for feature in feature_names:
            var = tk.BooleanVar(value=True)
            ttk.Checkbutton(features_frame, text=feature.replace('_', ' ').title(), variable=var).pack(anchor="w")
            feature_vars[feature] = var
        row += 1

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2, pady=20)

        def create_classroom():
            try:
                # Validate required fields
                if not fields['session_name'].get().strip():
                    messagebox.showerror("Error", "Session name is required")
                    return
                if not fields['instructor_id'].get().strip():
                    messagebox.showerror("Error", "Instructor ID is required")
                    return

                # Prepare features dict
                features = {name: var.get() for name, var in feature_vars.items()}

                # Create classroom
                classroom_id = self.classroom_manager.create_classroom(
                    session_name=fields['session_name'].get().strip(),
                    instructor_id=int(fields['instructor_id'].get().strip()),
                    platform=fields['platform'].get(),
                    course_id=int(fields['course_id'].get().strip()) if fields['course_id'].get().strip() else None,
                    meeting_link=fields['meeting_link'].get().strip() or None,
                    meeting_id=fields['meeting_id'].get().strip() or None,
                    passcode=fields['passcode'].get().strip() or None,
                    max_participants=int(fields['max_participants'].get()),
                    features=features
                )

                if classroom_id:
                    log_activity(f'Created virtual classroom: {classroom_id}')
                    messagebox.showinfo("Success", f"Classroom created successfully! ID: {classroom_id}")
                    dialog.destroy()
                    self._refresh_classrooms()
                else:
                    messagebox.showerror("Error", "Failed to create classroom")

            except ValueError as e:
                messagebox.showerror("Error", f"Invalid input: {str(e)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create classroom: {str(e)}")

        ttk.Button(button_frame, text="Create", command=create_classroom).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _edit_classroom_dialog(self):
        """Open dialog to edit selected classroom"""
        selection = self.classrooms_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a classroom to edit")
            return

        item = self.classrooms_tree.item(selection[0])
        classroom_id = item['values'][0]

        # Get classroom details
        classroom = self.classroom_manager.get_classroom(classroom_id)
        if not classroom:
            messagebox.showerror("Error", "Failed to load classroom details")
            return

        messagebox.showinfo("Info", "Edit functionality coming soon. Use CLI for advanced editing.")

    def _delete_classroom(self):
        """Delete selected classroom"""
        selection = self.classrooms_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a classroom to delete")
            return

        item = self.classrooms_tree.item(selection[0])
        classroom_id = item['values'][0]
        classroom_name = item['values'][1]

        if messagebox.askyesno("Confirm Delete",
                              f"Are you sure you want to delete classroom '{classroom_name}'?\n\n"
                              "This will also delete all associated sessions and data."):
            try:
                if self.classroom_manager.delete_classroom(classroom_id):
                    log_activity(f'Deleted virtual classroom: {classroom_id}')
                    messagebox.showinfo("Success", "Classroom deleted successfully")
                    self._refresh_classrooms()
                else:
                    messagebox.showerror("Error", "Failed to delete classroom")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete classroom: {str(e)}")

    def _refresh_classrooms(self):
        """Refresh the classrooms list"""
        try:
            # Clear existing items
            for item in self.classrooms_tree.get_children():
                self.classrooms_tree.delete(item)

            # Get all classrooms
            classrooms = self.classroom_manager.list_classrooms()

            for classroom in classrooms:
                status = "Active" if classroom.get('is_active') else "Inactive"
                self.classrooms_tree.insert("", "end", values=(
                    classroom['classroom_id'],
                    classroom['session_name'],
                    classroom['platform'].title(),
                    classroom['instructor_id'],
                    classroom['max_participants'],
                    status
                ))

            self.update_status(f"Loaded {len(classrooms)} classrooms")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh classrooms: {str(e)}")
            self.update_status("Error loading classrooms", error=True)

    # ==================== Session Management Methods ====================

    def _schedule_session_dialog(self):
        """Open dialog to schedule a new session"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("Schedule Virtual Session")
        dialog.geometry("500x500")
        dialog.transient(self.parent)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        fields = {}
        row = 0

        # Classroom selection
        ttk.Label(main_frame, text="Classroom:*").grid(row=row, column=0, sticky="w", pady=5)

        # Get available classrooms
        classrooms = self.classroom_manager.list_classrooms(active_only=True)
        classroom_options = [f"{c['classroom_id']}: {c['session_name']}" for c in classrooms]

        fields['classroom'] = ttk.Combobox(main_frame, values=classroom_options, state="readonly", width=38)
        fields['classroom'].grid(row=row, column=1, pady=5)
        if classroom_options:
            fields['classroom'].current(0)
        row += 1

        # Session Type
        ttk.Label(main_frame, text="Session Type:*").grid(row=row, column=0, sticky="w", pady=5)
        fields['session_type'] = ttk.Combobox(
            main_frame,
            values=["lecture", "lab", "office_hours", "review", "exam"],
            state="readonly",
            width=38
        )
        fields['session_type'].grid(row=row, column=1, pady=5)
        fields['session_type'].current(0)
        row += 1

        # Start Date
        ttk.Label(main_frame, text="Start Date (YYYY-MM-DD):*").grid(row=row, column=0, sticky="w", pady=5)
        fields['start_date'] = ttk.Entry(main_frame, width=40)
        fields['start_date'].insert(0, datetime.now().strftime("%Y-%m-%d"))
        fields['start_date'].grid(row=row, column=1, pady=5)
        row += 1

        # Start Time
        ttk.Label(main_frame, text="Start Time (HH:MM):*").grid(row=row, column=0, sticky="w", pady=5)
        fields['start_time'] = ttk.Entry(main_frame, width=40)
        fields['start_time'].insert(0, "09:00")
        fields['start_time'].grid(row=row, column=1, pady=5)
        row += 1

        # Duration
        ttk.Label(main_frame, text="Duration (minutes):*").grid(row=row, column=0, sticky="w", pady=5)
        fields['duration'] = ttk.Spinbox(main_frame, from_=15, to=480, width=38)
        fields['duration'].set(60)
        fields['duration'].grid(row=row, column=1, pady=5)
        row += 1

        # Notes
        ttk.Label(main_frame, text="Notes:").grid(row=row, column=0, sticky="nw", pady=5)
        fields['notes'] = tk.Text(main_frame, width=30, height=5)
        fields['notes'].grid(row=row, column=1, pady=5)
        row += 1

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2, pady=20)

        def schedule_session():
            try:
                if not fields['classroom'].get():
                    messagebox.showerror("Error", "Please select a classroom")
                    return

                # Parse classroom ID
                classroom_id = int(fields['classroom'].get().split(':')[0])

                # Parse datetime
                date_str = fields['start_date'].get().strip()
                time_str = fields['start_time'].get().strip()
                datetime_str = f"{date_str} {time_str}"
                start_time = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")

                # Create session
                session_id = self.session_manager.create_session(
                    classroom_id=classroom_id,
                    start_time=start_time,
                    session_type=fields['session_type'].get(),
                    duration_minutes=int(fields['duration'].get()),
                    notes=fields['notes'].get("1.0", "end-1c").strip() or None
                )

                if session_id:
                    log_activity(f'Created virtual session: {session_id}')
                    messagebox.showinfo("Success", f"Session scheduled successfully! ID: {session_id}")
                    dialog.destroy()
                    self._refresh_sessions()
                else:
                    messagebox.showerror("Error", "Failed to schedule session")

            except ValueError as e:
                messagebox.showerror("Error", f"Invalid input: {str(e)}\nExpected format: YYYY-MM-DD HH:MM")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to schedule session: {str(e)}")

        ttk.Button(button_frame, text="Schedule", command=schedule_session).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _start_session(self):
        """Start the selected session"""
        selection = self.sessions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a session to start")
            return

        item = self.sessions_tree.item(selection[0])
        session_id = item['values'][0]
        status = item['values'][5]

        if status != "scheduled":
            messagebox.showwarning("Warning", f"Cannot start session with status: {status}")
            return

        try:
            if self.session_manager.start_session(session_id):
                log_activity(f'Started virtual session: {session_id}')
                messagebox.showinfo("Success", "Session started successfully")
                self._refresh_sessions()
            else:
                messagebox.showerror("Error", "Failed to start session")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start session: {str(e)}")

    def _end_session(self):
        """End the selected session"""
        selection = self.sessions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a session to end")
            return

        item = self.sessions_tree.item(selection[0])
        session_id = item['values'][0]
        status = item['values'][5]

        if status != "in_progress":
            messagebox.showwarning("Warning", f"Cannot end session with status: {status}")
            return

        try:
            if self.session_manager.end_session(session_id):
                log_activity(f'Ended virtual session: {session_id}')
                messagebox.showinfo("Success", "Session ended successfully")
                self._refresh_sessions()
            else:
                messagebox.showerror("Error", "Failed to end session")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to end session: {str(e)}")

    def _view_session_details(self):
        """View details of selected session"""
        selection = self.sessions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a session to view")
            return

        item = self.sessions_tree.item(selection[0])
        session_id = item['values'][0]

        try:
            session = self.session_manager.get_session(session_id)
            if session:
                details = f"""Session Details:

ID: {session['session_id']}
Classroom ID: {session['classroom_id']}
Type: {session['session_type']}
Start Time: {session['start_time']}
End Time: {session['end_time']}
Status: {session['status']}
Notes: {session.get('notes', 'None')}
"""
                messagebox.showinfo("Session Details", details)
            else:
                messagebox.showerror("Error", "Failed to load session details")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load session details: {str(e)}")

    def _refresh_sessions(self):
        """Refresh the sessions list"""
        try:
            # Clear existing items
            for item in self.sessions_tree.get_children():
                self.sessions_tree.delete(item)

            # Get all sessions
            sessions = self.session_manager.list_sessions()

            # Also update participant session combo
            session_options = []

            for session in sessions:
                # Add to tree
                self.sessions_tree.insert("", "end", values=(
                    session['session_id'],
                    session['classroom_id'],
                    session['session_type'],
                    session['start_time'],
                    session.get('end_time', 'N/A'),
                    session['status']
                ))

                # Add to combo options
                session_options.append(f"{session['session_id']}: {session['session_type']} - {session['start_time']}")

            # Update participant session combo
            if hasattr(self, 'participant_session_combo'):
                self.participant_session_combo['values'] = session_options

            self.update_status(f"Loaded {len(sessions)} sessions")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh sessions: {str(e)}")
            self.update_status("Error loading sessions", error=True)

    # ==================== Participant Management Methods ====================

    def _add_participant_dialog(self):
        """Add participant to a session"""
        if not self.participant_session_var.get():
            messagebox.showwarning("Warning", "Please select a session first")
            return

        dialog = tk.Toplevel(self.parent)
        dialog.title("Add Participant")
        dialog.geometry("400x350")
        dialog.transient(self.parent)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        fields = {}
        row = 0

        # User ID
        ttk.Label(main_frame, text="User ID:*").grid(row=row, column=0, sticky="w", pady=5)
        fields['user_id'] = ttk.Entry(main_frame, width=30)
        fields['user_id'].grid(row=row, column=1, pady=5)
        row += 1

        # User Type
        ttk.Label(main_frame, text="User Type:*").grid(row=row, column=0, sticky="w", pady=5)
        fields['user_type'] = ttk.Combobox(
            main_frame,
            values=["student", "instructor", "guest"],
            state="readonly",
            width=28
        )
        fields['user_type'].grid(row=row, column=1, pady=5)
        fields['user_type'].current(0)
        row += 1

        # Device Type
        ttk.Label(main_frame, text="Device Type:").grid(row=row, column=0, sticky="w", pady=5)
        fields['device_type'] = ttk.Combobox(
            main_frame,
            values=["desktop", "mobile", "tablet"],
            state="readonly",
            width=28
        )
        fields['device_type'].grid(row=row, column=1, pady=5)
        fields['device_type'].current(0)
        row += 1

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2, pady=20)

        def add_participant():
            try:
                session_id = int(self.participant_session_var.get().split(':')[0])

                participant_id = self.participant_manager.add_participant(
                    session_id=session_id,
                    user_id=int(fields['user_id'].get().strip()),
                    user_type=fields['user_type'].get(),
                    device_type=fields['device_type'].get()
                )

                if participant_id:
                    log_activity(f'Added session participant: {participant_id}')
                    messagebox.showinfo("Success", "Participant added successfully")
                    dialog.destroy()
                    self._refresh_participants()
                else:
                    messagebox.showerror("Error", "Failed to add participant")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add participant: {str(e)}")

        ttk.Button(button_frame, text="Add", command=add_participant).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _mark_attendance_dialog(self):
        """Mark attendance for selected participant"""
        selection = self.participants_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a participant")
            return

        item = self.participants_tree.item(selection[0])
        participant_id = item['values'][0]

        # Simple dialog for attendance status
        status = simpledialog.askstring(
            "Mark Attendance",
            "Enter attendance status (present/absent/late/left_early):",
            parent=self.parent
        )

        if status and status.lower() in ['present', 'absent', 'late', 'left_early']:
            try:
                if self.participant_manager.update_attendance(participant_id, status.lower()):
                    log_activity(f'Updated participant attendance: {participant_id} - {status.lower()}')
                    messagebox.showinfo("Success", "Attendance marked successfully")
                    self._refresh_participants()
                else:
                    messagebox.showerror("Error", "Failed to mark attendance")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to mark attendance: {str(e)}")
        elif status:
            messagebox.showerror("Error", "Invalid attendance status")

    def _export_attendance(self):
        """Export attendance for the selected session"""
        if not self.participant_session_var.get():
            messagebox.showwarning("Warning", "Please select a session first")
            return

        try:
            session_id = int(self.participant_session_var.get().split(':')[0])
            participants = self.participant_manager.get_session_participants(session_id)

            if not participants:
                messagebox.showinfo("Info", "No participants found for this session")
                return

            # Create CSV content
            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Participant ID', 'User ID', 'Type', 'Join Time', 'Leave Time',
                           'Duration (sec)', 'Status', 'Connection Quality'])

            for p in participants:
                writer.writerow([
                    p['participant_id'], p['user_id'], p['user_type'],
                    p.get('join_time', 'N/A'), p.get('leave_time', 'N/A'),
                    p.get('duration', 0), p['attendance_status'],
                    p.get('connection_quality', 'N/A')
                ])

            # Save to file
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )

            if filename:
                with open(filename, 'w', newline='') as f:
                    f.write(output.getvalue())
                messagebox.showinfo("Success", f"Attendance exported to {filename}")
                log_activity(f'Exported attendance for session: {session_id}')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export attendance: {str(e)}")

    def _refresh_participants(self):
        """Refresh participants list for selected session"""
        try:
            # Clear existing items
            for item in self.participants_tree.get_children():
                self.participants_tree.delete(item)

            if not self.participant_session_var.get():
                self.update_status("Select a session to view participants")
                return

            session_id = int(self.participant_session_var.get().split(':')[0])
            participants = self.participant_manager.get_session_participants(session_id)

            for p in participants:
                duration = f"{p.get('duration', 0)} sec" if p.get('duration') else "N/A"
                self.participants_tree.insert("", "end", values=(
                    p['participant_id'],
                    p['user_id'],
                    p['user_type'],
                    p.get('join_time', 'N/A'),
                    duration,
                    p['attendance_status'],
                    p.get('connection_quality', 'N/A')
                ))

            self.update_status(f"Loaded {len(participants)} participants")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh participants: {str(e)}")

    # ==================== Recording Management Methods ====================

    def _add_recording_dialog(self):
        """Add a new recording"""
        dialog = tk.Toplevel(self.parent)
        dialog.title("Add Recording")
        dialog.geometry("500x450")
        dialog.transient(self.parent)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        fields = {}
        row = 0

        # Session selection
        ttk.Label(main_frame, text="Session:*").grid(row=row, column=0, sticky="w", pady=5)
        sessions = self.session_manager.list_sessions()
        session_options = [f"{s['session_id']}: {s['session_type']} - {s['start_time']}" for s in sessions]
        fields['session'] = ttk.Combobox(main_frame, values=session_options, state="readonly", width=38)
        fields['session'].grid(row=row, column=1, pady=5)
        if session_options:
            fields['session'].current(0)
        row += 1

        # File URL
        ttk.Label(main_frame, text="File URL:*").grid(row=row, column=0, sticky="w", pady=5)
        fields['file_url'] = ttk.Entry(main_frame, width=40)
        fields['file_url'].grid(row=row, column=1, pady=5)
        row += 1

        # File Name
        ttk.Label(main_frame, text="File Name:").grid(row=row, column=0, sticky="w", pady=5)
        fields['file_name'] = ttk.Entry(main_frame, width=40)
        fields['file_name'].grid(row=row, column=1, pady=5)
        row += 1

        # Duration
        ttk.Label(main_frame, text="Duration (seconds):").grid(row=row, column=0, sticky="w", pady=5)
        fields['duration'] = ttk.Entry(main_frame, width=40)
        fields['duration'].grid(row=row, column=1, pady=5)
        row += 1

        # File Size
        ttk.Label(main_frame, text="File Size (bytes):").grid(row=row, column=0, sticky="w", pady=5)
        fields['file_size'] = ttk.Entry(main_frame, width=40)
        fields['file_size'].grid(row=row, column=1, pady=5)
        row += 1

        # Is Public
        fields['is_public'] = tk.BooleanVar(value=False)
        ttk.Checkbutton(main_frame, text="Make recording public", variable=fields['is_public']).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=5
        )
        row += 1

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2, pady=20)

        def add_recording():
            try:
                if not fields['session'].get():
                    messagebox.showerror("Error", "Please select a session")
                    return
                if not fields['file_url'].get().strip():
                    messagebox.showerror("Error", "File URL is required")
                    return

                session_id = int(fields['session'].get().split(':')[0])

                recording_id = self.recording_manager.add_recording(
                    session_id=session_id,
                    file_url=fields['file_url'].get().strip(),
                    file_name=fields['file_name'].get().strip() or None,
                    duration=int(fields['duration'].get()) if fields['duration'].get().strip() else None,
                    file_size=int(fields['file_size'].get()) if fields['file_size'].get().strip() else None,
                    is_public=fields['is_public'].get()
                )

                if recording_id:
                    log_activity(f'Added virtual recording: {recording_id}')
                    messagebox.showinfo("Success", "Recording added successfully")
                    dialog.destroy()
                    self._refresh_recordings()
                else:
                    messagebox.showerror("Error", "Failed to add recording")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add recording: {str(e)}")

        ttk.Button(button_frame, text="Add", command=add_recording).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _view_recording(self):
        """View details of selected recording"""
        selection = self.recordings_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a recording to view")
            return

        item = self.recordings_tree.item(selection[0])
        recording_id = item['values'][0]

        try:
            recording = self.recording_manager.get_recording(recording_id)
            if recording:
                details = f"""Recording Details:

ID: {recording['recording_id']}
Session ID: {recording['session_id']}
File Name: {recording.get('file_name', 'N/A')}
File URL: {recording['file_url']}
Duration: {recording.get('duration', 'N/A')} seconds
Size: {recording.get('file_size', 'N/A')} bytes
Views: {recording.get('view_count', 0)}
Downloads: {recording.get('download_count', 0)}
Public: {'Yes' if recording.get('is_public') else 'No'}
Created: {recording.get('created_at', 'N/A')}
"""
                messagebox.showinfo("Recording Details", details)

                # Increment view count
                self.recording_manager.increment_view_count(recording_id)
            else:
                messagebox.showerror("Error", "Failed to load recording details")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load recording: {str(e)}")

    def _delete_recording(self):
        """Delete selected recording"""
        selection = self.recordings_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a recording to delete")
            return

        item = self.recordings_tree.item(selection[0])
        recording_id = item['values'][0]

        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this recording?"):
            try:
                if self.recording_manager.delete_recording(recording_id):
                    log_activity(f'Deleted virtual recording: {recording_id}')
                    messagebox.showinfo("Success", "Recording deleted successfully")
                    self._refresh_recordings()
                else:
                    messagebox.showerror("Error", "Failed to delete recording")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete recording: {str(e)}")

    def _refresh_recordings(self):
        """Refresh recordings list"""
        try:
            # Clear existing items
            for item in self.recordings_tree.get_children():
                self.recordings_tree.delete(item)

            # Get all recordings
            recordings = self.recording_manager.list_recordings()

            for rec in recordings:
                file_name = rec.get('file_name', 'N/A')
                duration = f"{rec.get('duration', 0)}s" if rec.get('duration') else "N/A"
                size_mb = f"{rec.get('file_size', 0) / (1024*1024):.2f} MB" if rec.get('file_size') else "N/A"
                is_public = "Yes" if rec.get('is_public') else "No"

                self.recordings_tree.insert("", "end", values=(
                    rec['recording_id'],
                    rec['session_id'],
                    file_name,
                    duration,
                    size_mb,
                    rec.get('view_count', 0),
                    is_public
                ))

            self.update_status(f"Loaded {len(recordings)} recordings")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh recordings: {str(e)}")

    # ==================== Analytics Methods ====================

    def _refresh_analytics(self):
        """Refresh analytics data"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Total classrooms
                cursor.execute("SELECT COUNT(*) FROM virtual_classrooms WHERE is_active = 1")
                total_classrooms = cursor.fetchone()[0]
                self.stats_labels['total_classrooms'].config(text=str(total_classrooms))

                # Active sessions
                cursor.execute("SELECT COUNT(*) FROM virtual_sessions WHERE status = 'in_progress'")
                active_sessions = cursor.fetchone()[0]
                self.stats_labels['active_sessions'].config(text=str(active_sessions))

                # Participants today
                cursor.execute("""
                    SELECT COUNT(*) FROM session_participants
                    WHERE DATE(join_time) = DATE('now')
                """)
                participants_today = cursor.fetchone()[0]
                self.stats_labels['participants_today'].config(text=str(participants_today))

                # Total recordings
                cursor.execute("SELECT COUNT(*) FROM virtual_recordings")
                total_recordings = cursor.fetchone()[0]
                self.stats_labels['total_recordings'].config(text=str(total_recordings))

                # Average attendance
                cursor.execute("""
                    SELECT
                        CAST(SUM(CASE WHEN attendance_status = 'present' THEN 1 ELSE 0 END) AS FLOAT) /
                        NULLIF(COUNT(*), 0) * 100
                    FROM session_participants
                """)
                result = cursor.fetchone()
                avg_attendance = f"{result[0]:.1f}%" if result and result[0] else "N/A"
                self.stats_labels['avg_attendance'].config(text=avg_attendance)

                # Peak connection time (simplified)
                self.stats_labels['peak_time'].config(text="10:00 AM - 12:00 PM")

            self.update_status("Analytics refreshed")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh analytics: {str(e)}")

    # ==================== Utility Methods ====================

    def _return_to_homepage(self):
        """Close the Virtual Classroom window and return to homepage"""
        try:
            # Log the activity
            log_activity('User closed Virtual Classroom GUI')

            # Close the window
            if hasattr(self.parent, 'destroy'):
                self.parent.destroy()
        except Exception as e:
            print(f"Error closing Virtual Classroom: {e}")
            messagebox.showerror("Error", f"Failed to close window: {str(e)}")

    def refresh_all_data(self):
        """Refresh all data in all tabs"""
        self._refresh_classrooms()
        self._refresh_sessions()
        self._refresh_recordings()
        self._refresh_analytics()

    def update_status(self, message, error=False):
        """Update status bar"""
        self.status_var.set(message)
        # Note: Color changes aren't directly supported in ttk.Label without styling

    def _sort_treeview(self, tree, col, reverse):
        """Sort treeview by column"""
        try:
            data = [(tree.set(child, col), child) for child in tree.get_children('')]
            data.sort(reverse=reverse)

            for index, (_, child) in enumerate(data):
                tree.move(child, '', index)

            # Reverse sort next time
            tree.heading(col, command=lambda: self._sort_treeview(tree, col, not reverse))
        except Exception as e:
            print(f"Sort error: {e}")


# Main function to launch the GUI
def launch_virtual_classroom_gui(parent=None, auth=None):
    """Launch the Virtual Classroom GUI

    Args:
        parent: Parent window (optional)
        auth: UserAuth instance (optional)
    """
    if parent is None:
        root = tk.Tk()
        app = VirtualClassroomGUI(root, auth=auth)
        root.mainloop()
    else:
        # Launch as child window
        child_window = tk.Toplevel(parent)
        app = VirtualClassroomGUI(child_window, auth=auth)
        return child_window


if __name__ == "__main__":
    launch_virtual_classroom_gui()
