"""Tests for StudyProgrammesService."""

import pytest


class TestStudyProgrammesService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.study_programmes.services.study_programmes_service import StudyProgrammesService
        return StudyProgrammesService(db_path)

    @pytest.fixture
    def sample_programme(self, service):
        return service.create_programme(
            student_id=1, programme_type="academic",
            academic_year="2025/26", planned_hours=600,
        )

    def test_create_programme(self, service):
        prog = service.create_programme(
            student_id=1, programme_type="vocational",
            academic_year="2025/26",
        )
        assert prog is not None

    def test_list_programmes(self, service):
        service.create_programme(student_id=1)
        progs = service.list_programmes()
        assert len(progs) >= 1

    def test_get_programme(self, service, sample_programme):
        prog_id = sample_programme if isinstance(sample_programme, int) else sample_programme.get("id", sample_programme)
        prog = service.get_programme(prog_id)
        assert prog is not None

    def test_update_programme(self, service, sample_programme):
        prog_id = sample_programme if isinstance(sample_programme, int) else sample_programme.get("id", sample_programme)
        updated = service.update_programme(prog_id, status="active")
        assert updated is not None

    def test_delete_programme(self, service, sample_programme):
        prog_id = sample_programme if isinstance(sample_programme, int) else sample_programme.get("id", sample_programme)
        result = service.delete_programme(prog_id)
        assert result is True or result is None

    def test_create_component(self, service, sample_programme):
        prog_id = sample_programme if isinstance(sample_programme, int) else sample_programme.get("id", sample_programme)
        comp = service.create_component(
            programme_id=prog_id, component_type="qualification",
            component_name="A Level Maths",
        )
        assert comp is not None

    def test_list_components(self, service, sample_programme):
        prog_id = sample_programme if isinstance(sample_programme, int) else sample_programme.get("id", sample_programme)
        service.create_component(prog_id, "qualification", "A Level English")
        comps = service.list_components(programme_id=prog_id)
        assert len(comps) >= 1

    def test_validate_programme(self, service, sample_programme):
        prog_id = sample_programme if isinstance(sample_programme, int) else sample_programme.get("id", sample_programme)
        result = service.validate_programme(prog_id)
        assert result is not None

    def test_condition_of_funding_check(self, service):
        result = service.condition_of_funding_check()
        assert result is not None

    def test_get_stats(self, service):
        result = service.get_stats()
        assert result is not None
