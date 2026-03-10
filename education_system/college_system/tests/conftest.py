"""Shared test fixtures for the Sixth Form College Management System."""

import os
import sys
import tempfile

import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from education_system.college_system.infrastructure.database.db import set_db_path
from education_system.college_system.infrastructure.database.schema import init_db, seed_default_data
from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.modules.domain.students.services.student_service import StudentService
from education_system.college_system.modules.domain.courses.services.course_service import CourseService
from education_system.college_system.modules.domain.enrollment.services.enrollment_service import EnrollmentService
from education_system.college_system.modules.domain.grades.services.grade_service import GradeService
from education_system.college_system.modules.domain.attendance.services.attendance_service import AttendanceService
from education_system.college_system.modules.domain.timetable.services.timetable_service import TimetableService
from education_system.college_system.modules.domain.assignments.services.assignment_service import AssignmentService
from education_system.college_system.modules.domain.notifications.services.notification_service import NotificationService
from education_system.college_system.infrastructure.auth.mfa_service import MFAService


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database for each test."""
    path = str(tmp_path / "test_sixthform.db")
    set_db_path(path)
    init_db(path)
    seed_default_data(path)
    yield path
    set_db_path(None)


@pytest.fixture
def auth(db_path):
    """Create a UserAuth instance with the test database."""
    return UserAuth(db_path)


@pytest.fixture
def student_service(db_path):
    """Create a StudentService instance with the test database."""
    return StudentService(db_path)


@pytest.fixture
def course_service(db_path):
    """Create a CourseService instance with the test database."""
    return CourseService(db_path)


@pytest.fixture
def enrollment_service(db_path):
    """Create an EnrollmentService instance with the test database."""
    return EnrollmentService(db_path)


@pytest.fixture
def grade_service(db_path):
    """Create a GradeService instance with the test database."""
    return GradeService(db_path)


@pytest.fixture
def attendance_service(db_path):
    """Create an AttendanceService instance with the test database."""
    return AttendanceService(db_path)


@pytest.fixture
def sample_student(student_service):
    """Create a sample student for testing."""
    return student_service.create_student(
        first_name="John", last_name="Doe",
        email="john.doe@sixthform.ac.uk",
        year_group="12", form_group="12A",
    )


@pytest.fixture
def sample_course(course_service):
    """Create a sample course for testing."""
    return course_service.create_course(
        course_code="TEST101", title="Intro to Computer Science",
        guided_learning_hours=3, capacity=30, subject_area="Computer Science",
    )


@pytest.fixture
def api_client(db_path):
    """Create a Flask test client."""
    from education_system.college_system.api.api_server import create_app
    app = create_app(db_path)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def api_token(api_client):
    """Get a JWT token by logging in as admin."""
    response = api_client.post("/api/auth/login", json={
        "username": "admin",
        "password": "Admin@123",
    })
    return response.get_json()["token"]


@pytest.fixture
def auth_headers(api_token):
    """Authorization headers with JWT token."""
    return {"Authorization": f"Bearer {api_token}"}


@pytest.fixture
def timetable_service(db_path):
    """Create a TimetableService instance with the test database."""
    return TimetableService(db_path)


@pytest.fixture
def assignment_service(db_path):
    """Create an AssignmentService instance with the test database."""
    return AssignmentService(db_path)


@pytest.fixture
def notification_service(db_path):
    """Create a NotificationService instance with the test database."""
    return NotificationService(db_path)


@pytest.fixture
def mfa_service(db_path):
    """Create an MFAService instance with the test database."""
    return MFAService(db_path)


@pytest.fixture
def department_service(db_path):
    """Create a DepartmentService instance with the test database."""
    from education_system.college_system.modules.domain.departments.services.department_service import DepartmentService
    return DepartmentService(db_path)


@pytest.fixture
def group_service(db_path):
    """Create a GroupService instance with the test database."""
    from education_system.college_system.modules.domain.departments.services.department_service import GroupService
    return GroupService(db_path)


@pytest.fixture
def finance_service(db_path):
    """Create a FinanceService instance with the test database."""
    from education_system.college_system.modules.domain.finance.services.finance_service import FinanceService
    return FinanceService(db_path)


@pytest.fixture
def student_support_service(db_path):
    """Create a StudentSupportService instance with the test database."""
    from education_system.college_system.modules.domain.student_support.services.student_support_service import StudentSupportService
    return StudentSupportService(db_path)


@pytest.fixture
def funding_service(db_path):
    """Create a FundingService instance with the test database."""
    from education_system.college_system.modules.domain.funding.services.funding_service import FundingService
    return FundingService(db_path)


@pytest.fixture
def destination_service(db_path):
    """Create a DestinationService instance with the test database."""
    from education_system.college_system.modules.domain.destinations.services.destination_service import DestinationService
    return DestinationService(db_path)


@pytest.fixture
def room_service(db_path):
    """Create a RoomService instance with the test database."""
    from education_system.college_system.modules.domain.timetable.services.room_service import RoomService
    return RoomService(db_path)


# ---- New feature module fixtures ----

@pytest.fixture
def cpd_service(db_path):
    """Create a CPDService instance."""
    from education_system.college_system.modules.domain.cpd.services.cpd_service import CPDService
    return CPDService(db_path)


@pytest.fixture
def observations_service(db_path):
    """Create an ObservationService instance."""
    from education_system.college_system.modules.domain.observations.services.observations_service import ObservationService
    return ObservationService(db_path)


@pytest.fixture
def appraisals_service(db_path):
    """Create an AppraisalService instance."""
    from education_system.college_system.modules.domain.appraisals.services.appraisals_service import AppraisalService
    return AppraisalService(db_path)


@pytest.fixture
def resource_booking_service(db_path):
    """Create a ResourceBookingService instance."""
    from education_system.college_system.modules.domain.resource_booking.services.resource_booking_service import ResourceBookingService
    return ResourceBookingService(db_path)


@pytest.fixture
def markbook_service(db_path):
    """Create a MarkbookService instance."""
    from education_system.college_system.modules.domain.markbook.services.markbook_service import MarkbookService
    return MarkbookService(db_path)


@pytest.fixture
def staff_wellbeing_service(db_path):
    """Create a StaffWellbeingService instance."""
    from education_system.college_system.modules.domain.staff_wellbeing.services.staff_wellbeing_service import StaffWellbeingService
    return StaffWellbeingService(db_path)


@pytest.fixture
def lesson_plans_service(db_path):
    """Create a LessonPlanService instance."""
    from education_system.college_system.modules.domain.lesson_plans.services.lesson_plans_service import LessonPlanService
    return LessonPlanService(db_path)


@pytest.fixture
def data_dashboard_service(db_path):
    """Create a DataDashboardService instance."""
    from education_system.college_system.modules.domain.data_dashboard.services.data_dashboard_service import DataDashboardService
    return DataDashboardService(db_path)


@pytest.fixture
def absence_requests_service(db_path):
    """Create an AbsenceRequestService instance."""
    from education_system.college_system.modules.domain.absence_requests.services.absence_requests_service import AbsenceRequestService
    return AbsenceRequestService(db_path)


@pytest.fixture
def intervention_tracking_service(db_path):
    """Create an InterventionService instance."""
    from education_system.college_system.modules.domain.intervention_tracking.services.intervention_tracking_service import InterventionService
    return InterventionService(db_path)


@pytest.fixture
def visitors_service(db_path):
    """Create a VisitorService instance."""
    from education_system.college_system.modules.domain.visitors.services.visitors_service import VisitorService
    return VisitorService(db_path)


@pytest.fixture
def policies_service(db_path):
    """Create a PolicyService instance."""
    from education_system.college_system.modules.domain.policies.services.policies_service import PolicyService
    return PolicyService(db_path)


@pytest.fixture
def gdpr_service(db_path):
    """Create a GDPRService instance."""
    from education_system.college_system.modules.domain.gdpr.services.gdpr_service import GDPRService
    return GDPRService(db_path)


@pytest.fixture
def quality_assurance_service(db_path):
    """Create a QualityAssuranceService instance."""
    from education_system.college_system.modules.domain.quality_assurance.services.quality_assurance_service import QualityAssuranceService
    return QualityAssuranceService(db_path)


@pytest.fixture
def bulk_operations_service(db_path):
    """Create a BulkOperationService instance."""
    from education_system.college_system.modules.domain.bulk_operations.services.bulk_operations_service import BulkOperationService
    return BulkOperationService(db_path)


@pytest.fixture
def emergency_service(db_path):
    """Create an EmergencyService instance."""
    from education_system.college_system.modules.domain.emergency.services.emergency_service import EmergencyService
    return EmergencyService(db_path)


@pytest.fixture
def academic_year_service(db_path):
    """Create an AcademicYearService instance."""
    from education_system.college_system.modules.domain.academic_year.services.academic_year_service import AcademicYearService
    return AcademicYearService(db_path)


@pytest.fixture
def kpi_dashboard_service(db_path):
    """Create a KPIDashboardService instance."""
    from education_system.college_system.modules.domain.kpi_dashboard.services.kpi_dashboard_service import KPIDashboardService
    return KPIDashboardService(db_path)


@pytest.fixture
def audit_reports_service(db_path):
    """Create an AuditReportService instance."""
    from education_system.college_system.modules.domain.audit_reports.services.audit_reports_service import AuditReportService
    return AuditReportService(db_path)


@pytest.fixture
def user_management_service(db_path):
    """Create a UserManagementService instance."""
    from education_system.college_system.modules.domain.user_management.services.user_management_service import UserManagementService
    return UserManagementService(db_path)


@pytest.fixture
def portfolio_service(db_path):
    """Create a PortfolioService instance."""
    from education_system.college_system.modules.domain.portfolio.services.portfolio_service import PortfolioService
    return PortfolioService(db_path)


@pytest.fixture
def study_planner_service(db_path):
    """Create a StudyPlannerService instance."""
    from education_system.college_system.modules.domain.study_planner.services.study_planner_service import StudyPlannerService
    return StudyPlannerService(db_path)


@pytest.fixture
def enrichment_service(db_path):
    """Create an EnrichmentService instance."""
    from education_system.college_system.modules.domain.enrichment.services.enrichment_service import EnrichmentService
    return EnrichmentService(db_path)


@pytest.fixture
def peer_mentoring_service(db_path):
    """Create a PeerMentoringService instance."""
    from education_system.college_system.modules.domain.peer_mentoring.services.peer_mentoring_service import PeerMentoringService
    return PeerMentoringService(db_path)


@pytest.fixture
def surveys_service(db_path):
    """Create a SurveyService instance."""
    from education_system.college_system.modules.domain.surveys.services.surveys_service import SurveyService
    return SurveyService(db_path)


@pytest.fixture
def skills_passport_service(db_path):
    """Create a SkillsPassportService instance."""
    from education_system.college_system.modules.domain.skills_passport.services.skills_passport_service import SkillsPassportService
    return SkillsPassportService(db_path)


@pytest.fixture
def progress_dashboard_service(db_path):
    """Create a ProgressDashboardService instance."""
    from education_system.college_system.modules.domain.progress_dashboard.services.progress_dashboard_service import ProgressDashboardService
    return ProgressDashboardService(db_path)


@pytest.fixture
def meal_ordering_service(db_path):
    """Create a MealOrderingService instance."""
    from education_system.college_system.modules.domain.meal_ordering.services.meal_ordering_service import MealOrderingService
    return MealOrderingService(db_path)


@pytest.fixture
def print_credits_service(db_path):
    """Create a PrintCreditService instance."""
    from education_system.college_system.modules.domain.print_credits.services.print_credits_service import PrintCreditService
    return PrintCreditService(db_path)


@pytest.fixture
def work_journal_service(db_path):
    """Create a WorkJournalService instance."""
    from education_system.college_system.modules.domain.work_journal.services.work_journal_service import WorkJournalService
    return WorkJournalService(db_path)


@pytest.fixture
def announcements_service(db_path):
    """Create an AnnouncementService instance."""
    from education_system.college_system.modules.domain.announcements.services.announcements_service import AnnouncementService
    return AnnouncementService(db_path)


@pytest.fixture
def document_hub_service(db_path):
    """Create a DocumentHubService instance."""
    from education_system.college_system.modules.domain.document_hub.services.document_hub_service import DocumentHubService
    return DocumentHubService(db_path)


@pytest.fixture
def advanced_search_service(db_path):
    """Create an AdvancedSearchService instance."""
    from education_system.college_system.modules.domain.advanced_search.services.advanced_search_service import AdvancedSearchService
    return AdvancedSearchService(db_path)


@pytest.fixture
def feedback_service(db_path):
    """Create a FeedbackService instance."""
    from education_system.college_system.modules.domain.feedback.services.feedback_service import FeedbackService
    return FeedbackService(db_path)


@pytest.fixture
def accessibility_service(db_path):
    """Create an AccessibilityService instance."""
    from education_system.college_system.modules.domain.accessibility.services.accessibility_service import AccessibilityService
    return AccessibilityService(db_path)


@pytest.fixture
def mobile_dashboard_service(db_path):
    """Create a MobileDashboardService instance."""
    from education_system.college_system.modules.domain.mobile_dashboard.services.mobile_dashboard_service import MobileDashboardService
    return MobileDashboardService(db_path)


@pytest.fixture
def attachments_service(db_path):
    """Create an AttachmentService instance."""
    from education_system.college_system.modules.domain.attachments.services.attachments_service import AttachmentService
    return AttachmentService(db_path)


@pytest.fixture
def activity_feed_service(db_path):
    """Create an ActivityFeedService instance."""
    from education_system.college_system.modules.domain.activity_feed.services.activity_feed_service import ActivityFeedService
    return ActivityFeedService(db_path)


@pytest.fixture
def sms_email_service(db_path):
    """Create a SmsEmailService instance."""
    from education_system.college_system.modules.domain.sms_email.services.sms_email_service import SmsEmailService
    return SmsEmailService(db_path)


@pytest.fixture
def multi_language_service(db_path):
    """Create a MultiLanguageService instance."""
    from education_system.college_system.modules.domain.multi_language.services.multi_language_service import MultiLanguageService
    return MultiLanguageService(db_path)
