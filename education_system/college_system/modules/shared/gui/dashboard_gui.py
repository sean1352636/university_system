"""Dashboard GUI for the College Management System.

Displays a welcome banner, quick statistics, and recent activity summary.
Navigation is handled by the sidebar in the main application window.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.core.i18n import t
from education_system.college_system.modules.domain.students.services.student_service import StudentService
from education_system.college_system.modules.domain.courses.services.course_service import CourseService


HEADER_BG = "#2c3e50"
CARD_BG = "white"
BG = "#ecf0f1"

QUICK_ACTION_COLORS = [
    "#2980b9", "#27ae60", "#8e44ad", "#e67e22", "#16a085", "#c0392b",
    "#2c3e50", "#f39c12", "#1abc9c", "#e74c3c", "#3498db", "#9b59b6",
]

ROLE_QUICK_ACTIONS: dict[str, list[tuple[str, str]]] = {
    "admin": [
        ("Students", "student_gui"), ("Courses", "course_gui"),
        ("Grades", "grade_gui"), ("Attendance", "attendance_gui"),
        ("Timetable", "timetable_gui"), ("Reports", "reports_gui"),
        ("Finance", "finance_gui"), ("Staff HR", "staff_hr_gui"),
        ("User Management", "user_management_gui"), ("Admissions", "admissions_gui"),
        ("KPI Dashboard", "kpi_dashboard_gui"), ("Quality Assurance", "quality_assurance_gui"),
        ("Safeguarding", "safeguarding_gui"), ("SEND", "send_gui"),
        ("Settings", "settings_gui"),
    ],
    "staff": [
        ("Students", "student_gui"), ("Courses", "course_gui"),
        ("Grades", "grade_gui"), ("Attendance", "attendance_gui"),
        ("Timetable", "timetable_gui"), ("Reports", "reports_gui"),
        ("Pastoral", "pastoral_gui"), ("Safeguarding", "safeguarding_gui"),
        ("SEND", "send_gui"), ("Admissions", "admissions_gui"),
        ("Cover", "cover_gui"), ("Exams", "exams_gui"),
    ],
    "instructor": [
        ("Courses", "course_gui"), ("Grades", "grade_gui"),
        ("Attendance", "attendance_gui"), ("Timetable", "timetable_gui"),
        ("Markbook", "markbook_gui"), ("Lesson Plans", "lesson_plan_gui"),
        ("Assignments", "assignment_gui"), ("Reports", "reports_gui"),
        ("CPD", "cpd_gui"), ("Observations", "observation_gui"),
        ("ILP", "ilp_gui"), ("Data Dashboard", "data_dashboard_gui"),
    ],
    "student": [
        ("Assignments", "assignment_gui"), ("Timetable", "timetable_gui"),
        ("Grades", "grade_gui"), ("Messages", "message_gui"),
        ("Notifications", "notification_gui"), ("Portfolio", "portfolio_gui"),
        ("Study Planner", "study_planner_gui"), ("Careers", "careers_gui"),
        ("Progress Dashboard", "progress_dashboard_gui"), ("Helpdesk", "helpdesk_gui"),
        ("Library", "library_gui"), ("Enrichment", "enrichment_gui"),
    ],
    "parent": [
        ("Parent Portal", "parent_gui"), ("Parents Evening", "parents_evening_gui"),
        ("Messages", "message_gui"), ("Announcements", "announcement_gui"),
        ("Calendar", "calendar_gui"), ("Feedback", "feedback_gui"),
    ],
}

# Default actions used before role is known
_DEFAULT_QUICK_ACTIONS = [
    ("Students", "student_gui"), ("Courses", "course_gui"),
    ("Attendance", "attendance_gui"), ("Timetable", "timetable_gui"),
    ("Messages", "message_gui"), ("Reports", "reports_gui"),
]


class DashboardFrame(tk.Frame):
    """Main dashboard displayed after a successful login.

    Shows a welcome banner and quick statistics.  Navigation to modules
    is provided by the sidebar in CollegeApp, but the dashboard can still
    invoke on_navigate for any quick-action links it renders.
    """

    def __init__(self, parent, db_path=None, auth=None,
                 on_navigate=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._on_navigate = on_navigate

        self._student_svc = StudentService(db_path)
        self._course_svc = CourseService(db_path)

        self._user_info: dict | None = None

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg=BG)

        # --- Top welcome bar ---
        self._header = tk.Frame(self, bg=HEADER_BG, height=90)
        self._header.pack(fill="x")
        self._header.pack_propagate(False)

        left = tk.Frame(self._header, bg=HEADER_BG)
        left.pack(side="left", fill="y", padx=20)

        self._welcome_var = tk.StringVar(value=t("dashboard.welcome", username=""))
        tk.Label(
            left, textvariable=self._welcome_var,
            font=("Helvetica", 18, "bold"), bg=HEADER_BG, fg="white",
        ).pack(anchor="w", pady=(18, 0))

        self._role_var = tk.StringVar()
        tk.Label(
            left, textvariable=self._role_var,
            font=("Helvetica", 11), bg=HEADER_BG, fg="#bdc3c7",
        ).pack(anchor="w")

        # --- Statistics cards ---
        stats_outer = tk.Frame(self, bg=BG)
        stats_outer.pack(fill="x", padx=30, pady=(20, 10))

        tk.Label(
            stats_outer, text=t("dashboard.quick_stats"),
            font=("Helvetica", 13, "bold"), bg=BG, fg="#2c3e50",
        ).pack(anchor="w", pady=(0, 10))

        self._stats_container = tk.Frame(stats_outer, bg=BG)
        self._stats_container.pack(fill="x")

        self._stat_cards: dict[str, tk.StringVar] = {}
        for stat_key, i18n_key, colour in (
            ("total_students",  "dashboard.total_students",  "#2980b9"),
            ("active_students", "dashboard.active_students", "#27ae60"),
            ("total_courses",   "dashboard.total_courses",   "#8e44ad"),
            ("active_courses",  "dashboard.active_courses",  "#e67e22"),
        ):
            self._add_stat_card(self._stats_container, stat_key, t(i18n_key), colour)

        # --- Quick actions row ---
        actions_frame = tk.Frame(self, bg=BG)
        actions_frame.pack(fill="x", padx=30, pady=(10, 10))

        tk.Label(
            actions_frame, text="Quick Actions",
            font=("Helvetica", 13, "bold"), bg=BG, fg="#2c3e50",
        ).pack(anchor="w", pady=(0, 10))

        self._quick_actions_container = tk.Frame(actions_frame, bg=BG)
        self._quick_actions_container.pack(fill="x")

        self._rebuild_quick_actions()

        # --- Info / tips area ---
        info_frame = tk.Frame(self, bg=BG)
        info_frame.pack(fill="both", expand=True, padx=30, pady=(10, 20))

        tip_card = tk.Frame(info_frame, bg=CARD_BG, bd=1, relief="solid",
                            padx=20, pady=16)
        tip_card.pack(fill="x", anchor="n")

        tk.Label(
            tip_card, text="Getting Started",
            font=("Helvetica", 12, "bold"), bg=CARD_BG, fg="#2c3e50",
        ).pack(anchor="w", pady=(0, 6))

        tk.Label(
            tip_card,
            text="Use the sidebar on the left to navigate between modules. "
                 "Click a section header to expand it and see available options. "
                 "The quick action buttons above provide shortcuts to the most "
                 "commonly used modules.",
            font=("Helvetica", 10), bg=CARD_BG, fg="#636e72",
            wraplength=700, justify="left",
        ).pack(anchor="w")

    def _add_stat_card(self, parent, stat_key: str, label_text: str, colour: str):
        """Add a single stat card widget."""
        card = tk.Frame(parent, bg=CARD_BG, bd=1, relief="solid",
                        padx=20, pady=14)
        card.pack(side="left", padx=(0, 12), fill="x", expand=True)

        var = tk.StringVar(value="--")
        tk.Label(card, textvariable=var,
                 font=("Helvetica", 24, "bold"), bg=CARD_BG, fg=colour,
                 ).pack()
        tk.Label(card, text=label_text,
                 font=("Helvetica", 9), bg=CARD_BG, fg="#7f8c8d",
                 ).pack()

        self._stat_cards[stat_key] = var

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def set_user(self, user_info: dict):
        """Set the logged-in user and refresh the dashboard contents."""
        self._user_info = user_info
        self._welcome_var.set(t("dashboard.welcome", username=user_info.get('username', 'User')))
        self._role_var.set(t("dashboard.role_display", role=user_info.get('role', 'N/A').capitalize()))
        self._rebuild_quick_actions()
        self._refresh_stats()

    def refresh(self):
        """Refresh statistics (can be called when returning to the dashboard)."""
        self._refresh_stats()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _rebuild_quick_actions(self):
        """Clear and repopulate quick action buttons based on the current role."""
        for child in self._quick_actions_container.winfo_children():
            child.destroy()

        role = (self._user_info or {}).get("role", "").lower()
        actions = ROLE_QUICK_ACTIONS.get(role, _DEFAULT_QUICK_ACTIONS)

        cols = 6
        for idx, (label, target) in enumerate(actions):
            row, col = divmod(idx, cols)
            colour = QUICK_ACTION_COLORS[idx % len(QUICK_ACTION_COLORS)]
            btn = tk.Button(
                self._quick_actions_container, text=label,
                font=("Helvetica", 10, "bold"),
                bg=colour, fg="white", activebackground=colour,
                activeforeground="white", relief="flat", cursor="hand2",
                padx=16, pady=8,
                command=lambda t=target: self._navigate(t),
            )
            btn.grid(row=row, column=col, padx=(0, 8), pady=4, sticky="w")

    def _refresh_stats(self):
        """Fetch live counts from the services and update the stat cards."""
        try:
            total_students = self._student_svc.count_students()
            active_students = self._student_svc.count_students(status="active")
        except Exception:
            total_students = active_students = "?"

        try:
            total_courses = self._course_svc.count_courses()
            active_courses = self._course_svc.count_courses(status="active")
        except Exception:
            total_courses = active_courses = "?"

        self._stat_cards["total_students"].set(str(total_students))
        self._stat_cards["active_students"].set(str(active_students))
        self._stat_cards["total_courses"].set(str(total_courses))
        self._stat_cards["active_courses"].set(str(active_courses))

    def _navigate(self, target: str):
        """Invoke the navigation callback."""
        if self._on_navigate:
            self._on_navigate(target)
