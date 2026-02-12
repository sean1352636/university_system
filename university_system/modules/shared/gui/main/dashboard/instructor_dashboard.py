"""Instructor role-based dashboard tab."""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

logger = logging.getLogger(__name__)


def _launch_roster(parent, auth):
    """Launch Class Roster Viewer."""
    from university_system.modules.domain.academics.gui.roster_viewer.roster_gui import ClassRosterGUI
    ClassRosterGUI(parent, auth=auth)


def _launch_bulk_grade(parent, auth):
    """Launch Bulk Grade Import."""
    from university_system.modules.domain.academics.gui.bulk_grade_import.bulk_grade_gui import BulkGradeImportGUI
    BulkGradeImportGUI(parent, auth=auth)


def _launch_messaging(parent, auth):
    """Launch Course Messaging."""
    from university_system.modules.domain.academics.gui.course_messaging.messaging_gui import CourseMessagingGUI
    CourseMessagingGUI(parent, auth=auth)


def _launch_attendance_grade(parent, auth):
    """Launch Attendance-Grade Config."""
    from university_system.modules.domain.academics.gui.attendance_grade.attendance_grade_gui import AttendanceGradeConfigGUI
    AttendanceGradeConfigGUI(parent, auth=auth)


def _launch_course_health(parent, auth):
    """Launch Course Health Dashboard."""
    from university_system.modules.domain.academics.gui.course_health.course_health_gui import CourseHealthDashboardGUI
    CourseHealthDashboardGUI(parent, auth=auth)


def _launch_semester_analytics(parent, auth):
    """Launch Semester Analytics."""
    from university_system.modules.domain.academics.gui.semester_analytics.semester_analytics_gui import SemesterAnalyticsGUI
    SemesterAnalyticsGUI(parent, auth=auth)


