"""Shared test fixtures for the Primary School Management System."""

import os
import sys

import pytest

# Ensure project root is on path
sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)

from education_system.primary_school.infrastructure.database.db import set_db_path
from education_system.primary_school.infrastructure.database.schema import (
    initialise_database,
    seed_default_users,
)
from education_system.shared.testing.conftest_helpers import (
    make_template_db_fixture,
    make_db_path_fixture,
)
from education_system.primary_school.modules.domain.academics.pupils.services.pupil_service import (
    PupilService,
)
from education_system.primary_school.modules.domain.academics.subjects.services.subject_service import (
    SubjectService,
)
from education_system.primary_school.modules.domain.academics.assessment.services.assessment_service import (
    AssessmentService,
)
from education_system.primary_school.modules.domain.academics.attendance.services.attendance_service import (
    AttendanceService,
)
from education_system.primary_school.modules.domain.academics.classes.services.class_service import (
    ClassService,
)
from education_system.primary_school.modules.domain.pastoral_care.behaviour.services.behaviour_service import (
    BehaviourService,
)
from education_system.primary_school.modules.domain.pastoral_care.rewards.services.rewards_service import (
    RewardsService,
)
from education_system.primary_school.modules.domain.academics.homework.services.homework_service import (
    HomeworkService,
)
from education_system.primary_school.modules.domain.academics.sats.services.sats_service import (
    SATsService,
)
from education_system.primary_school.modules.domain.academics.phonics.services.phonics_service import (
    PhonicsService,
)
from education_system.primary_school.modules.domain.academics.reading_records.services.reading_record_service import (
    ReadingRecordService,
)
from education_system.primary_school.modules.domain.academics.progress.services.progress_service import (
    ProgressService,
)
from education_system.primary_school.modules.domain.academics.timetable.services.timetable_service import (
    TimetableService,
)
from education_system.primary_school.modules.domain.pastoral_care.pastoral.services.pastoral_service import (
    PastoralService,
)
from education_system.primary_school.modules.domain.pastoral_care.safeguarding.services.safeguarding_service import (
    SafeguardingService,
)
from education_system.primary_school.modules.domain.pastoral_care.send.services.send_service import (
    SENDService,
)
from education_system.primary_school.modules.domain.admin.admissions.services.admissions_service import (
    AdmissionsService,
)
from education_system.primary_school.modules.domain.admin.finance.services.finance_service import (
    FinanceService,
)
from education_system.primary_school.modules.domain.communication.announcements.services.announcement_service import (
    AnnouncementService,
)
from education_system.primary_school.modules.domain.communication.calendar.services.calendar_service import (
    CalendarService,
)
from education_system.primary_school.modules.domain.communication.parents_evening.services.parents_evening_service import (
    ParentsEveningService,
)
from education_system.primary_school.modules.domain.pupil_life.clubs.services.club_service import (
    ClubService,
)
from education_system.primary_school.modules.domain.pupil_life.library.services.library_service import (
    LibraryService,
)
from education_system.primary_school.modules.domain.pupil_life.meals.services.meal_service import (
    MealService,
)
from education_system.primary_school.modules.domain.pupil_life.transport.services.transport_service import (
    TransportService,
)
from education_system.primary_school.modules.domain.pupil_life.medical.services.medical_service import (
    MedicalService,
)
from education_system.primary_school.modules.domain.facilities.assets.services.asset_service import (
    AssetService,
)
from education_system.primary_school.modules.domain.facilities.room_booking.services.room_booking_service import (
    RoomBookingService,
)
from education_system.primary_school.modules.domain.staff.hr.services.hr_service import (
    HRService,
)
from education_system.primary_school.modules.domain.staff.cpd.services.cpd_service import (
    CPDService,
)
from education_system.primary_school.modules.domain.staff.cover.services.cover_service import (
    CoverService,
)
from education_system.primary_school.modules.domain.staff.staff_directory.services.staff_directory_service import (
    StaffDirectoryService,
)
from education_system.primary_school.modules.domain.staff.appraisals.services.appraisals_service import (
    AppraisalsService,
)
from education_system.primary_school.modules.domain.staff.observations.services.observations_service import (
    ObservationsService,
)
from education_system.primary_school.modules.domain.staff.staff_wellbeing.services.staff_wellbeing_service import (
    StaffWellbeingService,
)
from education_system.primary_school.modules.domain.staff.lesson_plans.services.lesson_plans_service import (
    LessonPlansService,
)
from education_system.primary_school.modules.domain.admin.users.services.user_service import (
    UserService,
)
from education_system.primary_school.modules.domain.admin.settings.services.settings_service import (
    SettingsService,
)
from education_system.primary_school.modules.domain.admin.data_export.services.data_export_service import (
    DataExportService,
)
from education_system.primary_school.modules.domain.admin.audit_log.services.audit_service import (
    AuditService,
)
from education_system.primary_school.modules.domain.admin.policies.services.policy_service import (
    PolicyService,
)
from education_system.primary_school.modules.domain.admin.documents.services.document_service import (
    DocumentService,
)
from education_system.primary_school.modules.domain.admin.data_dashboard.services.data_dashboard_service import (
    DataDashboardService,
)
from education_system.primary_school.modules.domain.admin.gdpr.services.gdpr_service import (
    GDPRService,
)
from education_system.primary_school.modules.domain.admin.payroll.services.payroll_service import (
    PayrollService,
)
from education_system.primary_school.modules.domain.admin.complaints.services.complaints_service import (
    ComplaintsService,
)
from education_system.primary_school.modules.domain.pupil_life.class_groups.services.class_group_service import (
    ClassGroupService,
)
from education_system.primary_school.modules.domain.pupil_life.consent.services.consent_service import (
    ConsentService,
)
from education_system.primary_school.modules.domain.pupil_life.trips.services.trip_service import (
    TripService,
)
from education_system.primary_school.modules.domain.communication.email.services.email_service import (
    EmailService,
)
from education_system.primary_school.modules.domain.communication.notifications.services.notification_service import (
    NotificationService,
)
from education_system.primary_school.modules.domain.communication.communication_log.services.communication_log_service import (
    CommunicationLogService,
)
from education_system.primary_school.modules.domain.communication.feedback.services.feedback_service import (
    FeedbackService,
)
from education_system.primary_school.modules.domain.facilities.visitors.services.visitor_service import (
    VisitorService,
)
from education_system.primary_school.modules.domain.facilities.incidents.services.incident_service import (
    IncidentService,
)
from education_system.primary_school.modules.domain.pastoral_care.pupil_wellbeing.services.pupil_wellbeing_service import (
    PupilWellbeingService,
)
from education_system.primary_school.modules.domain.academics.portfolio.services.portfolio_service import (
    PortfolioService,
)
from education_system.primary_school.modules.domain.academics.skills_tracker.services.skills_tracker_service import (
    SkillsTrackerService,
)
from education_system.primary_school.modules.domain.academics.academic_year.services.academic_year_service import (
    AcademicYearService,
)
from education_system.primary_school.modules.domain.academics.assignments.services.assignments_service import (
    AssignmentService,
)
from education_system.primary_school.modules.domain.academics.baseline_assessment.services.baseline_assessment_service import (
    BaselineAssessmentService,
)
from education_system.primary_school.modules.domain.academics.markbook.services.markbook_service import (
    MarkbookService,
)
from education_system.primary_school.modules.domain.academics.question_analysis.services.question_analysis_service import (
    QuestionAnalysisService,
)
from education_system.primary_school.modules.domain.academics.target_setting.services.target_setting_service import (
    TargetSettingService,
)
from education_system.primary_school.modules.domain.admin.audit_reports.services.audit_reports_service import (
    AuditReportsService,
)
from education_system.primary_school.modules.domain.admin.bulk_operations.services.bulk_operations_service import (
    BulkOperationsService,
)
from education_system.primary_school.modules.domain.admin.census.services.census_service import (
    CensusService,
)
from education_system.primary_school.modules.domain.admin.compliance.services.compliance_service import (
    ComplianceService,
)
from education_system.primary_school.modules.domain.admin.health_safety.services.health_safety_service import (
    HealthSafetyService,
)
from education_system.primary_school.modules.domain.admin.helpdesk.services.helpdesk_service import (
    HelpdeskService,
)
from education_system.primary_school.modules.domain.admin.letter_templates.services.letter_templates_service import (
    LetterTemplatesService,
)
from education_system.primary_school.modules.domain.admin.multi_language.services.multi_language_service import (
    MultiLanguageService,
)
from education_system.primary_school.modules.domain.admin.onboarding.services.onboarding_service import (
    OnboardingService,
)
from education_system.primary_school.modules.domain.admin.prevent_duty.services.prevent_duty_service import (
    PreventDutyService,
)
from education_system.primary_school.modules.domain.admin.quality_assurance.services.quality_assurance_service import (
    QualityAssuranceService,
)
from education_system.primary_school.modules.domain.admin.risk_management.services.risk_management_service import (
    RiskManagementService,
)
from education_system.primary_school.modules.domain.admin.self_assessment.services.self_assessment_service import (
    SelfAssessmentService,
)
from education_system.primary_school.modules.domain.admin.todo.services.todo_service import (
    TodoService,
)
from education_system.primary_school.modules.domain.communication.activity_feed.services.activity_feed_service import (
    ActivityFeedService,
)
from education_system.primary_school.modules.domain.communication.messaging.services.messaging_service import (
    MessagingService,
)
from education_system.primary_school.modules.domain.communication.sms_email.services.sms_email_service import (
    SmsEmailService,
)
from education_system.primary_school.modules.domain.communication.surveys.services.surveys_service import (
    SurveysService,
)
from education_system.primary_school.modules.domain.facilities.departments.services.departments_service import (
    DepartmentsService,
)
from education_system.primary_school.modules.domain.facilities.emergency.services.emergency_service import (
    EmergencyService,
)
from education_system.primary_school.modules.domain.facilities.lettings.services.lettings_service import (
    LettingsService,
)
from education_system.primary_school.modules.domain.facilities.resource_booking.services.resource_booking_service import (
    ResourceBookingService,
)
from education_system.primary_school.modules.domain.pastoral_care.absence_requests.services.absence_requests_service import (
    AbsenceRequestsService,
)
from education_system.primary_school.modules.domain.pastoral_care.accessibility.services.accessibility_service import (
    AccessibilityService,
)
from education_system.primary_school.modules.domain.pastoral_care.early_warning.services.early_warning_service import (
    EarlyWarningService,
)
from education_system.primary_school.modules.domain.pupil_life.equality_diversity.services.equality_diversity_service import (
    EqualityDiversityService,
)
from education_system.primary_school.modules.domain.pupil_life.ilp.services.ilp_service import (
    IlpService,
)
from education_system.primary_school.modules.domain.pupil_life.peer_mentoring.services.peer_mentoring_service import (
    PeerMentoringService,
)
from education_system.primary_school.modules.domain.pupil_life.pupil_support.services.pupil_support_service import (
    PupilSupportService,
)
from education_system.primary_school.modules.domain.staff.dbs_checks.services.dbs_checks_service import (
    DbsChecksService,
)
from education_system.primary_school.modules.domain.staff.first_aid.services.first_aid_service import (
    FirstAidService,
)
from education_system.primary_school.modules.domain.staff.recruitment.services.recruitment_service import (
    RecruitmentService,
)
from education_system.primary_school.modules.domain.staff.staff_absence.services.staff_absence_service import (
    StaffAbsenceService,
)
from education_system.primary_school.modules.domain.portals.document_hub.services.document_hub_service import (
    DocumentHubService,
)
from education_system.primary_school.modules.domain.portals.kpi_dashboard.services.kpi_dashboard_service import (
    KpiDashboardService,
)
from education_system.primary_school.modules.domain.portals.mobile_dashboard.services.mobile_dashboard_service import (
    MobileDashboardService,
)
from education_system.primary_school.modules.domain.portals.parent_portal.services.parent_portal_service import (
    ParentPortalService,
)
from education_system.primary_school.modules.domain.portals.progress_dashboard.services.progress_dashboard_service import (
    ProgressDashboardService,
)
from education_system.primary_school.modules.domain.portals.pupil_portal.services.pupil_portal_service import (
    PupilPortalService,
)


