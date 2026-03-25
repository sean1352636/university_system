"""Tests for FirstAidService."""

import pytest

from education_system.college_system.modules.domain.first_aid.services.first_aid_service import FirstAidService
from education_system.college_system.core.exceptions import FirstAidError


class TestFirstAidService:
    @pytest.fixture
    def first_aid_service(self, db_path):
        return FirstAidService(db_path)

    def test_report_incident(self, first_aid_service, sample_student):
        incident = first_aid_service.report_incident(
            reported_by=1,
            student_id=sample_student["id"],
            description="Student fell during PE",
            location="Sports Hall",
            severity="minor",
        )
        assert incident["description"] == "Student fell during PE"
        assert incident["severity"] == "minor"
        assert incident["status"] == "open"
        assert incident["location"] == "Sports Hall"

    def test_report_incident_without_student(self, first_aid_service):
        incident = first_aid_service.report_incident(
            reported_by=1,
            description="Staff member cut finger in kitchen",
            location="Canteen",
            severity="moderate",
        )
        assert incident["student_id"] is None
        assert incident["severity"] == "moderate"

    def test_report_incident_empty_description_raises(self, first_aid_service):
        with pytest.raises(FirstAidError, match="Description is required"):
            first_aid_service.report_incident(
                reported_by=1, description="",
            )

    def test_report_incident_whitespace_description_raises(self, first_aid_service):
        with pytest.raises(FirstAidError, match="Description is required"):
            first_aid_service.report_incident(
                reported_by=1, description="   ",
            )

    def test_report_incident_invalid_severity_raises(self, first_aid_service):
        with pytest.raises(FirstAidError, match="Severity must be one of"):
            first_aid_service.report_incident(
                reported_by=1, description="Test", severity="critical",
            )

    def test_list_incidents(self, first_aid_service, sample_student):
        first_aid_service.report_incident(
            reported_by=1, student_id=sample_student["id"],
            description="Incident 1", severity="minor",
        )
        first_aid_service.report_incident(
            reported_by=1, student_id=sample_student["id"],
            description="Incident 2", severity="moderate",
        )
        incidents = first_aid_service.list_incidents()
        assert len(incidents) >= 2

    def test_list_incidents_filter_status(self, first_aid_service, sample_student):
        first_aid_service.report_incident(
            reported_by=1, student_id=sample_student["id"],
            description="Open incident", severity="minor",
        )
        open_incidents = first_aid_service.list_incidents(status="open")
        assert all(i["status"] == "open" for i in open_incidents)

    def test_get_incident(self, first_aid_service, sample_student):
        created = first_aid_service.report_incident(
            reported_by=1, student_id=sample_student["id"],
            description="Specific incident", severity="severe",
        )
        found = first_aid_service.get_incident(created["id"])
        assert found["description"] == "Specific incident"
        assert found["severity"] == "severe"

    def test_get_incident_not_found(self, first_aid_service):
        with pytest.raises(FirstAidError, match="not found"):
            first_aid_service.get_incident(99999)

    def test_update_incident_treatment(self, first_aid_service, sample_student):
        incident = first_aid_service.report_incident(
            reported_by=1, student_id=sample_student["id"],
            description="Scraped knee", severity="minor",
        )
        updated = first_aid_service.update_incident(
            incident["id"],
            treatment="Cleaned and bandaged",
            status="treated",
            treated_by="Nurse Smith",
        )
        assert updated["treatment"] == "Cleaned and bandaged"
        assert updated["status"] == "treated"

    def test_update_incident_parent_notified(self, first_aid_service, sample_student):
        incident = first_aid_service.report_incident(
            reported_by=1, student_id=sample_student["id"],
            description="Head bump", severity="moderate",
        )
        updated = first_aid_service.update_incident(
            incident["id"], parent_notified=1,
        )
        assert updated["parent_notified"] == 1

    def test_update_incident_invalid_status_raises(self, first_aid_service, sample_student):
        incident = first_aid_service.report_incident(
            reported_by=1, student_id=sample_student["id"],
            description="Test", severity="minor",
        )
        with pytest.raises(FirstAidError, match="Status must be one of"):
            first_aid_service.update_incident(incident["id"], status="invalid")

    def test_update_incident_no_valid_fields_raises(self, first_aid_service, sample_student):
        incident = first_aid_service.report_incident(
            reported_by=1, student_id=sample_student["id"],
            description="Test", severity="minor",
        )
        with pytest.raises(FirstAidError, match="No valid fields"):
            first_aid_service.update_incident(incident["id"], bad_field="nope")

    def test_delete_incident(self, first_aid_service, sample_student):
        incident = first_aid_service.report_incident(
            reported_by=1, student_id=sample_student["id"],
            description="To be deleted", severity="minor",
        )
        assert first_aid_service.delete_incident(incident["id"]) is True

    def test_delete_incident_not_found(self, first_aid_service):
        with pytest.raises(FirstAidError, match="not found"):
            first_aid_service.delete_incident(99999)

    def test_get_student_incidents(self, first_aid_service, sample_student):
        first_aid_service.report_incident(
            reported_by=1, student_id=sample_student["id"],
            description="Incident A", severity="minor",
        )
        first_aid_service.report_incident(
            reported_by=1, student_id=sample_student["id"],
            description="Incident B", severity="moderate",
        )
        student_incidents = first_aid_service.get_student_incidents(sample_student["id"])
        assert len(student_incidents) >= 2
        assert all(i["student_id"] == sample_student["id"] for i in student_incidents)

    def test_get_student_incidents_empty(self, first_aid_service, sample_student):
        incidents = first_aid_service.get_student_incidents(sample_student["id"])
        assert incidents == []

    def test_severity_levels(self, first_aid_service, sample_student):
        for severity in ("minor", "moderate", "severe", "emergency"):
            incident = first_aid_service.report_incident(
                reported_by=1, student_id=sample_student["id"],
                description=f"{severity} incident", severity=severity,
            )
            assert incident["severity"] == severity

    def test_close_incident(self, first_aid_service, sample_student):
        incident = first_aid_service.report_incident(
            reported_by=1, student_id=sample_student["id"],
            description="To be closed", severity="minor",
        )
        closed = first_aid_service.update_incident(
            incident["id"], status="closed", notes="Resolved",
        )
        assert closed["status"] == "closed"
        assert closed["notes"] == "Resolved"
