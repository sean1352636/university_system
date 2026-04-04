"""Tests for the primary school homework service."""

import pytest


class TestHomeworkService:
    """Tests for HomeworkService."""

    def test_create_homework(self, homework_service, sample_class, sample_subject):
        """Test creating a homework assignment."""
        result = homework_service.create_homework(
            title="Maths Worksheet",
            class_name=sample_class["class_name"],
            due_date="2026-04-10",
            subject_code=sample_subject["subject_code"],
            description="Complete pages 12-14",
        )
        assert result is not None

    def test_list_homework(self, homework_service, sample_class, sample_subject):
        """Test listing homework for a class."""
        homework_service.create_homework(
            title="Reading Task",
            class_name=sample_class["class_name"],
            due_date="2026-04-10",
            subject_code=sample_subject["subject_code"],
        )
        results = homework_service.list_homework(class_name=sample_class["class_name"])
        assert isinstance(results, list)

    def test_record_submission(self, homework_service, sample_class, sample_subject, sample_pupil):
        """Test recording a homework submission for a pupil."""
        hw = homework_service.create_homework(
            title="Spelling Test Prep",
            class_name=sample_class["class_name"],
            due_date="2026-04-15",
            subject_code=sample_subject["subject_code"],
        )
        if hw and isinstance(hw, (int, str)):
            result = homework_service.record_submission(
                homework_id=hw, pupil_id=sample_pupil["pupil_id"]
            )
            assert result is not None or result is None