# ── Template and per-test DB fixtures (shared boilerplate) ───────────────
_template_db = make_template_db_fixture(initialise_database)
db_path = make_db_path_fixture(set_db_path, "test_primary_school.db")


# ── Service fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def pupil_service(db_path):
    """Create a PupilService instance with the test database."""
    return PupilService(db_path)


@pytest.fixture
def subject_service(db_path):
    """Create a SubjectService instance with the test database."""
    return SubjectService(db_path)


@pytest.fixture
def assessment_service(db_path):
    """Create an AssessmentService instance with the test database."""
    return AssessmentService(db_path)


@pytest.fixture
def attendance_service(db_path):
    """Create an AttendanceService instance with the test database."""
    return AttendanceService(db_path)


@pytest.fixture
def class_service(db_path):
    """Create a ClassService instance with the test database."""
    return ClassService(db_path)


@pytest.fixture
def behaviour_service(db_path):
    """Create a BehaviourService instance with the test database."""
    return BehaviourService(db_path)


@pytest.fixture
def rewards_service(db_path):
    """Create a RewardsService instance with the test database."""
    return RewardsService(db_path)


# ── Sample data fixtures ─────────────────────────────────────────────────


@pytest.fixture
def sample_pupil(pupil_service):
    """Create a sample pupil in Reception for testing."""
    return pupil_service.create_pupil(
        first_name="Oliver",
        last_name="Smith",
        year_group="Reception",
        date_of_birth="2020-09-15",
        gender="Male",
        parent1_name="Sarah Smith",
        parent1_email="sarah.smith@example.com",
        parent1_phone="07700900001",
    )


