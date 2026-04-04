"""Tests for TargetSettingService."""

import pytest


class TestTargetSettingService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.target_setting.services.target_setting_service import TargetSettingService
        return TargetSettingService(db_path)

    def test_import_prior_attainment(self, service):
        result = service.import_prior_attainment(
            student_id=1, qualification_type="gcse",
            subject="Mathematics", grade="7", points=7,
            academic_year="2025/26",
        )
        assert result is not None

    def test_get_student_prior_attainment(self, service):
        service.import_prior_attainment(
            student_id=1, qualification_type="gcse",
            subject="English", grade="6", points=6,
            academic_year="2025/26",
        )
        attainment = service.get_student_prior_attainment(student_id=1)
        assert isinstance(attainment, list)
        assert len(attainment) >= 1

    def test_calculate_average_points(self, service):
        service.import_prior_attainment(
            student_id=1, qualification_type="gcse",
            subject="Maths", grade="8", points=8,
            academic_year="2025/26",
        )
        service.import_prior_attainment(
            student_id=1, qualification_type="gcse",
            subject="English", grade="6", points=6,
            academic_year="2025/26",
        )
        avg = service.calculate_average_points(student_id=1)
        assert avg is not None

    def test_generate_targets(self, service):
        service.import_prior_attainment(
            student_id=1, qualification_type="gcse",
            subject="Maths", grade="7", points=7,
            academic_year="2025/26",
        )
        target = service.generate_targets(
            student_id=1, course_id=1,
            academic_year="2025/26", method="alps",
        )
        assert target is not None

    def test_get_targets(self, service):
        service.import_prior_attainment(
            student_id=1, qualification_type="gcse",
            subject="Maths", grade="7", points=7,
            academic_year="2025/26",
        )
        service.generate_targets(
            student_id=1, course_id=1,
            academic_year="2025/26",
        )
        targets = service.get_targets(student_id=1)
        assert isinstance(targets, list)

    def test_set_benchmark(self, service):
        result = service.set_benchmark(
            qualification_type="gcse",
            prior_points_min=6.0, prior_points_max=7.0,
            subject_group="STEM", meg_grade="B",
            target_grade="A", aspirational_grade="A*",
            academic_year="2025/26",
        )
        assert result is not None

    def test_list_benchmarks(self, service):
        service.set_benchmark(
            qualification_type="gcse",
            prior_points_min=5.0, prior_points_max=6.0,
            subject_group="Arts", meg_grade="C",
            target_grade="B", aspirational_grade="A",
            academic_year="2025/26",
        )
        benchmarks = service.list_benchmarks()
        assert isinstance(benchmarks, list)
        assert len(benchmarks) >= 1
