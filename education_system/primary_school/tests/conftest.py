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
