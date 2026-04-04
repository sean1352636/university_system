"""Tests for the IncidentService in the Primary School system."""

import pytest

from education_system.primary_school.core.exceptions import IncidentError


class TestCreateIncident:
    """Tests for creating incidents."""

    def test_create_incident_returns_dict_with_id(self, incident_service):
        """Creating an incident returns a dict with a valid ID."""
        result = incident_service.create_incident(
            incident_type="Injury",
            description="Pupil fell in playground",
            reported_by="STF0001",
            location="Playground",
            severity="Minor",
            incident_date="2026-04-04",
            incident_time="10:30",
            action_taken="First aid applied",
        )
        assert isinstance(result, dict)
        assert result["id"] > 0
        assert result["incident_type"] == "Injury"
        assert result["severity"] == "Minor"

    def test_create_incident_persists(self, incident_service):
        """A created incident is retrievable via get_incident."""
        result = incident_service.create_incident(
            incident_type="Property Damage",
            description="Window cracked in classroom",
            reported_by="STF0002",
            location="Room 7",
            severity="Moderate",
        )
        fetched = incident_service.get_incident(result["id"])
        assert fetched is not None
        assert fetched["description"] == "Window cracked in classroom"
        assert fetched["location"] == "Room 7"
        assert fetched["status"] == "Open"

    def test_create_incident_with_witnesses(self, incident_service):
        """An incident can store pupil_ids and staff_ids as witnesses."""
        result = incident_service.create_incident(
            incident_type="Altercation",
            description="Pushing incident in corridor",
            reported_by="STF0003",
            severity="Serious",
            pupil_ids="PRI0001,PRI0002",
            staff_ids="STF0003",
        )
        fetched = incident_service.get_incident(result["id"])
        assert fetched["pupil_ids"] == "PRI0001,PRI0002"
        assert fetched["staff_ids"] == "STF0003"


class TestGetIncident:
    """Tests for retrieving a single incident."""

    def test_get_nonexistent_incident_returns_none(self, incident_service):
        """Requesting a non-existent incident ID returns None."""
        assert incident_service.get_incident(99999) is None


class TestListIncidents:
    """Tests for listing and filtering incidents."""

    def test_list_incidents_empty_db(self, incident_service):
        """Listing incidents on an empty database returns an empty list."""
        assert incident_service.list_incidents() == []

    def test_list_incidents_filter_by_severity(self, incident_service):
        """Filtering by severity returns only matching incidents."""
        incident_service.create_incident(
            incident_type="Injury", description="Scraped knee",
            reported_by="STF0001", severity="Minor",
        )
        incident_service.create_incident(
            incident_type="Injury", description="Broken arm",
            reported_by="STF0001", severity="Serious",
        )
        serious = incident_service.list_incidents(severity="Serious")
        assert len(serious) == 1
        assert serious[0]["description"] == "Broken arm"

    def test_list_incidents_filter_by_type(self, incident_service):
        """Filtering by incident_type returns only matching incidents."""
        incident_service.create_incident(
            incident_type="Fire Alarm", description="False alarm drill",
            reported_by="STF0001",
        )
        incident_service.create_incident(
            incident_type="Injury", description="Cut finger",
            reported_by="STF0002",
        )
        alarms = incident_service.list_incidents(incident_type="Fire Alarm")
        assert len(alarms) == 1
        assert alarms[0]["incident_type"] == "Fire Alarm"


class TestUpdateIncident:
    """Tests for updating incidents."""

    def test_update_incident_changes_fields(self, incident_service):
        """Updating an incident persists the new values."""
        result = incident_service.create_incident(
            incident_type="Injury", description="Original",
            reported_by="STF0001", severity="Minor",
        )
        updated = incident_service.update_incident(
            result["id"], description="Updated description",
            severity="Moderate",
        )
        assert updated["description"] == "Updated description"
        assert updated["severity"] == "Moderate"

    def test_update_incident_no_valid_fields_returns_none(self, incident_service):
        """Passing only unrecognised fields returns None."""
        result = incident_service.create_incident(
            incident_type="Injury", description="Test",
            reported_by="STF0001",
        )
        assert incident_service.update_incident(result["id"], bogus="x") is None


class TestCloseIncident:
    """Tests for closing incidents."""

    def test_close_incident_sets_status(self, incident_service):
        """Closing an incident sets its status to Closed."""
        result = incident_service.create_incident(
            incident_type="Injury", description="Minor bump",
            reported_by="STF0001",
        )
        closed = incident_service.close_incident(
            result["id"], action_taken="Ice pack applied, parent informed",
        )
        assert closed["status"] == "Closed"
        assert closed["action_taken"] == "Ice pack applied, parent informed"
        assert closed["closed_at"] is not None

    def test_close_nonexistent_incident_raises(self, incident_service):
        """Closing a non-existent incident raises an error."""
        with pytest.raises(IncidentError):
            incident_service.close_incident(99999, action_taken="N/A")

    def test_closed_incident_excluded_from_open_list(self, incident_service):
        """A closed incident does not appear in the default (Open) listing."""
        result = incident_service.create_incident(
            incident_type="Spill", description="Water in corridor",
            reported_by="STF0001",
        )
        incident_service.close_incident(
            result["id"], action_taken="Cleaned up",
        )
        open_incidents = incident_service.list_incidents()
        assert len(open_incidents) == 0
