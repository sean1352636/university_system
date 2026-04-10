"""Main application window for the College Management System GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.core.i18n import (
    t, set_language, get_current_language, get_available_languages, reload_translations,
)
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
from education_system.shared.gui.security_questions_gui import SecurityQuestionsFrame
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
# Features 31-40
from education_system.college_system.modules.domain.census_ilr.gui.census_ilr_gui import CensusILRFrame
from education_system.college_system.modules.domain.ucas_export.gui.ucas_export_gui import UCASExportFrame
from education_system.college_system.modules.domain.destination_outcomes.gui.destination_outcome_gui import DestinationOutcomeFrame
from education_system.college_system.modules.domain.iqr_manager.gui.iqr_manager_gui import IQRManagerFrame
from education_system.college_system.modules.domain.sef_builder.gui.sef_builder_gui import SEFBuilderFrame
from education_system.college_system.modules.domain.question_analysis.gui.question_analysis_gui import QuestionAnalysisFrame
from education_system.college_system.modules.domain.target_setting.gui.target_setting_gui import TargetSettingFrame
from education_system.college_system.modules.domain.cover_agency.gui.cover_agency_gui import CoverAgencyFrame
from education_system.college_system.modules.domain.lettings_portal.gui.lettings_portal_gui import LettingsPortalFrame
from education_system.college_system.modules.domain.employer_portal.gui.employer_portal_gui import EmployerPortalFrame

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
_SIDEBAR_BG = "#1a2332"
_SIDEBAR_FG = "#c8d6e5"
_SECTION_BG = "#243447"
_SECTION_FG = "#dfe6e9"
_SECTION_HOVER = "#2d4059"
_BTN_BG = _SIDEBAR_BG
_BTN_FG = "#b2bec3"
_BTN_HOVER = "#2d4059"
_BTN_ACTIVE_BG = "#0984e3"
_BTN_ACTIVE_FG = "#ffffff"
_HEADER_BG = "#2c3e50"
_HEADER_FG = "#ffffff"
_TOPBAR_BG = "#34495e"

# ---------------------------------------------------------------------------
# Sidebar section definitions
# Each section: (section_title, [(nav_label, frame_key, min_role), ...])
# ---------------------------------------------------------------------------
_SIDEBAR_SECTIONS = [
    ("Students & Learning", [
        ("Students",              "student_gui",               "staff"),
        ("Enrollment",            "enrollment_gui",            "staff"),
        ("Grades",                "grade_gui",                 "instructor"),
        ("Attendance",            "attendance_gui",            "instructor"),
        ("Assignments",           "assignment_gui",            "student"),
        ("Timetable",             "timetable_gui",             "student"),
        ("Markbook",              "markbook_gui",              "instructor"),
        ("Question Analysis",    "question_analysis_gui",     "instructor"),
        ("Target Setting",       "target_setting_gui",        "instructor"),
        ("ILP",                   "ilp_gui",                   "instructor"),
        ("Portfolio",             "portfolio_gui",             "student"),
        ("Progress Dashboard",    "progress_dashboard_gui",    "student"),
        ("Study Planner",         "study_planner_gui",         "student"),
        ("Baseline Assessment",   "baseline_assessment_gui",   "instructor"),
        ("Work Journal",          "work_journal_gui",          "student"),
        ("LMS",                   "lms_gui",                   "student"),
    ]),
    ("Courses & Curriculum", [
        ("Courses",               "course_gui",                "student"),
        ("Departments",           "departments_gui",           "admin"),
        ("Study Programmes",      "study_programme_gui",       "staff"),
        ("T-Levels",              "tlevel_gui",                "staff"),
        ("Functional Skills",     "functional_skills_gui",     "staff"),
        ("Apprenticeships",       "apprenticeship_gui",        "staff"),
        ("Employer Portal",       "employer_portal_gui",       "admin"),
        ("Value Added",           "value_added_gui",           "instructor"),
    ]),
    ("Teaching & Quality", [
        ("Lesson Plans",          "lesson_plan_gui",           "instructor"),
        ("Observations",          "observation_gui",           "instructor"),
        ("CPD",                   "cpd_gui",                   "instructor"),
        ("Quality Assurance",     "quality_assurance_gui",     "admin"),
        ("IQR Manager",           "iqr_manager_gui",           "admin"),
        ("Internal Verification", "internal_verification_gui", "instructor"),
        ("Self Assessment",       "self_assessment_gui",       "admin"),
        ("SEF Builder",           "sef_builder_gui",           "admin"),
        ("Data Dashboard",        "data_dashboard_gui",        "instructor"),
        ("KPI Dashboard",         "kpi_dashboard_gui",         "admin"),
        ("Tutorial",              "tutorial_gui",              "instructor"),
    ]),
    ("Pastoral & Welfare", [
        ("Pastoral",              "pastoral_gui",              "staff"),
        ("Behaviour",             "behaviour_gui",             "staff"),
        ("Disciplinary",          "disciplinary_gui",          "admin"),
        ("Safeguarding",          "safeguarding_gui",          "staff"),
        ("SEND",                  "send_gui",                  "staff"),
        ("Student Support",       "student_support_gui",       "staff"),
        ("Student Wellbeing",     "student_wellbeing_gui",     "staff"),
        ("Early Warning",         "early_warning_gui",         "instructor"),
        ("Interventions",         "intervention_gui",          "instructor"),
        ("Prevent Duty",          "prevent_duty_gui",          "staff"),
        ("First Aid",             "first_aid_gui",             "staff"),
    ]),
    ("Exams & Reports", [
        ("Exams",                 "exams_gui",                 "staff"),
        ("Reports",               "reports_gui",               "instructor"),
        ("Audit Reports",         "audit_report_gui",          "admin"),
        ("Census / ILR",          "census_ilr_gui",            "admin"),
        ("Certificates",          "certificates_gui",          "staff"),
    ]),
    ("Staff", [
        ("Staff Directory",       "staff_gui",                 "admin"),
        ("Staff HR",              "staff_hr_gui",              "admin"),
        ("Cover",                 "cover_gui",                 "staff"),
        ("Cover Agencies",        "cover_agency_gui",          "admin"),
        ("Staff Absence",         "staff_absence_gui",         "admin"),
        ("Staff Wellbeing",       "staff_wellbeing_gui",       "admin"),
        ("Appraisals",            "appraisal_gui",             "admin"),
        ("Absence Requests",      "absence_request_gui",       "instructor"),
        ("Recruitment",           "recruitment_gui",           "admin"),
        ("Onboarding",            "onboarding_gui",            "admin"),
        ("DBS Checks",            "dbs_check_gui",             "admin"),
        ("Expense Claims",        "expense_claim_gui",         "staff"),
    ]),
    ("Communication", [
        ("Messages",              "message_gui",               "student"),
        ("Notifications",         "notification_gui",          "student"),
        ("Announcements",         "announcement_gui",          "student"),
        ("SMS & Email",           "sms_email_gui",             "student"),
        ("Activity Feed",         "activity_feed_gui",         "student"),
        ("Forums",                "forum_gui",                 "student"),
        ("Feedback",              "feedback_gui",              "student"),
        ("Surveys",               "survey_gui",                "student"),
    ]),
    ("Student Life", [
        ("Careers",               "careers_gui",               "student"),
        ("UCAS",                  "ucas_gui",                  "staff"),
        ("UCAS Export",           "ucas_export_gui",           "admin"),
        ("Destinations",          "destinations_gui",          "staff"),
        ("Destination Outcomes",  "destination_outcome_gui",   "staff"),
        ("Enrichment",            "enrichment_gui",            "student"),
        ("Peer Mentoring",        "peer_mentoring_gui",        "student"),
        ("Skills Passport",       "skills_passport_gui",       "student"),
        ("Student Portal",        "student_portal_gui",        "student"),
        ("Student Council",       "student_council_gui",       "student"),
        ("Meal Ordering",         "meal_ordering_gui",         "student"),
        ("Print Credits",         "print_credit_gui",          "student"),
        ("Library",               "library_gui",               "student"),
        ("Alumni",                "alumni_gui",                "staff"),
        ("Helpdesk",              "helpdesk_gui",              "student"),
    ]),
    ("Parents & Community", [
        ("Parent Portal",         "parent_gui",                "parent"),
        ("Parents Evening",       "parents_evening_gui",       "student"),
        ("Visitors",              "visitor_gui",               "staff"),
        ("Marketing",             "marketing_gui",             "admin"),
        ("Lettings",              "lettings_gui",              "admin"),
        ("Lettings Portal",       "lettings_portal_gui",       "admin"),
        ("Admissions",            "admissions_gui",            "staff"),
    ]),
    ("Finance & Resources", [
        ("Finance",               "finance_gui",               "admin"),
        ("Bursary",               "bursary_gui",               "admin"),
        ("Funding",               "funding_gui",               "admin"),
        ("Transport",             "transport_gui",             "admin"),
        ("Assets",                "assets_gui",                "staff"),
        ("Resource Booking",      "resource_booking_gui",      "instructor"),
    ]),
    ("Administration", [
        ("Settings",              "settings_gui",              "student"),
        ("MFA Settings",          "mfa_gui",                   "student"),
        ("Security Questions",    "security_questions_gui",    "student"),
        ("User Management",       "user_management_gui",       "admin"),
        ("Academic Year",         "academic_year_gui",          "admin"),
        ("Bulk Operations",       "bulk_operation_gui",        "admin"),
        ("Data Export",           "data_export_gui",           "admin"),
        ("Document Hub",          "document_hub_gui",          "student"),
        ("Attachments",           "attachment_gui",            "student"),
        ("Advanced Search",       "advanced_search_gui",       "student"),
        ("Letter Templates",      "letter_template_gui",       "staff"),
        ("Policies",              "policy_gui",                "staff"),
        ("Todo",                  "todo_gui",                  "student"),
        ("Calendar",              "calendar_gui",              "student"),
    ]),
    ("Compliance & Safety", [
        ("Compliance",            "compliance_gui",            "admin"),
        ("GDPR",                  "gdpr_gui",                  "admin"),
        ("Governance",            "governance_gui",            "admin"),
        ("Risk Management",       "risk_management_gui",       "admin"),
        ("Equality & Diversity",  "equality_diversity_gui",    "admin"),
        ("Complaints",            "complaint_gui",             "admin"),
        ("Emergency",             "emergency_gui",             "staff"),
        ("Health & Safety",       "health_safety_gui",         "admin"),
    ]),
    ("Accessibility", [
        ("Accessibility",         "accessibility_gui",         "student"),
        ("Mobile Dashboard",      "mobile_dashboard_gui",      "student"),
        ("Multi-Language",        "multi_language_gui",        "student"),
    ]),
    ("Extras & Tools", [
        ("Extras & Tools",        "extras_tools_gui",          "student"),
        ("Academic Misconduct",   "misconduct_gui",            "staff"),
    ]),
    ("Cross-System Tools", [
        ("Student Journey",       "student_journey_gui",       "admin"),
        ("Analytics Dashboard",   "analytics_dashboard_gui",   "admin"),
        ("Outcome Tracking",      "outcome_tracking_gui",      "admin"),
        ("Predictive Alerts",     "predictive_alerts_gui",     "admin"),
        ("Bulk Transfer",         "bulk_transfer_gui",         "admin"),
        ("Transfer Documents",    "transfer_documents_gui",    "admin"),
        ("Reverse Lookup",        "reverse_lookup_gui",        "admin"),
        ("Parent Continuity",     "parent_continuity_gui",     "admin"),
        ("Cross-System Calendar", "cross_system_calendar_gui", "admin"),
        ("Central Admin Portal",  "central_admin_gui",         "admin"),
        ("GDPR Compliance",       "gdpr_compliance_gui",       "admin"),
        ("Shared Documents",      "shared_documents_gui",      "admin"),
        ("Student Self-Service",  "student_self_service_gui",  "admin"),
        ("Digital Transcript",    "digital_transcript_gui",    "admin"),
    ]),
]


class CollegeApp(tk.Tk):
    """Root application window.

    Layout after login:
    ┌───────────────────────────────────────────────────┐
    │                    Header bar                     │
    ├──────────────┬────────────────────────────────────┤
    │  Sidebar     │  Content area (stacked frames)     │
    │  (scrollable │                                    │
    │   sections)  │                                    │
    └──────────────┴────────────────────────────────────┘
    """

    _FRAME_MAP = {
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
        "security_questions_gui": SecurityQuestionsFrame,
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
        # Cross-system modules
        "student_journey_gui": JourneyDashboardFrame,
        # Shared modules
        "analytics_dashboard_gui": AnalyticsDashboardFrame,
        "outcome_tracking_gui": OutcomeTrackingFrame,
        "predictive_alerts_gui": PredictiveAlertsFrame,
        "bulk_transfer_gui": BulkTransferFrame,
        "transfer_documents_gui": TransferDocumentsFrame,
        "reverse_lookup_gui": ReverseLookupFrame,
        "parent_continuity_gui": ParentContinuityFrame,
        "cross_system_calendar_gui": CrossSystemCalendarFrame,
        "central_admin_gui": CentralAdminFrame,
        "gdpr_compliance_gui": GDPRComplianceFrame,
        "shared_documents_gui": SharedDocumentsFrame,
        "student_self_service_gui": StudentSelfServiceFrame,
        "digital_transcript_gui": DigitalTranscriptFrame,
        "certificates_gui": CertificatesGUI,
        "extras_tools_gui": ExtrasFrame,
        "misconduct_gui": MisconductFrame,
        "lms_gui":        LMSFrame,
        # Features 31-40
        "census_ilr_gui": CensusILRFrame,
        "ucas_export_gui": UCASExportFrame,
        "destination_outcome_gui": DestinationOutcomeFrame,
        "iqr_manager_gui": IQRManagerFrame,
        "sef_builder_gui": SEFBuilderFrame,
        "question_analysis_gui": QuestionAnalysisFrame,
        "target_setting_gui": TargetSettingFrame,
        "cover_agency_gui": CoverAgencyFrame,
        "lettings_portal_gui": LettingsPortalFrame,
        "employer_portal_gui": EmployerPortalFrame,
    }

    def __init__(self, db_path: str | None = None):
        super().__init__()

        self._db_path = db_path
        self._auth = UserAuth(db_path)
        self._user_info: dict | None = None
        self._active_frame_name: str | None = None

        # Track which sections are expanded (all collapsed by default)
        self._section_expanded: dict[str, bool] = {}
        self._section_btn_frames: dict[str, tk.Frame] = {}

        # Window configuration
        self.title(t("main.window_title"))
        self.geometry("1200x800")
        self.minsize(900, 600)

        # Build menu bar (hidden until logged in)
        self._build_menu()

        # --- Main layout paned window ---
        self._main_pw = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=4,
                                        bg="#3d566e")
        self._main_pw.pack(fill="both", expand=True)

        # --- Left: Sidebar (hidden until login) ---
        self._sidebar_outer = tk.Frame(self._main_pw, bg=_SIDEBAR_BG, width=250)
        self._sidebar_outer.pack_propagate(False)
        self._build_sidebar()

        # --- Right: Content area ---
        self._right_panel = tk.Frame(self._main_pw, bg="#ecf0f1")

        # Top bar inside right panel
        self._topbar = tk.Frame(self._right_panel, bg=_TOPBAR_BG, height=40)
        self._topbar.pack(fill="x")
        self._topbar.pack_propagate(False)

        self._dashboard_btn = tk.Button(
            self._topbar, text=t("main.dashboard_button"), font=("Helvetica", 10),
            bg="#3498db", fg="white", activebackground="#2980b9",
            activeforeground="white", bd=0, padx=12, pady=4,
            cursor="hand2", command=self._go_dashboard,
        )
        self._dashboard_btn.pack(side="left", padx=10, pady=5)

        self._location_var = tk.StringVar(value="Dashboard")
        tk.Label(self._topbar, textvariable=self._location_var,
                 font=("Helvetica", 10), bg=_TOPBAR_BG, fg="#bdc3c7",
                 ).pack(side="left", padx=(10, 0), pady=5)

        # Container for stacked frames
        self._container = tk.Frame(self._right_panel)
        self._container.pack(fill="both", expand=True)
        self._container.grid_rowconfigure(0, weight=1)
        self._container.grid_columnconfigure(0, weight=1)

        # Add only the right panel initially (sidebar shown after login)
        self._main_pw.add(self._right_panel, stretch="always")

        # Instantiate every frame once and stack them
        self._frames: dict[str, tk.Frame] = {}
        self._init_frames()

        # Start with the dashboard (login is handled externally)
        self.show_frame("dashboard_gui")

        # --- Keyboard shortcuts & accessibility ---
        self.bind("<Escape>", self._on_escape)
        self.bind("<Control-d>", lambda e: self._go_dashboard())
        self.bind("<Control-l>", lambda e: self._do_logout())
        self.bind("<Control-q>", lambda e: self._do_exit())

        # Ensure logical tab-order: sidebar first, then content area
        self._sidebar_outer.lift()
        self._right_panel.lift()

        # Idle / inactivity auto-logout (30 minutes)
        from education_system.shared.gui.idle_timeout import attach_idle_timeout
        self._cancel_idle_timeout = attach_idle_timeout(
            self, self._idle_logout, timeout_minutes=30,
        )
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _idle_logout(self):
        """Auto-logout fired by the idle-timeout watchdog."""
        try:
            self._auth.logout()
        except Exception:
            pass
        from education_system.switch import request_logout
        request_logout()
        self.destroy()

    def _on_close(self):
        try:
            self._cancel_idle_timeout()
        except Exception:
            pass
        self.destroy()

    # ------------------------------------------------------------------
    # Sidebar construction
    # ------------------------------------------------------------------

    def _build_sidebar(self):
        """Build the scrollable sidebar with section headers."""
        # Header
        hdr = tk.Frame(self._sidebar_outer, bg=_HEADER_BG, height=60)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="College System", font=("Helvetica", 14, "bold"),
                 bg=_HEADER_BG, fg=_HEADER_FG).pack(expand=True)

        # Dashboard button — always visible at top
        dash_frame = tk.Frame(self._sidebar_outer, bg=_SIDEBAR_BG)
        dash_frame.pack(fill="x", padx=6, pady=(8, 4))
        self._dash_btn = tk.Label(
            dash_frame, text="  Dashboard", font=("Helvetica", 11, "bold"),
            bg="#0984e3", fg="white", anchor="w", padx=10, pady=8, cursor="hand2",
        )
        self._dash_btn.pack(fill="x")
        self._dash_btn.bind("<Button-1>", lambda e: self._go_dashboard())

        # Scrollable area for sections — use a tk.Scrollbar for visibility
        # on dark backgrounds (ttk.Scrollbar can be invisible with some themes)
        self._sidebar_vsb = tk.Scrollbar(
            self._sidebar_outer, orient="vertical",
            bg="#3d566e", troughcolor=_SIDEBAR_BG, activebackground="#5a7a9a",
            width=12,
        )
        self._sidebar_vsb.pack(side="right", fill="y")

        self._sidebar_canvas = tk.Canvas(
            self._sidebar_outer, bg=_SIDEBAR_BG,
            highlightthickness=0, bd=0,
            yscrollcommand=self._sidebar_vsb.set,
        )
        self._sidebar_canvas.pack(side="left", fill="both", expand=True)

        self._sidebar_vsb.configure(command=self._sidebar_canvas.yview)

        self._sidebar_inner = tk.Frame(self._sidebar_canvas, bg=_SIDEBAR_BG)

        self._sidebar_inner.bind(
            "<Configure>",
            lambda e: self._sidebar_canvas.configure(
                scrollregion=self._sidebar_canvas.bbox("all")),
        )
        self._sidebar_canvas_win = self._sidebar_canvas.create_window(
            (0, 0), window=self._sidebar_inner, anchor="nw")

        self._sidebar_canvas.bind("<Configure>", self._on_sidebar_canvas_resize)

        # Mousewheel: bind on the entire sidebar outer frame so scrolling works
        # even when hovering over child widgets (headers, buttons, etc.)
        self._sidebar_outer.bind("<Enter>", self._bind_sidebar_wheel)
        self._sidebar_outer.bind("<Leave>", self._unbind_sidebar_wheel)

    def _on_sidebar_canvas_resize(self, event):
        self._sidebar_canvas.itemconfigure(self._sidebar_canvas_win, width=event.width)

    def _update_sidebar_scroll_region(self):
        """Refresh the canvas scroll region after sections expand/collapse."""
        self._sidebar_inner.update_idletasks()
        self._sidebar_canvas.configure(scrollregion=self._sidebar_canvas.bbox("all"))

    def _bind_sidebar_wheel(self, _event):
        self._sidebar_canvas.bind_all("<Button-4>", self._on_sidebar_scroll)
        self._sidebar_canvas.bind_all("<Button-5>", self._on_sidebar_scroll)
        self._sidebar_canvas.bind_all("<MouseWheel>", self._on_sidebar_scroll)

    def _unbind_sidebar_wheel(self, _event):
        self._sidebar_canvas.unbind_all("<Button-4>")
        self._sidebar_canvas.unbind_all("<Button-5>")
        self._sidebar_canvas.unbind_all("<MouseWheel>")

    def _on_sidebar_scroll(self, event):
        if event.num == 4:
            self._sidebar_canvas.yview_scroll(-4, "units")
        elif event.num == 5:
            self._sidebar_canvas.yview_scroll(4, "units")
        else:
            self._sidebar_canvas.yview_scroll(int(-1 * (event.delta / 60)), "units")

    def _populate_sidebar(self):
        """Fill the sidebar with sections based on the current user's role."""
        # Clear existing
        for child in self._sidebar_inner.winfo_children():
            child.destroy()
        self._section_expanded.clear()
        self._section_btn_frames.clear()
        self._section_arrows: dict[str, tk.StringVar] = {}

        if not self._user_info:
            return

        from education_system.college_system.infrastructure.auth.role_manager import ROLE_HIERARCHY

        user_role = self._user_info.get("role", "student")
        user_level = ROLE_HIERARCHY.get(user_role, 0)

        for section_title, items in _SIDEBAR_SECTIONS:
            # Filter items by role
            visible_items = []
            for label, frame_key, min_role in items:
                required = ROLE_HIERARCHY.get(min_role, 0)
                if user_level >= required:
                    visible_items.append((label, frame_key))

            if not visible_items:
                continue

            self._section_expanded[section_title] = False

            # Wrapper frame keeps header + buttons together so ordering is stable
            wrapper = tk.Frame(self._sidebar_inner, bg=_SIDEBAR_BG)
            wrapper.pack(fill="x", padx=6, pady=(4, 0))

            # Section header
            section_hdr = tk.Frame(wrapper, bg=_SECTION_BG, cursor="hand2")
            section_hdr.pack(fill="x")

            arrow_var = tk.StringVar(value="\u25b6")
            self._section_arrows[section_title] = arrow_var
            arrow_lbl = tk.Label(section_hdr, textvariable=arrow_var,
                                  font=("Helvetica", 9), bg=_SECTION_BG,
                                  fg=_SECTION_FG, padx=4)
            arrow_lbl.pack(side="left", padx=(6, 0), pady=6)

            title_lbl = tk.Label(section_hdr, text=section_title,
                                  font=("Helvetica", 10, "bold"),
                                  bg=_SECTION_BG, fg=_SECTION_FG, anchor="w",
                                  padx=4)
            title_lbl.pack(side="left", fill="x", expand=True, pady=6)

            count_lbl = tk.Label(section_hdr, text=str(len(visible_items)),
                                  font=("Helvetica", 8), bg=_SECTION_BG,
                                  fg="#636e72", padx=6)
            count_lbl.pack(side="right", pady=6)

            # Button container (hidden initially, inside wrapper)
            btn_frame = tk.Frame(wrapper, bg=_SIDEBAR_BG)
            self._section_btn_frames[section_title] = btn_frame

            for label, frame_key in visible_items:
                btn = tk.Label(
                    btn_frame, text=f"    {label}", font=("Helvetica", 9),
                    bg=_BTN_BG, fg=_BTN_FG, anchor="w", padx=12, pady=5,
                    cursor="hand2",
                )
                btn.pack(fill="x", padx=(12, 6))
                btn._frame_key = frame_key
                btn._label_text = label

                # Hover effects
                btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=_BTN_HOVER, fg="#ffffff"))
                btn.bind("<Leave>", lambda e, b=btn: (
                    b.configure(bg=_BTN_ACTIVE_BG, fg=_BTN_ACTIVE_FG)
                    if self._active_frame_name == b._frame_key
                    else b.configure(bg=_BTN_BG, fg=_BTN_FG)
                ))
                btn.bind("<Button-1>", lambda e, fk=frame_key: self._sidebar_navigate(fk))

            # Section header hover — apply to all children at once
            def _enter_hdr(e, hdr=section_hdr):
                hdr.configure(bg=_SECTION_HOVER)
                for c in hdr.winfo_children():
                    c.configure(bg=_SECTION_HOVER)

            def _leave_hdr(e, hdr=section_hdr):
                hdr.configure(bg=_SECTION_BG)
                for c in hdr.winfo_children():
                    c.configure(bg=_SECTION_BG)

            # Toggle on click
            def make_toggle(st=section_title, bf=btn_frame):
                def _toggle(_event=None):
                    self._toggle_section(st, bf)
                return _toggle

            toggle_fn = make_toggle()
            for widget in (section_hdr, arrow_lbl, title_lbl, count_lbl):
                widget.bind("<Enter>", _enter_hdr)
                widget.bind("<Leave>", _leave_hdr)
                widget.bind("<Button-1>", toggle_fn)

    def _toggle_section(self, section_title, btn_frame):
        """Expand or collapse a sidebar section."""
        expanded = self._section_expanded.get(section_title, False)
        arrow_var = self._section_arrows.get(section_title)
        if expanded:
            btn_frame.pack_forget()
            if arrow_var:
                arrow_var.set("\u25b6")
            self._section_expanded[section_title] = False
        else:
            btn_frame.pack(fill="x", pady=(0, 2))
            if arrow_var:
                arrow_var.set("\u25bc")
            self._section_expanded[section_title] = True
        self._update_sidebar_scroll_region()

    def _sidebar_navigate(self, frame_key):
        """Handle sidebar button click — navigate to a frame."""
        if frame_key in self._frames:
            self.show_frame(frame_key)
        else:
            messagebox.showwarning(t("common.warning"),
                                   t("main.navigation_error", target=frame_key))

    def _update_sidebar_active(self, frame_key):
        """Highlight the active button in the sidebar."""
        for section_title, btn_frame in self._section_btn_frames.items():
            for child in btn_frame.winfo_children():
                if isinstance(child, tk.Label):
                    child.configure(bg=_BTN_BG, fg=_BTN_FG)

        # Find and highlight the active button
        for section_title, items in _SIDEBAR_SECTIONS:
            for label, fk in [(l, fk) for l, fk, _ in items]:
                if fk == frame_key and section_title in self._section_btn_frames:
                    btn_frame = self._section_btn_frames[section_title]
                    for child in btn_frame.winfo_children():
                        if isinstance(child, tk.Label) and child.cget("text").strip() == label:
                            child.configure(bg=_BTN_ACTIVE_BG, fg=_BTN_ACTIVE_FG)
                            return

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _init_frames(self):
        """Create one instance of each registered frame."""
        for name, cls in self._FRAME_MAP.items():
            if cls is DashboardFrame:
                frame = cls(
                    self._container,
                    db_path=self._db_path,
                    auth=self._auth,
                    on_navigate=self._on_navigate,
                )
            elif cls is MisconductFrame:
                frame = cls(
                    self._container,
                    db_path=self._db_path,
                    auth=self._auth,
                    system_key='college',
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
        file_menu.add_command(
            label=t("main.dashboard"),
            command=self._go_dashboard,
            accelerator="Ctrl+D",
        )
        file_menu.add_separator()
        file_menu.add_command(label=t("main.switch_cli"), command=self._switch_to_cli)
        self._switch_system_menu = file_menu
        self._switch_system_menu_index = file_menu.index("end") + 1
        file_menu.add_command(label=t("main.switch_system"), command=self._switch_system, state="disabled")
        file_menu.add_separator()
        file_menu.add_command(
            label=t("main.logout"),
            command=self._do_logout,
            accelerator="Ctrl+L",
        )
        file_menu.add_command(
            label=t("main.exit"),
            command=self._do_exit,
            accelerator="Ctrl+Q",
        )
        self._menubar.add_cascade(label=t("main.file_menu"), menu=file_menu)

        # Menu is initially hidden; shown after login
        self.config(menu="")

    def _rebuild_ui(self):
        """Tear down and recreate all widgets so every string uses the new language."""
        saved_user = self._user_info

        # Destroy all existing child frames
        for frame in self._frames.values():
            frame.destroy()
        self._frames.clear()

        # Destroy everything
        self._main_pw.destroy()

        # Update the window title
        self.title(t("main.window_title"))

        # Rebuild the menu bar from scratch
        self._menubar.destroy()
        self._build_menu()
        self.config(menu=self._menubar)

        # Recreate the main layout
        self._main_pw = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=4,
                                        bg="#3d566e")
        self._main_pw.pack(fill="both", expand=True)

        self._sidebar_outer = tk.Frame(self._main_pw, bg=_SIDEBAR_BG, width=250)
        self._sidebar_outer.pack_propagate(False)
        self._build_sidebar()

        self._right_panel = tk.Frame(self._main_pw, bg="#ecf0f1")

        self._topbar = tk.Frame(self._right_panel, bg=_TOPBAR_BG, height=40)
        self._topbar.pack(fill="x")
        self._topbar.pack_propagate(False)

        self._dashboard_btn = tk.Button(
            self._topbar, text=t("main.dashboard_button"), font=("Helvetica", 10),
            bg="#3498db", fg="white", activebackground="#2980b9",
            activeforeground="white", bd=0, padx=12, pady=4,
            cursor="hand2", command=self._go_dashboard,
        )
        self._dashboard_btn.pack(side="left", padx=10, pady=5)

        self._location_var = tk.StringVar(value="Dashboard")
        tk.Label(self._topbar, textvariable=self._location_var,
                 font=("Helvetica", 10), bg=_TOPBAR_BG, fg="#bdc3c7",
                 ).pack(side="left", padx=(10, 0), pady=5)

        self._container = tk.Frame(self._right_panel)
        self._container.pack(fill="both", expand=True)
        self._container.grid_rowconfigure(0, weight=1)
        self._container.grid_columnconfigure(0, weight=1)

        self._main_pw.add(self._right_panel, stretch="always")

        self._init_frames()

        if saved_user:
            self._user_info = saved_user
            self._main_pw.add(self._sidebar_outer, before=self._right_panel,
                              stretch="never", width=250)
            self._populate_sidebar()
            self._topbar.pack(fill="x")
            dashboard: DashboardFrame = self._frames["dashboard_gui"]
            dashboard.set_user(saved_user)
            self.show_frame("dashboard_gui")
        else:
            # No saved session — show dashboard (login handled externally)
            self.show_frame("dashboard_gui")

    # ------------------------------------------------------------------
    # Frame switching
    # ------------------------------------------------------------------

    def show_frame(self, name: str):
        """Raise the frame identified by *name* to the top of the stack."""
        frame = self._frames.get(name)
        if frame is None:
            messagebox.showerror(t("common.error"), t("main.navigation_error", target=name))
            return

        self._active_frame_name = name

        # Ensure topbar is visible
        self._topbar.pack(fill="x", before=self._container)

        # Update breadcrumb
        if name == "dashboard_gui":
            self._location_var.set("Dashboard")
        else:
            # Try to find a human-readable label
            display = name.replace("_gui", "").replace("_", " ").title()
            for section_title, items in _SIDEBAR_SECTIONS:
                for label, fk, _role in items:
                    if fk == name:
                        display = f"{section_title}  >  {label}"
                        break
            self._location_var.set(display)

        # Highlight active sidebar item
        self._update_sidebar_active(name)

        # Lifecycle hook: let the frame refresh itself when shown
        if hasattr(frame, "refresh"):
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

        # Enable Switch System menu for superadmin users
        if self._is_superadmin():
            try:
                self._switch_system_menu.entryconfig(
                    self._switch_system_menu_index, state="normal")
            except Exception:
                pass

        # Show menu bar
        self.config(menu=self._menubar)

        # Show sidebar
        try:
            self._main_pw.add(self._sidebar_outer, before=self._right_panel,
                              stretch="never", width=250)
        except tk.TclError:
            pass  # already added
        self._populate_sidebar()

        # Configure and show the dashboard
        dashboard: DashboardFrame = self._frames["dashboard_gui"]
        dashboard.set_user(user_info)
        self.show_frame("dashboard_gui")

    def _on_navigate(self, target: str):
        """Called by DashboardFrame when the user clicks a navigation button."""
        if target in self._frames:
            self.show_frame(target)
        else:
            messagebox.showwarning(t("common.warning"), t("main.navigation_error", target=target))

    def _go_dashboard(self):
        """Return to the dashboard."""
        self.show_frame("dashboard_gui")

    def _do_logout(self):
        """Log out the current user and return to the universal login screen."""
        if messagebox.askyesno(t("main.confirm_logout"), t("main.confirm_logout_msg")):
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
        if messagebox.askyesno(t("main.switch_cli"), t("main.switch_cli_confirm")):
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
        dlg.title(t("main.switch_system"))
        dlg.resizable(False, False)
        dlg.grab_set()

        body = tk.Frame(dlg, padx=30, pady=20)
        body.pack(fill=tk.BOTH, expand=True)
        tk.Label(body, text=t("main.switch_to"), font=("Helvetica", 14, "bold")).pack(pady=(0, 15))

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

        tk.Button(body, text=t("main.university_system"),
                  bg="#2980b9", activebackground="#3498db", activeforeground="white",
                  command=lambda: _pick("university"), **btn_style).pack(pady=5)
        tk.Button(body, text=t("main.secondary_system"),
                  bg="#8e44ad", activebackground="#9b59b6", activeforeground="white",
                  command=lambda: _pick("school"), **btn_style).pack(pady=5)
        tk.Button(body, text=t("main.primary_system"),
                  bg="#e67e22", activebackground="#f39c12", activeforeground="white",
                  command=lambda: _pick("primary"), **btn_style).pack(pady=5)

        # Super Admin Dashboard button (only for superadmin users)
        if self._is_superadmin():
            ttk.Separator(body, orient="horizontal").pack(fill="x", pady=10)
            tk.Button(body, text="Super Admin Dashboard",
                      bg="#2c3e50", activebackground="#34495e", activeforeground="white",
                      command=lambda: _pick("__superadmin__"), **btn_style).pack(pady=5)

        tk.Button(body, text=t("common.cancel"), font=("Helvetica", 12), relief=tk.FLAT,
                  padx=20, pady=4, cursor="hand2", command=dlg.destroy).pack(pady=(10, 0))

        dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)

    def _is_superadmin(self):
        """Check if current user has admin access to all 4 systems."""
        if not self._user_info:
            return False
        systems = self._user_info.get("systems", [])
        admin_keys = {s["system_key"] for s in systems if s.get("role") == "admin"}
        return admin_keys >= {"university", "college", "school", "primary"}

    def _do_exit(self):
        """Confirm and close the application."""
        if messagebox.askyesno(t("main.confirm_exit"), t("main.confirm_exit_msg")):
            try:
                self._auth.logout()
            except Exception:
                pass
            self.destroy()

    def _on_escape(self, event=None):
        """Handle Escape key: close any open Toplevel dialog, or return to dashboard."""
        # First, try to close any open Toplevel (modal dialog)
        for widget in self.winfo_children():
            if isinstance(widget, tk.Toplevel):
                widget.destroy()
                return
        # If we are not on the dashboard, go back to the dashboard
        if self._active_frame_name and self._active_frame_name != "dashboard_gui":
            self._go_dashboard()


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

    # If not pre-authenticated, show the universal login window
    if not (user_info and role):
        from education_system.shared.gui.login_gui import UniversalLoginWindow
        login = UniversalLoginWindow()
        login.mainloop()

        if login.user_info is None:
            return

        user_info = login.user_info
        role = login.system_role or "admin"
        shared_auth = login.auth

    app = CollegeApp(db_path=db_path)

    # Build a user_info dict compatible with the college system
    college_user = {
        "user_id": user_info.get("user_id"),
        "username": user_info.get("username"),
        "role": role,
        "email": user_info.get("email"),
        "systems": user_info.get("systems", []),
    }
    if shared_auth:
        app._auth = shared_auth
        # Update auth reference on all frames so they see the logged-in user
        for frame in app._frames.values():
            if hasattr(frame, '_auth'):
                frame._auth = shared_auth
    app._on_login_success(college_user)

    app.mainloop()


def launch_gui(db_path: str | None = None, user_info=None, role=None, shared_auth=None):
    """Alias entry point supporting pre-authenticated launch."""
    main(db_path=db_path, user_info=user_info, role=role, shared_auth=shared_auth)


if __name__ == "__main__":
    main()
