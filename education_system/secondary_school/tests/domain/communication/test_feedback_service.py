"""Tests for FeedbackService."""
import pytest
from education_system.secondary_school.modules.domain.communication.feedback.services.feedback_service import FeedbackService


@pytest.fixture
def feedback_service(db_path):
    return FeedbackService(db_path)


class TestFeedbackCRUD:
    def test_create(self, feedback_service):
        r = feedback_service.create(title="Improve Wi-Fi", description="Wi-Fi is slow in block B",
                                     category="facilities")
        assert r["title"] == "Improve Wi-Fi"
        assert r["description"] == "Wi-Fi is slow in block B"
        assert r["category"] == "facilities"
        assert r["status"] == "open"
        assert r["anonymous"] == 0
        assert r["votes"] == 0

    def test_list_all(self, feedback_service):
        feedback_service.create(title="Feedback 1", description="Details 1")
        feedback_service.create(title="Feedback 2", description="Details 2")
        result = feedback_service.list_all()
        assert len(result) >= 2

    def test_get(self, feedback_service):
        r = feedback_service.create(title="Improve Wi-Fi", description="Wi-Fi is slow in block B",
                                     category="facilities")
        found = feedback_service.get(r["id"])
        assert found is not None
        assert found["title"] == "Improve Wi-Fi"
        assert found["description"] == "Wi-Fi is slow in block B"

    def test_update(self, feedback_service):
        r = feedback_service.create(title="Improve Wi-Fi", description="Wi-Fi is slow in block B")
        updated = feedback_service.update(r["id"], status="reviewed", votes=5)
        assert updated["status"] == "reviewed"
        assert updated["votes"] == 5

    def test_delete(self, feedback_service):
        r = feedback_service.create(title="Improve Wi-Fi", description="Wi-Fi is slow in block B")
        feedback_service.delete(r["id"])
        assert feedback_service.get(r["id"]) is None
