"""Tests for ValueAddedService."""

import pytest


class TestValueAddedService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.value_added.services.value_added_service import ValueAddedService
        return ValueAddedService(db_path)

    def test_set_baseline(self, service):
        result = service.set_baseline(
            student_id=1, academic_year="2025/26",
            gcse_average=6.5, gcse_english=6, gcse_maths=7,
        )
        assert result is not None

    def test_get_baseline(self, service):
        service.set_baseline(
            student_id=1, academic_year="2025/26",
            gcse_average=6.5, gcse_english=6, gcse_maths=7,
        )
        baseline = service.get_baseline(student_id=1)
        assert baseline is not None

    def test_set_prediction(self, service):
        service.set_baseline(student_id=1, gcse_average=6.5)
        result = service.set_prediction(
            student_id=1, course_id=1,
            predicted_grade="B", target_grade="A",
            academic_year="2025/26",
        )
        assert result is not None

    def test_list_predictions(self, service):
        service.set_baseline(student_id=1, gcse_average=6.0)
        service.set_prediction(
            student_id=1, course_id=1,
            predicted_grade="C", academic_year="2025/26",
        )
        preds = service.list_predictions(student_id=1)
        assert isinstance(preds, list)
        assert len(preds) >= 1

    def test_update_actual_grade(self, service):
        service.set_baseline(student_id=1, gcse_average=6.0)
        pred = service.set_prediction(
            student_id=1, course_id=1,
            predicted_grade="B", academic_year="2025/26",
        )
        pred_id = pred if isinstance(pred, int) else pred.get("id", pred)
        result = service.update_actual_grade(pred_id, actual_grade="A")
        assert result is not None

    def test_get_subject_value_added(self, service):
        service.set_baseline(student_id=1, gcse_average=6.0)
        service.set_prediction(
            student_id=1, course_id=1,
            predicted_grade="B", academic_year="2025/26",
        )
        va = service.get_subject_value_added(course_id=1, academic_year="2025/26")
        assert va is not None

    def test_get_college_value_added(self, service):
        result = service.get_college_value_added(academic_year="2025/26")
        assert result is not None
