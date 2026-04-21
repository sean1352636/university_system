"""Main GUI application for the Secondary School Management System.

Provides login, dashboard, and categorised navigation to all modules.
Layout and colour scheme matches the University System GUI.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import traceback

from education_system.secondary_school.core.logs import setup_logging
from education_system.secondary_school.infrastructure.database.schema import (
    initialise_database, seed_default_users, seed_default_staff,
)
from education_system.secondary_school.infrastructure.auth.core import UserAuth

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════
#  Main application
# ══════════════════════════════════════════════════════════════════════════

class MainApplication(tk.Tk):
    """Root window with categorised navigation and dynamic content area.

    Mirrors the University System GUI layout: ttk clam theme, grid-based
    LabelFrame panels, and category buttons that expand into sub-windows.
    """

    # Quick action configuration for the dashboard
    _QUICK_ACTIONS = {
        "admin": [
            "Students", "Subjects", "Grades", "Attendance", "Timetable",
            "Behaviour", "Exams", "Homework", "SEND", "Safeguarding",
            "HR", "Finance", "Users", "Admissions", "Reports", "Payroll",
            "Staff Directory", "Settings",
        ],
        "staff": [
            "Students", "Subjects", "Grades", "Attendance", "Timetable",
            "Behaviour", "Exams", "Homework", "SEND", "Safeguarding",
            "HR", "Finance", "Users", "Admissions", "Reports", "Payroll",
            "Staff Directory", "Settings",
        ],
        "teacher": [
            "Students", "Grades", "Attendance", "Timetable", "Behaviour",
            "Exams", "Homework", "Calendar", "Announcements", "SEND",
            "Cover", "Rewards", "Lesson Plans", "Staff Directory",
        ],
        "instructor": [
            "Students", "Grades", "Attendance", "Timetable", "Behaviour",
            "Exams", "Homework", "Calendar", "Announcements", "SEND",
            "Cover", "Rewards", "Lesson Plans", "Staff Directory",
        ],
        "parent": [
            "Announcements", "Calendar", "Parents Evening", "Notifications",
        ],
        "student": [
            "Grades", "Timetable", "Exams", "Homework", "Calendar",
            "Announcements", "Library", "Clubs", "Rewards", "Portfolio",
            "Study Planner", "LMS",
        ],
    }

    _ACTION_COLORS = [
        "#2980b9", "#27ae60", "#8e44ad", "#e67e22", "#16a085", "#c0392b",
        "#2c3e50", "#f39c12", "#1abc9c", "#e74c3c", "#3498db", "#9b59b6",
    ]

    def __init__(self, user: dict, db_path: str | None = None):
        super().__init__()
        self._db_path = db_path
        self._user = user
        self._frames: dict[str, tk.Frame] = {}

        self.title("Secondary School Management System")
        self.geometry("1200x800")
        self.minsize(1000, 700)

        # Configure ttk style to match university
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Status variables
        self.current_user_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")

        self._setup_gui()
        self._update_status()
        self._show_welcome()

        # Idle / inactivity auto-logout (30 minutes)
        from education_system.shared.gui.idle_timeout import attach_idle_timeout
        self._cancel_idle_timeout = attach_idle_timeout(
            self, self._idle_logout, timeout_minutes=30,
        )
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _idle_logout(self):
        """Auto-logout fired by the idle-timeout watchdog."""
        from education_system.switch import request_logout
        request_logout()
        self.destroy()

    def _on_close(self):
        try:
            self._cancel_idle_timeout()
        except Exception:
            pass
        self.destroy()

    # ── GUI setup ─────────────────────────────────────────────────────

    def _setup_gui(self):
        """Setup the GUI interface matching university layout."""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=0)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)

        self._create_header(main_frame)
        self._create_navigation_panel(main_frame)
        self._create_content_area(main_frame)

    def _create_header(self, parent):
        """Create header with system status and control buttons."""
        header_frame = ttk.LabelFrame(parent, text="System Control", padding="10")
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        button_frame = ttk.Frame(header_frame)
        button_frame.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 10))

        ttk.Button(button_frame, text="Shutdown",
                   command=self._on_shutdown).pack(side="left", padx=(0, 10))
        ttk.Button(button_frame, text="Logout",
                   command=self._on_logout).pack(side="left", padx=(0, 10))
        ttk.Button(button_frame, text="Switch to CLI",
                   command=self._switch_to_cli).pack(side="left", padx=(0, 10))

        if self._is_superadmin():
            ttk.Button(button_frame, text="Switch System",
                       command=self._on_switch_system).pack(side="left", padx=(0, 10))

        ttk.Label(header_frame, text="Status:").grid(row=1, column=0, sticky="w")
        ttk.Label(header_frame, textvariable=self.status_var).grid(row=1, column=1, sticky="w", padx=(10, 0))

        ttk.Label(header_frame, text="Current User:").grid(row=2, column=0, sticky="w")
        ttk.Label(header_frame, textvariable=self.current_user_var).grid(row=2, column=1, sticky="w", padx=(10, 0))

        header_frame.columnconfigure(1, weight=1)

    def _create_navigation_panel(self, parent):
        """Create navigation panel with categorised buttons and scrollbar."""
        nav_frame = ttk.LabelFrame(parent, text="Navigation", padding="5")
        nav_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))

        nav_frame.rowconfigure(0, weight=1)
        nav_frame.columnconfigure(0, weight=1)

        canvas = tk.Canvas(nav_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(nav_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind("<Configure>",
                              lambda _: canvas.configure(scrollregion=canvas.bbox("all")))

        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_mousewheel_linux(event):
            canvas.yview_scroll(-3 if event.num == 4 else 3, "units")

        canvas.bind('<Enter>', lambda e: (
            canvas.bind_all("<MouseWheel>", _on_mousewheel),
            canvas.bind_all("<Button-4>", _on_mousewheel_linux),
            canvas.bind_all("<Button-5>", _on_mousewheel_linux),
        ))
        canvas.bind('<Leave>', lambda e: (
            canvas.unbind_all("<MouseWheel>"),
            canvas.unbind_all("<Button-4>"),
            canvas.unbind_all("<Button-5>"),
        ))

        def configure_canvas_width(_):
            canvas.itemconfig(canvas_window, width=canvas.winfo_width())
        canvas.bind('<Configure>', configure_canvas_width)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._build_navigation_categories(scrollable_frame)

        scrollable_frame.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _build_navigation_categories(self, parent):
        """Create category buttons that expand into sub-windows."""
        role = self._user.get("role", "")

        admin_only = {
            "HR", "Finance", "Payroll", "Users", "Data Export", "Safeguarding",
            "Visitors", "Assets", "Admissions", "Settings", "Audit Log", "Policies",
            "Exclusions", "Consent", "Incidents",
            "Central Admin Portal", "GDPR Compliance", "Academic Misconduct",
            "Complaints", "GDPR", "Data Dashboard", "Appraisals", "Observations",
            "Student Journey", "Analytics Dashboard", "Outcome Tracking",
            "Predictive Alerts", "Bulk Transfer", "Transfer Documents",
            "Reverse Lookup", "Parent Continuity", "Cross-System Calendar",
            "Shared Documents", "Student Self-Service", "Digital Transcript",
        }
        student_modules = {
            "Dashboard", "Grades", "Timetable", "Exams", "Homework",
            "Calendar", "Announcements", "Library", "Clubs",
            "Staff Directory", "Email", "Notifications", "Rewards",
            "MFA Settings", "Security Questions", "LMS",
            "Portfolio", "Skills Passport", "Study Planner",
            "Feedback", "Student Council",
        }
        parent_modules = {
            "Dashboard", "Announcements", "Calendar",
            "Notifications", "Parents Evening", "MFA Settings",
            "Security Questions",
        }

        def is_visible(name):
            if role in ("admin", "staff"):
                return True
            elif role == "student":
                return name in student_modules
            elif role == "parent":
                return name in parent_modules
            elif role in ("teacher", "instructor"):
                return name not in admin_only
            return name == "Dashboard"

        def open_category_window(category_title, buttons_data):
            visible_buttons = [(n, t) for n, t in buttons_data if is_visible(n)]
            if not visible_buttons:
                messagebox.showinfo("Info", f"No features available in {category_title}")
                return

            cols = 4
            cat_window = tk.Toplevel(self)
            cat_window.title(category_title)
            cat_window.geometry("820x500")
            cat_window.transient(self)

            header = tk.Frame(cat_window, bg='#2c3e50', height=50)
            header.pack(fill='x')
            header.pack_propagate(False)
            tk.Label(header, text=category_title, font=('Arial', 16, 'bold'),
                     bg='#2c3e50', fg='white').pack(expand=True)

            cat_canvas = tk.Canvas(cat_window, highlightthickness=0)
            cat_scrollbar = ttk.Scrollbar(cat_window, orient="vertical", command=cat_canvas.yview)
            scrollable = ttk.Frame(cat_canvas)

            scrollable.bind("<Configure>",
                            lambda e: cat_canvas.configure(scrollregion=cat_canvas.bbox("all")))
            canvas_win = cat_canvas.create_window((0, 0), window=scrollable, anchor="nw")
            cat_canvas.configure(yscrollcommand=cat_scrollbar.set)

            def _resize_inner(event):
                cat_canvas.itemconfig(canvas_win, width=event.width)
            cat_canvas.bind('<Configure>', _resize_inner)

            cat_canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
            cat_scrollbar.pack(side="right", fill="y")

            for c in range(cols):
                scrollable.columnconfigure(c, weight=1)

            for idx, (module_name, display_text) in enumerate(visible_buttons):
                def make_command(name, window):
                    def wrapped():
                        window.destroy()
                        self._show_module(name)
                    return wrapped

                r = idx // cols
                c = idx % cols
                btn = ttk.Button(scrollable, text=display_text,
                                 command=make_command(module_name, cat_window))
                btn.grid(row=r, column=c, padx=4, pady=4, sticky='nsew')

            ttk.Button(cat_window, text="Close",
                       command=cat_window.destroy).pack(pady=10)

        # ── Category definitions ──────────────────────────────────────
        categories = [
            ("Academics", [
                ("Students", "Students"),
                ("Subjects", "Subjects"),
                ("Enrollment", "Enrollment"),
                ("Grades", "Grades"),
                ("Homework", "Homework"),
                ("Progress", "Progress"),
                ("Interventions", "Interventions"),
                ("Portfolio", "Portfolio"),
                ("Skills Passport", "Skills Passport"),
                ("Study Planner", "Study Planner"),
                ("LMS", "Learning Management"),
            ]),
            ("Scheduling & Attendance", [
                ("Attendance", "Attendance"),
                ("Timetable", "Timetable"),
                ("Calendar", "Calendar"),
            ]),
            ("Exams & Reports", [
                ("Exams", "Exams"),
                ("Reports", "Reports"),
                ("Data Dashboard", "Data Dashboard"),
            ]),
            ("Pastoral Care", [
                ("Behaviour", "Behaviour"),
                ("Rewards", "Rewards"),
                ("Detentions", "Detentions"),
                ("Exclusions", "Exclusions"),
                ("Safeguarding", "Safeguarding"),
                ("SEND", "SEND"),
                ("Pastoral", "Pastoral"),
                ("Student Wellbeing", "Student Wellbeing"),
                ("Intervention Tracking", "Intervention Tracking"),
            ]),
            ("Staff", [
                ("Staff Directory", "Staff Directory"),
                ("HR", "HR"),
                ("CPD", "CPD"),
                ("Cover", "Cover"),
                ("Appraisals", "Appraisals"),
                ("Observations", "Observations"),
                ("Staff Wellbeing", "Staff Wellbeing"),
                ("Lesson Plans", "Lesson Plans"),
            ]),
            ("Student Life", [
                ("Clubs", "Clubs"),
                ("Library", "Library"),
                ("Meals", "Meals"),
                ("Medical", "Medical"),
                ("Trips", "Trips"),
                ("Transport", "Transport"),
                ("Careers", "Careers"),
                ("Form Groups", "Form Groups"),
                ("Seating Plans", "Seating Plans"),
                ("Student Council", "Student Council"),
                ("Consent", "Consent"),
            ]),
            ("Communication", [
                ("Announcements", "Announcements"),
                ("Calendar", "Calendar"),
                ("Notifications", "Notifications"),
                ("Email", "Email"),
                ("Parents Evening", "Parents Evening"),
                ("Comms Log", "Communication Log"),
                ("Feedback", "Feedback"),
            ]),
            ("Administration", [
                ("Admissions", "Admissions"),
                ("Finance", "Finance"),
                ("Payroll", "Payroll"),
                ("Policies", "Policies"),
                ("Documents", "Documents"),
                ("Users", "User Management"),
                ("Settings", "Settings"),
                ("Audit Log", "Audit Log"),
                ("Data Export", "Data Export"),
                ("Complaints", "Complaints"),
                ("GDPR", "GDPR"),
                ("Academic Misconduct", "Academic Misconduct"),
            ]),
            ("Facilities", [
                ("Room Booking", "Room Booking"),
                ("Assets", "Assets"),
                ("Visitors", "Visitors"),
                ("Incidents", "Incidents"),
            ]),
            ("Security", [
                ("MFA Settings", "MFA Settings"),
                ("Security Questions", "Security Questions"),
            ]),
            ("Cross-System", [
                ("Student Journey", "Student Journey"),
                ("Analytics Dashboard", "Analytics Dashboard"),
                ("Outcome Tracking", "Outcome Tracking"),
                ("Predictive Alerts", "Predictive Alerts"),
                ("Bulk Transfer", "Bulk Transfer"),
                ("Transfer Documents", "Transfer Documents"),
                ("Reverse Lookup", "Reverse Lookup"),
                ("Parent Continuity", "Parent Continuity"),
                ("Cross-System Calendar", "Cross-System Calendar"),
                ("Central Admin Portal", "Central Admin Portal"),
                ("GDPR Compliance", "GDPR Compliance"),
                ("Shared Documents", "Shared Documents"),
                ("Student Self-Service", "Student Self-Service"),
                ("Digital Transcript", "Digital Transcript"),
                ("Certificates", "Certificates"),
                ("Extras & Tools", "Extras & Tools"),
            ]),
        ]

        # Dashboard button always first
        if is_visible("Dashboard"):
            ttk.Button(parent, text="Dashboard",
                       command=lambda: self._show_module("Dashboard")).pack(fill="x", pady=2, padx=5)

        for cat_title, buttons_data in categories:
            visible_in_cat = [b for b in buttons_data if is_visible(b[0])]
            if visible_in_cat:
                ttk.Button(
                    parent, text=cat_title + " \u25b6",
                    command=lambda t=cat_title, d=buttons_data: open_category_window(t, d),
                ).pack(fill="x", pady=2, padx=5)

    def _create_content_area(self, parent):
        """Create the main content area with scrollbar."""
        outer_frame = ttk.LabelFrame(parent, text="Content", padding="5")
        outer_frame.grid(row=1, column=1, sticky="nsew")
        outer_frame.columnconfigure(0, weight=1)
        outer_frame.rowconfigure(0, weight=1)

        self._content_canvas = tk.Canvas(outer_frame, highlightthickness=0)
        self._content_canvas.grid(row=0, column=0, sticky="nsew")

        v_scrollbar = ttk.Scrollbar(outer_frame, orient="vertical", command=self._content_canvas.yview)
        v_scrollbar.grid(row=0, column=1, sticky="ns")

        h_scrollbar = ttk.Scrollbar(outer_frame, orient="horizontal", command=self._content_canvas.xview)
        h_scrollbar.grid(row=1, column=0, sticky="ew")

        self._content_canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        self._content = ttk.Frame(self._content_canvas, padding="10")
        self._content_window = self._content_canvas.create_window((0, 0), window=self._content, anchor="nw")

        self._content.bind("<Configure>",
                           lambda _: self._content_canvas.configure(scrollregion=self._content_canvas.bbox("all")))

        def configure_canvas_width(event):
            self._content_canvas.itemconfig(self._content_window, width=event.width)
        self._content_canvas.bind("<Configure>", configure_canvas_width)

        def on_mousewheel(event):
            self._content_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def on_mousewheel_linux(event):
            self._content_canvas.yview_scroll(-3 if event.num == 4 else 3, "units")

        self._content_canvas.bind("<Enter>", lambda e: (
            self._content_canvas.bind_all("<MouseWheel>", on_mousewheel),
            self._content_canvas.bind_all("<Button-4>", on_mousewheel_linux),
            self._content_canvas.bind_all("<Button-5>", on_mousewheel_linux),
        ))
        self._content_canvas.bind("<Leave>", lambda e: (
            self._content_canvas.unbind_all("<MouseWheel>"),
            self._content_canvas.unbind_all("<Button-4>"),
            self._content_canvas.unbind_all("<Button-5>"),
        ))

        self._content.columnconfigure(0, weight=1)
        self._content.rowconfigure(0, weight=1)

        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(1, weight=1)

    # ── Status ────────────────────────────────────────────────────────

    def _update_status(self):
        user = self._user
        display = user.get("username", "Unknown")
        role = user.get("role", "unknown")
        self.current_user_var.set(f"{display} ({role})")
        self.status_var.set("Logged in")

    # ── Welcome / content ─────────────────────────────────────────────

    def _show_welcome(self):
        """Show the welcome dashboard in the content area."""
        self._clear_content()

        welcome = ttk.Frame(self._content)
        welcome.pack(fill="both", expand=True)

        user_display = self._user.get("username", "User")
        role_display = self._user.get("role", "").title()

        ttk.Label(welcome, text=f"Welcome, {user_display}",
                  font=("Helvetica", 18, "bold")).pack(pady=(25, 2))
        ttk.Label(welcome, text=f"Role: {role_display}",
                  font=("Helvetica", 11)).pack()
        ttk.Label(welcome, text="Secondary School Management System",
                  font=("Helvetica", 12)).pack(pady=(2, 20))

        # Stats cards
        self._build_stats(welcome)

        # Quick actions
        self._build_quick_actions(welcome)

        self._frames["Dashboard"] = welcome

    def _build_stats(self, parent):
        """Build summary statistics cards."""
        cards_frame = ttk.Frame(parent)
        cards_frame.pack(fill="x", padx=30, pady=(0, 10))

        try:
            from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
            from education_system.secondary_school.modules.domain.academics.subjects.services.subject_service import SubjectService

            stu_svc = StudentService(self._db_path)
            subj_svc = SubjectService(self._db_path)

            stats = [
                ("Total Students", str(stu_svc.count_students()), "#2ecc71"),
                ("Active Students", str(stu_svc.count_students(status="active")), "#3498db"),
                ("Year 7", str(stu_svc.count_students(year_group="7")), "#9b59b6"),
                ("Year 8", str(stu_svc.count_students(year_group="8")), "#e67e22"),
                ("Year 9", str(stu_svc.count_students(year_group="9")), "#1abc9c"),
                ("Year 10", str(stu_svc.count_students(year_group="10")), "#e74c3c"),
                ("Year 11", str(stu_svc.count_students(year_group="11")), "#f39c12"),
                ("Subjects", str(len(subj_svc.list_subjects(status="active"))), "#34495e"),
            ]
        except Exception:
            stats = [("Total Students", "0", "#2ecc71")]

        for idx, (label, value, colour) in enumerate(stats):
            row, col = divmod(idx, 4)
            card = tk.Frame(cards_frame, bg=colour, padx=15, pady=10)
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            tk.Label(card, text=value, font=("Helvetica", 22, "bold"),
                     bg=colour, fg="white").pack()
            tk.Label(card, text=label, font=("Helvetica", 10),
                     bg=colour, fg="white").pack()
            cards_frame.columnconfigure(col, weight=1)

    def _build_quick_actions(self, parent):
        """Build role-appropriate quick action buttons."""
        role = self._user.get("role", "student")
        actions = self._QUICK_ACTIONS.get(role, self._QUICK_ACTIONS.get("student", []))
        if not actions:
            return

        ttk.Label(parent, text="Quick Actions",
                  font=("Helvetica", 14, "bold")).pack(pady=(20, 8))

        qa_frame = ttk.Frame(parent)
        qa_frame.pack(fill="x", padx=30)

        cols = 6
        for i, action in enumerate(actions):
            color = self._ACTION_COLORS[i % len(self._ACTION_COLORS)]
            btn = tk.Button(
                qa_frame, text=action, font=("Helvetica", 9, "bold"),
                bg=color, fg="white", bd=0, padx=10, pady=8,
                activebackground=color, activeforeground="white",
                cursor="hand2",
                command=lambda a=action: self._show_module(a),
            )
            btn.grid(row=i // cols, column=i % cols, padx=4, pady=4, sticky="ew")
        for c in range(cols):
            qa_frame.columnconfigure(c, weight=1)

    # ── Module loading ────────────────────────────────────────────────

    def _get_module_classes(self):
        """Lazy-import all module frame classes. Returns dict of name -> class."""
        from education_system.secondary_school.modules.domain.academics.students.gui.student_gui import StudentFrame
        from education_system.secondary_school.modules.domain.academics.subjects.gui.subject_gui import SubjectFrame
        from education_system.secondary_school.modules.domain.academics.enrollment.gui.enrollment_gui import EnrollmentFrame
        from education_system.secondary_school.modules.domain.academics.grades.gui.grade_gui import GradeFrame
        from education_system.secondary_school.modules.domain.academics.attendance.gui.attendance_gui import AttendanceFrame
        from education_system.secondary_school.modules.domain.academics.timetable.gui.timetable_gui import TimetableFrame
        from education_system.secondary_school.modules.domain.pastoral_care.behaviour.gui.behaviour_gui import BehaviourFrame
        from education_system.secondary_school.modules.domain.communication.email.gui.email_gui import EmailFrame
        from education_system.secondary_school.modules.domain.academics.exams.gui.exam_gui import ExamFrame
        from education_system.secondary_school.modules.domain.staff.hr.gui.hr_gui import HRFrame
        from education_system.secondary_school.modules.domain.admin.finance.gui.finance_gui import FinanceFrame
        from education_system.secondary_school.modules.domain.admin.payroll.gui.payroll_gui import PayrollFrame
        from education_system.secondary_school.modules.domain.academics.reports.gui.report_gui import ReportFrame
        from education_system.secondary_school.modules.domain.pastoral_care.send.gui.send_gui import SENDFrame
        from education_system.secondary_school.modules.domain.pastoral_care.safeguarding.gui.safeguarding_gui import SafeguardingFrame
        from education_system.secondary_school.modules.domain.communication.parents_evening.gui.parents_evening_gui import ParentsEveningFrame
        from education_system.secondary_school.modules.domain.staff.cover.gui.cover_gui import CoverFrame
        from education_system.secondary_school.modules.domain.academics.homework.gui.homework_gui import HomeworkFrame
        from education_system.secondary_school.modules.domain.communication.calendar.gui.calendar_gui import CalendarFrame
        from education_system.secondary_school.modules.domain.communication.announcements.gui.announcement_gui import AnnouncementFrame
        from education_system.secondary_school.modules.domain.admin.users.gui.user_gui import UserFrame
        from education_system.secondary_school.modules.domain.pastoral_care.pastoral.gui.pastoral_gui import PastoralFrame
        from education_system.secondary_school.modules.domain.student_life.library.gui.library_gui import LibraryFrame
        from education_system.secondary_school.modules.domain.admin.data_export.gui.export_gui import ExportFrame
        from education_system.secondary_school.modules.domain.student_life.medical.gui.medical_gui import MedicalFrame
        from education_system.secondary_school.modules.domain.student_life.meals.gui.meals_gui import MealsFrame
        from education_system.secondary_school.modules.domain.student_life.trips.gui.trips_gui import TripsFrame
        from education_system.secondary_school.modules.domain.student_life.clubs.gui.clubs_gui import ClubsFrame
        from education_system.secondary_school.modules.domain.pastoral_care.detentions.gui.detention_gui import DetentionFrame
        from education_system.secondary_school.modules.domain.admin.documents.gui.document_gui import DocumentFrame
        from education_system.secondary_school.modules.domain.facilities.visitors.gui.visitor_gui import VisitorFrame
        from education_system.secondary_school.modules.domain.facilities.room_booking.gui.room_booking_gui import RoomBookingFrame
        from education_system.secondary_school.modules.domain.staff.staff_directory.gui.staff_directory_gui import StaffDirectoryFrame
        from education_system.secondary_school.modules.domain.facilities.assets.gui.asset_gui import AssetFrame
        from education_system.secondary_school.modules.domain.admin.settings.gui.settings_gui import SettingsFrame
        from education_system.secondary_school.modules.domain.admin.admissions.gui.admissions_gui import AdmissionsFrame
        from education_system.secondary_school.modules.domain.communication.notifications.gui.notification_gui import NotificationFrame
        from education_system.secondary_school.modules.domain.academics.interventions.gui.intervention_gui import InterventionFrame
        from education_system.secondary_school.modules.domain.staff.cpd.gui.cpd_gui import CPDFrame
        from education_system.secondary_school.modules.domain.student_life.transport.gui.transport_gui import TransportFrame
        from education_system.secondary_school.modules.domain.pastoral_care.rewards.gui.rewards_gui import RewardsFrame
        from education_system.secondary_school.modules.domain.student_life.careers.gui.careers_gui import CareersFrame
        from education_system.secondary_school.modules.domain.student_life.form_groups.gui.form_group_gui import FormGroupFrame
        from education_system.secondary_school.modules.domain.admin.audit_log.gui.audit_gui import AuditFrame
        from education_system.secondary_school.modules.domain.admin.policies.gui.policy_gui import PolicyFrame
        from education_system.secondary_school.modules.domain.communication.communication_log.gui.comms_gui import CommsFrame
        from education_system.secondary_school.modules.domain.pastoral_care.exclusions.gui.exclusion_gui import ExclusionFrame
        from education_system.secondary_school.modules.domain.academics.progress.gui.progress_gui import ProgressFrame
        from education_system.secondary_school.modules.domain.facilities.seating_plans.gui.seating_gui import SeatingFrame
        from education_system.secondary_school.modules.domain.student_life.consent.gui.consent_gui import ConsentFrame
        from education_system.secondary_school.modules.domain.facilities.incidents.gui.incident_gui import IncidentFrame
        from education_system.secondary_school.modules.shared.gui.mfa_gui import MFASettingsFrame
        from education_system.shared.gui.security_questions_gui import SecurityQuestionsFrame
        from education_system.shared.cross_system.journey_dashboard import JourneyDashboardFrame
        from education_system.shared.analytics.analytics_gui import AnalyticsDashboardFrame
        from education_system.shared.outcomes.outcomes_gui import OutcomeTrackingFrame
        from education_system.shared.predictive.predictive_gui import PredictiveAlertsFrame
        from education_system.shared.bulk_transfer.bulk_transfer_gui import BulkTransferFrame
        from education_system.shared.transfer_docs.transfer_docs_gui import TransferDocumentsFrame
        from education_system.shared.reverse_lookup.reverse_lookup_gui import ReverseLookupFrame
        from education_system.shared.parent_continuity.parent_gui import ParentContinuityFrame
        from education_system.shared.calendar.calendar_gui import CrossSystemCalendarFrame
        from education_system.shared.admin_portal.admin_gui import CentralAdminFrame
        from education_system.shared.gdpr.gdpr_gui import GDPRComplianceFrame
        from education_system.shared.documents.document_gui import SharedDocumentsFrame
        from education_system.shared.student_portal.portal_gui import StudentSelfServiceFrame
        from education_system.shared.transcript.transcript_gui import DigitalTranscriptFrame
        from education_system.shared.certificates.certificates_gui import CertificatesGUI
        from education_system.shared.extras.extras_frame import ExtrasFrame
        from education_system.shared.academic_misconduct.misconduct_frame import MisconductFrame
        from education_system.shared.lms.lms_gui import LMSFrame
        from education_system.secondary_school.modules.domain.pastoral_care.student_wellbeing.gui.student_wellbeing_gui import StudentWellbeingFrame
        from education_system.secondary_school.modules.domain.pastoral_care.interventions.gui.intervention_gui import InterventionFrame as InterventionTrackingFrame
        from education_system.secondary_school.modules.domain.communication.feedback.gui.feedback_gui import FeedbackFrame
        from education_system.secondary_school.modules.domain.admin.complaints.gui.complaints_gui import ComplaintsFrame
        from education_system.secondary_school.modules.domain.admin.gdpr.gui.gdpr_gui import GDPRFrame
        from education_system.secondary_school.modules.domain.admin.data_dashboard.gui.data_dashboard_gui import DataDashboardFrame
        from education_system.secondary_school.modules.domain.staff.appraisals.gui.appraisals_gui import AppraisalsFrame
        from education_system.secondary_school.modules.domain.staff.observations.gui.observations_gui import ObservationsFrame
        from education_system.secondary_school.modules.domain.staff.staff_wellbeing.gui.staff_wellbeing_gui import StaffWellbeingFrame
        from education_system.secondary_school.modules.domain.staff.lesson_plans.gui.lesson_plans_gui import LessonPlansFrame
        from education_system.secondary_school.modules.domain.student_life.portfolio.gui.portfolio_gui import PortfolioFrame
        from education_system.secondary_school.modules.domain.student_life.skills_passport.gui.skills_passport_gui import SkillsPassportFrame
        from education_system.secondary_school.modules.domain.student_life.student_council.gui.student_council_gui import StudentCouncilFrame
        from education_system.secondary_school.modules.domain.student_life.study_planner.gui.study_planner_gui import StudyPlannerFrame

        return {
            "Students": StudentFrame, "Subjects": SubjectFrame,
            "Enrollment": EnrollmentFrame, "Grades": GradeFrame,
            "Attendance": AttendanceFrame, "Timetable": TimetableFrame,
            "Behaviour": BehaviourFrame, "Exams": ExamFrame,
            "Homework": HomeworkFrame, "Calendar": CalendarFrame,
            "Announcements": AnnouncementFrame, "Reports": ReportFrame,
            "SEND": SENDFrame, "Safeguarding": SafeguardingFrame,
            "Pastoral": PastoralFrame, "Parents Evening": ParentsEveningFrame,
            "Cover": CoverFrame, "Medical": MedicalFrame,
            "Meals": MealsFrame, "Trips": TripsFrame,
            "Clubs": ClubsFrame, "Detentions": DetentionFrame,
            "Library": LibraryFrame, "Documents": DocumentFrame,
            "Staff Directory": StaffDirectoryFrame, "Room Booking": RoomBookingFrame,
            "Visitors": VisitorFrame, "Assets": AssetFrame,
            "Interventions": InterventionFrame, "Admissions": AdmissionsFrame,
            "Transport": TransportFrame, "CPD": CPDFrame,
            "Notifications": NotificationFrame, "Email": EmailFrame,
            "Users": UserFrame, "HR": HRFrame,
            "Finance": FinanceFrame, "Payroll": PayrollFrame,
            "Data Export": ExportFrame, "Settings": SettingsFrame,
            "Rewards": RewardsFrame, "Careers": CareersFrame,
            "Form Groups": FormGroupFrame, "Audit Log": AuditFrame,
            "Policies": PolicyFrame, "Comms Log": CommsFrame,
            "Exclusions": ExclusionFrame, "Progress": ProgressFrame,
            "Seating Plans": SeatingFrame, "Consent": ConsentFrame,
            "Incidents": IncidentFrame, "MFA Settings": MFASettingsFrame,
            "Security Questions": SecurityQuestionsFrame,
            "Student Journey": JourneyDashboardFrame,
            "Analytics Dashboard": AnalyticsDashboardFrame,
            "Outcome Tracking": OutcomeTrackingFrame,
            "Predictive Alerts": PredictiveAlertsFrame,
            "Bulk Transfer": BulkTransferFrame,
            "Transfer Documents": TransferDocumentsFrame,
            "Reverse Lookup": ReverseLookupFrame,
            "Parent Continuity": ParentContinuityFrame,
            "Cross-System Calendar": CrossSystemCalendarFrame,
            "Central Admin Portal": CentralAdminFrame,
            "GDPR Compliance": GDPRComplianceFrame,
            "Shared Documents": SharedDocumentsFrame,
            "Student Self-Service": StudentSelfServiceFrame,
            "Digital Transcript": DigitalTranscriptFrame,
            "Certificates": CertificatesGUI, "Extras & Tools": ExtrasFrame,
            "Academic Misconduct": MisconductFrame, "LMS": LMSFrame,
            "Student Wellbeing": StudentWellbeingFrame,
            "Intervention Tracking": InterventionTrackingFrame,
            "Feedback": FeedbackFrame, "Complaints": ComplaintsFrame,
            "GDPR": GDPRFrame, "Data Dashboard": DataDashboardFrame,
            "Appraisals": AppraisalsFrame, "Observations": ObservationsFrame,
            "Staff Wellbeing": StaffWellbeingFrame,
            "Lesson Plans": LessonPlansFrame, "Portfolio": PortfolioFrame,
            "Skills Passport": SkillsPassportFrame,
            "Student Council": StudentCouncilFrame,
            "Study Planner": StudyPlannerFrame,
        }

    # ── Navigation ────────────────────────────────────────────────────

    def _clear_content(self):
        for widget in self._content.winfo_children():
            widget.destroy()
        self._frames.clear()

    def _show_module(self, name: str):
        """Show a module frame in the content area."""
        if name == "Dashboard":
            self._show_welcome()
            return

        if name not in self._frames:
            try:
                classes = self._get_module_classes()
                frame_cls = classes.get(name)
                if frame_cls is None:
                    logger.error("No frame class for module: %s", name)
                    return

                if frame_cls.__name__ == 'MisconductFrame':
                    frame = frame_cls(self._content, db_path=self._db_path, auth=self._user, system_key='secondary')
                else:
                    frame = frame_cls(self._content, db_path=self._db_path, auth=self._user)
                self._frames[name] = frame
            except Exception as e:
                logger.error("Failed to load module %s: %s", name, e, exc_info=True)
                traceback.print_exc()
                err_frame = ttk.Frame(self._content)
                ttk.Label(err_frame, text=f"Failed to load {name}:\n{e}",
                          foreground="red", font=("Helvetica", 11)).pack(expand=True)
                self._frames[name] = err_frame

        for frame in self._content.winfo_children():
            frame.pack_forget()

        frame = self._frames[name]
        frame.pack(fill="both", expand=True)
        if hasattr(frame, "refresh"):
            try:
                frame.refresh()
            except Exception as e:
                logger.error("Error refreshing %s: %s", name, e, exc_info=True)
                traceback.print_exc()

    # ── Actions ───────────────────────────────────────────────────────

    def _switch_to_cli(self):
        if messagebox.askyesno("Switch to CLI", "Switch to the command-line interface?"):
            from education_system.switch import request_switch
            request_switch("school", "cli")
            self.destroy()

    def _on_switch_system(self):
        picker = tk.Toplevel(self)
        picker.title("Switch System")
        picker.resizable(False, False)
        picker.grab_set()
        picker.transient(self)

        body = ttk.Frame(picker, padding="30 20")
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Switch to:", font=("Helvetica", 14, "bold")).pack(pady=(0, 15))

        btn_style = {"font": ("Helvetica", 12), "fg": "white", "relief": "flat",
                     "cursor": "hand2", "width": 30, "height": 2}

        def _pick(system):
            picker.destroy()
            from education_system.switch import request_switch
            request_switch(system, "gui")
            self.destroy()

        tk.Button(body, text="University Management System",
                  bg="#2980b9", activebackground="#3498db", activeforeground="white",
                  command=lambda: _pick("university"), **btn_style).pack(pady=5)
        tk.Button(body, text="Sixth Form College System",
                  bg="#27ae60", activebackground="#2ecc71", activeforeground="white",
                  command=lambda: _pick("college"), **btn_style).pack(pady=5)
        tk.Button(body, text="Primary School System",
                  bg="#e67e22", activebackground="#f39c12", activeforeground="white",
                  command=lambda: _pick("primary"), **btn_style).pack(pady=5)

        if self._is_superadmin():
            ttk.Separator(body, orient="horizontal").pack(fill="x", pady=10)
            tk.Button(body, text="Super Admin Dashboard",
                      bg="#2c3e50", activebackground="#34495e", activeforeground="white",
                      command=lambda: _pick("__superadmin__"), **btn_style).pack(pady=5)

        ttk.Button(body, text="Cancel", command=picker.destroy).pack(pady=(10, 0))

    def _is_superadmin(self):
        user = getattr(self, "_user", None) or {}
        systems = user.get("systems", [])
        if not systems:
            return False
        admin_keys = {s["system_key"] for s in systems if s.get("role") == "admin"}
        return admin_keys >= {"university", "college", "school", "primary"}

    def _on_logout(self):
        if messagebox.askyesno("Logout", "Are you sure you want to logout?"):
            from education_system.switch import request_logout
            request_logout()
            self.destroy()

    def _on_shutdown(self):
        if messagebox.askyesno("Shutdown", "Are you sure you want to shut down the application?"):
            self.destroy()


# ══════════════════════════════════════════════════════════════════════════
#  Application entry
# ══════════════════════════════════════════════════════════════════════════

def run(db_path: str | None = None, user_info=None, role=None, shared_auth=None):
    """Entry point: initialise DB, show login, launch main app."""
    setup_logging()

    from education_system.secondary_school.infrastructure.database.db import get_db_path
    from pathlib import Path
    db_file = Path(db_path) if db_path else Path(get_db_path())
    first_run = not db_file.exists()

    initialise_database(db_path)
    seed_default_users(db_path)
    seed_default_staff(db_path)

    if first_run:
        from education_system.secondary_school.scripts.seed_subjects import seed_subjects
        seed_subjects(db_path)

    if user_info and role:
        user = {
            "id": user_info.get("user_id"),
            "username": user_info.get("username"),
            "role": role,
            "email": user_info.get("email"),
            "systems": user_info.get("systems", []),
        }
        app = MainApplication(user, db_path)
        app.mainloop()
        return

    from education_system.shared.gui.login_gui import UniversalLoginWindow
    login = UniversalLoginWindow()
    login.mainloop()

    if login.user_info is None:
        return

    user = {
        "id": login.user_info.get("user_id"),
        "username": login.user_info.get("username"),
        "role": login.system_role or "admin",
        "email": login.user_info.get("email"),
        "systems": login.user_info.get("systems", []),
    }
    app = MainApplication(user, db_path)
    app.mainloop()


if __name__ == "__main__":
    run()
