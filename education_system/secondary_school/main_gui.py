"""Main GUI application for the Secondary School Management System.

Provides a login screen and a tabbed main interface with modules for:
- Students, Subjects, Enrollment, Grades, Attendance, Timetable, Behaviour

Run with:
    /home/seancatchpole989/venv/bin/python -m education_system.secondary_school.main_gui
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

from education_system.secondary_school.core.logs import setup_logging
from education_system.secondary_school.infrastructure.database.schema import (
    initialise_database, seed_default_users, seed_default_staff,
)
from education_system.secondary_school.infrastructure.auth.core import UserAuth

logger = logging.getLogger(__name__)

# Module colours
HEADER_BG = "#1a5276"
SIDEBAR_BG = "#2c3e50"
MAIN_BG = "#ecf0f1"


class DashboardFrame(tk.Frame):
    """Dashboard / home screen with summary stats."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)

        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Dashboard", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)

        self._stats_frame = tk.Frame(self, bg=MAIN_BG, pady=20)
        self._stats_frame.pack(fill="x", padx=20)

        # Welcome message
        user_display = self._auth.get("username", "User") if self._auth else "User"
        role_display = self._auth.get("role", "").title() if self._auth else ""
        tk.Label(self._stats_frame,
                 text=f"Welcome, {user_display} ({role_display})",
                 font=("Helvetica", 14), bg=MAIN_BG).pack(anchor="w", pady=(0, 20))

        self._cards_frame = tk.Frame(self._stats_frame, bg=MAIN_BG)
        self._cards_frame.pack(fill="x")

    def refresh(self):
        for w in self._cards_frame.winfo_children():
            w.destroy()

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

            for i, (label, value, color) in enumerate(stats):
                card = tk.Frame(self._cards_frame, bg=color, width=120, height=80,
                                bd=0, highlightthickness=0)
                card.grid(row=i // 4, column=i % 4, padx=8, pady=8, sticky="nsew")
                card.grid_propagate(False)
                tk.Label(card, text=value, font=("Helvetica", 20, "bold"),
                         bg=color, fg="white").pack(expand=True)
                tk.Label(card, text=label, font=("Helvetica", 9),
                         bg=color, fg="white").pack(pady=(0, 8))

        except Exception as exc:
            tk.Label(self._cards_frame, text=f"Error loading stats: {exc}",
                     bg=MAIN_BG, fg="red").pack()


class MainApplication(tk.Tk):
    """Main application window with sidebar navigation and module frames."""

    def __init__(self, user: dict, db_path: str | None = None):
        super().__init__()
        self.title("Secondary School Management System")
        self.geometry("1100x700")
        self.minsize(900, 600)
        self._user = user
        self._db_path = db_path
        self._frames: dict[str, tk.Frame] = {}
        self._build_ui()
        self._show_module("Dashboard")

    def _build_ui(self):
        # Top bar
        top = tk.Frame(self, bg=HEADER_BG, height=40)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(top, text="Secondary School Management System",
                 font=("Helvetica", 12, "bold"), bg=HEADER_BG, fg="white").pack(
            side="left", padx=15)
        tk.Label(top, text=f"Logged in: {self._user['username']} ({self._user['role']})",
                 font=("Helvetica", 9), bg=HEADER_BG, fg="#aed6f1").pack(
            side="right", padx=15)

        # Sidebar + content
        body = tk.Frame(self)
        body.pack(fill="both", expand=True)

        sidebar_outer = tk.Frame(body, bg=SIDEBAR_BG, width=180)
        sidebar_outer.pack(side="left", fill="y")
        sidebar_outer.pack_propagate(False)

        # Scrollable sidebar using Canvas + Scrollbar
        sidebar_canvas = tk.Canvas(sidebar_outer, bg=SIDEBAR_BG, highlightthickness=0)
        sidebar_scrollbar = tk.Scrollbar(sidebar_outer, orient="vertical", command=sidebar_canvas.yview)
        sidebar_canvas.configure(yscrollcommand=sidebar_scrollbar.set)
        sidebar_scrollbar.pack(side="right", fill="y")
        sidebar_canvas.pack(side="top", fill="both", expand=True)
        sidebar = tk.Frame(sidebar_canvas, bg=SIDEBAR_BG)
        sidebar_canvas.create_window((0, 0), window=sidebar, anchor="nw", width=164)

        def _on_sidebar_configure(event):
            sidebar_canvas.configure(scrollregion=sidebar_canvas.bbox("all"))
        sidebar.bind("<Configure>", _on_sidebar_configure)

        # Cross-platform mousewheel scrolling
        def _on_mousewheel(event):
            sidebar_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        def _on_mousewheel_linux(event):
            if event.num == 4:
                sidebar_canvas.yview_scroll(-3, "units")
            elif event.num == 5:
                sidebar_canvas.yview_scroll(3, "units")
        sidebar_canvas.bind_all("<MouseWheel>", _on_mousewheel, add="+")
        sidebar_canvas.bind_all("<Button-4>", _on_mousewheel_linux, add="+")
        sidebar_canvas.bind_all("<Button-5>", _on_mousewheel_linux, add="+")

        # Bottom buttons frame (outside scrollable area)
        bottom_frame = tk.Frame(sidebar_outer, bg=SIDEBAR_BG)
        bottom_frame.pack(side="bottom", fill="x")

        self._content = tk.Frame(body, bg=MAIN_BG)
        self._content.pack(side="left", fill="both", expand=True)

        # Module definitions — full list for admin
        modules = [
            ("Dashboard", None),
            ("Students", None),
            ("Subjects", None),
            ("Enrollment", None),
            ("Grades", None),
            ("Attendance", None),
            ("Timetable", None),
            ("Behaviour", None),
            ("Exams", None),
            ("Homework", None),
            ("Calendar", None),
            ("Announcements", None),
            ("Reports", None),
            ("SEND", None),
            ("Safeguarding", None),
            ("Pastoral", None),
            ("Parents Evening", None),
            ("Cover", None),
            ("Medical", None),
            ("Meals", None),
            ("Trips", None),
            ("Clubs", None),
            ("Detentions", None),
            ("Library", None),
            ("Documents", None),
            ("Exclusions", None),
            ("Rewards", None),
            ("Progress", None),
            ("Careers", None),
            ("Form Groups", None),
            ("Seating Plans", None),
            ("Staff Directory", None),
            ("Room Booking", None),
            ("Comms Log", None),
            ("Consent", None),
            ("Incidents", None),
            ("Visitors", None),
            ("Assets", None),
            ("Email", None),
            ("Notifications", None),
            ("Interventions", None),
            ("CPD", None),
            ("Transport", None),
            ("Policies", None),
            ("Audit Log", None),
            ("Admissions", None),
            ("Settings", None),
            ("Users", None),
            ("HR", None),
            ("Finance", None),
            ("Payroll", None),
            ("Data Export", None),
            ("MFA Settings", None),
            ("Cross-System Notifications", None),
            ("Student Journey", None),
            # Shared modules
            ("Analytics Dashboard", None),
            ("Outcome Tracking", None),
            ("Predictive Alerts", None),
            ("Bulk Transfer", None),
            ("Transfer Documents", None),
            ("Reverse Lookup", None),
            ("Parent Continuity", None),
            ("Cross-System Calendar", None),
            ("Inter-System Messaging", None),
            ("Central Admin Portal", None),
            ("GDPR Compliance", None),
            ("Shared Documents", None),
            ("Student Self-Service", None),
            ("Digital Transcript", None),
            ("Certificates", None),
            ("Extras & Tools", None),
            ("Academic Misconduct", None),
            ("LMS", None),
            # New modules
            ("Student Wellbeing", None),
            ("Intervention Tracking", None),
            ("Feedback", None),
            ("Complaints", None),
            ("GDPR", None),
            ("Data Dashboard", None),
            ("Appraisals", None),
            ("Observations", None),
            ("Staff Wellbeing", None),
            ("Lesson Plans", None),
            ("Portfolio", None),
            ("Skills Passport", None),
            ("Student Council", None),
            ("Study Planner", None),
        ]

        # Admin-only modules
        admin_only = {"HR", "Finance", "Payroll", "Users", "Data Export", "Safeguarding", "Visitors", "Assets",
                          "Admissions", "Settings", "Audit Log", "Policies",
                          "Exclusions", "Consent", "Incidents",
                          "Central Admin Portal", "GDPR Compliance", "Academic Misconduct",
                          "Complaints", "GDPR", "Data Dashboard", "Appraisals", "Observations",
                          "Cross-System Notifications", "Student Journey",
                          "Analytics Dashboard", "Outcome Tracking", "Predictive Alerts",
                          "Bulk Transfer", "Transfer Documents", "Reverse Lookup",
                          "Parent Continuity", "Cross-System Calendar", "Inter-System Messaging",
                          "Shared Documents", "Student Self-Service", "Digital Transcript"}
        # Modules students can see
        student_modules = {"Dashboard", "Grades", "Timetable", "Exams", "Homework",
                           "Calendar", "Announcements", "Library", "Clubs",
                           "Staff Directory", "Email", "Notifications", "Rewards",
                           "MFA Settings", "LMS",
                           "Portfolio", "Skills Passport", "Study Planner",
                           "Feedback", "Student Council"}

        if self._user["role"] == "student":
            modules = [m for m in modules if m[0] in student_modules]
        elif self._user["role"] == "teacher":
            modules = [m for m in modules if m[0] not in admin_only]

        self._nav_buttons = {}
        for name, _ in modules:
            btn = tk.Button(
                sidebar, text=name, font=("Helvetica", 10),
                bg=SIDEBAR_BG, fg="white", bd=0, pady=12,
                activebackground="#34495e", activeforeground="white",
                anchor="w", padx=20,
                command=lambda n=name: self._show_module(n),
            )
            btn.pack(fill="x")
            self._nav_buttons[name] = btn

        # Switch System (superadmin only), Logout and Shutdown in bottom frame
        if self._is_superadmin():
            tk.Button(
                bottom_frame, text="Switch System", font=("Helvetica", 10),
                bg="#2980b9", fg="white", bd=0, pady=12,
                activebackground="#3498db", activeforeground="white",
                command=self._on_switch_system,
            ).pack(fill="x")
        tk.Button(
            bottom_frame, text="Logout", font=("Helvetica", 10),
            bg="#c0392b", fg="white", bd=0, pady=12,
            activebackground="#e74c3c", activeforeground="white",
            command=self._on_logout,
        ).pack(fill="x")
        tk.Button(
            bottom_frame, text="Shutdown", font=("Helvetica", 10),
            bg="#7b241c", fg="white", bd=0, pady=12,
            activebackground="#922b21", activeforeground="white",
            command=self._on_shutdown,
        ).pack(fill="x")

        # Create module frames
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
        from education_system.shared.notifications.gui import CrossSystemNotificationsFrame
        from education_system.shared.cross_system.journey_dashboard import JourneyDashboardFrame
        from education_system.shared.analytics.analytics_gui import AnalyticsDashboardFrame
        from education_system.shared.outcomes.outcomes_gui import OutcomeTrackingFrame
        from education_system.shared.predictive.predictive_gui import PredictiveAlertsFrame
        from education_system.shared.bulk_transfer.bulk_transfer_gui import BulkTransferFrame
        from education_system.shared.transfer_docs.transfer_docs_gui import TransferDocumentsFrame
        from education_system.shared.reverse_lookup.reverse_lookup_gui import ReverseLookupFrame
        from education_system.shared.parent_continuity.parent_gui import ParentContinuityFrame
        from education_system.shared.calendar.calendar_gui import CrossSystemCalendarFrame
        from education_system.shared.messaging.messaging_gui import InterSystemMessagingFrame
        from education_system.shared.admin_portal.admin_gui import CentralAdminFrame
        from education_system.shared.gdpr.gdpr_gui import GDPRComplianceFrame
        from education_system.shared.documents.document_gui import SharedDocumentsFrame
        from education_system.shared.student_portal.portal_gui import StudentSelfServiceFrame
        from education_system.shared.transcript.transcript_gui import DigitalTranscriptFrame
        from education_system.shared.certificates.certificates_gui import CertificatesGUI
        from education_system.shared.extras.extras_frame import ExtrasFrame
        from education_system.shared.academic_misconduct.misconduct_frame import MisconductFrame
        from education_system.shared.lms.lms_gui import LMSFrame
        # New modules
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

        frame_classes = {
            "Dashboard": DashboardFrame,
            "Students": StudentFrame,
            "Subjects": SubjectFrame,
            "Enrollment": EnrollmentFrame,
            "Grades": GradeFrame,
            "Attendance": AttendanceFrame,
            "Timetable": TimetableFrame,
            "Behaviour": BehaviourFrame,
            "Exams": ExamFrame,
            "Homework": HomeworkFrame,
            "Calendar": CalendarFrame,
            "Announcements": AnnouncementFrame,
            "Reports": ReportFrame,
            "SEND": SENDFrame,
            "Safeguarding": SafeguardingFrame,
            "Pastoral": PastoralFrame,
            "Parents Evening": ParentsEveningFrame,
            "Cover": CoverFrame,
            "Medical": MedicalFrame,
            "Meals": MealsFrame,
            "Trips": TripsFrame,
            "Clubs": ClubsFrame,
            "Detentions": DetentionFrame,
            "Library": LibraryFrame,
            "Documents": DocumentFrame,
            "Staff Directory": StaffDirectoryFrame,
            "Room Booking": RoomBookingFrame,
            "Visitors": VisitorFrame,
            "Assets": AssetFrame,
            "Interventions": InterventionFrame,
            "Admissions": AdmissionsFrame,
            "Transport": TransportFrame,
            "CPD": CPDFrame,
            "Notifications": NotificationFrame,
            "Email": EmailFrame,
            "Users": UserFrame,
            "HR": HRFrame,
            "Finance": FinanceFrame,
            "Payroll": PayrollFrame,
            "Data Export": ExportFrame,
            "Settings": SettingsFrame,
            "Rewards": RewardsFrame,
            "Careers": CareersFrame,
            "Form Groups": FormGroupFrame,
            "Audit Log": AuditFrame,
            "Policies": PolicyFrame,
            "Comms Log": CommsFrame,
            "Exclusions": ExclusionFrame,
            "Progress": ProgressFrame,
            "Seating Plans": SeatingFrame,
            "Consent": ConsentFrame,
            "Incidents": IncidentFrame,
            "MFA Settings": MFASettingsFrame,
            "Cross-System Notifications": CrossSystemNotificationsFrame,
            "Student Journey": JourneyDashboardFrame,
            # Shared modules
            "Analytics Dashboard": AnalyticsDashboardFrame,
            "Outcome Tracking": OutcomeTrackingFrame,
            "Predictive Alerts": PredictiveAlertsFrame,
            "Bulk Transfer": BulkTransferFrame,
            "Transfer Documents": TransferDocumentsFrame,
            "Reverse Lookup": ReverseLookupFrame,
            "Parent Continuity": ParentContinuityFrame,
            "Cross-System Calendar": CrossSystemCalendarFrame,
            "Inter-System Messaging": InterSystemMessagingFrame,
            "Central Admin Portal": CentralAdminFrame,
            "GDPR Compliance": GDPRComplianceFrame,
            "Shared Documents": SharedDocumentsFrame,
            "Student Self-Service": StudentSelfServiceFrame,
            "Digital Transcript": DigitalTranscriptFrame,
            "Certificates": CertificatesGUI,
            "Extras & Tools": ExtrasFrame,
            "Academic Misconduct": MisconductFrame,
            "LMS": LMSFrame,
            # New modules
            "Student Wellbeing": StudentWellbeingFrame,
            "Intervention Tracking": InterventionTrackingFrame,
            "Feedback": FeedbackFrame,
            "Complaints": ComplaintsFrame,
            "GDPR": GDPRFrame,
            "Data Dashboard": DataDashboardFrame,
            "Appraisals": AppraisalsFrame,
            "Observations": ObservationsFrame,
            "Staff Wellbeing": StaffWellbeingFrame,
            "Lesson Plans": LessonPlansFrame,
            "Portfolio": PortfolioFrame,
            "Skills Passport": SkillsPassportFrame,
            "Student Council": StudentCouncilFrame,
            "Study Planner": StudyPlannerFrame,
        }

        for name, cls in frame_classes.items():
            if name in [n for n, _ in modules]:
                if cls is MisconductFrame:
                    frame = cls(self._content, db_path=self._db_path, auth=self._user, system_key='secondary')
                else:
                    frame = cls(self._content, db_path=self._db_path, auth=self._user)
                self._frames[name] = frame

    def _show_module(self, name: str):
        # Hide all frames
        for frame in self._frames.values():
            frame.pack_forget()

        # Highlight active nav button
        for btn_name, btn in self._nav_buttons.items():
            if btn_name == name:
                btn.configure(bg="#34495e")
            else:
                btn.configure(bg=SIDEBAR_BG)

        # Show selected frame
        if name in self._frames:
            frame = self._frames[name]
            frame.pack(fill="both", expand=True)
            if hasattr(frame, "refresh"):
                frame.refresh()

    def _on_switch_system(self):
        """Show a dialog to pick which system to switch to."""
        dlg = tk.Toplevel(self)
        dlg.title("Switch System")
        dlg.resizable(False, False)
        dlg.grab_set()

        body = tk.Frame(dlg, padx=30, pady=20)
        body.pack(fill=tk.BOTH, expand=True)
        tk.Label(body, text="Switch to:", font=("Helvetica", 14, "bold")).pack(pady=(0, 15))

        btn_style = {"font": ("Helvetica", 12), "fg": "white", "relief": tk.FLAT,
                     "cursor": "hand2", "width": 30, "height": 2}

        def _pick(system):
            dlg.destroy()
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

        # Super Admin Dashboard button (only for superadmin users)
        if self._is_superadmin():
            ttk.Separator(body, orient="horizontal").pack(fill="x", pady=10)
            tk.Button(body, text="Super Admin Dashboard",
                      bg="#2c3e50", activebackground="#34495e", activeforeground="white",
                      command=lambda: _pick("__superadmin__"), **btn_style).pack(pady=5)

        tk.Button(body, text="Cancel", font=("Helvetica", 12), relief=tk.FLAT,
                  padx=20, pady=4, cursor="hand2", command=dlg.destroy).pack(pady=(10, 0))

        dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)

    def _is_superadmin(self):
        """Check if current user has admin access to all 4 systems."""
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
        if messagebox.askyesno("Shutdown", "Are you sure you want to shut down the application?\n\n"
                               "This will close the program completely."):
            self.destroy()


def run(db_path: str | None = None, user_info=None, role=None, shared_auth=None):
    """Entry point: initialise DB, show login, launch main app.

    If *user_info* and *role* are provided (from universal login), the
    login dialog is skipped.
    """
    setup_logging()

    # Seed subjects on first run (when the DB file doesn't exist yet)
    from education_system.secondary_school.infrastructure.database.db import get_db_path
    from pathlib import Path
    db_file = Path(db_path) if db_path else Path(get_db_path())
    first_run = not db_file.exists()

    initialise_database(db_path)
    seed_default_users(db_path)
    seed_default_staff(db_path)

    if first_run:
        from education_system.secondary_school.seed_subjects import seed_subjects
        seed_subjects(db_path)

    if user_info and role:
        # Pre-authenticated via universal login
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

    # Standalone launch — use the universal login window
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
