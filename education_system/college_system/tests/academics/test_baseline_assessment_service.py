"""Tests for BaselineAssessmentService."""

import pytest
from education_system.college_system.core.exceptions import BaselineAssessmentError


class TestBaselineAssessmentService:
    """Test suite for BaselineAssessmentService."""

    # --- Baselines ---

    def test_create_baseline(self, baseline_assessment_service, sample_student):
        item = baseline_assessment_service.create_baseline(
            sample_student["id"], assessment_type="initial", english_score=65, maths_score=70,
        )
        assert item["id"] is not None

    def test_get_baseline(self, baseline_assessment_service, sample_student):
        item = baseline_assessment_service.create_baseline(sample_student["id"])
        found = baseline_assessment_service.get_baseline(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_get_baseline_nonexistent(self, baseline_assessment_service):
        assert baseline_assessment_service.get_baseline(99999) is None

    def test_list_baselines(self, baseline_assessment_service, sample_student):
        baseline_assessment_service.create_baseline(sample_student["id"])
        items = baseline_assessment_service.list_baselines()
        assert len(items) >= 1

    def test_list_baselines_filter_type(self, baseline_assessment_service, sample_student):
        baseline_assessment_service.create_baseline(
            sample_student["id"], assessment_type="initial",
        )
        items = baseline_assessment_service.list_baselines(assessment_type="initial")
        assert all(r["assessment_type"] == "initial" for r in items)

    def test_update_baseline(self, baseline_assessment_service, sample_student):
        item = baseline_assessment_service.create_baseline(sample_student["id"])
        updated = baseline_assessment_service.update_baseline(item["id"], english_score=80)
        assert updated["english_score"] == 80

    def test_delete_baseline(self, baseline_assessment_service, sample_student):
        item = baseline_assessment_service.create_baseline(sample_student["id"])
        result = baseline_assessment_service.delete_baseline(item["id"])
        assert result is True
        assert baseline_assessment_service.get_baseline(item["id"]) is None

    def test_delete_nonexistent(self, baseline_assessment_service):
        result = baseline_assessment_service.delete_baseline(99999)
        assert result is True or result is False

    # --- Checkpoints ---

    def test_create_checkpoint(self, baseline_assessment_service, sample_student):
        item = baseline_assessment_service.create_checkpoint(
            sample_student["id"], "2024-06-01", current_grade="B",
        )
        assert item["id"] is not None

    def test_list_checkpoints(self, baseline_assessment_service, sample_student):
        baseline_assessment_service.create_checkpoint(sample_student["id"], "2024-06-01")
        items = baseline_assessment_service.list_checkpoints(student_id=sample_student["id"])
        assert len(items) >= 1

    def test_get_checkpoint(self, baseline_assessment_service, sample_student):
        item = baseline_assessment_service.create_checkpoint(sample_student["id"], "2024-06-01")
        found = baseline_assessment_service.get_checkpoint(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_update_checkpoint(self, baseline_assessment_service, sample_student):
        item = baseline_assessment_service.create_checkpoint(sample_student["id"], "2024-06-01")
        updated = baseline_assessment_service.update_checkpoint(item["id"], target_grade="A")
        assert updated["target_grade"] == "A"

    def test_delete_checkpoint(self, baseline_assessment_service, sample_student):
        item = baseline_assessment_service.create_checkpoint(sample_student["id"], "2024-06-01")
        result = baseline_assessment_service.delete_checkpoint(item["id"])
        assert result is True
        assert baseline_assessment_service.get_checkpoint(item["id"]) is None

    # --- Aggregates ---

    def test_get_student_progress(self, baseline_assessment_service, sample_student):
        baseline_assessment_service.create_baseline(sample_student["id"])
        baseline_assessment_service.create_checkpoint(sample_student["id"], "2024-06-01")
        progress = baseline_assessment_service.get_student_progress(sample_student["id"])
        assert "baselines" in progress
        assert "checkpoints" in progress
        assert len(progress["baselines"]) >= 1
        assert len(progress["checkpoints"]) >= 1

    def test_get_stats(self, baseline_assessment_service, sample_student):
        baseline_assessment_service.create_baseline(sample_student["id"])
        stats = baseline_assessment_service.get_stats()
        assert stats["total_baselines"] >= 1
        assert "total_checkpoints" in stats
