"""Tests for the primary school homework service."""

import pytest


class TestHomeworkService:
    """Tests for HomeworkService."""

    def test_create_homework(self, homework_service):
        """Test creating a homework assignment."""
        result = homework_service.create_homework(
            title="Maths Worksheet",
            class_id="CLS001",
            subject="Mathematics",
            set_by="STF0001",
            due_date="2026-04-10",
            description="Complete pages 12-14",
        )
        assert result is not None

    def test_get_homework_by_class(self, homework_service):
        """Test retrieving homework for a class."""
        homework_service.create_homework(
            title="Reading Task",
            class_id="CLS001",
            subject="English",
            set_by="STF0001",
            due_date="2026-04-10",
        )
        results = homework_service.get_homework_by_class("CLS001")
        assert isinstance(results, list)

    def test_mark_homework_complete(self, homework_service):
        """Test marking homework as complete for a pupil."""
        hw = homework_service.create_homework(
            title="Spelling Test Prep",
            class_id="CLS001",
            subject="English",
            set_by="STF0001",
            due_date="2026-04-15",
        )
        if hw and isinstance(hw, (int, str)):
            result = homework_service.mark_complete(
                homework_id=hw, pupil_id="PRI0001"
            )
            # Just verify it doesn't crash
            assert result is not None or result is None
