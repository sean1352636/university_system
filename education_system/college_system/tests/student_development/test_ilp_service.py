"""Tests for ILPService."""

import pytest


class TestILPService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.ilp.services.ilp_service import ILPService
        return ILPService(db_path)

    @pytest.fixture
    def sample_plan(self, service):
        return service.create_plan(
            student_id=1, academic_year="2025/26",
            long_term_goal="Achieve A-level grades ABB",
            support_needs="Extra maths support",
            created_by=1,
        )

    def test_create_plan(self, service):
        plan = service.create_plan(
            student_id=1, academic_year="2025/26",
            plan_type="standard", created_by=1,
        )
        assert plan is not None

    def test_list_plans(self, service):
        service.create_plan(student_id=1, created_by=1)
        plans = service.list_plans()
        assert len(plans) >= 1

    def test_get_plan(self, service, sample_plan):
        pid = sample_plan if isinstance(sample_plan, int) else sample_plan.get("id", sample_plan)
        found = service.get_plan(pid)
        assert found is not None

    def test_update_plan(self, service, sample_plan):
        pid = sample_plan if isinstance(sample_plan, int) else sample_plan.get("id", sample_plan)
        updated = service.update_plan(pid, status="active")
        assert updated is not None

    def test_add_target(self, service, sample_plan):
        pid = sample_plan if isinstance(sample_plan, int) else sample_plan.get("id", sample_plan)
        target = service.add_target(
            plan_id=pid,
            target_description="Achieve grade B in Maths",
            subject_area="Mathematics",
            current_grade="C", target_grade="B",
        )
        assert target is not None

    def test_list_targets(self, service, sample_plan):
        pid = sample_plan if isinstance(sample_plan, int) else sample_plan.get("id", sample_plan)
        service.add_target(pid, "Target A")
        targets = service.list_targets(pid)
        assert len(targets) >= 1

    def test_add_review(self, service, sample_plan):
        pid = sample_plan if isinstance(sample_plan, int) else sample_plan.get("id", sample_plan)
        review = service.add_review(
            plan_id=pid, review_date="2026-04-01",
            summary="Student making good progress",
            student_voice="I feel confident",
        )
        assert review is not None

    def test_list_reviews(self, service, sample_plan):
        pid = sample_plan if isinstance(sample_plan, int) else sample_plan.get("id", sample_plan)
        service.add_review(pid, "2026-04-01", summary="Review 1")
        reviews = service.list_reviews(pid)
        assert len(reviews) >= 1

    def test_get_due_reviews(self, service):
        result = service.get_due_reviews()
        assert isinstance(result, list)
