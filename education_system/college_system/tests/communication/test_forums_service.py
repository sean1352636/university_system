"""Tests for ForumService."""

import pytest


class TestForumService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.forums.services.forums_service import ForumService
        return ForumService(db_path)

    @pytest.fixture
    def sample_category(self, service):
        return service.create_category(
            name="General Discussion",
            description="Open discussion for all students",
        )

    def test_create_category(self, service):
        cat = service.create_category(name="Announcements", description="Official notices")
        assert cat is not None

    def test_list_categories(self, service):
        service.create_category(name="Cat A")
        service.create_category(name="Cat B")
        cats = service.list_categories()
        assert len(cats) >= 2

    def test_get_category(self, service, sample_category):
        cid = sample_category["id"]
        found = service.get_category(cid)
        assert found["name"] == "General Discussion"

    def test_update_category(self, service, sample_category):
        updated = service.update_category(sample_category["id"], name="Updated")
        assert updated["name"] == "Updated"

    def test_delete_category(self, service, sample_category):
        result = service.delete_category(sample_category["id"])
        assert result is True

    def test_create_thread(self, service, sample_category):
        thread = service.create_thread(
            category_id=sample_category["id"],
            title="Welcome Thread", author_id=1,
        )
        assert thread is not None

    def test_list_threads(self, service, sample_category):
        service.create_thread(sample_category["id"], "Thread 1", 1)
        service.create_thread(sample_category["id"], "Thread 2", 2)
        threads = service.list_threads(category_id=sample_category["id"])
        assert len(threads) >= 2

    def test_pin_thread(self, service, sample_category):
        thread = service.create_thread(sample_category["id"], "Important", 1)
        pinned = service.pin_thread(thread["id"])
        assert pinned is not None

    def test_lock_thread(self, service, sample_category):
        thread = service.create_thread(sample_category["id"], "Old Thread", 1)
        locked = service.lock_thread(thread["id"])
        assert locked is not None

    def test_create_post(self, service, sample_category):
        thread = service.create_thread(sample_category["id"], "Q&A", 1)
        post = service.create_post(
            thread_id=thread["id"], author_id=1,
            content="This is a reply.",
        )
        assert post is not None

    def test_list_posts(self, service, sample_category):
        thread = service.create_thread(sample_category["id"], "Discussion", 1)
        service.create_post(thread["id"], 1, "Reply 1")
        service.create_post(thread["id"], 2, "Reply 2")
        posts = service.list_posts(thread["id"])
        assert len(posts) >= 2

    def test_mark_solution(self, service, sample_category):
        thread = service.create_thread(sample_category["id"], "Help", 1)
        post = service.create_post(thread["id"], 2, "Solution here")
        result = service.mark_solution(post["id"])
        assert result is not None

    def test_get_stats(self, service):
        stats = service.get_stats()
        assert stats is not None
