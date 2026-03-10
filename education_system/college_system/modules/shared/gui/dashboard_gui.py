"""Dashboard GUI for the College Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.students.services.student_service import StudentService
from education_system.college_system.modules.domain.courses.services.course_service import CourseService


class DashboardFrame(tk.Frame):
    """Main dashboard displayed after a successful login.

    Shows a welcome banner, quick statistics, and navigation buttons to each
    domain module.  The set of visible navigation buttons adapts to the
    current user's role.
    """

    # Minimum role level required for each navigation target
    _NAV_ITEMS = [
        ("Students",      "student_gui",      "staff"),
        ("Staff",         "staff_gui",        "admin"),
        ("Courses",       "course_gui",       "student"),
        ("Enrollment",    "enrollment_gui",   "staff"),
        ("Grades",        "grade_gui",        "instructor"),
        ("Attendance",    "attendance_gui",    "instructor"),
        ("Timetable",     "timetable_gui",    "student"),
        ("Assignments",   "assignment_gui",   "student"),
        ("To-Do List",    "todo_gui",         "student"),
        ("Calendar",      "calendar_gui",     "student"),
        ("First Aid",     "first_aid_gui",    "staff"),
        ("Helpdesk",      "helpdesk_gui",     "student"),
        ("Parent Portal", "parent_gui",       "parent"),
        ("Notifications", "notification_gui", "student"),
        ("Messages",      "message_gui",      "student"),
        ("Settings",      "settings_gui",     "student"),
        ("MFA Settings",  "mfa_gui",          "student"),
        ("Admissions",    "admissions_gui",   "staff"),
        ("Safeguarding",  "safeguarding_gui", "staff"),
        ("Behaviour",     "behaviour_gui",    "staff"),
        ("Pastoral",      "pastoral_gui",     "staff"),
        ("SEND/ALS",      "send_gui",         "staff"),
        ("Exams",         "exams_gui",        "staff"),
        ("Compliance",    "compliance_gui",   "admin"),
        ("Reports",       "reports_gui",      "instructor"),
        ("Parents Evening", "parents_evening_gui", "student"),
        ("Careers",       "careers_gui",      "student"),
        ("Bursary",       "bursary_gui",      "admin"),
        ("Transport",     "transport_gui",    "admin"),
        ("Assets",        "assets_gui",       "staff"),
        ("Library",       "library_gui",      "student"),
        ("Staff HR",      "staff_hr_gui",     "admin"),
        ("Cover",         "cover_gui",        "staff"),
        ("Funding & ILR", "funding_gui",      "admin"),
        ("Destinations",  "destinations_gui", "staff"),
        ("Student Support", "student_support_gui", "staff"),
        ("Finance",       "finance_gui",      "admin"),
        ("Departments",   "departments_gui",  "admin"),
        # New feature modules
        ("CPD Records",   "cpd_gui",          "instructor"),
        ("Observations",  "observation_gui",  "instructor"),
        ("Appraisals",    "appraisal_gui",    "admin"),
        ("Resource Booking", "resource_booking_gui", "instructor"),
        ("Markbook",      "markbook_gui",     "instructor"),
        ("Staff Wellbeing", "staff_wellbeing_gui", "admin"),
        ("Lesson Plans",  "lesson_plan_gui",  "instructor"),
        ("Data Dashboard", "data_dashboard_gui", "instructor"),
        ("Absence Requests", "absence_request_gui", "instructor"),
        ("Interventions", "intervention_gui", "instructor"),
        ("Visitors",      "visitor_gui",      "staff"),
        ("Policies",      "policy_gui",       "staff"),
        ("GDPR",          "gdpr_gui",         "admin"),
        ("Quality Assurance", "quality_assurance_gui", "admin"),
        ("Bulk Operations", "bulk_operation_gui", "admin"),
        ("Emergency",     "emergency_gui",    "staff"),
        ("Academic Year",  "academic_year_gui", "admin"),
        ("KPI Dashboard", "kpi_dashboard_gui", "admin"),
        ("Audit Reports", "audit_report_gui", "admin"),
        ("User Management", "user_management_gui", "admin"),
        ("Portfolio",     "portfolio_gui",    "student"),
        ("Study Planner", "study_planner_gui", "student"),
        ("Enrichment",    "enrichment_gui",   "student"),
        ("Peer Mentoring", "peer_mentoring_gui", "student"),
        ("Surveys",       "survey_gui",       "student"),
        ("Skills Passport", "skills_passport_gui", "student"),
        ("Progress",      "progress_dashboard_gui", "student"),
        ("Meal Ordering", "meal_ordering_gui", "student"),
        ("Print Credits", "print_credit_gui", "student"),
        ("Work Journal",  "work_journal_gui", "student"),
        ("Announcements", "announcement_gui", "student"),
        ("Document Hub",  "document_hub_gui", "student"),
        ("Search",        "advanced_search_gui", "student"),
        ("Feedback",      "feedback_gui",     "student"),
        ("Accessibility", "accessibility_gui", "student"),
        ("Mobile Dashboard", "mobile_dashboard_gui", "student"),
        ("Attachments",   "attachment_gui",   "student"),
        ("Activity Feed", "activity_feed_gui", "student"),
        ("SMS & Email",   "sms_email_gui",    "student"),
        ("Multi-Language", "multi_language_gui", "student"),
        # New modules
        ("ILP",             "ilp_gui",          "instructor"),
        ("UCAS Applications", "ucas_gui",       "staff"),
        ("T-Levels",        "tlevel_gui",       "staff"),
        ("Apprenticeships", "apprenticeship_gui", "staff"),
        ("Value-Added",     "value_added_gui",  "instructor"),
        ("Governance",      "governance_gui",   "admin"),
        ("DBS Checks",      "dbs_check_gui",    "admin"),
        ("Risk Management", "risk_management_gui", "admin"),
        ("Prevent Duty",    "prevent_duty_gui", "staff"),
        ("Complaints",      "complaint_gui",    "admin"),
        ("Equality & Diversity", "equality_diversity_gui", "admin"),
        ("Staff Absence",   "staff_absence_gui", "admin"),
        ("Recruitment",     "recruitment_gui",  "admin"),
        ("Marketing",       "marketing_gui",    "admin"),
        ("Early Warning",   "early_warning_gui", "instructor"),
        ("Self-Assessment", "self_assessment_gui", "admin"),
        ("Alumni",          "alumni_gui",       "staff"),
        ("Student Portal",  "student_portal_gui", "student"),
        ("Forums",          "forum_gui",        "student"),
        # Batch 2 modules
        ("Internal Verification", "internal_verification_gui", "instructor"),
        ("Functional Skills", "functional_skills_gui", "staff"),
        ("Study Programmes", "study_programme_gui", "staff"),
        ("Tutorial",        "tutorial_gui",     "instructor"),
        ("Student Wellbeing", "student_wellbeing_gui", "staff"),
        ("Student Council", "student_council_gui", "student"),
        ("Lettings",        "lettings_gui",     "admin"),
        ("Health & Safety", "health_safety_gui", "admin"),
        ("Letter Templates", "letter_template_gui", "staff"),
        ("Disciplinary",    "disciplinary_gui", "admin"),
        ("Onboarding",      "onboarding_gui",   "admin"),
        ("Expense Claims",  "expense_claim_gui", "staff"),
        ("Baseline Assessment", "baseline_assessment_gui", "instructor"),
        ("Data Export",     "data_export_gui",  "admin"),
    ]

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
        self.configure(bg="#ecf0f1")

        # --- Top welcome bar ---
        self._header = tk.Frame(self, bg="#2c3e50", height=80)
        self._header.pack(fill="x")
        self._header.pack_propagate(False)

        self._welcome_var = tk.StringVar(value="Welcome!")
        tk.Label(
            self._header, textvariable=self._welcome_var,
            font=("Helvetica", 16, "bold"), bg="#2c3e50", fg="white",
        ).pack(side="left", padx=20, pady=20)

        self._role_var = tk.StringVar()
        tk.Label(
            self._header, textvariable=self._role_var,
            font=("Helvetica", 11), bg="#2c3e50", fg="#bdc3c7",
        ).pack(side="right", padx=20, pady=20)

        # --- Stats section ---
        stats_frame = tk.Frame(self, bg="#ecf0f1")
        stats_frame.pack(fill="x", padx=30, pady=(20, 10))

        tk.Label(
            stats_frame, text="Quick Statistics",
            font=("Helvetica", 13, "bold"), bg="#ecf0f1", fg="#2c3e50",
        ).pack(anchor="w", pady=(0, 8))

        self._stats_container = tk.Frame(stats_frame, bg="#ecf0f1")
        self._stats_container.pack(fill="x")

        # Stat cards (created once, text updated on refresh)
        self._stat_cards: dict[str, tk.StringVar] = {}
        for label_text in ("Total Students", "Active Students",
                           "Total Courses", "Active Courses"):
            self._add_stat_card(self._stats_container, label_text)

        # --- Scrollable navigation section ---
        nav_section = tk.Frame(self, bg="#ecf0f1")
        nav_section.pack(fill="both", expand=True, padx=30, pady=(10, 20))

        tk.Label(
            nav_section, text="Navigation",
            font=("Helvetica", 13, "bold"), bg="#ecf0f1", fg="#2c3e50",
        ).pack(anchor="w", pady=(0, 8))

        # Canvas + scrollbar for the navigation buttons
        nav_canvas_container = tk.Frame(nav_section, bg="#ecf0f1")
        nav_canvas_container.pack(fill="both", expand=True)

        self._nav_canvas = tk.Canvas(nav_canvas_container, bg="#ecf0f1",
                                      highlightthickness=0)
        nav_vsb = ttk.Scrollbar(nav_canvas_container, orient="vertical",
                                 command=self._nav_canvas.yview)
        self._nav_frame = tk.Frame(self._nav_canvas, bg="#ecf0f1")

        self._nav_frame.bind(
            "<Configure>",
            lambda e: self._nav_canvas.configure(
                scrollregion=self._nav_canvas.bbox("all")),
        )
        self._nav_canvas_window = self._nav_canvas.create_window(
            (0, 0), window=self._nav_frame, anchor="nw")
        self._nav_canvas.configure(yscrollcommand=nav_vsb.set)

        # Resize the inner frame width to match the canvas
        self._nav_canvas.bind("<Configure>", self._on_nav_canvas_resize)

        # Mousewheel scrolling
        self._nav_canvas.bind("<Enter>", self._bind_mousewheel)
        self._nav_canvas.bind("<Leave>", self._unbind_mousewheel)

        self._nav_canvas.pack(side="left", fill="both", expand=True)
        nav_vsb.pack(side="right", fill="y")

    def _add_stat_card(self, parent, label_text: str):
        """Add a single stat card widget."""
        card = tk.Frame(parent, bg="white", bd=1, relief="solid",
                        padx=16, pady=12)
        card.pack(side="left", padx=(0, 12), fill="x", expand=True)

        var = tk.StringVar(value="--")
        tk.Label(card, textvariable=var,
                 font=("Helvetica", 20, "bold"), bg="white", fg="#2980b9",
                 ).pack()
        tk.Label(card, text=label_text,
                 font=("Helvetica", 9), bg="white", fg="#7f8c8d",
                 ).pack()

        self._stat_cards[label_text] = var

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def set_user(self, user_info: dict):
        """Set the logged-in user and refresh the dashboard contents."""
        self._user_info = user_info
        self._welcome_var.set(f"Welcome, {user_info.get('username', 'User')}!")
        self._role_var.set(f"Role: {user_info.get('role', 'N/A').capitalize()}")
        self._refresh_stats()
        self._build_nav_buttons()

    def refresh(self):
        """Refresh statistics (can be called when returning to the dashboard)."""
        self._refresh_stats()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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

        self._stat_cards["Total Students"].set(str(total_students))
        self._stat_cards["Active Students"].set(str(active_students))
        self._stat_cards["Total Courses"].set(str(total_courses))
        self._stat_cards["Active Courses"].set(str(active_courses))

    def _build_nav_buttons(self):
        """Build navigation buttons appropriate for the current user role."""
        # Clear existing buttons
        for child in self._nav_frame.winfo_children():
            child.destroy()

        if not self._user_info:
            return

        from education_system.college_system.infrastructure.auth.role_manager import ROLE_HIERARCHY

        user_role = self._user_info.get("role", "student")
        user_level = ROLE_HIERARCHY.get(user_role, 0)

        COLS_PER_ROW = 5
        col = 0
        for label, target, min_role in self._NAV_ITEMS:
            required_level = ROLE_HIERARCHY.get(min_role, 0)
            if user_level >= required_level:
                row = col // COLS_PER_ROW
                col_in_row = col % COLS_PER_ROW
                btn = ttk.Button(
                    self._nav_frame,
                    text=label,
                    command=lambda t=target: self._navigate(t),
                )
                btn.grid(row=row, column=col_in_row, padx=8, pady=8,
                         ipadx=20, ipady=10)
                col += 1

        # Make columns expand equally
        for c in range(COLS_PER_ROW):
            self._nav_frame.columnconfigure(c, weight=1)

    def _on_nav_canvas_resize(self, event):
        """Keep the inner frame width in sync with the canvas."""
        self._nav_canvas.itemconfigure(self._nav_canvas_window, width=event.width)

    def _bind_mousewheel(self, event):
        self._nav_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self._nav_canvas.bind_all("<Button-4>", self._on_mousewheel)
        self._nav_canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _unbind_mousewheel(self, event):
        self._nav_canvas.unbind_all("<MouseWheel>")
        self._nav_canvas.unbind_all("<Button-4>")
        self._nav_canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        # Linux uses Button-4/5, Windows/Mac uses MouseWheel
        if event.num == 4:
            self._nav_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._nav_canvas.yview_scroll(1, "units")
        else:
            self._nav_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _navigate(self, target: str):
        """Invoke the navigation callback."""
        if self._on_navigate:
            self._on_navigate(target)
        else:
            messagebox.showinfo("Navigate", f"Navigate to: {target}")