@pytest.fixture
def sample_pupil_ks1(pupil_service):
    """Create a sample pupil in Year 1 (KS1) for testing."""
    return pupil_service.create_pupil(
        first_name="Amelia",
        last_name="Jones",
        year_group="Year 1",
        date_of_birth="2019-03-22",
        gender="Female",
        parent1_name="David Jones",
        parent1_email="david.jones@example.com",
    )


@pytest.fixture
def sample_pupil_ks2(pupil_service):
    """Create a sample pupil in Year 5 (KS2) for testing."""
    return pupil_service.create_pupil(
        first_name="Mohammed",
        last_name="Ali",
        year_group="Year 5",
        date_of_birth="2015-07-10",
        gender="Male",
    )


@pytest.fixture
def sample_subject(subject_service):
    """Create a sample core subject for testing."""
    return subject_service.create_subject(
        subject_code="ENG",
        title="English",
        description="English language and literacy",
        is_core=1,
    )


@pytest.fixture
def sample_subject_maths(subject_service):
    """Create a maths subject for testing."""
    return subject_service.create_subject(
        subject_code="MAT",
        title="Mathematics",
        description="Mathematics and numeracy",
        is_core=1,
    )


@pytest.fixture
def sample_class(class_service):
    """Create a sample class for testing."""
    return class_service.create_class(
        class_name="1A",
        year_group="Year 1",
        room="Room 3",
        capacity=30,
    )


