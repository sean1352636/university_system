"""Tests for IncidentService."""
import pytest


class TestIncident:
    def test_log_incident(self, incident_service):
        incident = incident_service.log_incident(
            description="Pupil fell in playground",
            incident_type="accident", severity="minor",
            location="Playground",
        )
        assert incident["description"] == "Pupil fell in playground"
        assert incident["incident_type"] == "accident"

    def test_list_incidents(self, incident_service):
        incident_service.log_incident("Incident A")
        incident_service.log_incident("Incident B")
        incidents = incident_service.list_incidents()
        assert len(incidents) >= 2

    def test_list_incidents_filters_by_severity(self, incident_service):
        incident_service.log_incident("Minor issue", severity="minor")
        incident_service.log_incident("Serious issue", severity="serious")
        incidents = incident_service.list_incidents(severity="minor")
        assert all(i["severity"] == "minor" for i in incidents)

    def test_close_incident(self, incident_service):
        incident = incident_service.log_incident("Close me")
        incident_service.close_incident(incident["id"], investigation_notes="Resolved")
        incidents = incident_service.list_incidents(status="closed")
        assert any(i["id"] == incident["id"] for i in incidents)

    def test_delete_incident(self, incident_service):
        incident = incident_service.log_incident("Delete me")
        incident_service.delete_incident(incident["id"])
        incidents = incident_service.list_incidents()
        assert all(i["id"] != incident["id"] for i in incidents)
