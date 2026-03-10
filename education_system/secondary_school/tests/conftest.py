"""Shared test fixtures for the Secondary School Management System."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from education_system.secondary_school.infrastructure.database.db import set_db_path
from education_system.secondary_school.infrastructure.database.schema import initialise_database, seed_default_users
from education_system.secondary_school.infrastructure.auth.core import UserAuth
from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
from education_system.secondary_school.modules.domain.academics.subjects.services.subject_service import SubjectService
from education_system.secondary_school.modules.domain.academics.enrollment.services.enrollment_service import EnrollmentService
from education_system.secondary_school.modules.domain.academics.grades.services.grade_service import GradeService
from education_system.secondary_school.modules.domain.academics.attendance.services.attendance_service import AttendanceService
from education_system.secondary_school.modules.domain.pastoral_care.behaviour.services.behaviour_service import BehaviourService
from education_system.shared.auth.schema import initialise_auth_db, seed_default_users as seed_auth_users


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database for each test."""
    path = str(tmp_path / "test_secondary.db")
    set_db_path(path)
    initialise_database(path)
    seed_default_users(path)
    yield path
    set_db_path(None)


@pytest.fixture
def auth_db_path(tmp_path):
    """Create a temporary shared auth database for each test."""
    path = str(tmp_path / "test_auth.db")
    initialise_auth_db(path)
    seed_auth_users(path)
    return path


@pytest.fixture
def auth(auth_db_path):
    """Create a UserAuth instance with the test auth database."""
    return UserAuth(auth_db_path)


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
    from education_system.secondary_school.api.api_server import create_app
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
