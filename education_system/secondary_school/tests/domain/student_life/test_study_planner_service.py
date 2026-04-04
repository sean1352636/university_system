"""Tests for StudyPlannerService."""
import pytest
from education_system.secondary_school.modules.domain.student_life.study_planner.services.study_planner_service import StudyPlannerService


@pytest.fixture
def study_planner_service(db_path):
    return StudyPlannerService(db_path)


class TestStudyPlannerCRUD:
    def test_create(self, study_planner_service):
        rid = study_planner_service.create(
            student_id="SEC0001", subject="Mathematics",
            goal_description="Revise algebra", target_date="2026-05-01",
        )
        assert isinstance(rid, int)
        record = study_planner_service.get(rid)
        assert record["student_id"] == "SEC0001"
        assert record["subject"] == "Mathematics"
        assert record["goal_description"] == "Revise algebra"
        assert record["target_date"] == "2026-05-01"
        assert record["status"] == "active"

    def test_list_all(self, study_planner_service):
        study_planner_service.create(
            student_id="SEC0001", goal_description="Revise fractions",
        )
        study_planner_service.create(
            student_id="SEC0002", goal_description="Practice essay writing",
        )
        result = study_planner_service.list_all()
        assert len(result) >= 2

    def test_get(self, study_planner_service):
        rid = study_planner_service.create(
            student_id="SEC0003", goal_description="Learn trigonometry",
        )
        found = study_planner_service.get(rid)
        assert found is not None
        assert found["goal_description"] == "Learn trigonometry"

    def test_update(self, study_planner_service):
        rid = study_planner_service.create(
            student_id="SEC0001", goal_description="Revise algebra",
        )
        study_planner_service.update(rid, status="completed")
        updated = study_planner_service.get(rid)
        assert updated["status"] == "completed"

    def test_delete(self, study_planner_service):
        rid = study_planner_service.create(
            student_id="SEC0004", goal_description="Temp goal",
        )
        study_planner_service.delete(rid)
        assert study_planner_service.get(rid) is None
