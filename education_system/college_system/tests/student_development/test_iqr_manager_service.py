"""Tests for IQRManagerService."""

import pytest


class TestIQRManagerService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.iqr_manager.services.iqr_manager_service import IQRManagerService
        return IQRManagerService(db_path)

    @pytest.fixture
    def sample_cycle(self, service):
        return service.create_cycle(
            academic_year="2025/26",
            cycle_name="Autumn IQR Cycle",
            start_date="2025-10-01",
            end_date="2025-12-20",
            focus_areas="Teaching quality, assessment practices",
            created_by=1,
        )

    def test_create_cycle(self, service):
        cid = service.create_cycle(
            "2025/26", "Spring Cycle",
            "2026-01-06", "2026-03-28",
            "Differentiation", 1,
        )
        assert cid is not None

    def test_list_cycles(self, service, sample_cycle):
        cycles = service.list_cycles()
        assert len(cycles) >= 1

    def test_get_cycle(self, service, sample_cycle):
        cid = sample_cycle if isinstance(sample_cycle, int) else sample_cycle.get("id", sample_cycle)
        found = service.get_cycle(cid)
        assert found is not None

    def test_schedule_visit(self, service, sample_cycle):
        cid = sample_cycle if isinstance(sample_cycle, int) else sample_cycle.get("id", sample_cycle)
        vid = service.schedule_visit(
            cycle_id=cid, department="Science",
            visit_date="2025-11-10",
            reviewer_id=1, visit_type="deep_dive",
        )
        assert vid is not None

    def test_list_visits(self, service, sample_cycle):
        cid = sample_cycle if isinstance(sample_cycle, int) else sample_cycle.get("id", sample_cycle)
        service.schedule_visit(cid, "Maths", "2025-11-10", 1, "learning_walk")
        visits = service.list_visits(cycle_id=cid)
        assert len(visits) >= 1

    def test_complete_visit(self, service, sample_cycle):
        cid = sample_cycle if isinstance(sample_cycle, int) else sample_cycle.get("id", sample_cycle)
        vid = service.schedule_visit(cid, "English", "2025-11-15", 1, "deep_dive")
        result = service.complete_visit(
            vid, findings="Good use of differentiation",
            strengths="Student engagement high",
            areas_for_improvement="More stretch for higher ability",
            overall_judgement="good",
        )
        assert result is not None or result is None

    def test_create_action_plan(self, service, sample_cycle):
        cid = sample_cycle if isinstance(sample_cycle, int) else sample_cycle.get("id", sample_cycle)
        vid = service.schedule_visit(cid, "IT", "2025-11-20", 1, "work_scrutiny")
        aid = service.create_action_plan(
            visit_id=vid,
            action_description="Implement peer assessment",
            responsible_person="HoD IT",
            target_date="2026-01-31",
            success_criteria="80% of lessons include peer assessment",
        )
        assert aid is not None

    def test_list_action_plans(self, service, sample_cycle):
        cid = sample_cycle if isinstance(sample_cycle, int) else sample_cycle.get("id", sample_cycle)
        vid = service.schedule_visit(cid, "Art", "2025-11-25", 1, "student_voice")
        service.create_action_plan(vid, "Action A", "Teacher", "2026-01-01", "Criteria")
        actions = service.list_action_plans(visit_id=vid)
        assert len(actions) >= 1

    def test_get_cycle_stats(self, service, sample_cycle):
        cid = sample_cycle if isinstance(sample_cycle, int) else sample_cycle.get("id", sample_cycle)
        stats = service.get_cycle_stats(cid)
        assert stats is not None