# ── Academic service fixtures ─────────────────────────────────────────────


@pytest.fixture
def homework_service(db_path):
    """Create a HomeworkService instance with the test database."""
    return HomeworkService(db_path)


@pytest.fixture
def sats_service(db_path):
    """Create a SATsService instance with the test database."""
    return SATsService(db_path)


@pytest.fixture
def phonics_service(db_path):
    """Create a PhonicsService instance with the test database."""
    return PhonicsService(db_path)


@pytest.fixture
def reading_record_service(db_path):
    """Create a ReadingRecordService instance with the test database."""
    return ReadingRecordService(db_path)


@pytest.fixture
def progress_service(db_path):
    """Create a ProgressService instance with the test database."""
    return ProgressService(db_path)


@pytest.fixture
def timetable_service(db_path):
    """Create a TimetableService instance with the test database."""
    return TimetableService(db_path)


# ── Pastoral service fixtures ─────────────────────────────────────────────


@pytest.fixture
def pastoral_service(db_path):
    """Create a PastoralService instance with the test database."""
    return PastoralService(db_path)


@pytest.fixture
def safeguarding_service(db_path):
    """Create a SafeguardingService instance with the test database."""
    return SafeguardingService(db_path)


@pytest.fixture
def send_service(db_path):
    """Create a SENDService instance with the test database."""
    return SENDService(db_path)


