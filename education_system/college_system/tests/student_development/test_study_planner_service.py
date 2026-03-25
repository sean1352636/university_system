"""Tests for StudyPlannerService."""

import pytest
from education_system.college_system.core.exceptions import StudyPlannerError, ValidationError


class TestStudyPlannerService:
    """Test suite for StudyPlannerService."""

    def test_create_session(self, study_planner_service):
        item = study_planner_service.create_session(student_id=1, subject="test_subject", planned_date="test_planned_date")
        assert item["id"] is not None

    def test_get_session(self, study_planner_service):
        item = study_planner_service.create_session(student_id=1, subject="test_subject", planned_date="test_planned_date")
        found = study_planner_service.get_session(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_sessions(self, study_planner_service):
        study_planner_service.create_session(student_id=1, subject="test_subject", planned_date="test_planned_date")
        items = study_planner_service.list_sessions()
        assert len(items) >= 1

    def test_update_session(self, study_planner_service):
        item = study_planner_service.create_session(student_id=1, subject="test_subject", planned_date="test_planned_date")
        updated = study_planner_service.update_session(item["id"], subject="updated_value")
        assert updated["subject"] == "updated_value"

    def test_delete_session(self, study_planner_service):
        item = study_planner_service.create_session(student_id=1, subject="test_subject", planned_date="test_planned_date")
        result = study_planner_service.delete_session(item["id"])
        assert result is True
        assert study_planner_service.get_session(item["id"]) is None

    def test_count_sessions(self, study_planner_service):
        study_planner_service.create_session(student_id=1, subject="test_subject", planned_date="test_planned_date")
        count = study_planner_service.count_sessions()
        assert count >= 1

    def test_delete_nonexistent_raises(self, study_planner_service):
        with pytest.raises(StudyPlannerError):
            study_planner_service.delete_session(99999)
