"""Tests for AdmissionsService."""

import pytest
from education_system.college_system.core.exceptions import AdmissionsError


class TestAdmissionsService:
    @pytest.fixture
    def admissions_service(self, db_path):
        from education_system.college_system.modules.domain.admissions.services.admissions_service import AdmissionsService
        return AdmissionsService(db_path)

    def test_create_application(self, admissions_service):
        app = admissions_service.create_application(
            applicant_name="Jane Doe",
            date_of_birth="2009-05-15",
            email="jane@example.com",
            course_preferences="A-Level Maths",
        )
        assert app["applicant_name"] == "Jane Doe"
        assert app["status"] == "enquiry"

    def test_list_applications(self, admissions_service):
        admissions_service.create_application(
            applicant_name="App One", date_of_birth="2009-01-01",
        )
        admissions_service.create_application(
            applicant_name="App Two", date_of_birth="2009-02-02",
        )
        apps = admissions_service.list_applications()
        assert len(apps) >= 2

    def test_list_applications_filter_status(self, admissions_service):
        admissions_service.create_application(
            applicant_name="Enquiry App", date_of_birth="2009-01-01",
        )
        enquiry = admissions_service.list_applications(status="enquiry")
        assert all(a["status"] == "enquiry" for a in enquiry)

    def test_get_application(self, admissions_service):
        created = admissions_service.create_application(
            applicant_name="Get Me", date_of_birth="2009-03-03",
        )
        found = admissions_service.get_application(created["id"])
        assert found["applicant_name"] == "Get Me"

    def test_update_application_status(self, admissions_service):
        app = admissions_service.create_application(
            applicant_name="Status Test", date_of_birth="2009-04-04",
        )
        updated = admissions_service.update_application_status(
            app["id"], status="accepted", notes="Strong application",
        )
        assert updated["status"] == "accepted"
