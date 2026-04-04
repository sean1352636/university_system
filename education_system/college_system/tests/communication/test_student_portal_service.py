"""Tests for StudentPortalService."""

import pytest


class TestStudentPortalService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.student_portal.services.student_portal_service import StudentPortalService
        return StudentPortalService(db_path)

    def test_create_page(self, service):
        page = service.create_page(
            page_title="Welcome", page_slug="welcome",
            category="general",
        )
        assert page is not None

    def test_list_pages(self, service):
        service.create_page("Page A", "page-a")
        service.create_page("Page B", "page-b")
        pages = service.list_pages()
        assert len(pages) >= 2

    def test_get_page(self, service):
        page = service.create_page("Test", "test-page")
        found = service.get_page(page["id"])
        assert found["page_title"] == "Test"

    def test_get_page_by_slug(self, service):
        service.create_page("Slug Test", "slug-test")
        found = service.get_page_by_slug("slug-test")
        assert found is not None

    def test_update_page(self, service):
        page = service.create_page("Old Title", "old-title")
        updated = service.update_page(page["id"], page_title="New Title")
        assert updated["page_title"] == "New Title"

    def test_delete_page(self, service):
        page = service.create_page("Delete Me", "delete-me")
        result = service.delete_page(page["id"])
        assert result is True

    def test_toggle_publish(self, service):
        page = service.create_page("Draft", "draft-page")
        toggled = service.toggle_publish(page["id"])
        assert toggled is not None

    def test_create_link(self, service):
        link = service.create_link(
            link_title="Student Union",
            url="https://su.college.ac.uk",
            category="student_life",
        )
        assert link is not None

    def test_list_links(self, service):
        service.create_link("Link A", "https://a.com")
        service.create_link("Link B", "https://b.com")
        links = service.list_links()
        assert len(links) >= 2

    def test_delete_link(self, service):
        link = service.create_link("Temp", "https://temp.com")
        result = service.delete_link(link["id"])
        assert result is True

    def test_get_stats(self, service):
        stats = service.get_stats()
        assert stats is not None
