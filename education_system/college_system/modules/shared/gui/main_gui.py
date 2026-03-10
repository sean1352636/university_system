"""Main application window for the College Management System GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.modules.shared.gui.login_gui import LoginFrame
from education_system.college_system.modules.shared.gui.dashboard_gui import DashboardFrame
from education_system.college_system.modules.domain.students.gui.student_gui import StudentFrame
from education_system.college_system.modules.domain.courses.gui.course_gui import CourseFrame
from education_system.college_system.modules.domain.enrollment.gui.enrollment_gui import EnrollmentFrame
from education_system.college_system.modules.domain.grades.gui.grade_gui import GradeFrame
from education_system.college_system.modules.domain.attendance.gui.attendance_gui import AttendanceFrame
from education_system.college_system.modules.domain.timetable.gui.timetable_gui import TimetableFrame
from education_system.college_system.modules.domain.assignments.gui.assignment_gui import AssignmentFrame
from education_system.college_system.modules.domain.notifications.gui.notification_gui import NotificationFrame
from education_system.college_system.modules.shared.gui.mfa_gui import MFASettingsFrame
from education_system.college_system.modules.domain.staff.gui.staff_gui import StaffFrame
from education_system.college_system.modules.domain.messaging.gui.message_gui import MessageFrame
from education_system.college_system.modules.domain.todo.gui.todo_gui import TodoFrame
from education_system.college_system.modules.domain.calendar.gui.calendar_gui import CalendarFrame
from education_system.college_system.modules.domain.first_aid.gui.first_aid_gui import FirstAidFrame
from education_system.college_system.modules.domain.helpdesk.gui.helpdesk_gui import HelpdeskFrame
from education_system.college_system.modules.domain.parent_portal.gui.parent_gui import ParentFrame
from education_system.college_system.modules.domain.settings.gui.settings_gui import SettingsFrame
from education_system.college_system.modules.domain.admissions.gui.admissions_gui import AdmissionsFrame
from education_system.college_system.modules.domain.safeguarding.gui.safeguarding_gui import SafeguardingFrame
from education_system.college_system.modules.domain.behaviour.gui.behaviour_gui import BehaviourFrame
from education_system.college_system.modules.domain.pastoral.gui.pastoral_gui import PastoralFrame
from education_system.college_system.modules.domain.send.gui.send_gui import SENDFrame
from education_system.college_system.modules.domain.exams.gui.exams_gui import ExamsFrame
from education_system.college_system.modules.domain.compliance.gui.compliance_gui import ComplianceFrame
from education_system.college_system.modules.domain.reports.gui.reports_gui import ReportsFrame
from education_system.college_system.modules.domain.parents_evening.gui.parents_evening_gui import ParentsEveningFrame
from education_system.college_system.modules.domain.careers.gui.careers_gui import CareersFrame
from education_system.college_system.modules.domain.bursary.gui.bursary_gui import BursaryFrame
from education_system.college_system.modules.domain.transport.gui.transport_gui import TransportFrame
from education_system.college_system.modules.domain.assets.gui.assets_gui import AssetsFrame
from education_system.college_system.modules.domain.library.gui.library_gui import LibraryFrame
from education_system.college_system.modules.domain.staff_hr.gui.staff_hr_gui import StaffHRFrame
from education_system.college_system.modules.domain.cover.gui.cover_gui import CoverFrame
from education_system.college_system.modules.domain.funding.gui.funding_gui import FundingFrame
from education_system.college_system.modules.domain.destinations.gui.destinations_gui import DestinationsFrame
from education_system.college_system.modules.domain.student_support.gui.student_support_gui import StudentSupportFrame
from education_system.college_system.modules.domain.finance.gui.finance_gui import FinanceFrame
from education_system.college_system.modules.domain.departments.gui.departments_gui import DepartmentsFrame
# New feature modules
from education_system.college_system.modules.domain.cpd.gui.cpd_gui import CPDFrame
from education_system.college_system.modules.domain.observations.gui.observations_gui import ObservationFrame
from education_system.college_system.modules.domain.appraisals.gui.appraisals_gui import AppraisalFrame
from education_system.college_system.modules.domain.resource_booking.gui.resource_booking_gui import ResourceBookingFrame
from education_system.college_system.modules.domain.markbook.gui.markbook_gui import MarkbookFrame
from education_system.college_system.modules.domain.staff_wellbeing.gui.staff_wellbeing_gui import StaffWellbeingFrame
from education_system.college_system.modules.domain.lesson_plans.gui.lesson_plans_gui import LessonPlanFrame
from education_system.college_system.modules.domain.data_dashboard.gui.data_dashboard_gui import DataDashboardFrame
from education_system.college_system.modules.domain.absence_requests.gui.absence_requests_gui import AbsenceRequestFrame
from education_system.college_system.modules.domain.intervention_tracking.gui.intervention_tracking_gui import InterventionFrame
from education_system.college_system.modules.domain.visitors.gui.visitors_gui import VisitorFrame
from education_system.college_system.modules.domain.policies.gui.policies_gui import PolicyFrame
from education_system.college_system.modules.domain.gdpr.gui.gdpr_gui import GDPRFrame
from education_system.college_system.modules.domain.quality_assurance.gui.quality_assurance_gui import QualityAssuranceFrame
from education_system.college_system.modules.domain.bulk_operations.gui.bulk_operations_gui import BulkOperationFrame
from education_system.college_system.modules.domain.emergency.gui.emergency_gui import EmergencyFrame
from education_system.college_system.modules.domain.academic_year.gui.academic_year_gui import AcademicYearFrame
from education_system.college_system.modules.domain.kpi_dashboard.gui.kpi_dashboard_gui import KPIDashboardFrame
from education_system.college_system.modules.domain.audit_reports.gui.audit_reports_gui import AuditReportFrame
from education_system.college_system.modules.domain.user_management.gui.user_management_gui import UserManagementFrame
from education_system.college_system.modules.domain.portfolio.gui.portfolio_gui import PortfolioFrame
from education_system.college_system.modules.domain.study_planner.gui.study_planner_gui import StudyPlannerFrame
from education_system.college_system.modules.domain.enrichment.gui.enrichment_gui import EnrichmentFrame
from education_system.college_system.modules.domain.peer_mentoring.gui.peer_mentoring_gui import PeerMentoringFrame
from education_system.college_system.modules.domain.surveys.gui.surveys_gui import SurveyFrame
from education_system.college_system.modules.domain.skills_passport.gui.skills_passport_gui import SkillsPassportFrame
from education_system.college_system.modules.domain.progress_dashboard.gui.progress_dashboard_gui import ProgressDashboardFrame
from education_system.college_system.modules.domain.meal_ordering.gui.meal_ordering_gui import MealOrderingFrame
from education_system.college_system.modules.domain.print_credits.gui.print_credits_gui import PrintCreditFrame
from education_system.college_system.modules.domain.work_journal.gui.work_journal_gui import WorkJournalFrame
from education_system.college_system.modules.domain.announcements.gui.announcements_gui import AnnouncementFrame
from education_system.college_system.modules.domain.document_hub.gui.document_hub_gui import DocumentHubFrame
from education_system.college_system.modules.domain.advanced_search.gui.advanced_search_gui import AdvancedSearchFrame
from education_system.college_system.modules.domain.feedback.gui.feedback_gui import FeedbackFrame
from education_system.college_system.modules.domain.accessibility.gui.accessibility_gui import AccessibilityFrame
from education_system.college_system.modules.domain.mobile_dashboard.gui.mobile_dashboard_gui import MobileDashboardFrame
from education_system.college_system.modules.domain.attachments.gui.attachments_gui import AttachmentFrame
from education_system.college_system.modules.domain.activity_feed.gui.activity_feed_gui import ActivityFeedFrame
from education_system.college_system.modules.domain.sms_email.gui.sms_email_gui import SmsEmailFrame
from education_system.college_system.modules.domain.multi_language.gui.multi_language_gui import MultiLanguageFrame
# New modules
from education_system.college_system.modules.domain.ilp.gui.ilp_gui import ILPFrame
from education_system.college_system.modules.domain.ucas.gui.ucas_gui import UCASFrame
from education_system.college_system.modules.domain.tlevel.gui.tlevel_gui import TLevelFrame
from education_system.college_system.modules.domain.apprenticeships.gui.apprenticeships_gui import ApprenticeshipFrame
from education_system.college_system.modules.domain.value_added.gui.value_added_gui import ValueAddedFrame
from education_system.college_system.modules.domain.governance.gui.governance_gui import GovernanceFrame
from education_system.college_system.modules.domain.dbs_checks.gui.dbs_checks_gui import DBSCheckFrame
from education_system.college_system.modules.domain.risk_management.gui.risk_management_gui import RiskManagementFrame
from education_system.college_system.modules.domain.prevent_duty.gui.prevent_duty_gui import PreventDutyFrame
from education_system.college_system.modules.domain.complaints.gui.complaints_gui import ComplaintFrame
from education_system.college_system.modules.domain.equality_diversity.gui.equality_diversity_gui import EqualityDiversityFrame
from education_system.college_system.modules.domain.staff_absence.gui.staff_absence_gui import StaffAbsenceFrame
from education_system.college_system.modules.domain.recruitment.gui.recruitment_gui import RecruitmentFrame
from education_system.college_system.modules.domain.marketing.gui.marketing_gui import MarketingFrame
from education_system.college_system.modules.domain.early_warning.gui.early_warning_gui import EarlyWarningFrame
from education_system.college_system.modules.domain.self_assessment.gui.self_assessment_gui import SelfAssessmentFrame
from education_system.college_system.modules.domain.alumni.gui.alumni_gui import AlumniFrame
from education_system.college_system.modules.domain.student_portal.gui.student_portal_gui import StudentPortalFrame
from education_system.college_system.modules.domain.forums.gui.forums_gui import ForumFrame
# Batch 2 modules
from education_system.college_system.modules.domain.internal_verification.gui.internal_verification_gui import InternalVerificationFrame
from education_system.college_system.modules.domain.functional_skills.gui.functional_skills_gui import FunctionalSkillsFrame
from education_system.college_system.modules.domain.study_programmes.gui.study_programmes_gui import StudyProgrammeFrame
from education_system.college_system.modules.domain.tutorial.gui.tutorial_gui import TutorialFrame
from education_system.college_system.modules.domain.student_wellbeing.gui.student_wellbeing_gui import StudentWellbeingFrame
from education_system.college_system.modules.domain.student_council.gui.student_council_gui import StudentCouncilFrame
from education_system.college_system.modules.domain.lettings.gui.lettings_gui import LettingsFrame
from education_system.college_system.modules.domain.health_safety.gui.health_safety_gui import HealthSafetyFrame
from education_system.college_system.modules.domain.letter_templates.gui.letter_templates_gui import LetterTemplateFrame
from education_system.college_system.modules.domain.disciplinary.gui.disciplinary_gui import DisciplinaryFrame
from education_system.college_system.modules.domain.onboarding.gui.onboarding_gui import OnboardingFrame
from education_system.college_system.modules.domain.expense_claims.gui.expense_claims_gui import ExpenseClaimFrame
from education_system.college_system.modules.domain.baseline_assessment.gui.baseline_assessment_gui import BaselineAssessmentFrame
from education_system.college_system.modules.domain.data_export.gui.data_export_gui import DataExportFrame

logger = logging.getLogger(__name__)


class CollegeApp(tk.Tk):
    """Root application window.

    Manages frame switching between the login screen, dashboard and each
    domain module screen.  A menu bar provides Logout and Exit actions.
    """

    _FRAME_MAP = {
        "login_gui":        LoginFrame,
        "dashboard_gui":    DashboardFrame,
        "student_gui":      StudentFrame,
        "course_gui":       CourseFrame,
        "enrollment_gui":   EnrollmentFrame,
        "grade_gui":        GradeFrame,
        "attendance_gui":   AttendanceFrame,
        "timetable_gui":    TimetableFrame,
        "assignment_gui":   AssignmentFrame,
        "notification_gui": NotificationFrame,
        "mfa_gui":          MFASettingsFrame,
        "staff_gui":        StaffFrame,
        "message_gui":      MessageFrame,
        "todo_gui":         TodoFrame,
        "calendar_gui":     CalendarFrame,
        "first_aid_gui":    FirstAidFrame,
        "helpdesk_gui":     HelpdeskFrame,
        "parent_gui":       ParentFrame,
        "settings_gui":     SettingsFrame,
        "admissions_gui":   AdmissionsFrame,
        "safeguarding_gui": SafeguardingFrame,
        "behaviour_gui":    BehaviourFrame,
        "pastoral_gui":     PastoralFrame,
        "send_gui":         SENDFrame,
        "exams_gui":        ExamsFrame,
        "compliance_gui":   ComplianceFrame,
        "reports_gui":      ReportsFrame,
        "parents_evening_gui": ParentsEveningFrame,
        "careers_gui":      CareersFrame,
        "bursary_gui":      BursaryFrame,
        "transport_gui":    TransportFrame,
        "assets_gui":       AssetsFrame,
        "library_gui":      LibraryFrame,
        "staff_hr_gui":     StaffHRFrame,
        "cover_gui":        CoverFrame,
        "funding_gui":      FundingFrame,
        "destinations_gui": DestinationsFrame,
        "student_support_gui": StudentSupportFrame,
        "finance_gui":      FinanceFrame,
        "departments_gui":  DepartmentsFrame,
        # New feature modules
        "cpd_gui":          CPDFrame,
        "observation_gui":  ObservationFrame,
        "appraisal_gui":    AppraisalFrame,
        "resource_booking_gui": ResourceBookingFrame,
        "markbook_gui":     MarkbookFrame,
        "staff_wellbeing_gui": StaffWellbeingFrame,
        "lesson_plan_gui":  LessonPlanFrame,
        "data_dashboard_gui": DataDashboardFrame,
        "absence_request_gui": AbsenceRequestFrame,
        "intervention_gui": InterventionFrame,
        "visitor_gui":      VisitorFrame,
        "policy_gui":       PolicyFrame,
        "gdpr_gui":         GDPRFrame,
        "quality_assurance_gui": QualityAssuranceFrame,
        "bulk_operation_gui": BulkOperationFrame,
        "emergency_gui":    EmergencyFrame,
        "academic_year_gui": AcademicYearFrame,
        "kpi_dashboard_gui": KPIDashboardFrame,
        "audit_report_gui": AuditReportFrame,
        "user_management_gui": UserManagementFrame,
        "portfolio_gui":    PortfolioFrame,
        "study_planner_gui": StudyPlannerFrame,
        "enrichment_gui":   EnrichmentFrame,
        "peer_mentoring_gui": PeerMentoringFrame,
        "survey_gui":       SurveyFrame,
        "skills_passport_gui": SkillsPassportFrame,
        "progress_dashboard_gui": ProgressDashboardFrame,
        "meal_ordering_gui": MealOrderingFrame,
        "print_credit_gui": PrintCreditFrame,
        "work_journal_gui": WorkJournalFrame,
        "announcement_gui": AnnouncementFrame,
        "document_hub_gui": DocumentHubFrame,
        "advanced_search_gui": AdvancedSearchFrame,
        "feedback_gui":     FeedbackFrame,
        "accessibility_gui": AccessibilityFrame,
        "mobile_dashboard_gui": MobileDashboardFrame,
        "attachment_gui":   AttachmentFrame,
        "activity_feed_gui": ActivityFeedFrame,
        "sms_email_gui":    SmsEmailFrame,
        "multi_language_gui": MultiLanguageFrame,
        # New modules
        "ilp_gui":          ILPFrame,
        "ucas_gui":         UCASFrame,
        "tlevel_gui":       TLevelFrame,
        "apprenticeship_gui": ApprenticeshipFrame,
        "value_added_gui":  ValueAddedFrame,
        "governance_gui":   GovernanceFrame,
        "dbs_check_gui":    DBSCheckFrame,
        "risk_management_gui": RiskManagementFrame,
        "prevent_duty_gui": PreventDutyFrame,
        "complaint_gui":    ComplaintFrame,
        "equality_diversity_gui": EqualityDiversityFrame,
        "staff_absence_gui": StaffAbsenceFrame,
        "recruitment_gui":  RecruitmentFrame,
        "marketing_gui":    MarketingFrame,
        "early_warning_gui": EarlyWarningFrame,
        "self_assessment_gui": SelfAssessmentFrame,
        "alumni_gui":       AlumniFrame,
        "student_portal_gui": StudentPortalFrame,
        "forum_gui":        ForumFrame,
        # Batch 2 modules
        "internal_verification_gui": InternalVerificationFrame,
        "functional_skills_gui": FunctionalSkillsFrame,
        "study_programme_gui": StudyProgrammeFrame,
        "tutorial_gui":     TutorialFrame,
        "student_wellbeing_gui": StudentWellbeingFrame,
        "student_council_gui": StudentCouncilFrame,
        "lettings_gui":     LettingsFrame,
        "health_safety_gui": HealthSafetyFrame,
        "letter_template_gui": LetterTemplateFrame,
        "disciplinary_gui": DisciplinaryFrame,
        "onboarding_gui":   OnboardingFrame,
        "expense_claim_gui": ExpenseClaimFrame,
        "baseline_assessment_gui": BaselineAssessmentFrame,
        "data_export_gui":  DataExportFrame,
    }

    def __init__(self, db_path: str | None = None):
        super().__init__()

        self._db_path = db_path
        self._auth = UserAuth(db_path)
        self._user_info: dict | None = None

        # Window configuration
        self.title("Sixth Form College Management System")
        self.geometry("1024x768")
        self.minsize(800, 600)

        # Build menu bar (hidden until logged in)
        self._build_menu()

        # Top navigation bar with Dashboard button (hidden until a module is shown)
        self._topbar = tk.Frame(self, bg="#2c3e50", height=36)
        self._topbar.pack_propagate(False)
        self._dashboard_btn = tk.Button(
            self._topbar, text="< Dashboard", font=("Helvetica", 10),
            bg="#3498db", fg="white", activebackground="#2980b9",
            activeforeground="white", bd=0, padx=12, pady=4,
            cursor="hand2", command=self._go_dashboard,
        )
        self._dashboard_btn.pack(side="left", padx=10, pady=4)
        # Hidden by default; shown when navigating to a module screen
        self._topbar.pack_forget()

        # Container for stacked frames
        self._container = tk.Frame(self)
        self._container.pack(fill="both", expand=True)
        self._container.grid_rowconfigure(0, weight=1)
        self._container.grid_columnconfigure(0, weight=1)

        # Instantiate every frame once and stack them
        self._frames: dict[str, tk.Frame] = {}
        self._init_frames()

        # Start with the login screen
        self.show_frame("login_gui")

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _init_frames(self):
        """Create one instance of each registered frame."""
        for name, cls in self._FRAME_MAP.items():
            if cls is LoginFrame:
                frame = cls(
                    self._container,
                    db_path=self._db_path,
                    auth=self._auth,
                    on_login=self._on_login_success,
                )
            elif cls is DashboardFrame:
                frame = cls(
                    self._container,
                    db_path=self._db_path,
                    auth=self._auth,
                    on_navigate=self._on_navigate,
                )
            else:
                frame = cls(
                    self._container,
                    db_path=self._db_path,
                    auth=self._auth,
                )

            frame.grid(row=0, column=0, sticky="nsew")
            self._frames[name] = frame

    def _build_menu(self):
        """Create the application menu bar."""
        self._menubar = tk.Menu(self)

        file_menu = tk.Menu(self._menubar, tearoff=0)
        file_menu.add_command(label="Dashboard", command=self._go_dashboard)
        file_menu.add_separator()
        file_menu.add_command(label="Switch to CLI", command=self._switch_to_cli)
        file_menu.add_command(label="Switch System", command=self._switch_system)
        file_menu.add_separator()
        file_menu.add_command(label="Logout", command=self._do_logout)
        file_menu.add_command(label="Exit", command=self._do_exit)
        self._menubar.add_cascade(label="File", menu=file_menu)

        # Menu is initially hidden; shown after login
        self.config(menu="")

    # ------------------------------------------------------------------
    # Frame switching
    # ------------------------------------------------------------------

    def show_frame(self, name: str):
        """Raise the frame identified by *name* to the top of the stack."""
        frame = self._frames.get(name)
        if frame is None:
            messagebox.showerror("Error", f"Unknown frame: {name}")
            return

        # Show the top-bar Dashboard button on module screens only
        if name in ("login_gui", "dashboard_gui"):
            self._topbar.pack_forget()
        else:
            self._topbar.pack(fill="x", before=self._container)

        # Lifecycle hook: let the frame refresh itself when shown
        if hasattr(frame, "refresh") and name != "login_gui":
            try:
                frame.refresh()
            except Exception:
                pass

        frame.tkraise()

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_login_success(self, user_info: dict):
        """Called by LoginFrame after successful authentication."""
        logger.info("GUI login: user '%s'", user_info.get('username', '?'))
        self._user_info = user_info

        # Show menu bar
        self.config(menu=self._menubar)

        # Configure and show the dashboard
        dashboard: DashboardFrame = self._frames["dashboard_gui"]
        dashboard.set_user(user_info)
        self.show_frame("dashboard_gui")

    def _on_navigate(self, target: str):
        """Called by DashboardFrame when the user clicks a navigation button."""
        if target in self._frames:
            self.show_frame(target)
        else:
            messagebox.showwarning("Navigation", f"Module '{target}' is not available.")

    def _go_dashboard(self):
        """Return to the dashboard."""
        self.show_frame("dashboard_gui")

    def _do_logout(self):
        """Log out the current user and return to the universal login screen."""
        if messagebox.askyesno("Confirm Logout", "Are you sure you want to log out?"):
            try:
                self._auth.logout()
            except Exception:
                pass
            logger.info("GUI logout")

            from education_system.switch import request_logout
            request_logout()
            self.destroy()

    def _switch_to_cli(self):
        """Switch to the College CLI interface."""
        if messagebox.askyesno("Switch to CLI", "Switch to the command-line interface?"):
            from education_system.switch import request_switch
            request_switch("college", "cli")
            try:
                self._auth.logout()
            except Exception:
                pass
            self.destroy()

    def _switch_system(self):
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
            try:
                self._auth.logout()
            except Exception:
                pass
            self.destroy()

        tk.Button(body, text="University Management System",
                  bg="#2980b9", activebackground="#3498db", activeforeground="white",
                  command=lambda: _pick("university"), **btn_style).pack(pady=5)
        tk.Button(body, text="Secondary School System",
                  bg="#8e44ad", activebackground="#9b59b6", activeforeground="white",
                  command=lambda: _pick("school"), **btn_style).pack(pady=5)
        tk.Button(body, text="Primary School System",
                  bg="#e67e22", activebackground="#f39c12", activeforeground="white",
                  command=lambda: _pick("primary"), **btn_style).pack(pady=5)
        tk.Button(body, text="Cancel", font=("Helvetica", 12), relief=tk.FLAT,
                  padx=20, pady=4, cursor="hand2", command=dlg.destroy).pack(pady=(10, 0))

        dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)

    def _do_exit(self):
        """Confirm and close the application."""
        if messagebox.askyesno("Confirm Exit", "Are you sure you want to exit?"):
            try:
                self._auth.logout()
            except Exception:
                pass
            self.destroy()


def main(db_path: str | None = None, user_info=None, role=None, shared_auth=None):
    """Entry point for launching the GUI application.

    If *user_info* and *role* are provided (from universal login), the
    login screen is skipped and the user goes straight to the dashboard.
    """
    from education_system.college_system.core.paths import ensure_directories
    from education_system.college_system.infrastructure.database.schema import init_db, seed_default_data

    ensure_directories()
    init_db(db_path)
    seed_default_data(db_path)
    from education_system.college_system.core.logs import configure_logging
    configure_logging()
    logger.info("GUI application starting")

    app = CollegeApp(db_path=db_path)

    # If pre-authenticated via universal login, skip the login frame
    if user_info and role:
        # Build a user_info dict compatible with the college system
        college_user = {
            "user_id": user_info.get("user_id"),
            "username": user_info.get("username"),
            "role": role,
            "email": user_info.get("email"),
        }
        if shared_auth:
            app._auth = shared_auth
        app._on_login_success(college_user)

    app.mainloop()


def launch_gui(db_path: str | None = None, user_info=None, role=None, shared_auth=None):
    """Alias entry point supporting pre-authenticated launch."""
    main(db_path=db_path, user_info=user_info, role=role, shared_auth=shared_auth)


if __name__ == "__main__":
    main()