def create_instructor_dashboard(parent_frame, auth, service):
    """Create the instructor-specific dashboard content.

    Args:
        parent_frame: The ttk.Frame to populate.
        auth: Auth manager instance.
        service: DashboardService instance.
    """
    instructor_id = auth.current_user.get('username', '') if auth.current_user else ''
    data = service.get_instructor_dashboard_data(instructor_id)

    canvas = tk.Canvas(parent_frame)
    scrollbar = ttk.Scrollbar(parent_frame, orient=tk.VERTICAL, command=canvas.yview)
    scrollable = ttk.Frame(canvas)

    scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas_window = canvas.create_window((0, 0), window=scrollable, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    # Bind canvas resize to stretch scrollable frame to full width
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Welcome
    ttk.Label(scrollable, text=f"Instructor Dashboard - {instructor_id}",
              font=('Arial', 14, 'bold')).pack(anchor="w", padx=15, pady=(15, 5))

    # Quick Actions button bar
    actions_frame = ttk.LabelFrame(scrollable, text="Quick Actions", padding="5")
    actions_frame.pack(fill=tk.X, padx=15, pady=5)
    actions_row = ttk.Frame(actions_frame)
    actions_row.pack(fill=tk.X)

    root = parent_frame.winfo_toplevel()
    ttk.Button(actions_row, text="Class Roster",
               command=lambda: _launch_roster(root, auth)).pack(side=tk.LEFT, padx=3)
    ttk.Button(actions_row, text="Bulk Grade Import",
               command=lambda: _launch_bulk_grade(root, auth)).pack(side=tk.LEFT, padx=3)
    ttk.Button(actions_row, text="Course Messaging",
               command=lambda: _launch_messaging(root, auth)).pack(side=tk.LEFT, padx=3)
    ttk.Button(actions_row, text="Attendance-Grade",
               command=lambda: _launch_attendance_grade(root, auth)).pack(side=tk.LEFT, padx=3)
    ttk.Button(actions_row, text="Course Health",
               command=lambda: _launch_course_health(root, auth)).pack(side=tk.LEFT, padx=3)
    ttk.Button(actions_row, text="Semester Analytics",
               command=lambda: _launch_semester_analytics(root, auth)).pack(side=tk.LEFT, padx=3)

    # Summary Cards
    summary_frame = ttk.LabelFrame(scrollable, text="Overview", padding="10")
    summary_frame.pack(fill=tk.X, padx=15, pady=5)

    cards_frame = ttk.Frame(summary_frame)
    cards_frame.pack(fill=tk.X)
    for i in range(4):
        cards_frame.columnconfigure(i, weight=1)

    _create_stat_card(cards_frame, "Courses", str(len(data['courses_taught'])), 0, 0)
    _create_stat_card(cards_frame, "Students", str(data['total_students']), 0, 1)
    _create_stat_card(cards_frame, "Pending Grading", str(data['pending_grading']), 0, 2)
    _create_stat_card(cards_frame, "TAs", str(len(data['ta_assignments'])), 0, 3)

    # Courses Taught
    courses_frame = ttk.LabelFrame(scrollable, text="Courses Taught", padding="10")
    courses_frame.pack(fill=tk.X, padx=15, pady=5)

    if data['courses_taught']:
        cols = ('code', 'name', 'credits')
        tree = ttk.Treeview(courses_frame, columns=cols, show='headings',
                            height=min(5, len(data['courses_taught'])))
        tree.heading('code', text='Code')
        tree.heading('name', text='Course Name')
        tree.heading('credits', text='Credits')
        tree.column('code', width=120)
        tree.column('name', width=300)
        tree.column('credits', width=80)
        for c in data['courses_taught']:
            tree.insert('', tk.END, values=(
                c.get('module_code', ''),
                c.get('module_name', ''),
                c.get('credits', '')
            ))
        tree.pack(fill=tk.X)
    else:
        ttk.Label(courses_frame, text="No courses assigned.").pack(anchor="w")

    # Office Hours
    oh_frame = ttk.LabelFrame(scrollable, text="My Office Hours", padding="10")
    oh_frame.pack(fill=tk.X, padx=15, pady=5)

    if data['office_hours']:
        cols = ('day', 'time', 'location', 'capacity')
        tree = ttk.Treeview(oh_frame, columns=cols, show='headings',
                            height=min(4, len(data['office_hours'])))
        tree.heading('day', text='Day')
        tree.heading('time', text='Time')
        tree.heading('location', text='Location')
        tree.heading('capacity', text='Capacity')
        tree.column('day', width=100)
        tree.column('time', width=150)
        tree.column('location', width=150)
        tree.column('capacity', width=80)
        for oh in data['office_hours']:
            tree.insert('', tk.END, values=(
                oh.get('day_of_week', ''),
                f"{oh.get('start_time', '')} - {oh.get('end_time', '')}",
                oh.get('location', ''),
                oh.get('capacity', '')
            ))
        tree.pack(fill=tk.X)
    else:
        ttk.Label(oh_frame, text="No office hours configured.").pack(anchor="w")

    # Upcoming Bookings
    bookings_frame = ttk.LabelFrame(scrollable, text="Upcoming Bookings", padding="10")
    bookings_frame.pack(fill=tk.X, padx=15, pady=5)

    if data['upcoming_bookings']:
        cols = ('student', 'date', 'day', 'time', 'notes')
        tree = ttk.Treeview(bookings_frame, columns=cols, show='headings',
                            height=min(5, len(data['upcoming_bookings'])))
        tree.heading('student', text='Student')
        tree.heading('date', text='Date')
        tree.heading('day', text='Day')
        tree.heading('time', text='Time')
        tree.heading('notes', text='Notes')
        tree.column('student', width=120)
        tree.column('date', width=100)
        tree.column('day', width=80)
        tree.column('time', width=120)
        tree.column('notes', width=200)
        for b in data['upcoming_bookings']:
            tree.insert('', tk.END, values=(
                b.get('student_id', ''),
                b.get('booking_date', ''),
                b.get('day_of_week', ''),
                f"{b.get('start_time', '')} - {b.get('end_time', '')}",
                b.get('notes', '')
            ))
        tree.pack(fill=tk.X)
    else:
        ttk.Label(bookings_frame, text="No upcoming bookings.").pack(anchor="w")

    # TA Assignments
    if data['ta_assignments']:
        ta_frame = ttk.LabelFrame(scrollable, text="Teaching Assistants", padding="10")
        ta_frame.pack(fill=tk.X, padx=15, pady=5)

        cols = ('student', 'module', 'role', 'hours')
        tree = ttk.Treeview(ta_frame, columns=cols, show='headings',
                            height=min(4, len(data['ta_assignments'])))
        tree.heading('student', text='Student ID')
        tree.heading('module', text='Module')
        tree.heading('role', text='Role')
        tree.heading('hours', text='Hours/Week')
        tree.column('student', width=120)
        tree.column('module', width=150)
        tree.column('role', width=100)
        tree.column('hours', width=80)
        for t in data['ta_assignments']:
            tree.insert('', tk.END, values=(
                t.get('student_id', ''),
                t.get('module_code', ''),
                t.get('role_type', ''),
                t.get('hours_per_week', '')
            ))
        tree.pack(fill=tk.X)

    # --- Feature 21: At-Risk Students ---
    risk_frame = ttk.LabelFrame(scrollable, text="At-Risk Students", padding="10")
    risk_frame.pack(fill=tk.X, padx=15, pady=5)

    at_risk = data.get('at_risk_students', [])
    if at_risk:
        cols = ('student_id', 'name', 'module', 'risk_score', 'risk_level')
        tree = ttk.Treeview(risk_frame, columns=cols, show='headings',
                            height=min(6, len(at_risk)))
        tree.heading('student_id', text='Student ID')
        tree.heading('name', text='Name')
        tree.heading('module', text='Module')
        tree.heading('risk_score', text='Risk Score')
        tree.heading('risk_level', text='Risk Level')
        tree.column('student_id', width=100)
        tree.column('name', width=200)
        tree.column('module', width=120)
        tree.column('risk_score', width=80)
        tree.column('risk_level', width=100)
        tree.tag_configure('critical', background='#f8d7da')
        tree.tag_configure('high', background='#ffe0b2')
        tree.tag_configure('medium', background='#fff9c4')
        for r in at_risk:
            level = r.get('risk_level', 'medium').lower()
            tag = level if level in ('critical', 'high', 'medium') else ''
            tree.insert('', tk.END, values=(
                r.get('student_id', ''),
                r.get('name', ''),
                r.get('module_code', ''),
                r.get('overall_risk_score', ''),
                r.get('risk_level', ''),
            ), tags=(tag,))
        tree.pack(fill=tk.X)
    else:
        ttk.Label(risk_frame, text="No at-risk students detected.").pack(anchor="w")

    # --- Feature 22: Grading Backlog ---
    backlog_frame = ttk.LabelFrame(scrollable, text="Grading Backlog", padding="10")
    backlog_frame.pack(fill=tk.X, padx=15, pady=5)

    backlog = data.get('grading_backlog', [])
    if backlog:
        cols = ('assignment', 'module', 'ungraded', 'due_date')
        tree = ttk.Treeview(backlog_frame, columns=cols, show='headings',
                            height=min(6, len(backlog)))
        tree.heading('assignment', text='Assignment')
        tree.heading('module', text='Module')
        tree.heading('ungraded', text='Ungraded')
        tree.heading('due_date', text='Due Date')
        tree.column('assignment', width=250)
        tree.column('module', width=120)
        tree.column('ungraded', width=80)
        tree.column('due_date', width=120)
        for b in backlog:
            tree.insert('', tk.END, values=(
                b.get('assignment', ''),
                b.get('module_code', ''),
                b.get('ungraded_count', 0),
                b.get('due_date', ''),
            ))
        tree.pack(fill=tk.X)
    else:
        ttk.Label(backlog_frame, text="No ungraded submissions.").pack(anchor="w")

    # --- Feature 23: Announcements ---
    ann_frame = ttk.LabelFrame(scrollable, text="Recent Announcements", padding="10")
    ann_frame.pack(fill=tk.X, padx=15, pady=5)

    announcements = data.get('announcements', [])
    if announcements:
        for ann in announcements[:5]:
            a_row = ttk.Frame(ann_frame)
            a_row.pack(fill=tk.X, pady=2)
            priority = ann.get('priority', 'normal')
            prefix = "[!] " if priority in ('high', 'urgent') else ""
            ttk.Label(a_row, text=f"{prefix}{ann.get('title', 'Untitled')}",
                      font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
            ttk.Label(a_row, text=ann.get('created_at', ''),
                      font=('Arial', 8)).pack(side=tk.RIGHT)
    else:
        ttk.Label(ann_frame, text="No recent announcements.").pack(anchor="w")

    def _create_announcement():
        """Open a simple dialog to create an announcement."""
        dialog = tk.Toplevel(parent_frame.winfo_toplevel())
        dialog.title("Create Announcement")
        dialog.geometry("500x350")
        dialog.transient(parent_frame.winfo_toplevel())

        ttk.Label(dialog, text="Title:").pack(anchor="w", padx=10, pady=(10, 2))
        title_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=title_var, width=60).pack(padx=10)

        ttk.Label(dialog, text="Content:").pack(anchor="w", padx=10, pady=(5, 2))
        content_text = tk.Text(dialog, height=8, wrap=tk.WORD)
        content_text.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text="Priority:").pack(anchor="w", padx=10, pady=(5, 2))
        prio_var = tk.StringVar(value="normal")
        ttk.Combobox(dialog, textvariable=prio_var, state='readonly',
                      values=['low', 'normal', 'high', 'urgent'], width=15).pack(anchor="w", padx=10)

        def _save():
            title = title_var.get().strip()
            content = content_text.get("1.0", tk.END).strip()
            if not title or not content:
                messagebox.showwarning("Missing Fields", "Title and content are required.",
                                       parent=dialog)
                return
            try:
                from university_system.infrastructure.database.db import transaction
                with transaction() as conn:
                    conn.execute(
                        "INSERT INTO announcements (title, content, priority, created_by) "
                        "VALUES (?, ?, ?, ?)",
                        (title, content, prio_var.get(), instructor_id)
                    )
                messagebox.showinfo("Created", "Announcement created.", parent=dialog)
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed: {e}", parent=dialog)

        ttk.Button(dialog, text="Save", command=_save).pack(pady=10)

    ttk.Button(ann_frame, text="Create Announcement",
               command=_create_announcement).pack(anchor="w", pady=(5, 0))


def _create_stat_card(parent, label, value, row, col):
    """Create a small stat card widget."""
    frame = ttk.Frame(parent, relief="groove", borderwidth=1)
    frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
    ttk.Label(frame, text=value, font=('Arial', 18, 'bold')).pack(pady=(8, 2))
    ttk.Label(frame, text=label, font=('Arial', 9)).pack(pady=(0, 8))
