"""Tests for WorkJournalService."""

import pytest
from education_system.college_system.core.exceptions import WorkJournalError, ValidationError


class TestWorkJournalService:
    """Test suite for WorkJournalService."""

    def test_create_placement(self, work_journal_service):
        item = work_journal_service.create_placement(student_id=1, employer_name="test_employer_name", start_date="test_start_date")
        assert item["id"] is not None

    def test_get_placement(self, work_journal_service):
        item = work_journal_service.create_placement(student_id=1, employer_name="test_employer_name", start_date="test_start_date")
        found = work_journal_service.get_placement(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_list_placements(self, work_journal_service):
        work_journal_service.create_placement(student_id=1, employer_name="test_employer_name", start_date="test_start_date")
        items = work_journal_service.list_placements()
        assert len(items) >= 1

    def test_update_placement(self, work_journal_service):
        item = work_journal_service.create_placement(student_id=1, employer_name="test_employer_name", start_date="test_start_date")
        updated = work_journal_service.update_placement(item["id"], employer_name="updated_value")
        assert updated["employer_name"] == "updated_value"

    def test_delete_placement(self, work_journal_service):
        item = work_journal_service.create_placement(student_id=1, employer_name="test_employer_name", start_date="test_start_date")
        result = work_journal_service.delete_placement(item["id"])
        assert result is True
        assert work_journal_service.get_placement(item["id"]) is None

    def test_count_placements(self, work_journal_service):
        work_journal_service.create_placement(student_id=1, employer_name="test_employer_name", start_date="test_start_date")
        count = work_journal_service.count_placements()
        assert count >= 1

    def test_delete_nonexistent_raises(self, work_journal_service):
        with pytest.raises(WorkJournalError):
            work_journal_service.delete_placement(99999)
