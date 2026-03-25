"""Shared test fixtures for the Sixth Form College Management System."""

import os
import sys

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
from education_system.college_system.infrastructure.auth.mfa_service import MFAService
from education_system.shared.testing.conftest_helpers import (
    make_template_db_fixture,
    make_template_auth_db_fixture,
    make_db_path_fixture,
    make_auth_db_path_fixture,
    make_auth_fixture,
)

# ── Template and per-test DB fixtures (shared boilerplate) ───────────────
_template_db = make_template_db_fixture(init_db, seed_default_data)
_template_auth_db = make_template_auth_db_fixture()
db_path = make_db_path_fixture(set_db_path, "test_sixthform.db")
auth_db_path = make_auth_db_path_fixture()
auth = make_auth_fixture(UserAuth)


# ── Service fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def student_service(db_path):
    return StudentService(db_path)


@pytest.fixture
def course_service(db_path):
    return CourseService(db_path)


@pytest.fixture
def enrollment_service(db_path):
    return EnrollmentService(db_path)


@pytest.fixture
def grade_service(db_path):
    return GradeService(db_path)


@pytest.fixture
def sample_student(student_service):
    return student_service.create_student(
        first_name="John", last_name="Doe",
        email="john.doe@sixthform.ac.uk",
        year_group="12", form_group="12A",
    )


@pytest.fixture
def sample_course(course_service):
    return course_service.create_course(
        course_code="TEST101", title="Intro to Computer Science",
        guided_learning_hours=3, capacity=30, subject_area="Computer Science",
    )


@pytest.fixture
def api_client(db_path, auth_db_path):
    from education_system.shared.api.college.api_server import create_app
    from education_system.shared.api import auth as shared_auth_module
    from education_system.shared.api.college.routes import auth_routes as college_auth_routes
    shared_auth_module._rate_store.clear()
    shared_auth_module._username_rate_store.clear()
    college_auth_routes._rate_limit_store.clear()
    app = create_app(db_path, auth_db_path=auth_db_path)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def api_token(api_client):
    response = api_client.post("/api/auth/login", json={
        "username": "admin1",
        "password": "admin1234",
    })
    return response.get_json()["token"]


@pytest.fixture
def auth_headers(api_token):
    return {"Authorization": f"Bearer {api_token}"}


@pytest.fixture
def mfa_service(auth_db_path):
    return MFAService(auth_db_path)
