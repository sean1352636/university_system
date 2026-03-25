"""Tests for CoverService."""
import pytest
from education_system.secondary_school.core.exceptions import CoverError


class TestCreateCover:
    def test_create_cover_basic(self, cover_service):
        cover = cover_service.create_cover(
            absent_teacher="Mrs Jones",
            date="2026-03-25",
            period="3",
        )
        assert cover["absent_teacher"] == "Mrs Jones"
        assert cover["date"] == "2026-03-25"
        assert str(cover["period"]) == "3"
        assert cover["status"] == "pending"

    def test_create_cover_with_assignment(self, cover_service):
        cover = cover_service.create_cover(
            absent_teacher="Mrs Jones",
            date="2026-03-25",
            period="1",
            cover_teacher="Mr Smith",
            year_group="9",
            room="B12",
            work_set="Textbook p.45",
        )
        assert cover["cover_teacher"] == "Mr Smith"
        assert cover["status"] == "assigned"
        assert cover["room"] == "B12"


class TestListCovers:
    def test_list_covers_returns_created(self, cover_service):
        cover_service.create_cover(absent_teacher="A", date="2026-03-25", period="1")
        cover_service.create_cover(absent_teacher="B", date="2026-03-26", period="2")
        covers = cover_service.list_covers()
        teachers = [c["absent_teacher"] for c in covers]
        assert "A" in teachers
        assert "B" in teachers

    def test_list_covers_filter_by_date(self, cover_service):
        cover_service.create_cover(absent_teacher="A", date="2026-03-25", period="1")
        cover_service.create_cover(absent_teacher="B", date="2026-03-26", period="2")
        result = cover_service.list_covers(date="2026-03-25")
        assert all(c["date"] == "2026-03-25" for c in result)
        assert len(result) >= 1


class TestAssignCover:
    def test_assign_cover(self, cover_service):
        cover = cover_service.create_cover(absent_teacher="Mrs Jones", date="2026-03-25", period="3")
        assert cover["status"] == "pending"
        cover_service.assign_cover(cover["id"], cover_teacher="Mr Brown")
        updated = cover_service.list_covers(date="2026-03-25")
        assigned = [c for c in updated if c["id"] == cover["id"]]
        assert assigned[0]["cover_teacher"] == "Mr Brown"
        assert assigned[0]["status"] == "assigned"


class TestCompleteCover:
    def test_complete_cover(self, cover_service):
        cover = cover_service.create_cover(
            absent_teacher="Mrs Jones", date="2026-03-25",
            period="3", cover_teacher="Mr Brown",
        )
        cover_service.complete_cover(cover["id"])
        covers = cover_service.list_covers(status="completed")
        completed_ids = [c["id"] for c in covers]
        assert cover["id"] in completed_ids


class TestDeleteCover:
    def test_delete_cover_removes_it(self, cover_service):
        cover = cover_service.create_cover(absent_teacher="X", date="2026-04-01", period="5")
        cover_service.delete_cover(cover["id"])
        remaining = cover_service.list_covers(date="2026-04-01")
        ids = [c["id"] for c in remaining]
        assert cover["id"] not in ids
