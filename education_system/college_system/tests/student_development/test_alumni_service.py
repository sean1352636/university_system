"""Tests for AlumniService."""

import pytest
from education_system.college_system.core.exceptions import AlumniError


class TestAlumniService:
    """Test suite for AlumniService."""

    # --- Alumni Records ---

    def test_create_record(self, alumni_service):
        item = alumni_service.create_record("Jane", "Doe", graduation_year="2024")
        assert item["id"] is not None
        assert item["first_name"] == "Jane"
        assert item["last_name"] == "Doe"

    def test_get_record(self, alumni_service):
        item = alumni_service.create_record("Jane", "Doe")
        found = alumni_service.get_record(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_get_record_nonexistent(self, alumni_service):
        assert alumni_service.get_record(99999) is None

    def test_list_records(self, alumni_service):
        alumni_service.create_record("Jane", "Doe", graduation_year="2024")
        alumni_service.create_record("John", "Smith", graduation_year="2023")
        items = alumni_service.list_records()
        assert len(items) >= 2

    def test_list_records_filter_graduation_year(self, alumni_service):
        alumni_service.create_record("Jane", "Doe", graduation_year="2024")
        alumni_service.create_record("John", "Smith", graduation_year="2023")
        items = alumni_service.list_records(graduation_year="2024")
        assert all(r["graduation_year"] == "2024" for r in items)

    def test_list_records_filter_willing_to_mentor(self, alumni_service):
        alumni_service.create_record("Jane", "Doe", willing_to_mentor=1)
        alumni_service.create_record("John", "Smith", willing_to_mentor=0)
        items = alumni_service.list_records(willing_to_mentor=1)
        assert all(r["willing_to_mentor"] == 1 for r in items)

    def test_list_records_search(self, alumni_service):
        alumni_service.create_record("Unique", "Alumnus")
        items = alumni_service.list_records(search="Unique")
        assert len(items) >= 1

    def test_update_record(self, alumni_service):
        item = alumni_service.create_record("Jane", "Doe")
        updated = alumni_service.update_record(item["id"], current_employer="Acme Corp")
        assert updated["current_employer"] == "Acme Corp"

    def test_delete_record(self, alumni_service):
        item = alumni_service.create_record("Jane", "Doe")
        result = alumni_service.delete_record(item["id"])
        assert result is True
        assert alumni_service.get_record(item["id"]) is None

    def test_delete_nonexistent(self, alumni_service):
        result = alumni_service.delete_record(99999)
        assert result is True or result is False

    # --- Alumni Events ---

    def test_create_event(self, alumni_service):
        item = alumni_service.create_event("Reunion 2024", "2024-07-01")
        assert item["id"] is not None
        assert item["event_name"] == "Reunion 2024"

    def test_list_events(self, alumni_service):
        alumni_service.create_event("Reunion", "2024-07-01", event_type="reunion")
        items = alumni_service.list_events()
        assert len(items) >= 1

    def test_list_events_filter(self, alumni_service):
        alumni_service.create_event("Reunion", "2024-07-01", event_type="reunion")
        items = alumni_service.list_events(event_type="reunion")
        assert all(e["event_type"] == "reunion" for e in items)

    def test_get_event(self, alumni_service):
        item = alumni_service.create_event("Reunion", "2024-07-01")
        found = alumni_service.get_event(item["id"])
        assert found is not None
        assert found["id"] == item["id"]

    def test_update_event(self, alumni_service):
        item = alumni_service.create_event("Reunion", "2024-07-01")
        updated = alumni_service.update_event(item["id"], location="Main Hall")
        assert updated["location"] == "Main Hall"

    def test_delete_event(self, alumni_service):
        item = alumni_service.create_event("Reunion", "2024-07-01")
        result = alumni_service.delete_event(item["id"])
        assert result is True
        assert alumni_service.get_event(item["id"]) is None

    # --- Alumni Surveys ---

    def test_create_survey(self, alumni_service):
        record = alumni_service.create_record("Jane", "Doe")
        survey = alumni_service.create_survey(record["id"], satisfaction_rating=4)
        assert survey["id"] is not None

    def test_list_surveys(self, alumni_service):
        record = alumni_service.create_record("Jane", "Doe")
        alumni_service.create_survey(record["id"], survey_year="2024")
        items = alumni_service.list_surveys(alumni_id=record["id"])
        assert len(items) >= 1

    def test_delete_survey(self, alumni_service):
        record = alumni_service.create_record("Jane", "Doe")
        survey = alumni_service.create_survey(record["id"])
        result = alumni_service.delete_survey(survey["id"])
        assert result is True

    def test_delete_record_cascades_surveys(self, alumni_service):
        record = alumni_service.create_record("Jane", "Doe")
        alumni_service.create_survey(record["id"])
        alumni_service.delete_record(record["id"])
        surveys = alumni_service.list_surveys(alumni_id=record["id"])
        assert len(surveys) == 0

    # --- Statistics ---

    def test_get_stats(self, alumni_service):
        alumni_service.create_record("Jane", "Doe", willing_to_mentor=1)
        stats = alumni_service.get_stats()
        assert stats["total_alumni"] >= 1
        assert "willing_to_mentor" in stats