# ── Admin service fixtures ────────────────────────────────────────────────


@pytest.fixture
def admissions_service(db_path):
    """Create an AdmissionsService instance with the test database."""
    return AdmissionsService(db_path)


@pytest.fixture
def finance_service(db_path):
    """Create a FinanceService instance with the test database."""
    return FinanceService(db_path)


# ── Communication service fixtures ────────────────────────────────────────


@pytest.fixture
def announcement_service(db_path):
    """Create an AnnouncementService instance with the test database."""
    return AnnouncementService(db_path)


@pytest.fixture
def calendar_service(db_path):
    """Create a CalendarService instance with the test database."""
    return CalendarService(db_path)


@pytest.fixture
def parents_evening_service(db_path):
    """Create a ParentsEveningService instance with the test database."""
    return ParentsEveningService(db_path)


# ── Pupil Life service fixtures ───────────────────────────────────────────


@pytest.fixture
def club_service(db_path):
    """Create a ClubService instance with the test database."""
    return ClubService(db_path)


@pytest.fixture
def library_service(db_path):
    """Create a LibraryService instance with the test database."""
    return LibraryService(db_path)


@pytest.fixture
def meal_service(db_path):
    """Create a MealService instance with the test database."""
    return MealService(db_path)


@pytest.fixture
def transport_service(db_path):
    """Create a TransportService instance with the test database."""
    return TransportService(db_path)


@pytest.fixture
def medical_service(db_path):
    """Create a MedicalService instance with the test database."""
    return MedicalService(db_path)


# ── Facilities service fixtures ───────────────────────────────────────────


@pytest.fixture
def asset_service(db_path):
    """Create an AssetService instance with the test database."""
    return AssetService(db_path)


@pytest.fixture
def room_booking_service(db_path):
    """Create a RoomBookingService instance with the test database."""
    return RoomBookingService(db_path)


# ── Staff service fixtures ────────────────────────────────────────────────


@pytest.fixture
def hr_service(db_path):
    """Create an HRService instance with the test database."""
    return HRService(db_path)


@pytest.fixture
def cpd_service(db_path):
    """Create a CPDService instance with the test database."""
    return CPDService(db_path)


@pytest.fixture
def cover_service(db_path):
    """Create a CoverService instance with the test database."""
    return CoverService(db_path)


@pytest.fixture
def staff_directory_service(db_path):
    """Create a StaffDirectoryService instance with the test database."""
    return StaffDirectoryService(db_path)


@pytest.fixture
def appraisals_service(db_path):
    """Create an AppraisalsService instance with the test database."""
    return AppraisalsService(db_path)


@pytest.fixture
def observations_service(db_path):
    """Create an ObservationsService instance with the test database."""
    return ObservationsService(db_path)


