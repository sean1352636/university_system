"""Tests for CoverService."""

import pytest


class TestCoverService:
    @pytest.fixture
    def cover_service(self, db_path):
        from education_system.college_system.modules.domain.cover.services.cover_service import CoverService
        return CoverService(db_path)

    def test_create_arrangement(self, cover_service):
        arrangement = cover_service.create_arrangement(
            absent_staff_id=1, cover_staff_id=2,
            cover_date="2026-04-15", reason="Sick leave",
        )
        assert arrangement["cover_date"] == "2026-04-15"
        assert arrangement["status"] == "requested"

    def test_list_arrangements(self, cover_service):
        cover_service.create_arrangement(
            absent_staff_id=1, cover_date="2026-04-15",
        )
        cover_service.create_arrangement(
            absent_staff_id=1, cover_date="2026-04-15",
        )
        arrangements = cover_service.list_arrangements()
        assert len(arrangements) >= 2

    def test_list_arrangements_filter_date(self, cover_service):
        cover_service.create_arrangement(
            absent_staff_id=1, cover_date="2026-04-15",
        )
        cover_service.create_arrangement(
            absent_staff_id=1, cover_date="2026-04-16",
        )
        today = cover_service.list_arrangements(cover_date="2026-04-15")
        assert all(a["cover_date"] == "2026-04-15" for a in today)

    def test_get_arrangement(self, cover_service):
        created = cover_service.create_arrangement(
            absent_staff_id=1, cover_date="2026-04-15",
            reason="Training",
        )
        found = cover_service.get_arrangement(created["id"])
        assert found["reason"] == "Training"

    def test_update_arrangement(self, cover_service):
        arrangement = cover_service.create_arrangement(
            absent_staff_id=1, cover_date="2026-04-15",
        )
        updated = cover_service.update_arrangement(
            arrangement["id"], status="confirmed", cover_staff_id=3,
        )
        assert updated["status"] == "confirmed"

    def test_delete_arrangement(self, cover_service):
        arrangement = cover_service.create_arrangement(
            absent_staff_id=1, cover_date="2026-04-15",
        )
        result = cover_service.delete_arrangement(arrangement["id"])
        assert result is True
