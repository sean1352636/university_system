"""Tests for OnboardingService."""

import pytest


class TestOnboardingService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.onboarding.services.onboarding_service import OnboardingService
        return OnboardingService(db_path)

    @pytest.fixture
    def sample_checklist(self, service):
        return service.create_checklist(staff_id=1, start_date="2026-09-01")

    def test_create_checklist(self, service):
        cl = service.create_checklist(staff_id=1, start_date="2026-09-01")
        assert cl is not None

    def test_list_checklists(self, service):
        service.create_checklist(staff_id=1)
        service.create_checklist(staff_id=2)
        checklists = service.list_checklists()
        assert len(checklists) >= 2

    def test_get_checklist(self, service, sample_checklist):
        cid = sample_checklist["id"]
        found = service.get_checklist(cid)
        assert found is not None

    def test_update_checklist(self, service, sample_checklist):
        updated = service.update_checklist(sample_checklist["id"], notes="Updated notes")
        assert updated is not None

    def test_delete_checklist(self, service, sample_checklist):
        result = service.delete_checklist(sample_checklist["id"])
        assert result is True

    def test_complete_checklist(self, service, sample_checklist):
        result = service.complete_checklist(sample_checklist["id"])
        assert result is not None

    def test_create_task(self, service, sample_checklist):
        task = service.create_task(
            checklist_id=sample_checklist["id"],
            task_name="Complete DBS check",
            category="compliance",
        )
        assert task is not None

    def test_list_tasks(self, service, sample_checklist):
        service.create_task(sample_checklist["id"], "Task A")
        tasks = service.list_tasks(checklist_id=sample_checklist["id"])
        assert len(tasks) >= 1

    def test_complete_task(self, service, sample_checklist):
        task = service.create_task(sample_checklist["id"], "Finish me")
        result = service.complete_task(task["id"])
        assert result is not None

    def test_get_pending_tasks(self, service, sample_checklist):
        service.create_task(sample_checklist["id"], "Pending task")
        pending = service.get_pending_tasks()
        assert isinstance(pending, list)

    def test_create_review(self, service, sample_checklist):
        review = service.create_review(
            checklist_id=sample_checklist["id"],
            review_date="2026-10-01",
        )
        assert review is not None

    def test_get_stats(self, service):
        stats = service.get_stats()
        assert stats is not None