@pytest.fixture
def staff_wellbeing_service(db_path):
    """Create a StaffWellbeingService instance with the test database."""
    return StaffWellbeingService(db_path)


@pytest.fixture
def lesson_plans_service(db_path):
    """Create a LessonPlansService instance with the test database."""
    return LessonPlansService(db_path)


@pytest.fixture
def user_service(db_path):
    """Create a UserService instance with the test database."""
    return UserService(db_path)


@pytest.fixture
def settings_service(db_path):
    """Create a SettingsService instance with the test database."""
    return SettingsService(db_path)


@pytest.fixture
def data_export_service(db_path):
    """Create a DataExportService instance with the test database."""
    return DataExportService(db_path)


@pytest.fixture
def audit_service(db_path):
    """Create an AuditService instance with the test database."""
    return AuditService(db_path)


@pytest.fixture
def policy_service(db_path):
    """Create a PolicyService instance with the test database."""
    return PolicyService(db_path)


@pytest.fixture
def document_service(db_path):
    """Create a DocumentService instance with the test database."""
    return DocumentService(db_path)


@pytest.fixture
def data_dashboard_service(db_path):
    """Create a DataDashboardService instance with the test database."""
    return DataDashboardService(db_path)


@pytest.fixture
def gdpr_service(db_path):
    """Create a GDPRService instance with the test database."""
    return GDPRService(db_path)


@pytest.fixture
def payroll_service(db_path):
    """Create a PayrollService instance with the test database."""
    return PayrollService(db_path)


@pytest.fixture
def complaints_service(db_path):
    """Create a ComplaintsService instance with the test database."""
    return ComplaintsService(db_path)


@pytest.fixture
def class_group_service(db_path):
    """Create a ClassGroupService instance with the test database."""
    return ClassGroupService(db_path)


@pytest.fixture
def consent_service(db_path):
    """Create a ConsentService instance with the test database."""
    return ConsentService(db_path)


@pytest.fixture
def trip_service(db_path):
    """Create a TripService instance with the test database."""
    return TripService(db_path)


@pytest.fixture
def email_service(db_path):
    """Create an EmailService instance with the test database."""
    return EmailService(db_path)


@pytest.fixture
def notification_service(db_path):
    """Create a NotificationService instance with the test database."""
    return NotificationService(db_path)


@pytest.fixture
def communication_log_service(db_path):
    """Create a CommunicationLogService instance with the test database."""
    return CommunicationLogService(db_path)


@pytest.fixture
def feedback_service(db_path):
    """Create a FeedbackService instance with the test database."""
    return FeedbackService(db_path)


@pytest.fixture
def visitor_service(db_path):
    """Create a VisitorService instance with the test database."""
    return VisitorService(db_path)


@pytest.fixture
def incident_service(db_path):
    """Create an IncidentService instance with the test database."""
    return IncidentService(db_path)


@pytest.fixture
def pupil_wellbeing_service(db_path):
    """Create a PupilWellbeingService instance with the test database."""
    return PupilWellbeingService(db_path)


@pytest.fixture
def portfolio_service(db_path):
    """Create a PortfolioService instance with the test database."""
    return PortfolioService(db_path)


@pytest.fixture
def skills_tracker_service(db_path):
    """Create a SkillsTrackerService instance with the test database."""
    return SkillsTrackerService(db_path)


@pytest.fixture
def sample_staff(hr_service):
    """Create a sample staff member for testing."""
    return hr_service.create_staff(
        first_name="Alice",
        last_name="Teacher",
        email="alice.teacher@school.local",
        role="Teacher",
        department="Year 1",
    )


# ── New module service fixtures ──────────────────────────────────────────


@pytest.fixture
def academic_year_service(db_path):
    return AcademicYearService(db_path)


@pytest.fixture
def assignment_service(db_path):
    return AssignmentService(db_path)


@pytest.fixture
def baseline_assessment_service(db_path):
    return BaselineAssessmentService(db_path)


@pytest.fixture
def markbook_service(db_path):
    return MarkbookService(db_path)


