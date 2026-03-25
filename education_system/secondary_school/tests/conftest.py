"""Shared test fixtures for the Secondary School Management System."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from education_system.secondary_school.infrastructure.database.db import set_db_path
from education_system.secondary_school.infrastructure.database.schema import initialise_database, seed_default_users, seed_default_staff
from education_system.secondary_school.infrastructure.auth.core import UserAuth
from education_system.shared.testing.conftest_helpers import (
    make_template_db_fixture,
    make_template_auth_db_fixture,
    make_db_path_fixture,
    make_auth_db_path_fixture,
    make_auth_fixture,
)
from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
from education_system.secondary_school.modules.domain.academics.subjects.services.subject_service import SubjectService
from education_system.secondary_school.modules.domain.academics.enrollment.services.enrollment_service import EnrollmentService
from education_system.secondary_school.modules.domain.academics.grades.services.grade_service import GradeService
from education_system.secondary_school.modules.domain.academics.attendance.services.attendance_service import AttendanceService
from education_system.secondary_school.modules.domain.pastoral_care.behaviour.services.behaviour_service import BehaviourService
from education_system.secondary_school.modules.domain.academics.exams.services.exam_service import ExamService
from education_system.secondary_school.modules.domain.academics.homework.services.homework_service import HomeworkService
from education_system.secondary_school.modules.domain.academics.timetable.services.timetable_service import TimetableService
from education_system.secondary_school.modules.domain.academics.progress.services.progress_service import ProgressService
from education_system.secondary_school.modules.domain.academics.interventions.services.intervention_service import InterventionService
from education_system.secondary_school.modules.domain.academics.reports.services.report_service import ReportService
from education_system.secondary_school.modules.domain.staff.hr.services.hr_service import HRService
from education_system.secondary_school.modules.domain.staff.cpd.services.cpd_service import CPDService
from education_system.secondary_school.modules.domain.staff.cover.services.cover_service import CoverService
from education_system.secondary_school.modules.domain.staff.staff_directory.services.staff_directory_service import StaffDirectoryService
from education_system.secondary_school.modules.domain.pastoral_care.detentions.services.detention_service import DetentionService
from education_system.secondary_school.modules.domain.pastoral_care.exclusions.services.exclusion_service import ExclusionService
from education_system.secondary_school.modules.domain.pastoral_care.rewards.services.rewards_service import RewardsService
from education_system.secondary_school.modules.domain.pastoral_care.pastoral.services.pastoral_service import PastoralService
from education_system.secondary_school.modules.domain.pastoral_care.safeguarding.services.safeguarding_service import SafeguardingService
from education_system.secondary_school.modules.domain.pastoral_care.send.services.send_service import SENDService
from education_system.secondary_school.modules.domain.admin.admissions.services.admissions_service import AdmissionsService
from education_system.secondary_school.modules.domain.admin.audit_log.services.audit_service import AuditService
from education_system.secondary_school.modules.domain.admin.documents.services.document_service import DocumentService
from education_system.secondary_school.modules.domain.admin.finance.services.finance_service import FinanceService
from education_system.secondary_school.modules.domain.admin.policies.services.policy_service import PolicyService
from education_system.secondary_school.modules.domain.admin.users.services.user_service import UserService
from education_system.secondary_school.modules.domain.admin.settings.services.settings_service import SettingsService
from education_system.secondary_school.modules.domain.communication.announcements.services.announcement_service import AnnouncementService
from education_system.secondary_school.modules.domain.communication.calendar.services.calendar_service import CalendarService
from education_system.secondary_school.modules.domain.communication.email.services.email_service import EmailService
from education_system.secondary_school.modules.domain.communication.notifications.services.notification_service import NotificationService
from education_system.secondary_school.modules.domain.communication.parents_evening.services.parents_evening_service import ParentsEveningService
from education_system.secondary_school.modules.domain.communication.communication_log.services.comms_service import CommsService
from education_system.secondary_school.modules.domain.facilities.assets.services.asset_service import AssetService
from education_system.secondary_school.modules.domain.facilities.incidents.services.incident_service import IncidentService
from education_system.secondary_school.modules.domain.facilities.room_booking.services.room_booking_service import RoomBookingService
from education_system.secondary_school.modules.domain.facilities.seating_plans.services.seating_service import SeatingService
from education_system.secondary_school.modules.domain.facilities.visitors.services.visitor_service import VisitorService
from education_system.secondary_school.modules.domain.student_life.clubs.services.clubs_service import ClubsService
from education_system.secondary_school.modules.domain.student_life.library.services.library_service import LibraryService
from education_system.secondary_school.modules.domain.student_life.transport.services.transport_service import TransportService
from education_system.secondary_school.modules.domain.student_life.medical.services.medical_service import MedicalService

# ── Template and per-test DB fixtures (shared boilerplate) ───────────────
_template_db = make_template_db_fixture(initialise_database, seed_default_users, seed_default_staff)
_template_auth_db = make_template_auth_db_fixture()
db_path = make_db_path_fixture(set_db_path, "test_secondary.db")
auth_db_path = make_auth_db_path_fixture()
auth = make_auth_fixture(UserAuth)


# ── Service fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def student_service(db_path):
    """Create a StudentService instance with the test database."""
    return StudentService(db_path)


@pytest.fixture
def subject_service(db_path):
    """Create a SubjectService instance with the test database."""
    return SubjectService(db_path)


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
def behaviour_service(db_path):
    """Create a BehaviourService instance with the test database."""
    return BehaviourService(db_path)


@pytest.fixture
def sample_student(student_service):
    """Create a sample student for testing."""
    return student_service.create_student(
        first_name="John", last_name="Doe",
        email="john.doe@school.local",
        year_group="9", form_group="9A",
    )


@pytest.fixture
def sample_student_ks4(student_service):
    """Create a sample KS4 student for testing."""
    return student_service.create_student(
        first_name="Jane", last_name="Smith",
        email="jane.smith@school.local",
        year_group="10", form_group="10B",
    )


@pytest.fixture
def sample_subject(subject_service):
    """Create a sample subject for testing."""
    return subject_service.create_subject(
        subject_code="MAT01", title="Mathematics",
        department="Maths", key_stage="KS3",
        is_core=True, capacity=30,
    )


@pytest.fixture
def sample_subject_science(subject_service):
    """Create a second sample subject for testing."""
    return subject_service.create_subject(
        subject_code="SCI01", title="Combined Science",
        department="Science", key_stage="KS4",
        is_core=True, capacity=25,
    )


@pytest.fixture
def enrolled_student(sample_student, sample_subject, enrollment_service):
    """Create a student enrolled in a subject."""
    enrollment_service.enroll_student(sample_student["id"], sample_subject["id"])
    return sample_student


@pytest.fixture
def enrolled_student_multi(sample_student, sample_subject, sample_subject_science, enrollment_service):
    """Create a student enrolled in two subjects."""
    enrollment_service.enroll_student(sample_student["id"], sample_subject["id"])
    enrollment_service.enroll_student(sample_student["id"], sample_subject_science["id"])
    return sample_student


@pytest.fixture
def api_client(db_path, auth_db_path):
    """Create a Flask test client."""
    from education_system.shared.api.secondary.api_server import create_app
    from education_system.shared.api import auth as shared_auth_module
    # Clear rate limit stores so tests don't interfere with each other
    shared_auth_module._rate_store.clear()
    shared_auth_module._username_rate_store.clear()
    app = create_app(db_path, auth_db_path=auth_db_path)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def api_token(api_client):
    """Get a JWT token by logging in as school admin."""
    response = api_client.post("/api/auth/login", json={
        "username": "admin2",
        "password": "admin1234",
    })
    return response.get_json()["token"]


@pytest.fixture
def auth_headers(api_token):
    """Authorization headers with JWT token."""
    return {"Authorization": f"Bearer {api_token}"}


@pytest.fixture
def detention_service(db_path):
    """Create a DetentionService instance with the test database."""
    return DetentionService(db_path)


@pytest.fixture
def exclusion_service(db_path):
    """Create an ExclusionService instance with the test database."""
    return ExclusionService(db_path)


@pytest.fixture
def rewards_service(db_path):
    """Create a RewardsService instance with the test database."""
    return RewardsService(db_path)


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
def exam_service(db_path):
    """Create an ExamService instance with the test database."""
    return ExamService(db_path)


@pytest.fixture
def homework_service(db_path):
    """Create a HomeworkService instance with the test database."""
    return HomeworkService(db_path)


@pytest.fixture
def timetable_service(db_path):
    """Create a TimetableService instance with the test database."""
    return TimetableService(db_path)


@pytest.fixture
def progress_service(db_path):
    """Create a ProgressService instance with the test database."""
    return ProgressService(db_path)


@pytest.fixture
def intervention_service(db_path):
    """Create an InterventionService instance with the test database."""
    return InterventionService(db_path)


@pytest.fixture
def report_service(db_path):
    """Create a ReportService instance with the test database."""
    return ReportService(db_path)


@pytest.fixture
def sample_exam(exam_service, sample_subject):
    """Create a sample exam for testing."""
    return exam_service.create_exam(
        subject_id=sample_subject["id"],
        title="End of Term Maths",
        exam_type="end_of_term",
        year_group="9",
        date="2025-12-15",
        start_time="09:00",
        duration_minutes=90,
        room="Hall A",
        total_marks=100,
    )


@pytest.fixture
def sample_homework(homework_service, sample_subject):
    """Create a sample homework for testing."""
    return homework_service.create_homework(
        subject_id=sample_subject["id"],
        title="Algebra Practice",
        due_date="2025-12-20",
        year_group="9",
        description="Complete exercises 1-10",
        max_marks=50,
    )


@pytest.fixture
def sample_staff(hr_service):
    """Create a sample staff member for testing."""
    return hr_service.create_staff(
        first_name="Alice",
        last_name="Teacher",
        email="alice.teacher@school.local",
        department="Maths",
        job_title="Teacher",
        contract_type="permanent",
    )


# ── Admin service fixtures ──


@pytest.fixture
def admissions_service(db_path):
    """Create an AdmissionsService instance with the test database."""
    return AdmissionsService(db_path)


@pytest.fixture
def audit_service(db_path):
    """Create an AuditService instance with the test database."""
    return AuditService(db_path)


@pytest.fixture
def document_service(db_path):
    """Create a DocumentService instance with the test database."""
    return DocumentService(db_path)


@pytest.fixture
def finance_service(db_path):
    """Create a FinanceService instance with the test database."""
    return FinanceService(db_path)


@pytest.fixture
def policy_service(db_path):
    """Create a PolicyService instance with the test database."""
    return PolicyService(db_path)


@pytest.fixture
def user_service(db_path):
    """Create a UserService instance with the test database."""
    return UserService(db_path)


@pytest.fixture
def settings_service(db_path):
    """Create a SettingsService instance with the test database."""
    return SettingsService(db_path)


# ── Communication service fixtures ──


@pytest.fixture
def announcement_service(db_path):
    """Create an AnnouncementService instance with the test database."""
    return AnnouncementService(db_path)


@pytest.fixture
def calendar_service(db_path):
    """Create a CalendarService instance with the test database."""
    return CalendarService(db_path)


@pytest.fixture
def email_service(db_path):
    """Create an EmailService instance with the test database."""
    return EmailService(db_path)


@pytest.fixture
def notification_service(db_path):
    """Create a NotificationService instance with the test database."""
    return NotificationService(db_path)


@pytest.fixture
def parents_evening_service(db_path):
    """Create a ParentsEveningService instance with the test database."""
    return ParentsEveningService(db_path)


@pytest.fixture
def comms_service(db_path):
    """Create a CommsService instance with the test database."""
    return CommsService(db_path)


# ── Facilities service fixtures ──


@pytest.fixture
def asset_service(db_path):
    """Create an AssetService instance with the test database."""
    return AssetService(db_path)


@pytest.fixture
def incident_service(db_path):
    """Create an IncidentService instance with the test database."""
    return IncidentService(db_path)


@pytest.fixture
def room_booking_service(db_path):
    """Create a RoomBookingService instance with the test database."""
    return RoomBookingService(db_path)


@pytest.fixture
def seating_service(db_path):
    """Create a SeatingService instance with the test database."""
    return SeatingService(db_path)


@pytest.fixture
def visitor_service(db_path):
    """Create a VisitorService instance with the test database."""
    return VisitorService(db_path)


# ── Student Life service fixtures ──


@pytest.fixture
def clubs_service(db_path):
    """Create a ClubsService instance with the test database."""
    return ClubsService(db_path)


@pytest.fixture
def library_service(db_path):
    """Create a LibraryService instance with the test database."""
    return LibraryService(db_path)


@pytest.fixture
def transport_service(db_path):
    """Create a TransportService instance with the test database."""
    return TransportService(db_path)


@pytest.fixture
def medical_service(db_path):
    """Create a MedicalService instance with the test database."""
    return MedicalService(db_path)
