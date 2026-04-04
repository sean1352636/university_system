"""Tests for UCASService."""

import pytest


class TestUCASService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.ucas.services.ucas_service import UCASService
        return UCASService(db_path)

    @pytest.fixture
    def sample_application(self, service):
        return service.create_application(
            student_id=1, academic_year="2025/26",
            ucas_id="UC123456",
        )

    def test_create_application(self, service):
        app = service.create_application(
            student_id=1, academic_year="2025/26",
        )
        assert app is not None

    def test_list_applications(self, service):
        service.create_application(student_id=1)
        apps = service.list_applications()
        assert len(apps) >= 1

    def test_get_application(self, service, sample_application):
        aid = sample_application if isinstance(sample_application, int) else sample_application.get("id", sample_application)
        found = service.get_application(aid)
        assert found is not None

    def test_update_application(self, service, sample_application):
        aid = sample_application if isinstance(sample_application, int) else sample_application.get("id", sample_application)
        updated = service.update_application(aid, notes="Personal statement reviewed")
        assert updated is not None

    def test_submit_application(self, service, sample_application):
        aid = sample_application if isinstance(sample_application, int) else sample_application.get("id", sample_application)
        result = service.submit_application(aid)
        assert result is not None

    def test_add_choice(self, service, sample_application):
        aid = sample_application if isinstance(sample_application, int) else sample_application.get("id", sample_application)
        choice = service.add_choice(
            application_id=aid,
            university_name="University of Oxford",
            course_title="Computer Science",
            ucas_code="G400",
        )
        assert choice is not None

    def test_list_choices(self, service, sample_application):
        aid = sample_application if isinstance(sample_application, int) else sample_application.get("id", sample_application)
        service.add_choice(aid, "Uni A", "Course A")
        service.add_choice(aid, "Uni B", "Course B")
        choices = service.list_choices(aid)
        assert len(choices) >= 2

    def test_get_statistics(self, service):
        stats = service.get_statistics()
        assert stats is not None
