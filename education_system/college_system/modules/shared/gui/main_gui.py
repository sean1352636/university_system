"""Main application window for the College Management System GUI.

Layout and colour scheme matches the University System GUI:
ttk clam theme, grid-based LabelFrame panels, and category buttons
that expand into sub-windows.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import traceback

from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.core.i18n import t

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════
#  Sidebar section definitions (used for category navigation)
#  Each section: (section_title, [(nav_label, frame_key, min_role), ...])
# ══════════════════════════════════════════════════════════════════════════

_SIDEBAR_SECTIONS = [
    ("Students & Learning", [
        ("Students", "student_gui", "staff"),
        ("Enrollment", "enrollment_gui", "staff"),
        ("Grades", "grade_gui", "instructor"),
        ("Attendance", "attendance_gui", "instructor"),
        ("Assignments", "assignment_gui", "student"),
        ("Timetable", "timetable_gui", "student"),
        ("Markbook", "markbook_gui", "instructor"),
        ("Question Analysis", "question_analysis_gui", "instructor"),
        ("Target Setting", "target_setting_gui", "instructor"),
        ("ILP", "ilp_gui", "instructor"),
        ("Portfolio", "portfolio_gui", "student"),
        ("Progress Dashboard", "progress_dashboard_gui", "student"),
        ("Study Planner", "study_planner_gui", "student"),
        ("Baseline Assessment", "baseline_assessment_gui", "instructor"),
        ("Work Journal", "work_journal_gui", "student"),
        ("LMS", "lms_gui", "student"),
    ]),
    ("Courses & Curriculum", [
        ("Courses", "course_gui", "student"),
        ("Departments", "departments_gui", "admin"),
        ("Study Programmes", "study_programme_gui", "staff"),
        ("T-Levels", "tlevel_gui", "staff"),
        ("Functional Skills", "functional_skills_gui", "staff"),
        ("Apprenticeships", "apprenticeship_gui", "staff"),
        ("Employer Portal", "employer_portal_gui", "admin"),
        ("Value Added", "value_added_gui", "instructor"),
    ]),
    ("Teaching & Quality", [
        ("Lesson Plans", "lesson_plan_gui", "instructor"),
        ("Observations", "observation_gui", "instructor"),
        ("CPD", "cpd_gui", "instructor"),
        ("Quality Assurance", "quality_assurance_gui", "admin"),
        ("IQR Manager", "iqr_manager_gui", "admin"),
        ("Internal Verification", "internal_verification_gui", "instructor"),
        ("Self Assessment", "self_assessment_gui", "admin"),
        ("SEF Builder", "sef_builder_gui", "admin"),
        ("Data Dashboard", "data_dashboard_gui", "instructor"),
        ("KPI Dashboard", "kpi_dashboard_gui", "admin"),
        ("Tutorial", "tutorial_gui", "instructor"),
    ]),
    ("Pastoral & Welfare", [
        ("Pastoral", "pastoral_gui", "staff"),
        ("Behaviour", "behaviour_gui", "staff"),
        ("Disciplinary", "disciplinary_gui", "admin"),
        ("Safeguarding", "safeguarding_gui", "staff"),
        ("SEND", "send_gui", "staff"),
        ("Student Support", "student_support_gui", "staff"),
        ("Student Wellbeing", "student_wellbeing_gui", "staff"),
        ("Early Warning", "early_warning_gui", "instructor"),
        ("Interventions", "intervention_gui", "instructor"),
        ("Prevent Duty", "prevent_duty_gui", "staff"),
        ("First Aid", "first_aid_gui", "staff"),
    ]),
    ("Exams & Reports", [
        ("Exams", "exams_gui", "staff"),
        ("Reports", "reports_gui", "instructor"),
        ("Audit Reports", "audit_report_gui", "admin"),
        ("Census / ILR", "census_ilr_gui", "admin"),
        ("Certificates", "certificates_gui", "staff"),
    ]),
    ("Staff", [
        ("Staff Directory", "staff_gui", "admin"),
        ("Staff HR", "staff_hr_gui", "admin"),
        ("Cover", "cover_gui", "staff"),
        ("Cover Agencies", "cover_agency_gui", "admin"),
        ("Staff Absence", "staff_absence_gui", "admin"),
        ("Staff Wellbeing", "staff_wellbeing_gui", "admin"),
        ("Appraisals", "appraisal_gui", "admin"),
        ("Absence Requests", "absence_request_gui", "instructor"),
        ("Recruitment", "recruitment_gui", "admin"),
        ("Onboarding", "onboarding_gui", "admin"),
        ("DBS Checks", "dbs_check_gui", "admin"),
        ("Expense Claims", "expense_claim_gui", "staff"),
    ]),
    ("Communication", [
        ("Messages", "message_gui", "student"),
        ("Notifications", "notification_gui", "student"),
        ("Announcements", "announcement_gui", "student"),
        ("SMS & Email", "sms_email_gui", "student"),
        ("Activity Feed", "activity_feed_gui", "student"),
        ("Forums", "forum_gui", "student"),
        ("Feedback", "feedback_gui", "student"),
        ("Surveys", "survey_gui", "student"),
    ]),
    ("Student Life", [
        ("Careers", "careers_gui", "student"),
        ("UCAS", "ucas_gui", "staff"),
        ("UCAS Export", "ucas_export_gui", "admin"),
        ("Destinations", "destinations_gui", "staff"),
        ("Destination Outcomes", "destination_outcome_gui", "staff"),
        ("Enrichment", "enrichment_gui", "student"),
        ("Peer Mentoring", "peer_mentoring_gui", "student"),
        ("Skills Passport", "skills_passport_gui", "student"),
        ("Student Portal", "student_portal_gui", "student"),
        ("Student Council", "student_council_gui", "student"),
        ("Meal Ordering", "meal_ordering_gui", "student"),
        ("Print Credits", "print_credit_gui", "student"),
        ("Library", "library_gui", "student"),
        ("Alumni", "alumni_gui", "staff"),
        ("Helpdesk", "helpdesk_gui", "student"),
    ]),
    ("Parents & Community", [
        ("Parent Portal", "parent_gui", "parent"),
        ("Parents Evening", "parents_evening_gui", "student"),
        ("Visitors", "visitor_gui", "staff"),
        ("Marketing", "marketing_gui", "admin"),
        ("Lettings", "lettings_gui", "admin"),
        ("Lettings Portal", "lettings_portal_gui", "admin"),
        ("Admissions", "admissions_gui", "staff"),
    ]),
    ("Finance & Resources", [
        ("Finance", "finance_gui", "admin"),
        ("Bursary", "bursary_gui", "admin"),
        ("Funding", "funding_gui", "admin"),
        ("Transport", "transport_gui", "admin"),
        ("Assets", "assets_gui", "staff"),
        ("Resource Booking", "resource_booking_gui", "instructor"),
    ]),
    ("Administration", [
        ("Settings", "settings_gui", "student"),
        ("MFA Settings", "mfa_gui", "student"),
        ("Security Questions", "security_questions_gui", "student"),
        ("User Management", "user_management_gui", "admin"),
        ("Academic Year", "academic_year_gui", "admin"),
        ("Bulk Operations", "bulk_operation_gui", "admin"),
        ("Data Export", "data_export_gui", "admin"),
        ("Document Hub", "document_hub_gui", "student"),
        ("Attachments", "attachment_gui", "student"),
        ("Advanced Search", "advanced_search_gui", "student"),
        ("Letter Templates", "letter_template_gui", "staff"),
        ("Policies", "policy_gui", "staff"),
        ("Todo", "todo_gui", "student"),
        ("Calendar", "calendar_gui", "student"),
    ]),
    ("Compliance & Safety", [
        ("Compliance", "compliance_gui", "admin"),
        ("GDPR", "gdpr_gui", "admin"),
        ("Governance", "governance_gui", "admin"),
        ("Risk Management", "risk_management_gui", "admin"),
        ("Equality & Diversity", "equality_diversity_gui", "admin"),
        ("Complaints", "complaint_gui", "admin"),
        ("Emergency", "emergency_gui", "staff"),
        ("Health & Safety", "health_safety_gui", "admin"),
    ]),
    ("Accessibility", [
        ("Accessibility", "accessibility_gui", "student"),
        ("Mobile Dashboard", "mobile_dashboard_gui", "student"),
        ("Multi-Language", "multi_language_gui", "student"),
    ]),
    ("Extras & Tools", [
        ("Extras & Tools", "extras_tools_gui", "student"),
        ("Academic Misconduct", "misconduct_gui", "staff"),
    ]),
    ("Cross-System Tools", [
        ("Student Journey", "student_journey_gui", "admin"),
        ("Analytics Dashboard", "analytics_dashboard_gui", "admin"),
        ("Outcome Tracking", "outcome_tracking_gui", "admin"),
        ("Predictive Alerts", "predictive_alerts_gui", "admin"),
        ("Bulk Transfer", "bulk_transfer_gui", "admin"),
        ("Transfer Documents", "transfer_documents_gui", "admin"),
        ("Reverse Lookup", "reverse_lookup_gui", "admin"),
        ("Parent Continuity", "parent_continuity_gui", "admin"),
        ("Cross-System Calendar", "cross_system_calendar_gui", "admin"),
        ("Central Admin Portal", "central_admin_gui", "admin"),
        ("GDPR Compliance", "gdpr_compliance_gui", "admin"),
        ("Shared Documents", "shared_documents_gui", "admin"),
        ("Student Self-Service", "student_self_service_gui", "admin"),
        ("Digital Transcript", "digital_transcript_gui", "admin"),
    ]),
]


def _get_frame_map():
    """Lazy-import all frame classes and return the frame key -> class mapping."""
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

    return {
        "dashboard_gui": DashboardFrame,
        "student_gui": StudentFrame, "course_gui": CourseFrame,
        "enrollment_gui": EnrollmentFrame, "grade_gui": GradeFrame,
        "attendance_gui": AttendanceFrame, "timetable_gui": TimetableFrame,
        "assignment_gui": AssignmentFrame, "notification_gui": NotificationFrame,
        "mfa_gui": MFASettingsFrame, "security_questions_gui": SecurityQuestionsFrame,
        "staff_gui": StaffFrame, "message_gui": MessageFrame,
        "todo_gui": TodoFrame, "calendar_gui": CalendarFrame,
        "first_aid_gui": FirstAidFrame, "helpdesk_gui": HelpdeskFrame,
        "parent_gui": ParentFrame, "settings_gui": SettingsFrame,
        "admissions_gui": AdmissionsFrame, "safeguarding_gui": SafeguardingFrame,
        "behaviour_gui": BehaviourFrame, "pastoral_gui": PastoralFrame,
        "send_gui": SENDFrame, "exams_gui": ExamsFrame,
        "compliance_gui": ComplianceFrame, "reports_gui": ReportsFrame,
        "parents_evening_gui": ParentsEveningFrame, "careers_gui": CareersFrame,
        "bursary_gui": BursaryFrame, "transport_gui": TransportFrame,
        "assets_gui": AssetsFrame, "library_gui": LibraryFrame,
        "staff_hr_gui": StaffHRFrame, "cover_gui": CoverFrame,
        "funding_gui": FundingFrame, "destinations_gui": DestinationsFrame,
        "student_support_gui": StudentSupportFrame, "finance_gui": FinanceFrame,
        "departments_gui": DepartmentsFrame, "cpd_gui": CPDFrame,
        "observation_gui": ObservationFrame, "appraisal_gui": AppraisalFrame,
        "resource_booking_gui": ResourceBookingFrame, "markbook_gui": MarkbookFrame,
        "staff_wellbeing_gui": StaffWellbeingFrame, "lesson_plan_gui": LessonPlanFrame,
        "data_dashboard_gui": DataDashboardFrame, "absence_request_gui": AbsenceRequestFrame,
        "intervention_gui": InterventionFrame, "visitor_gui": VisitorFrame,
        "policy_gui": PolicyFrame, "gdpr_gui": GDPRFrame,
        "quality_assurance_gui": QualityAssuranceFrame,
        "bulk_operation_gui": BulkOperationFrame, "emergency_gui": EmergencyFrame,
        "academic_year_gui": AcademicYearFrame, "kpi_dashboard_gui": KPIDashboardFrame,
        "audit_report_gui": AuditReportFrame, "user_management_gui": UserManagementFrame,
        "portfolio_gui": PortfolioFrame, "study_planner_gui": StudyPlannerFrame,
        "enrichment_gui": EnrichmentFrame, "peer_mentoring_gui": PeerMentoringFrame,
        "survey_gui": SurveyFrame, "skills_passport_gui": SkillsPassportFrame,
        "progress_dashboard_gui": ProgressDashboardFrame,
        "meal_ordering_gui": MealOrderingFrame, "print_credit_gui": PrintCreditFrame,
        "work_journal_gui": WorkJournalFrame, "announcement_gui": AnnouncementFrame,
        "document_hub_gui": DocumentHubFrame, "advanced_search_gui": AdvancedSearchFrame,
        "feedback_gui": FeedbackFrame, "accessibility_gui": AccessibilityFrame,
        "mobile_dashboard_gui": MobileDashboardFrame, "attachment_gui": AttachmentFrame,
        "activity_feed_gui": ActivityFeedFrame, "sms_email_gui": SmsEmailFrame,
        "multi_language_gui": MultiLanguageFrame, "ilp_gui": ILPFrame,
        "ucas_gui": UCASFrame, "tlevel_gui": TLevelFrame,
        "apprenticeship_gui": ApprenticeshipFrame, "value_added_gui": ValueAddedFrame,
        "governance_gui": GovernanceFrame, "dbs_check_gui": DBSCheckFrame,
        "risk_management_gui": RiskManagementFrame, "prevent_duty_gui": PreventDutyFrame,
        "complaint_gui": ComplaintFrame, "equality_diversity_gui": EqualityDiversityFrame,
        "staff_absence_gui": StaffAbsenceFrame, "recruitment_gui": RecruitmentFrame,
        "marketing_gui": MarketingFrame, "early_warning_gui": EarlyWarningFrame,
        "self_assessment_gui": SelfAssessmentFrame, "alumni_gui": AlumniFrame,
        "student_portal_gui": StudentPortalFrame, "forum_gui": ForumFrame,
        "internal_verification_gui": InternalVerificationFrame,
        "functional_skills_gui": FunctionalSkillsFrame,
        "study_programme_gui": StudyProgrammeFrame, "tutorial_gui": TutorialFrame,
        "student_wellbeing_gui": StudentWellbeingFrame,
        "student_council_gui": StudentCouncilFrame, "lettings_gui": LettingsFrame,
        "health_safety_gui": HealthSafetyFrame, "letter_template_gui": LetterTemplateFrame,
        "disciplinary_gui": DisciplinaryFrame, "onboarding_gui": OnboardingFrame,
        "expense_claim_gui": ExpenseClaimFrame,
        "baseline_assessment_gui": BaselineAssessmentFrame,
        "data_export_gui": DataExportFrame,
        "student_journey_gui": JourneyDashboardFrame,
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
        "certificates_gui": CertificatesGUI, "extras_tools_gui": ExtrasFrame,
        "misconduct_gui": MisconductFrame, "lms_gui": LMSFrame,
        "census_ilr_gui": CensusILRFrame, "ucas_export_gui": UCASExportFrame,
        "destination_outcome_gui": DestinationOutcomeFrame,
        "iqr_manager_gui": IQRManagerFrame, "sef_builder_gui": SEFBuilderFrame,
        "question_analysis_gui": QuestionAnalysisFrame,
        "target_setting_gui": TargetSettingFrame, "cover_agency_gui": CoverAgencyFrame,
        "lettings_portal_gui": LettingsPortalFrame,
        "employer_portal_gui": EmployerPortalFrame,
    }


# ══════════════════════════════════════════════════════════════════════════
#  Main application
# ══════════════════════════════════════════════════════════════════════════

class CollegeApp(tk.Tk):
    """Root window with categorised navigation and dynamic content area.

    Mirrors the University System GUI layout: ttk clam theme, grid-based
    LabelFrame panels, and category buttons that expand into sub-windows.
    """

    def __init__(self, db_path: str | None = None):
        super().__init__()

        self._db_path = db_path
        self._auth = UserAuth(db_path)
        self._user_info: dict | None = None
        self._frames: dict[str, tk.Frame] = {}

        self.title(t("main.window_title"))
        self.geometry("1200x800")
        self.minsize(1000, 700)

        # Configure ttk style to match university
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Status variables
        self.current_user_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")

        self._setup_gui()

        # Keyboard shortcuts
        self.bind("<Escape>", self._on_escape)
        self.bind("<Control-d>", lambda e: self._show_frame("dashboard_gui"))
        self.bind("<Control-l>", lambda e: self._do_logout())
        self.bind("<Control-q>", lambda e: self._do_exit())

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

    # ── GUI setup ─────────────────────────────────────────────────────

    def _setup_gui(self):
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
        header_frame = ttk.LabelFrame(parent, text=t("gui.system_control") if hasattr(t, '__call__') else "System Control", padding="10")
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        button_frame = ttk.Frame(header_frame)
        button_frame.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 10))

        ttk.Button(button_frame, text=t("main.exit"),
                   command=self._do_exit).pack(side="left", padx=(0, 10))
        ttk.Button(button_frame, text=t("main.logout"),
                   command=self._do_logout).pack(side="left", padx=(0, 10))
        ttk.Button(button_frame, text=t("main.switch_cli"),
                   command=self._switch_to_cli).pack(side="left", padx=(0, 10))

        # Switch System button — enabled after login if superadmin
        self._switch_system_btn = ttk.Button(button_frame, text=t("main.switch_system"),
                                              command=self._switch_system, state="disabled")
        self._switch_system_btn.pack(side="left", padx=(0, 10))

        ttk.Label(header_frame, text="Status:").grid(row=1, column=0, sticky="w")
        ttk.Label(header_frame, textvariable=self.status_var).grid(row=1, column=1, sticky="w", padx=(10, 0))

        ttk.Label(header_frame, text="Current User:").grid(row=2, column=0, sticky="w")
        ttk.Label(header_frame, textvariable=self.current_user_var).grid(row=2, column=1, sticky="w", padx=(10, 0))

        header_frame.columnconfigure(1, weight=1)

    def _create_navigation_panel(self, parent):
        self._nav_frame = ttk.LabelFrame(parent, text=t("main.navigation") if hasattr(t, '__call__') else "Navigation", padding="5")
        self._nav_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))

        self._nav_frame.rowconfigure(0, weight=1)
        self._nav_frame.columnconfigure(0, weight=1)

        canvas = tk.Canvas(self._nav_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self._nav_frame, orient="vertical", command=canvas.yview)
        self._nav_scrollable = ttk.Frame(canvas)

        self._nav_scrollable.bind("<Configure>",
                                   lambda _: canvas.configure(scrollregion=canvas.bbox("all")))

        canvas_window = canvas.create_window((0, 0), window=self._nav_scrollable, anchor="nw")
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

    def _populate_navigation(self):
        """Build category buttons based on current user role."""
        for w in self._nav_scrollable.winfo_children():
            w.destroy()

        if not self._user_info:
            return

        from education_system.college_system.infrastructure.auth.role_manager import ROLE_HIERARCHY

        user_role = self._user_info.get("role", "student")
        user_level = ROLE_HIERARCHY.get(user_role, 0)

        def open_category_window(category_title, items):
            visible_items = []
            for label, frame_key, min_role in items:
                required = ROLE_HIERARCHY.get(min_role, 0)
                if user_level >= required:
                    visible_items.append((label, frame_key))

            if not visible_items:
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

            for idx, (label, frame_key) in enumerate(visible_items):
                def make_command(fk, window):
                    def wrapped():
                        window.destroy()
                        self._show_frame(fk)
                    return wrapped

                r = idx // cols
                c = idx % cols
                btn = ttk.Button(scrollable, text=label,
                                 command=make_command(frame_key, cat_window))
                btn.grid(row=r, column=c, padx=4, pady=4, sticky='nsew')

            ttk.Button(cat_window, text=t("common.close"),
                       command=cat_window.destroy).pack(pady=10)

        # Dashboard button — hidden initially (shown when navigating away)
        self._dashboard_nav_btn = ttk.Button(
            self._nav_scrollable, text=t("main.dashboard_button"),
            command=lambda: self._show_frame("dashboard_gui"))
        # Don't pack yet — _show_frame will manage visibility

        for section_title, items in _SIDEBAR_SECTIONS:
            visible_items = [
                (label, fk) for label, fk, min_role in items
                if ROLE_HIERARCHY.get(user_role, 0) >= ROLE_HIERARCHY.get(min_role, 0)
            ]
            if visible_items:
                ttk.Button(
                    self._nav_scrollable, text=section_title + " \u25b6",
                    command=lambda st=section_title, it=items: open_category_window(st, it),
                ).pack(fill="x", pady=2, padx=5)

    def _create_content_area(self, parent):
        outer_frame = ttk.LabelFrame(parent, text=t("main.content") if hasattr(t, '__call__') else "Content", padding="5")
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

    # ── Frame management ──────────────────────────────────────────────

    def _clear_content(self):
        for widget in self._content.winfo_children():
            widget.destroy()

    def _show_frame(self, frame_key: str):
        """Show a module frame in the content area, lazy-loading on first access."""
        # Toggle dashboard nav button: hide when on dashboard, show otherwise
        if hasattr(self, '_dashboard_nav_btn'):
            if frame_key == "dashboard_gui":
                self._dashboard_nav_btn.pack_forget()
            elif not self._dashboard_nav_btn.winfo_ismapped():
                # Pack at the top of navigation
                self._dashboard_nav_btn.pack(fill="x", pady=2, padx=5)
                first_child = self._nav_scrollable.pack_slaves()
                if first_child and first_child[0] is not self._dashboard_nav_btn:
                    self._dashboard_nav_btn.pack(fill="x", pady=2, padx=5, before=first_child[0])

        if frame_key == "dashboard_gui" and "dashboard_gui" in self._frames:
            # Show existing dashboard
            for w in self._content.winfo_children():
                w.pack_forget()
            frame = self._frames["dashboard_gui"]
            frame.pack(fill="both", expand=True)
            if hasattr(frame, "refresh"):
                try:
                    frame.refresh()
                except Exception:
                    pass
            return

        if frame_key not in self._frames:
            try:
                frame_map = _get_frame_map()
                cls = frame_map.get(frame_key)
                if cls is None:
                    messagebox.showwarning(t("common.warning"),
                                           t("main.navigation_error", target=frame_key))
                    return

                if frame_key == "dashboard_gui":
                    frame = cls(self._content, db_path=self._db_path, auth=self._auth,
                                on_navigate=self._on_navigate)
                elif cls.__name__ == 'MisconductFrame':
                    frame = cls(self._content, db_path=self._db_path, auth=self._auth,
                                system_key='college')
                else:
                    frame = cls(self._content, db_path=self._db_path, auth=self._auth)
                self._frames[frame_key] = frame
            except Exception as e:
                logger.error("Failed to load %s: %s", frame_key, e, exc_info=True)
                traceback.print_exc()
                err_frame = ttk.Frame(self._content)
                ttk.Label(err_frame, text=f"Failed to load {frame_key}:\n{e}",
                          foreground="red", font=("Helvetica", 11)).pack(expand=True)
                self._frames[frame_key] = err_frame

        # Hide all, show selected
        for w in self._content.winfo_children():
            w.pack_forget()

        frame = self._frames[frame_key]
        frame.pack(fill="both", expand=True)
        if hasattr(frame, "refresh"):
            try:
                frame.refresh()
            except Exception:
                pass

    # ── Callbacks ─────────────────────────────────────────────────────

    def _on_login_success(self, user_info: dict):
        """Called after successful authentication."""
        logger.info("GUI login: user '%s'", user_info.get('username', '?'))
        self._user_info = user_info

        # Update status
        display = user_info.get("username", "Unknown")
        role = user_info.get("role", "unknown")
        self.current_user_var.set(f"{display} ({role})")
        self.status_var.set("Logged in")

        # Enable Switch System for superadmin
        if self._is_superadmin():
            self._switch_system_btn.configure(state="normal")

        # Populate navigation
        self._populate_navigation()

        # Show dashboard
        from education_system.college_system.modules.shared.gui.dashboard_gui import DashboardFrame
        frame_map = _get_frame_map()
        cls = frame_map["dashboard_gui"]
        dashboard = cls(self._content, db_path=self._db_path, auth=self._auth,
                        on_navigate=self._on_navigate)
        dashboard.set_user(user_info)
        self._frames["dashboard_gui"] = dashboard
        self._show_frame("dashboard_gui")

    def _on_navigate(self, target: str):
        if target in self._frames or target in (_get_frame_map() if not hasattr(self, '_cached_map') else {}):
            self._show_frame(target)
        else:
            # Try to find the frame key
            self._show_frame(target)

    def _do_logout(self):
        if messagebox.askyesno(t("main.confirm_logout"), t("main.confirm_logout_msg")):
            try:
                self._auth.logout()
            except Exception:
                pass
            from education_system.switch import request_logout
            request_logout()
            self.destroy()

    def _switch_to_cli(self):
        if messagebox.askyesno(t("main.switch_cli"), t("main.switch_cli_confirm")):
            from education_system.switch import request_switch
            request_switch("college", "cli")
            try:
                self._auth.logout()
            except Exception:
                pass
            self.destroy()

    def _switch_system(self):
        picker = tk.Toplevel(self)
        picker.title(t("main.switch_system"))
        picker.resizable(False, False)
        picker.grab_set()
        picker.transient(self)

        body = ttk.Frame(picker, padding="30 20")
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=t("main.switch_to"), font=("Helvetica", 14, "bold")).pack(pady=(0, 15))

        btn_style = {"font": ("Helvetica", 12), "fg": "white", "relief": "flat",
                     "cursor": "hand2", "width": 30, "height": 2}

        def _pick(system):
            picker.destroy()
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

        if self._is_superadmin():
            ttk.Separator(body, orient="horizontal").pack(fill="x", pady=10)
            tk.Button(body, text="Super Admin Dashboard",
                      bg="#2c3e50", activebackground="#34495e", activeforeground="white",
                      command=lambda: _pick("__superadmin__"), **btn_style).pack(pady=5)

        ttk.Button(body, text=t("common.cancel"), command=picker.destroy).pack(pady=(10, 0))

    def _is_superadmin(self):
        if not self._user_info:
            return False
        systems = self._user_info.get("systems", [])
        admin_keys = {s["system_key"] for s in systems if s.get("role") == "admin"}
        return admin_keys >= {"university", "college", "school", "primary"}

    def _do_exit(self):
        if messagebox.askyesno(t("main.confirm_exit"), t("main.confirm_exit_msg")):
            try:
                self._auth.logout()
            except Exception:
                pass
            self.destroy()

    def _on_escape(self, event=None):
        for widget in self.winfo_children():
            if isinstance(widget, tk.Toplevel):
                widget.destroy()
                return
        self._show_frame("dashboard_gui")


# ══════════════════════════════════════════════════════════════════════════
#  Application entry
# ══════════════════════════════════════════════════════════════════════════

def main(db_path: str | None = None, user_info=None, role=None, shared_auth=None):
    """Entry point for launching the GUI application."""
    from education_system.college_system.core.paths import ensure_directories
    from education_system.college_system.infrastructure.database.schema import init_db, seed_default_data

    ensure_directories()
    init_db(db_path)
    seed_default_data(db_path)
    from education_system.college_system.core.logs import configure_logging
    configure_logging()
    logger.info("GUI application starting")

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

    college_user = {
        "user_id": user_info.get("user_id"),
        "username": user_info.get("username"),
        "role": role,
        "email": user_info.get("email"),
        "systems": user_info.get("systems", []),
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