@pytest.fixture
def question_analysis_service(db_path):
    return QuestionAnalysisService(db_path)


@pytest.fixture
def target_setting_service(db_path):
    return TargetSettingService(db_path)


@pytest.fixture
def audit_reports_service(db_path):
    return AuditReportsService(db_path)


@pytest.fixture
def bulk_operations_service(db_path):
    return BulkOperationsService(db_path)


@pytest.fixture
def census_service(db_path):
    return CensusService(db_path)


@pytest.fixture
def compliance_service(db_path):
    return ComplianceService(db_path)


@pytest.fixture
def health_safety_service(db_path):
    return HealthSafetyService(db_path)


@pytest.fixture
def helpdesk_service(db_path):
    return HelpdeskService(db_path)


@pytest.fixture
def letter_templates_service(db_path):
    return LetterTemplatesService(db_path)


@pytest.fixture
def multi_language_service(db_path):
    return MultiLanguageService(db_path)


@pytest.fixture
def onboarding_service(db_path):
    return OnboardingService(db_path)


@pytest.fixture
def prevent_duty_service(db_path):
    return PreventDutyService(db_path)


@pytest.fixture
def quality_assurance_service(db_path):
    return QualityAssuranceService(db_path)


@pytest.fixture
def risk_management_service(db_path):
    return RiskManagementService(db_path)


@pytest.fixture
def self_assessment_service(db_path):
    return SelfAssessmentService(db_path)


@pytest.fixture
def todo_service(db_path):
    return TodoService(db_path)


@pytest.fixture
def activity_feed_service(db_path):
    return ActivityFeedService(db_path)


@pytest.fixture
def messaging_service(db_path):
    return MessagingService(db_path)


@pytest.fixture
def sms_email_service(db_path):
    return SmsEmailService(db_path)


@pytest.fixture
def surveys_service(db_path):
    return SurveysService(db_path)


@pytest.fixture
def departments_service(db_path):
    return DepartmentsService(db_path)


@pytest.fixture
def emergency_service(db_path):
    return EmergencyService(db_path)


@pytest.fixture
def lettings_service(db_path):
    return LettingsService(db_path)


@pytest.fixture
def resource_booking_service(db_path):
    return ResourceBookingService(db_path)


@pytest.fixture
def absence_requests_service(db_path):
    return AbsenceRequestsService(db_path)


@pytest.fixture
def accessibility_service(db_path):
    return AccessibilityService(db_path)


@pytest.fixture
def early_warning_service(db_path):
    return EarlyWarningService(db_path)


@pytest.fixture
def equality_diversity_service(db_path):
    return EqualityDiversityService(db_path)


@pytest.fixture
def ilp_service(db_path):
    return IlpService(db_path)


@pytest.fixture
def peer_mentoring_service(db_path):
    return PeerMentoringService(db_path)


@pytest.fixture
def pupil_support_service(db_path):
    return PupilSupportService(db_path)


@pytest.fixture
def dbs_checks_service(db_path):
    return DbsChecksService(db_path)


@pytest.fixture
def first_aid_service(db_path):
    return FirstAidService(db_path)


@pytest.fixture
def recruitment_service(db_path):
    return RecruitmentService(db_path)


@pytest.fixture
def staff_absence_service(db_path):
    return StaffAbsenceService(db_path)


@pytest.fixture
def document_hub_service(db_path):
    return DocumentHubService(db_path)


@pytest.fixture
def kpi_dashboard_service(db_path):
    return KpiDashboardService(db_path)


@pytest.fixture
def mobile_dashboard_service(db_path):
    return MobileDashboardService(db_path)


@pytest.fixture
def parent_portal_service(db_path):
    return ParentPortalService(db_path)


@pytest.fixture
def progress_dashboard_service(db_path):
    return ProgressDashboardService(db_path)


@pytest.fixture
def pupil_portal_service(db_path):
    return PupilPortalService(db_path)
